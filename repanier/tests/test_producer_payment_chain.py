"""Producer by producer payment chain: the producers can be paid one
after another, across permanences.

When the treasurer selects only a subset of the producers to be paid
("to be booked"), the other ones are MOVED into a child permanence
(master_permanence, still at SEND): the parent is invoiced with the
paid producers only, and the child is invoiced later, when the treasurer
pays the remaining producers. This is the split mechanism of
Permanence.invoice().

The chain tested end to end:

- round 1: producer A is paid, producer B is not selected. B's
  ProducerInvoice, the purchases of B and the customers buying from B
  move into the child; the parent is invoiced with A only: the customer
  is charged for his A purchases, A ends square, B is untouched;
- round 2: the child (its own permanence, boards duplicated) is
  invoiced with B paid: the customer is now charged for his B
  purchases, B ends square;
- the bank anchor chains: net(anchor 2) - net(anchor 1) == the
  movements of round 2 only.
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
    """Build a permanence where Alice buys from two producers; producer B
    is invoiced now, producer A is paid by the treasurer, B is paid at
    the child permanence."""

    pay_b_at_child = True
    # When True, B is selected at the parent too: nobody is split.
    b_selected_at_parent = False

    @classmethod
    def setUpTestData(cls):
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
        # A is selected to be paid, B is NOT selected.
        cls.parent = cls.open_and_close(cls.product_a, D("2"), cls.product_b, D("3"))
        ProducerInvoice.objects.filter(
            permanence_id=cls.parent.id, producer_id=cls.producer_a.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("6.00"))
        ProducerInvoice.objects.filter(
            permanence_id=cls.parent.id, producer_id=cls.producer_b.id
        ).update(
            to_be_paid=cls.b_selected_at_parent,
            to_be_invoiced_balance=D("6.00") if cls.b_selected_at_parent else D("0"),
        )
        cls.parent.invoice(payment_date=PAYMENT_DATE)
        cls.parent.refresh_from_db()
        assert cls.parent.status == SaleStatus.INVOICED

        if cls.pay_b_at_child:
            # Round 2: the child receives B's purchases; the treasurer
            # now pays B for its calculated amount.
            cls.child = Permanence.objects.get(master_permanence_id=cls.parent.id)
            ProducerInvoice.objects.filter(
                permanence_id=cls.child.id, producer_id=cls.producer_b.id
            ).update(to_be_paid=True, to_be_invoiced_balance=D("6.00"))
            cls.child.invoice(payment_date=PAYMENT_DATE)
            cls.child.refresh_from_db()
            assert cls.child.status == SaleStatus.INVOICED

    @classmethod
    def open_and_close(cls, product_a, quantity_a, product_b, quantity_b):
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        permanence.producers.add(product_a.producer, product_b.producer)
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


class SplitUnpaidProducersTest(ProducerChainFixtureMixin, TestCase):
    """After round 1, the unpaid producer is carried by the child."""

    pay_b_at_child = False

    def test_the_unpaid_producer_is_moved_to_a_child_permanence(self):
        # The parent is invoiced, and an alive child exists at SEND
        self.assertEqual(self.parent.status, SaleStatus.INVOICED)
        child = Permanence.objects.get(master_permanence_id=self.parent.id)
        self.assertEqual(child.status, SaleStatus.SEND)
        self.assertEqual(child.permanence_date, self.parent.permanence_date)

        # The producer invoice of B moved to the child, unstamped
        self.assertFalse(
            ProducerInvoice.objects.filter(
                permanence_id=self.parent.id, producer_id=self.producer_b.id
            ).exists()
        )
        invoice_b = ProducerInvoice.objects.get(
            permanence_id=child.id, producer_id=self.producer_b.id
        )
        self.assertEqual(invoice_b.status, SaleStatus.SEND)
        self.assertIsNone(invoice_b.invoice_sort_order)

        # No bank movement for B, B's balance stayed untouched
        self.producer_b.refresh_from_db()
        self.assertEqual(self.producer_b.balance.amount, D("0"))
        self.assertFalse(
            BankAccount.objects.filter(producer_id=self.producer_b.id).exists()
        )

    def test_the_customer_is_charged_for_the_paid_producer_only(self):
        # The parent customer invoice keeps A's purchases only
        parent_invoice = CustomerInvoice.objects.get(
            permanence_id=self.parent.id, customer_id=self.alice.id
        )
        self.assertEqual(parent_invoice.get_total_price_with_tax().amount, D("6.00"))
        # The purchases of B moved to a child customer invoice
        child = Permanence.objects.get(master_permanence_id=self.parent.id)
        child_invoice = CustomerInvoice.objects.get(
            permanence_id=child.id, customer_id=self.alice.id
        )
        self.assertEqual(child_invoice.get_total_price_with_tax().amount, D("6.00"))
        # Alice is charged for A only, so far
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-6.00"))

        # A is paid its claimed amount, square, stamped with the anchor
        self.producer_a.refresh_from_db()
        self.assertEqual(self.producer_a.balance.amount, D("0"))
        pay_a = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=self.producer_a.id,
        )
        self.assertEqual(pay_a.bank_amount_out.amount, D("6.00"))
        self.assertEqual(pay_a.permanence_id, self.parent.id)
        # The anchor of round 1 counts A's payment only
        anchor = self.latest_total(self.parent.id)
        self.assertEqual(
            anchor.bank_amount_in.amount - anchor.bank_amount_out.amount,
            D("-6.00"),
        )


class InvoiceTheChildPaysTheLastProducerTest(ProducerChainFixtureMixin, TestCase):
    """Round 2: invoicing the child pays B and charges the customer."""

    pay_b_at_child = True

    def test_the_child_is_invoiced_and_b_gets_square(self):
        pay_b = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=self.producer_b.id,
        )
        self.assertEqual(pay_b.bank_amount_out.amount, D("6.00"))
        self.assertEqual(pay_b.permanence_id, self.child.id)
        # B, square for the child
        self.producer_b.refresh_from_db()
        self.assertEqual(self.producer_b.balance.amount, D("0"))
        invoice_b = ProducerInvoice.objects.get(
            permanence_id=self.child.id, producer_id=self.producer_b.id
        )
        self.assertEqual(invoice_b.balance.amount, D("0"))
        self.assertEqual(invoice_b.get_total_price_with_tax().amount, D("6.00"))
        self.assertEqual(invoice_b.invoice_sort_order, self.latest_total(self.child.id).id)

        # No profit correction: B was paid exactly what he was owed
        self.assertFalse(
            BankAccount.objects.filter(
                producer__isnull=True,
                operation_status=BankMovement.PROFIT,
            ).exists()
        )
        # Alice is charged for her B purchases now
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-12.00"))

    def test_the_bank_anchor_chains_from_parent_to_child(self):
        anchor_1 = self.latest_total(self.parent.id)
        anchor_2 = self.latest_total(self.child.id)
        # Round 1: A paid 6.00 out
        self.assertEqual(
            anchor_1.bank_amount_in.amount - anchor_1.bank_amount_out.amount,
            D("-6.00"),
        )
        # Round 2: B paid 6.00 out
        self.assertEqual(
            anchor_2.bank_amount_in.amount - anchor_2.bank_amount_out.amount,
            D("-12.00"),
        )
        # The chain identity: anchor 2 - anchor 1 == movements of round 2
        self.assertEqual(
            (anchor_2.bank_amount_in.amount - anchor_2.bank_amount_out.amount)
            - (anchor_1.bank_amount_in.amount - anchor_1.bank_amount_out.amount),
            D("-6.00"),
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
        # And each permanence is stamped with its own anchor
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.invoice_sort_order, anchor_1.id)
        self.child.refresh_from_db()
        self.assertEqual(self.child.invoice_sort_order, anchor_2.id)


class NoSplitWhenEveryProducerIsSelectedTest(ProducerChainFixtureMixin, TestCase):
    """When the treasurer selects every producer (the common case), the
    permanence is invoiced as a whole: no child permanence."""

    pay_b_at_child = False
    b_selected_at_parent = True

    def test_everybody_selected_invoices_as_a_whole(self):
        self.assertEqual(self.parent.status, SaleStatus.INVOICED)
        # No child: nothing was split
        self.assertEqual(Permanence.objects.count(), 1)
        self.assertFalse(
            Permanence.objects.exclude(id=self.parent.id).exists()
        )
        # Both producers are paid, square
        for producer in (self.producer_a, self.producer_b):
            producer.refresh_from_db()
            self.assertEqual(producer.balance.amount, D("0"))
        # Alice is charged for both purchases at once
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-12.00"))
        # One movement per producer, both attached to the parent
        self.assertEqual(
            BankAccount.objects.filter(
                operation_status=BankMovement.CALCULATED_INVOICE,
                permanence_id=self.parent.id,
            ).count(),
            2,
        )
