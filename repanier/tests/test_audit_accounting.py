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
from django.test import TestCase

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
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.producer import Producer
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
