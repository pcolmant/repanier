"""The accounting audit replays the history and changes nothing.

Every class of invariant runs twice here: once over the clean
journal of AccountingJourneyMixin (no finding is expected, a false
positive would break the trust in the tool), and once over the same
journal scratched on purpose (the finding is expected, precise, and
the audit still has not written anything).
"""
import datetime
import io
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from repanier.const import BankMovement, SaleStatus
from repanier.management.commands.audit_accounting import (
    audit_bank,
    audit_customer_accounts,
    audit_invoice_purchase_totals,
    audit_permanence_closure,
    audit_permanence_totals,
    audit_producer_accounts,
)
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.producer import Producer
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tests.test_accounting_chain import AccountingJourneyMixin, PAYMENT_DATE

D = Decimal


class AuditAccountingTestCaseMixin(AccountingJourneyMixin):
    def snapshot(self):
        """Every money column a repair tool could be tempted to fix."""
        customers = list(
            Customer.objects.values_list("id", "balance").order_by("id")
        )
        invoices = {
            "customer": list(
                CustomerInvoice.objects.values_list(
                    "id", "balance", "total_price_with_tax"
                ).order_by("id")
            ),
            "producer": list(
                ProducerInvoice.objects.values_list(
                    "id", "balance", "total_price_with_tax"
                ).order_by("id")
            ),
        }
        bank = list(
            BankAccount.objects.values_list(
                "id",
                "bank_amount_in",
                "bank_amount_out",
                "customer_invoice_id",
                "producer_invoice_id",
                "operation_status",
            ).order_by("id")
        )
        return {"customers": customers, "invoices": invoices, "bank": bank}

    def run_audit(self, audit, *args):
        """Run one audit class, prove it wrote nothing, return findings."""
        before = self.snapshot()
        findings = list(audit(*args))
        self.assertEqual(
            self.snapshot(),
            before,
            "the audit must stay read only",
        )
        return findings

    def codes(self, findings):
        return sorted(finding.code for finding in findings)


class AuditCleanJournalTest(AuditAccountingTestCaseMixin, TestCase):
    """The whole journey replays square: no finding allowed."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def test_every_class_stays_silent_over_the_clean_journal(self):
        self.assertEqual(self.run_audit(audit_customer_accounts), [])
        self.assertEqual(self.run_audit(audit_producer_accounts), [])
        self.assertEqual(self.run_audit(audit_invoice_purchase_totals), [])
        self.assertEqual(self.run_audit(audit_permanence_totals), [])
        self.assertEqual(self.run_audit(audit_permanence_closure), [])
        self.assertEqual(self.run_audit(audit_bank), [])

    def test_the_command_succeeds_on_a_clean_journal(self):
        stdout = io.StringIO()
        call_command("audit_accounting", stdout=stdout)
        self.assertIn("replays square", stdout.getvalue())


class AuditScratchedJournalTest(AuditAccountingTestCaseMixin, TestCase):
    """One scratch per class of invariant: the finding is expected."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def test_a_drifted_customer_balance_is_caught(self):
        Customer.objects.filter(id=self.alice.id).update(balance=D("100.00"))
        findings = self.run_audit(audit_customer_accounts)
        self.assertEqual(self.codes(findings), ["A1"])
        self.assertIn("customer {}".format(self.alice.id), findings[0].reference)

    def test_a_scratched_customer_book_is_caught(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        CustomerInvoice.objects.filter(id=alice_invoice.id).update(
            total_price_with_tax=D("9.10")
        )
        self.assertEqual(
            self.codes(self.run_audit(audit_invoice_purchase_totals)), ["C1"]
        )
        # The whole round drifts with it.
        self.assertEqual(self.codes(self.run_audit(audit_permanence_totals)), ["D1"])

    def test_a_drifted_customer_vat_only_is_reported_as_benign(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        CustomerInvoice.objects.filter(id=alice_invoice.id).update(
            total_vat=D("0.0400")
        )
        findings = self.run_audit(audit_invoice_purchase_totals)
        self.assertEqual(self.codes(findings), ["C4"])
        self.assertIn("no money moved", findings[0].suggestion)

    def test_a_scratched_book_with_its_vat_keeps_the_money_code(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        CustomerInvoice.objects.filter(id=alice_invoice.id).update(
            total_price_with_tax=D("9.10"), total_vat=D("0.0400")
        )
        findings = self.run_audit(audit_invoice_purchase_totals)
        self.assertEqual(self.codes(findings), ["C1"])
        self.assertIn("vat 0.0400", findings[0].message)

    def test_a_drifted_producer_vat_only_is_reported_as_benign(self):
        legumes_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        )
        ProducerInvoice.objects.filter(id=legumes_invoice.id).update(
            total_vat=D("0.0400")
        )
        findings = self.run_audit(audit_invoice_purchase_totals)
        self.assertEqual(self.codes(findings), ["C4"])
        self.assertIn("no money moved", findings[0].suggestion)

    def test_a_scratched_producer_book_is_caught(self):
        legumes_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        )
        ProducerInvoice.objects.filter(id=legumes_invoice.id).update(
            total_price_with_tax=D("17.20")
        )
        self.assertEqual(
            self.codes(self.run_audit(audit_invoice_purchase_totals)), ["C2"]
        )
        # The whole round drifts with it.
        self.assertEqual(self.codes(self.run_audit(audit_permanence_totals)), ["D1"])
        # The correction the books imply no longer matches the booked one.
        self.assertEqual(self.codes(self.run_audit(audit_producer_accounts)), ["B2"])

    def test_a_deleted_profit_row_is_caught(self):
        # Viande claimed 7.50 for a calculated 8.00: the 0.50 correction
        # is booked on the site consumer account. Delete it.
        BankAccount.objects.filter(
            permanence_id=self.permanence.id, operation_status=BankMovement.PROFIT
        ).delete()
        self.assertEqual(
            self.codes(self.run_audit(audit_producer_accounts)), ["B2"]
        )
        # The site customer lost the 0.50 the correction was carrying.
        self.assertIn("A1", self.codes(self.run_audit(audit_customer_accounts)))

    def test_a_drifted_producer_balance_is_caught(self):
        Producer.objects.filter(id=self.viande.id).update(balance=D("12.00"))
        findings = self.run_audit(audit_producer_accounts)
        self.assertEqual(self.codes(findings), ["B1"])
        self.assertIn("producer {}".format(self.viande.id), findings[0].reference)

    def test_a_scratched_anchor_is_caught(self):
        anchor = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL,
            permanence_id=self.permanence.id,
        )
        BankAccount.objects.filter(id=anchor.id).update(bank_amount_out=D("99.00"))
        self.assertEqual(self.codes(self.run_audit(audit_bank)), ["F2"])

    def test_a_lost_payment_is_caught(self):
        alice_row = BankAccount.objects.get(operation_comment="Payment Alice")
        BankAccount.objects.filter(id=alice_row.id).update(customer_invoice=None)
        self.assertIn("F3", self.codes(self.run_audit(audit_bank)))
        # Class A sees it too: the bank side of Alice lost its payment.
        self.assertIn("A1", self.codes(self.run_audit(audit_customer_accounts)))

    def test_a_two_anchors_bank_is_caught(self):
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date="2026-12-01",
        )
        self.assertIn("F1", self.codes(self.run_audit(audit_bank)))

    def test_a_book_closed_outside_its_round_is_caught(self):
        legumes_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        )
        ProducerInvoice.objects.filter(id=legumes_invoice.id).update(
            status=SaleStatus.SEND
        )
        self.assertIn("E4", self.codes(self.run_audit(audit_permanence_closure)))

    def test_an_unstamped_book_is_caught(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        CustomerInvoice.objects.filter(id=alice_invoice.id).update(
            invoice_sort_order=None
        )
        self.assertIn("E3", self.codes(self.run_audit(audit_permanence_closure)))

    def test_the_command_fails_on_a_scratched_journal(self):
        Customer.objects.filter(id=self.bob.id).update(balance=D("55.00"))
        before = self.snapshot()
        with self.assertRaises(CommandError):
            call_command("audit_accounting", stdout=io.StringIO())
        self.assertEqual(self.snapshot(), before)

    def test_the_customer_and_permanence_filters_scope_the_audit(self):
        Customer.objects.filter(id=self.alice.id).update(balance=D("100.00"))
        # Another customer is clean.
        alice_findings = self.run_audit(audit_customer_accounts, self.alice.id)
        self.assertEqual(self.codes(alice_findings), ["A1"])
        self.assertEqual(self.run_audit(audit_customer_accounts, self.bob.id), [])
        # The permanence filter scopes the book classes.
        self.assertEqual(
            self.run_audit(audit_invoice_purchase_totals, self.permanence.id),
            [],
        )
        stdout = io.StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "audit_accounting",
                customer="alice@example.com",
                stdout=stdout,
            )
        self.assertIn("A1", stdout.getvalue())


class AuditEraAndDrillDownTest(AuditAccountingTestCaseMixin, TestCase):
    """--since scopes the era, --invoice drills down one book."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def scratch_alice_book(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        CustomerInvoice.objects.filter(id=alice_invoice.id).update(
            total_price_with_tax=D("9.10")
        )
        return alice_invoice

    def test_a_payment_of_the_latest_anchor_day_waits_for_the_next_round(self):
        # The two cheese rows of the production audit: dated the day of
        # the latest anchor, they wait for the next round, not lost.
        BankAccount.objects.create(
            customer_id=self.alice.id,
            operation_date=PAYMENT_DATE,
            operation_comment="Payment same day",
            bank_amount_in=D("3.00"),
        )
        self.assertEqual(self.run_audit(audit_bank), [])

    def test_a_payment_older_than_the_latest_anchor_is_still_lost(self):
        BankAccount.objects.create(
            customer_id=self.alice.id,
            operation_date=PAYMENT_DATE - datetime.timedelta(days=1),
            operation_comment="Payment too old",
            bank_amount_in=D("3.00"),
        )
        self.assertEqual(self.codes(self.run_audit(audit_bank)), ["F3"])

    def test_since_silences_the_rounds_outside_the_era(self):
        self.scratch_alice_book()
        self.assertEqual(
            self.run_audit(
                audit_invoice_purchase_totals, None, datetime.date(2027, 1, 1)
            ),
            [],
        )
        self.assertEqual(
            self.run_audit(audit_permanence_totals, None, datetime.date(2027, 1, 1)),
            [],
        )
        self.assertEqual(
            self.run_audit(
                audit_permanence_closure, None, datetime.date(2027, 1, 1)
            ),
            [],
        )
        # The era of the round sees the scratch.
        findings = self.run_audit(
            audit_invoice_purchase_totals, None, datetime.date(2020, 1, 1)
        )
        self.assertEqual(self.codes(findings), ["C1"])

    def test_since_scopes_the_command_but_the_identities_stay_lifetime(self):
        self.scratch_alice_book()
        # The era of 2027 starts after the round: the book classes stay
        # silent, but the balance is an identity over the whole history
        # - the CommandError carries the identity finding, no C1.
        stdout = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_accounting", since="2027-01-01", stdout=stdout)
        output = stdout.getvalue()
        self.assertNotIn("C1", output)
        self.assertIn("A1", output)
        # The era of the round sees the scratch in the books too.
        stdout = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_accounting", since="2020-01-01", stdout=stdout)
        self.assertIn("C1", stdout.getvalue())
        # A malformed era is refused.
        with self.assertRaises(CommandError):
            call_command("audit_accounting", since="2020-13-01")

    def test_the_invoice_drill_down_confirms_a_clean_customer_book(self):
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        stdout = io.StringIO()
        call_command(
            "audit_accounting", invoice="c:{}".format(alice_invoice.id), stdout=stdout
        )
        output = stdout.getvalue()
        self.assertIn("OK - the purchases add up", output)
        self.assertIn("purchase #", output)

    def test_the_invoice_drill_down_spots_a_scratched_customer_book(self):
        alice_invoice = self.scratch_alice_book()
        before = self.snapshot()
        stdout = io.StringIO()
        call_command(
            "audit_accounting", invoice="c:{}".format(alice_invoice.id), stdout=stdout
        )
        self.assertEqual(
            self.snapshot(), before, "the drill down must stay read only"
        )
        output = stdout.getvalue()
        self.assertIn("MISMATCH", output)
        self.assertIn("stored total", output)
        self.assertIn("purchase #", output)

    def test_the_invoice_drill_down_spots_a_scratched_producer_book(self):
        legumes_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        )
        ProducerInvoice.objects.filter(id=legumes_invoice.id).update(
            total_price_with_tax=D("17.20")
        )
        stdout = io.StringIO()
        call_command(
            "audit_accounting", invoice="p:{}".format(legumes_invoice.id), stdout=stdout
        )
        output = stdout.getvalue()
        self.assertIn("MISMATCH", output)
        self.assertIn("purchase #", output)

    def test_the_invoice_drill_down_refuses_an_unknown_book(self):
        with self.assertRaises(CommandError):
            call_command("audit_accounting", invoice="c:999999")
        with self.assertRaises(CommandError):
            call_command("audit_accounting", invoice="p:999999")
        with self.assertRaises(CommandError):
            call_command("audit_accounting", invoice="c:not-an-id")


class AuditMarginTest(AuditAccountingTestCaseMixin, TestCase):
    """The sites which resell above the purchase price keep the
    difference: the audit must recognize the resale margin, not ring
    D1 on every round and B2 on every profit line."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def inject_margin(self):
        """Sell every cerise 0.10 above the purchase price, the way a
        reseller round books it: the purchase lines rise, every book
        of the round follows - each one on the purchases its replay
        attributes to it. Returns the margin the round carries."""
        purchases = list(
            PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence.id, producer_id=self.legumes.id
            )
            .select_related("customer_invoice")
            .only(
                "id",
                "customer_id",
                "selling_price",
                "customer_invoice__customer_charged_id",
            )
        )
        by_customer = {}
        by_charged = {}
        for purchase in purchases:
            PurchaseWoReceiver.objects.filter(id=purchase.id).update(
                selling_price=purchase.selling_price.amount + D("0.10")
            )
            by_customer[purchase.customer_id] = (
                by_customer.get(purchase.customer_id, D("0")) + D("0.10")
            )
            charged_id = purchase.customer_invoice.customer_charged_id
            by_charged[charged_id] = (
                by_charged.get(charged_id, D("0")) + D("0.10")
            )
        for book in CustomerInvoice.objects.filter(
            permanence_id=self.permanence.id
        ):
            if book.is_group:
                extra = by_charged.get(book.customer_id, D("0"))
            else:
                extra = by_customer.get(book.customer_id, D("0"))
            if extra:
                book.total_price_with_tax.amount += extra
                book.save(update_fields=["total_price_with_tax"])
        for cross in CustomerProducerInvoice.objects.filter(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        ):
            cross.total_selling_with_tax.amount += by_customer.get(
                cross.customer_id, D("0")
            )
            cross.save(update_fields=["total_selling_with_tax"])
        return D("0.10") * len(purchases)

    def test_the_margin_belongs_to_the_group_and_stays_silent_in_d(self):
        margin = self.inject_margin()
        self.assertGreater(margin, D("0"))
        # The books stay coherent: C recomputes them from the purchases.
        self.assertEqual(self.run_audit(audit_invoice_purchase_totals), [])
        # The customers pay the margin, the producers do not book it:
        # the group keeps it.
        self.assertEqual(self.run_audit(audit_permanence_totals), [])

    def test_a_margin_never_booked_on_the_site_account_is_reported(self):
        margin = self.inject_margin()
        findings = self.run_audit(audit_producer_accounts)
        self.assertEqual(self.codes(findings), ["B2"])
        self.assertIn(
            "resale margin of {}".format(margin), findings[0].message
        )
        self.assertIn("never", findings[0].suggestion)

    def test_a_margin_booked_on_the_site_account_stays_silent(self):
        margin = self.inject_margin()
        BankAccount.objects.create(
            permanence_id=self.permanence.id,
            customer_id=self.site_customer.id,
            operation_date=PAYMENT_DATE,
            operation_status=BankMovement.PROFIT,
            operation_comment="Resale margin",
            bank_amount_in=margin,
        )
        self.assertEqual(self.run_audit(audit_producer_accounts), [])

    def test_a_profit_booked_above_the_margin_keeps_the_finding(self):
        margin = self.inject_margin()
        BankAccount.objects.create(
            permanence_id=self.permanence.id,
            customer_id=self.site_customer.id,
            operation_date=PAYMENT_DATE,
            operation_status=BankMovement.PROFIT,
            operation_comment="Profit of doubt",
            bank_amount_in=margin + D("5.00"),
        )
        findings = self.run_audit(audit_producer_accounts)
        self.assertEqual(self.codes(findings), ["B2"])
        self.assertIn("excess 5.00", findings[0].message)

    def test_an_order_only_site_skips_the_money_identities(self):
        # The federated order sites: Repanier manages no money there -
        # the A, B, E and F identities would fire on every account.
        stdout = io.StringIO()
        with override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=False):
            call_command("audit_accounting", stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("C. Book totals", output)
        self.assertIn("D. Round totals", output)
        self.assertNotIn("A. Customer accounts", output)
        self.assertNotIn("B. Producer accounts", output)
        self.assertNotIn("E. Closure", output)
        self.assertNotIn("F. The bank anchor chain", output)
        self.assertIn("replays square", output)

    def sell_as_the_buying_group(self):
        """The buying group sells to the members: its own producer
        book carries the 5.00, its claim stays empty and the book
        is marked to be paid - the way the invoicing generates the
        'Correction <site>' compensation."""
        site_book = ProducerInvoice.objects.filter(
            permanence_id=self.permanence.id, producer_id=self.site_producer.id
        ).first()
        if site_book is None:
            # The journey sells nothing as the group: the book appears
            # only when the group itself sells.
            site_book = ProducerInvoice.objects.create(
                permanence_id=self.permanence.id,
                producer_id=self.site_producer.id,
                status=SaleStatus.INVOICED,
            )
        site_book.total_price_with_tax.amount = D("5.00")
        site_book.to_be_paid = True
        site_book.save(
            update_fields=["total_price_with_tax", "to_be_paid"]
        )
        return site_book

    def test_what_the_buying_group_sells_is_compensated_and_stays_silent(self):
        # The book bump drifts B1 for the site producer (the group owes
        # itself the 5.00), but the compensation rides the site account:
        # B2 recognizes the flow and stays silent.
        self.sell_as_the_buying_group()
        BankAccount.objects.create(
            permanence_id=self.permanence.id,
            customer_id=self.site_customer.id,
            operation_date=PAYMENT_DATE,
            operation_status=BankMovement.PROFIT,
            operation_comment="Correction Court Circuit",
            bank_amount_in=D("5.00"),
        )
        self.assertEqual(self.codes(self.run_audit(audit_producer_accounts)), ["B1"])

    def test_a_site_income_never_compensated_is_reported(self):
        self.sell_as_the_buying_group()
        findings = self.run_audit(audit_producer_accounts)
        self.assertEqual(self.codes(findings), ["B1", "B2"])
        b2 = [f for f in findings if f.code == "B2"][0]
        self.assertIn("keeps 5.00", b2.message)
        self.assertIn("never", b2.suggestion)
