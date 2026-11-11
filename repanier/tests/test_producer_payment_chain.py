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
from repanier.models.purchase import Purchase
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


class ProducerChainJourneyMixin:
    """Shared machinery for the multi-producer payment journeys: Alice
    buys from several producers and the treasurer pays them over several
    invoicing rounds, one child permanence per round."""

    # [(short_profile_name, producer_unit_price, quantity), ...]
    purchases = []

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
        cls.producers = {}
        cls.products = {}
        for name, price, _quantity in cls.purchases:
            producer = Producer.objects.create(short_profile_name=name)
            cls.producers[name] = producer
            product = Product.objects.create(
                producer=producer,
                long_name_v2=name,
                order_unit="100",
                producer_unit_price=price,
                vat_level=Vat.VAT_100,
                stock=D("99"),
            )
            product.is_into_offer = True
            product.save()
            cls.products[name] = product
        cls.first_permanence = cls.order_and_close()

    @classmethod
    def order_and_close(cls):
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        permanence.producers.add(*[p.id for p in cls.producers.values()])
        task_order.open_order(permanence.id, send_mail=False)
        CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=cls.alice.id,
            status=SaleStatus.OPENED,
        )
        for name, _price, quantity in cls.purchases:
            offer_item = cls.products[name].offeritem_set.get(permanence=permanence)
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

    @classmethod
    def pay_producers(cls, permanence, claims):
        # claims: {producer_name: amount claimed by the producer}
        for name, claimed in claims.items():
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id, producer_id=cls.producers[name].id
            ).update(to_be_paid=True, to_be_invoiced_balance=claimed)
        permanence.invoice(payment_date=PAYMENT_DATE)
        permanence.refresh_from_db()
        assert permanence.status == SaleStatus.INVOICED

    @classmethod
    def child_of(cls, permanence):
        return Permanence.objects.get(master_permanence_id=permanence.id)

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

    def anchor_net(self, permanence_id):
        anchor = self.latest_total(permanence_id)
        return anchor.bank_amount_in.amount - anchor.bank_amount_out.amount


class ThreeRoundsChainTest(ProducerChainJourneyMixin, TestCase):
    """Three producers paid one after another, over three invoicing
    rounds: the child chain (parent -> child -> grandchild) and the bank
    anchor chain across the rounds."""

    purchases = [
        ("Abrigots", D("3.00"), D("2")),  # 6.00, paid at round 1
        ("Bananes", D("2.00"), D("3")),  # 6.00, paid at round 2
        ("Cerises", D("1.00"), D("4")),  # 4.00, paid at round 3
    ]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.round_1 = cls.first_permanence
        cls.pay_producers(cls.round_1, {"Abrigots": D("6.00")})
        cls.round_2 = cls.child_of(cls.round_1)
        cls.pay_producers(cls.round_2, {"Bananes": D("6.00")})
        cls.round_3 = cls.child_of(cls.round_2)
        cls.pay_producers(cls.round_3, {"Cerises": D("4.00")})

    def test_the_child_chain_spans_the_three_rounds(self):
        for permanence in (self.round_1, self.round_2, self.round_3):
            self.assertEqual(permanence.status, SaleStatus.INVOICED)
        self.assertEqual(self.round_2.master_permanence_id, self.round_1.id)
        self.assertEqual(self.round_3.master_permanence_id, self.round_2.id)
        # Exactly the three permanences: the chain is closed
        self.assertEqual(Permanence.objects.count(), 3)

    def test_each_producer_ends_square_at_its_own_round(self):
        rounds = {
            "Abrigots": self.round_1,
            "Bananes": self.round_2,
            "Cerises": self.round_3,
        }
        for name, permanence in rounds.items():
            producer = self.producers[name]
            producer.refresh_from_db()
            self.assertEqual(producer.balance.amount, D("0"), name)
            # The producer invoice of each producer sits at its own round
            invoice = ProducerInvoice.objects.get(producer_id=producer.id)
            self.assertEqual(invoice.permanence_id, permanence.id, name)
            self.assertEqual(invoice.balance.amount, D("0"), name)
            self.assertEqual(
                invoice.invoice_sort_order, self.latest_total(permanence.id).id, name
            )
            # The payment is attached to that same round
            pay = BankAccount.objects.get(
                operation_status=BankMovement.CALCULATED_INVOICE,
                producer_id=producer.id,
            )
            self.assertEqual(pay.permanence_id, permanence.id, name)

    def test_the_customer_is_charged_progressively(self):
        expected_totals = {
            self.round_1.id: D("6.00"),
            self.round_2.id: D("6.00"),
            self.round_3.id: D("4.00"),
        }
        for permanence_id, expected in expected_totals.items():
            invoice = CustomerInvoice.objects.get(
                permanence_id=permanence_id, customer_id=self.alice.id
            )
            self.assertEqual(invoice.get_total_price_with_tax().amount, expected)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-16.00"))

    def test_the_bank_anchor_chains_across_the_three_rounds(self):
        # Each anchor is cumulative: it adds the movements of its round
        # to the previous one, and the last one is the only one alive
        self.assertEqual(self.anchor_net(self.round_1.id), D("-6.00"))
        self.assertEqual(self.anchor_net(self.round_2.id), D("-12.00"))
        self.assertEqual(self.anchor_net(self.round_3.id), D("-16.00"))
        # Round deltas: exactly the payment of that round
        self.assertEqual(
            self.anchor_net(self.round_2.id) - self.anchor_net(self.round_1.id),
            D("-6.00"),
        )
        self.assertEqual(
            self.anchor_net(self.round_3.id) - self.anchor_net(self.round_2.id),
            D("-4.00"),
        )
        # One alive anchor, the previous ones demoted
        self.assertEqual(
            BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL
            ).count(),
            1,
        )
        for permanence in (self.round_1, self.round_2):
            anchor = self.latest_total(permanence.id)
            anchor.refresh_from_db()
            self.assertEqual(anchor.operation_status, BankMovement.NOT_LATEST_TOTAL)
        # Each permanence is stamped with the anchor of its own round
        for permanence in (self.round_1, self.round_2, self.round_3):
            permanence.refresh_from_db()
            self.assertEqual(
                permanence.invoice_sort_order, self.latest_total(permanence.id).id
            )


class TwoUnpaidProducersMoveTogetherTest(ProducerChainJourneyMixin, TestCase):
    """When the treasurer pays one producer out of three, the two unpaid
    ones move together into the SAME child permanence, and paying them
    together at the child closes the chain."""

    purchases = [
        ("Abrigots", D("3.00"), D("2")),  # 6.00, paid at round 1
        ("Bananes", D("2.00"), D("3")),  # 6.00, unpaid at round 1
        ("Cerises", D("1.00"), D("4")),  # 4.00, unpaid at round 1
    ]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.round_1 = cls.first_permanence
        cls.pay_producers(cls.round_1, {"Abrigots": D("6.00")})
        cls.child = cls.child_of(cls.round_1)
        # The treasurer pays the two remaining producers together
        cls.pay_producers(cls.child, {"Bananes": D("6.00"), "Cerises": D("4.00")})

    def test_the_child_carries_the_two_unpaid_producers(self):
        expected = {self.producers["Bananes"].id, self.producers["Cerises"].id}
        self.assertEqual(
            set(self.child.producers.values_list("id", flat=True)), expected
        )
        for name in ("Bananes", "Cerises"):
            invoice = ProducerInvoice.objects.get(producer_id=self.producers[name].id)
            self.assertEqual(invoice.permanence_id, self.child.id, name)
        # Paying both at once closes the chain: no grandchild
        self.assertEqual(Permanence.objects.count(), 2)

    def test_everybody_gets_square_after_the_second_round(self):
        paid = {
            "Abrigots": D("6.00"),
            "Bananes": D("6.00"),
            "Cerises": D("4.00"),
        }
        for name, expected_payment in paid.items():
            producer = self.producers[name]
            producer.refresh_from_db()
            self.assertEqual(producer.balance.amount, D("0"), name)
            pay = BankAccount.objects.get(
                operation_status=BankMovement.CALCULATED_INVOICE,
                producer_id=producer.id,
            )
            self.assertEqual(pay.bank_amount_out.amount, expected_payment, name)
        # Alice bought 6.00 + 6.00 + 4.00
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-16.00"))
        # The child customer invoice carries both moved purchases
        child_invoice = CustomerInvoice.objects.get(
            permanence_id=self.child.id, customer_id=self.alice.id
        )
        self.assertEqual(child_invoice.get_total_price_with_tax().amount, D("10.00"))
        # The anchors chain over the two rounds
        self.assertEqual(self.anchor_net(self.round_1.id), D("-6.00"))
        self.assertEqual(self.anchor_net(self.child.id), D("-16.00"))


class ClaimedLowerThanCalculatedAtTheChildTest(ProducerChainJourneyMixin, TestCase):
    """Between two rounds the treasurer received the producer's paper
    invoice, which claims LESS than calculated: the discount becomes a
    profit of the site consumer account, at the child level too."""

    purchases = [
        ("Abrigots", D("3.00"), D("2")),  # 6.00 calculated, unpaid at round 1
        ("Bananes", D("2.00"), D("3")),  # 6.00, paid at round 1
    ]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.round_1 = cls.first_permanence
        cls.pay_producers(cls.round_1, {"Bananes": D("6.00")})
        cls.child = cls.child_of(cls.round_1)
        # The producer claims 5.50 instead of the calculated 6.00
        cls.pay_producers(cls.child, {"Abrigots": D("5.50")})

    def test_the_producer_is_paid_the_claimed_amount_and_ends_square(self):
        producer = self.producers["Abrigots"]
        pay = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=producer.id,
        )
        self.assertEqual(pay.bank_amount_out.amount, D("5.50"))
        self.assertEqual(pay.permanence_id, self.child.id)
        producer.refresh_from_db()
        self.assertEqual(producer.balance.amount, D("0"))
        invoice = ProducerInvoice.objects.get(producer_id=producer.id)
        # Still calculated on the full delivered amount, but balanced
        self.assertEqual(invoice.total_price_with_tax.amount, D("6.00"))
        self.assertEqual(invoice.to_be_invoiced_balance.amount, D("5.50"))
        self.assertEqual(invoice.bank_amount_out.amount, D("5.50"))
        self.assertEqual(invoice.balance.amount, D("0"))

    def test_the_discount_books_as_a_profit_on_the_site_consumer_account(self):
        site_customer = Customer.get_or_create_group()
        profit = BankAccount.objects.get(operation_status=BankMovement.PROFIT)
        self.assertEqual(profit.customer_id, site_customer.id)
        self.assertEqual(profit.bank_amount_in.amount, D("0.50"))
        self.assertEqual(profit.bank_amount_out.amount, D("0"))
        self.assertEqual(profit.permanence_id, self.child.id)
        # The profit is attached to the site invoice of the child
        site_invoice = CustomerInvoice.objects.get(
            permanence_id=self.child.id, customer_id=site_customer.id
        )
        self.assertEqual(profit.customer_invoice_id, site_invoice.id)
        site_customer.refresh_from_db()
        self.assertEqual(site_customer.balance.amount, D("0.50"))

    def test_the_customer_pays_the_calculated_amount_anyway(self):
        # The producer discount is not charged back to the customer:
        # Alice pays the full calculated amount of her purchases
        child_invoice = CustomerInvoice.objects.get(
            permanence_id=self.child.id, customer_id=self.alice.id
        )
        self.assertEqual(child_invoice.get_total_price_with_tax().amount, D("6.00"))
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-12.00"))
        # The anchor reflects the payments only: the profit is not a real
        # bank entry, so it does not move the anchor
        self.assertEqual(self.anchor_net(self.round_1.id), D("-6.00"))
        self.assertEqual(self.anchor_net(self.child.id), D("-11.50"))


class BreakageAdjustedBetweenRoundsTest(ProducerChainJourneyMixin, TestCase):
    """Between two rounds the group records breakage for the still unpaid
    producer: the invoiced quantity of the child is adjusted BEFORE the
    second invoicing, and the customer pays only what he received."""

    purchases = [
        ("Abrigots", D("3.00"), D("2")),  # 6.00 estimated, unpaid at round 1
        ("Bananes", D("2.00"), D("3")),  # 6.00, paid at round 1
    ]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.round_1 = cls.first_permanence
        cls.pay_producers(cls.round_1, {"Bananes": D("6.00")})
        cls.child = cls.child_of(cls.round_1)
        # One of the two Abrigots was broken at distribution: the child
        # purchase is adjusted, exactly what the correction screens do
        cls.purchase = Purchase.objects.get(
            permanence_id=cls.child.id, producer_id=cls.producers["Abrigots"].id
        )
        cls.purchase.quantity_invoiced = D("1.000")
        cls.purchase.save()
        cls.child.calculate_order_amount()
        # The producer is paid for what was actually delivered
        cls.pay_producers(cls.child, {"Abrigots": D("3.00")})

    def test_the_adjustment_only_touches_the_child(self):
        # The parent invoice of Alice keeps the fully paid producer only
        parent_invoice = CustomerInvoice.objects.get(
            permanence_id=self.round_1.id, customer_id=self.alice.id
        )
        self.assertEqual(parent_invoice.get_total_price_with_tax().amount, D("6.00"))
        # The child invoice carries the adjusted purchase
        child_invoice = CustomerInvoice.objects.get(
            permanence_id=self.child.id, customer_id=self.alice.id
        )
        self.assertEqual(child_invoice.get_total_price_with_tax().amount, D("3.00"))
        # Alice pays only what she received, not what she ordered
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("-9.00"))

    def test_the_producer_is_paid_one_broken_piece_less(self):
        producer = self.producers["Abrigots"]
        producer.refresh_from_db()
        self.assertEqual(producer.balance.amount, D("0"))
        pay = BankAccount.objects.get(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=producer.id,
        )
        self.assertEqual(pay.bank_amount_out.amount, D("3.00"))
        self.assertEqual(pay.permanence_id, self.child.id)
        invoice = ProducerInvoice.objects.get(producer_id=producer.id)
        self.assertEqual(invoice.permanence_id, self.child.id)
        self.assertEqual(invoice.total_price_with_tax.amount, D("3.00"))
        self.assertEqual(invoice.balance.amount, D("0"))
        # The anchors chain: round 2 adds exactly 3.00 out
        self.assertEqual(self.anchor_net(self.round_1.id), D("-6.00"))
        self.assertEqual(self.anchor_net(self.child.id), D("-9.00"))
