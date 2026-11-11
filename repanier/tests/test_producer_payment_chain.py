"""Producer by producer payment chain: the producers can be paid one
after another, across permanences.

Repanier allows the treasurer to pay the producers of a permanence one
after the other until the last one is paid. The chain tested here is the
REAL mechanism observed end to end:

- round 1: producer A is paid ("to be booked"), producer B is not yet;
  B simply keeps his calculated balance (no bank movement for him), and
  the permanence is fully invoiced;
- round 2: a new permanence sells B again; B is now paid for everything
  accumulated up to this permanence included (claimed = round 1 + round
  2), exactly like the "Deliveries ... up to the ... (included)"
  operation comment says;
- the bank anchor chains: the net of the LATEST_TOTAL of round 2 equals
  the net of round 1 plus the movements attached during round 2 only.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import BankMovement, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal
PAYMENT_DATE = datetime.date(2026, 12, 31)


class ProducerChainFixtureMixin:
    """Build round 1 (A paid, B explicitly not paid yet), and optionally
    round 2 where B is paid for everything accumulated up to it."""

    # Override in the test classes observing the intermediate state
    rounds = 2

    @classmethod
    def setUpTestData(cls):
        # Round 1: Alice buys from both producers, only A is paid
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The bank anchor required by Permanence.invoice()
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Account opening",
        )
        user = User.objects.create_user(
            username="alice@example.com", email="alice@example.com", password="x"
        )
        cls.alice = Customer.objects.create(
            user=user, short_basket_name="Alice", may_order=True
        )
        cls.producer_a = Producer.objects.create(short_profile_name="Abrigots")
        cls.producer_b = Producer.objects.create(short_profile_name="Bananes")
        cls.product_a = Product.objects.create(
            producer=cls.producer_a,
            long_name_v2="Abrigots",
            order_unit="100",
            producer_unit_price=D("3.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product_b = Product.objects.create(
            producer=cls.producer_b,
            long_name_v2="Bananes",
            order_unit="100",
            producer_unit_price=D("2.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        for product in (cls.product_a, cls.product_b):
            product.is_into_offer = True
            product.save()

        # Round 1: Alice orders 2 from A (6.00) and 3 from B (6.00);
        # A is paid its calculated amount, B is explicitly NOT paid yet.
        cls.permanence_1 = cls.open_and_close(
            cls.product_a, D("2"), cls.product_b, D("3")
        )
        ProducerInvoice.objects.filter(
            permanence_id=cls.permanence_1.id, producer_id=cls.producer_a.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("6.00"))
        ProducerInvoice.objects.filter(
            permanence_id=cls.permanence_1.id, producer_id=cls.producer_b.id
        ).update(to_be_paid=False)
        cls.permanence_1.invoice(payment_date=PAYMENT_DATE)
        cls.permanence_1.refresh_from_db()
        assert cls.permanence_1.status == SaleStatus.INVOICED

        if cls.rounds == 2:
            # Round 2: a new permanence sells B again (Alice orders 2
            # more); B is now paid for everything owed up to this
            # permanence included: 6.00 (round 1) + 4.00 (round 2).
            cls.permanence_2 = cls.open_and_close(
                None, None, cls.product_b, D("2")
            )
            ProducerInvoice.objects.filter(
                permanence_id=cls.permanence_2.id, producer_id=cls.producer_b.id
            ).update(to_be_paid=True, to_be_invoiced_balance=D("10.00"))
            cls.permanence_2.invoice(payment_date=PAYMENT_DATE)
            cls.permanence_2.refresh_from_db()
            assert cls.permanence_2.status == SaleStatus.INVOICED

    @classmethod
    def open_and_close(cls, product_a, quantity_a, product_b, quantity_b):
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        producers = set()
        if product_a is not None:
            producers.add(product_a.producer)
        if product_b is not None:
            producers.add(product_b.producer)
        permanence.producers.add(*producers)
        task_order.open_order(permanence.id, send_mail=False)
        CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=cls.alice.id,
            status=SaleStatus.OPENED,
        )
        for product, quantity in (
            (product_a, quantity_a),
            (product_b, quantity_b),
        ):
            if product is None:
                continue
            offer_item = product.offeritem_set.get(permanence=permanence)
            purchase, updated = create_or_update_one_cart_item(
                customer=cls.alice,
                offer_item_id=offer_item.id,
                q_order=quantity,
                comment="",
            )
            assert updated and purchase is not None
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        permanence.refresh_from_db()
        assert permanence.status == SaleStatus.SEND
        return permanence

    def latest_total(self, permanence_id):
        # After several invoicings, the previous anchors are demoted:
        # fetch the anchor of a permanence whatever its live status.
        return BankAccount.objects.get(
            operation_status__in=[
                BankMovement.LATEST_TOTAL,
                BankMovement.NOT_LATEST_TOTAL,
            ],
            permanence_id=permanence_id,
        )


class Round1UnpaidProducerTest(ProducerChainFixtureMixin, TestCase):
    """After round 1, the unpaid producer keeps his balance."""

    rounds = 1

    def test_round_1_the_unpaid_producer_keeps_his_balance(self):
        # A: calculated 6.00, claimed 6.00, paid 6.00 -> square
        self.producer_a.refresh_from_db()
        self.assertEqual(self.producer_a.balance.amount, D("0"))
        pay_a = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=self.producer_a.id,
        )
        self.assertEqual(pay_a.bank_amount_out.amount, D("6.00"))
        # The payment movement ends attached to the invoicing permanence
        self.assertEqual(pay_a.permanence_id, self.permanence_1.id)

        # B: calculated 6.00, not paid: no bank movement at all, the
        # balance keeps what is owed to him.
        self.producer_b.refresh_from_db()
        self.assertEqual(self.producer_b.balance.amount, D("6.00"))
        self.assertFalse(
            BankAccount.objects.filter(producer_id=self.producer_b.id).exists()
        )
        invoice_b = ProducerInvoice.objects.get(
            permanence_id=self.permanence_1.id, producer_id=self.producer_b.id
        )
        self.assertEqual(invoice_b.get_total_price_with_tax().amount, D("6.00"))
        self.assertEqual(invoice_b.balance.amount, D("6.00"))
        # ... and B is stamped like every invoice of round 1
        self.assertEqual(
            invoice_b.invoice_sort_order, self.latest_total(self.permanence_1.id).id
        )

        # The customer is charged for both purchases anyway
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-12.00"))

    def test_round_1_is_fully_invoiced_without_awaiting_b(self):
        self.assertEqual(self.permanence_1.status, SaleStatus.INVOICED)
        # No child permanence is created: the carry over of B is held by
        # the producer balance, not by a split of the permanence.
        self.assertEqual(Permanence.objects.count(), 1)


class ProducerByProducerPaymentChainTest(ProducerChainFixtureMixin, TestCase):
    """Round 2 pays B for everything accumulated, and the bank anchor
    chains from invoicing to invoicing."""

    rounds = 2

    def test_round_2_pays_b_for_everything_accumulated(self):
        # A single payment movement covering round 1 + round 2
        pay_b = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=self.producer_b.id,
        )
        self.assertEqual(pay_b.bank_amount_out.amount, D("10.00"))
        # A single payment movement, attached to the invoicing permanence
        self.assertEqual(pay_b.permanence_id, self.permanence_2.id)
        # B is square for both permanences
        self.producer_b.refresh_from_db()
        self.assertEqual(self.producer_b.balance.amount, D("0"))
        invoice_b2 = ProducerInvoice.objects.get(
            permanence_id=self.permanence_2.id, producer_id=self.producer_b.id
        )
        self.assertEqual(invoice_b2.get_total_price_with_tax().amount, D("4.00"))
        self.assertEqual(invoice_b2.balance.amount, D("0"))
        self.assertEqual(invoice_b2.bank_amount_out.amount, D("10.00"))
        # No profit correction: B was paid exactly what he was owed
        self.assertFalse(
            BankAccount.objects.filter(
                producer__isnull=True,
                operation_status=BankMovement.PROFIT,
            ).exists()
        )
        # Alice is charged for the round 2 purchases too
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-16.00"))

    def test_the_bank_anchor_chains_from_round_to_round(self):
        anchor_1 = self.latest_total(self.permanence_1.id)
        anchor_2 = self.latest_total(self.permanence_2.id)
        # Round 1: A paid 6.00 out, no customer payment
        self.assertEqual(
            anchor_1.bank_amount_in.amount - anchor_1.bank_amount_out.amount,
            D("-6.00"),
        )
        # Round 2: B paid 10.00 out, no customer payment
        self.assertEqual(
            anchor_2.bank_amount_in.amount - anchor_2.bank_amount_out.amount,
            D("-16.00"),
        )
        # The chain identity: anchor 2 - anchor 1 == movements of round 2
        self.assertEqual(
            (anchor_2.bank_amount_in.amount - anchor_2.bank_amount_out.amount)
            - (anchor_1.bank_amount_in.amount - anchor_1.bank_amount_out.amount),
            D("-10.00"),
        )
        # Anchor 1 was demoted, exactly one LATEST_TOTAL remains
        anchor_1.refresh_from_db()
        self.assertEqual(anchor_1.operation_status, BankMovement.NOT_LATEST_TOTAL)
        self.assertEqual(
            BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL
            ).count(),
            1,
        )
        # And both permanences are stamped with their own anchor
        self.permanence_1.refresh_from_db()
        self.assertEqual(self.permanence_1.invoice_sort_order, anchor_1.id)
        self.permanence_2.refresh_from_db()
        self.assertEqual(self.permanence_2.invoice_sort_order, anchor_2.id)
