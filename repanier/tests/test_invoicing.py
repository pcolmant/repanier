"""Business tests of the invoicing pipeline (Permanence.invoice).

Repanier allows two charging models, both covered here:
- individual: each customer pays for his own purchases
  (customer_charged_id == customer_id)
- via a group: members buy individually but the GROUP is charged.
  The group is bound to its DELIVERY POINT (LUT_DeliveryPoint.group):
  members of the group get the group's delivery board by default at
  order time, which routes both the logistics and the charging.

The pipeline also picks up bank account movements recorded before the
invoicing (customer payments / deposits) and stamps the whole
permanence as invoiced, anchored by a new bank LATEST_TOTAL.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import BankMovement, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.lut import LUT_DeliveryPoint
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal
PAYMENT_DATE = datetime.date(2026, 11, 30)


class InvoicingFixtureMixin:
    """Build a permanence at SEND with one ordered product (PC, 2.50 + 0.20 deposit)."""

    group_id = None  # class attribute shadowed by GroupInvoicingTest

    @classmethod
    def build_permanence_at_send(cls, ordered_by, with_group=False):
        # The configuration record a real site always has
        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        # The bank anchor required by Permanence.invoice()
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Account opening",
        )

        if with_group:
            # A group is a customer bound to a delivery point
            group_user = User.objects.create_user(
                username="group@example.com", email="group@example.com", password="x"
            )
            cls.group = Customer.objects.create(
                user=group_user,
                short_basket_name="MonGroupe",
                may_order=True,
                is_group=True,
            )
            cls.group_id = cls.group.id
            cls.delivery_point = LUT_DeliveryPoint.objects.create(
                short_name_v2="PointGroupe", group=cls.group
            )

        cls.producer = Producer.objects.create(short_profile_name="Ferme Compta")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.PLANNED,
            with_delivery_point=with_group,
        )
        cls.permanence.producers.add(cls.producer)
        if with_group:
            cls.delivery_board = DeliveryBoard.objects.create(
                permanence=cls.permanence, delivery_point=cls.delivery_point
            )
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Cerises",
            order_unit="100",  # PC
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.offer_item = cls.product.offeritem_set.get(permanence=cls.permanence)

        cls.customers = []
        for n, quantity in enumerate(ordered_by):
            user = User.objects.create_user(
                username="client%d@example.com" % n,
                email="client%d@example.com" % n,
                password="x",
            )
            customer = Customer.objects.create(
                user=user,
                short_basket_name="Client%d" % n,
                may_order=True,
                group_id=cls.group_id,
            )
            CustomerInvoice.get_or_create_invoice(
                permanence_id=cls.permanence.id,
                customer_id=customer.id,
                status=SaleStatus.OPENED,
            )
            purchase, updated = create_or_update_one_cart_item(
                customer=customer,
                offer_item_id=cls.offer_item.id,
                q_order=quantity,
                comment="",
            )
            assert updated and purchase is not None
            cls.customers.append(customer)

        deliveries_id = ()
        if with_group:
            deliveries_id = (cls.delivery_board.id,)
        task_order.close_order(
            cls.permanence.id,
            everything=True,
            deliveries_id=deliveries_id,
            send_mail=False,
        )
        cls.permanence.refresh_from_db()
        assert cls.permanence.status == SaleStatus.SEND

    @classmethod
    def invoice(cls):
        cls.permanence.refresh_from_db()
        cls.permanence.invoice(payment_date=PAYMENT_DATE)
        cls.permanence.refresh_from_db()


class IndividualInvoicingTest(InvoicingFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_permanence_at_send(ordered_by=[D("3")])

    def test_invoice_updates_balances_and_status(self):
        total = D("2.70") * D("3")  # (unit price + deposit) x quantity
        self.invoice()

        # The permanence is invoiced and remembers the payment date
        self.assertEqual(self.permanence.status, SaleStatus.INVOICED)
        self.assertEqual(self.permanence.payment_date, PAYMENT_DATE)
        self.assertIsNotNone(self.permanence.invoice_sort_order)

        customer = self.customers[0]
        customer.refresh_from_db()
        self.assertEqual(customer.balance.amount, -total)

        invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=customer.id
        )
        self.assertEqual(invoice.status, SaleStatus.INVOICED)
        self.assertEqual(invoice.previous_balance.amount, D("0"))
        self.assertEqual(invoice.balance.amount, -total)
        self.assertEqual(invoice.get_total_price_with_tax().amount, total)
        self.assertIsNotNone(invoice.invoice_sort_order)

        # Producer side: the producer is owed the purchase price
        producer_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        )
        self.assertEqual(producer_invoice.balance.amount, total)
        self.producer.refresh_from_db()
        self.assertEqual(self.producer.balance.amount, total)

    def test_invoice_generates_bank_movements_and_new_total(self):
        # The accounting staff records what the producer claims and that
        # this invoice must be paid (to_be_paid, "à booker")
        ProducerInvoice.objects.filter(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("8.10"))
        self.invoice()

        # One payment movement to the producer of the claimed amount
        pay_producer = BankAccount.objects.filter(
            operation_status=BankMovement.CALCULATED_INVOICE,
            producer_id=self.producer.id,
        ).get()
        self.assertEqual(pay_producer.bank_amount_out.amount, D("8.10"))

        # The previous total is demoted, a new one anchored on the permanence
        self.assertFalse(
            BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL,
                permanence_id__isnull=True,
            ).exists()
        )
        latest_total = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL,
            permanence_id=self.permanence.id,
        )
        # Invoices are stamped with the bank total id
        for invoice in CustomerInvoice.objects.filter(permanence_id=self.permanence.id):
            self.assertEqual(invoice.invoice_sort_order, latest_total.id)

    def test_customer_payment_recorded_beforehand_is_integrated(self):
        customer = self.customers[0]
        # A 10.00 payment recorded by the accounting staff before invoicing
        BankAccount.objects.create(
            customer_id=customer.id,
            operation_date=datetime.date.today(),
            operation_comment="Payment",
            bank_amount_in=D("10.00"),
        )
        self.invoice()

        customer.refresh_from_db()
        # 10.00 paid - 8.10 owed
        self.assertEqual(customer.balance.amount, D("1.90"))
        invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=customer.id
        )
        self.assertEqual(invoice.balance.amount, D("1.90"))
        self.assertEqual(invoice.bank_amount_in.amount, D("10.00"))

        # The bank row is now attached to this permanence
        payment = BankAccount.objects.get(operation_comment="Payment")
        self.assertEqual(payment.customer_invoice_id, invoice.id)
        self.assertEqual(payment.permanence_id, self.permanence.id)


class GroupInvoicingTest(InvoicingFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        # Two members of the group, with different order sizes
        cls.build_permanence_at_send(ordered_by=[D("2"), D("1")], with_group=True)

    def test_group_is_charged_not_the_members(self):
        total = D("2.70") * D("2") + D("2.70") * D("1")  # 8.10 for the group
        self.invoice()

        self.group.refresh_from_db()
        self.assertEqual(self.group.balance.amount, -total)

        # The group invoice aggregates the purchases charged to the group
        group_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.group.id
        )
        self.assertTrue(group_invoice.is_group)
        self.assertEqual(group_invoice.get_total_price_with_tax().amount, total)
        self.assertEqual(group_invoice.balance.amount, -total)

        # The members do not pay: their balance is untouched
        for member in self.customers:
            member.refresh_from_db()
            self.assertEqual(member.balance.amount, D("0"))
            member_invoice = CustomerInvoice.objects.get(
                permanence_id=self.permanence.id, customer_id=member.id
            )
            self.assertEqual(member_invoice.customer_charged_id, self.group.id)
            self.assertEqual(member_invoice.balance.amount, D("0"))

    def test_group_invoicing_still_pays_the_producer(self):
        self.invoice()
        producer_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        )
        self.assertEqual(producer_invoice.balance.amount, D("8.10"))
        self.producer.refresh_from_db()
        self.assertEqual(self.producer.balance.amount, D("8.10"))


class PartialDeliveryPointClosureTest(InvoicingFixtureMixin, TestCase):
    """A permanence with delivery points can be closed point by point."""

    @classmethod
    def setUpTestData(cls):
        # The configuration record a real site always has
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme Partielle")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.PLANNED,
            with_delivery_point=True,
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Poireaux",
            order_unit="100",
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()

        # Two delivery points, each bound to its own group
        cls.boards = []
        cls.members = []
        for n in range(2):
            group_user = User.objects.create_user(
                username="group%d@example.com" % n, password="x"
            )
            group = Customer.objects.create(
                user=group_user,
                short_basket_name="Groupe%d" % n,
                may_order=True,
                is_group=True,
            )
            point = LUT_DeliveryPoint.objects.create(
                short_name_v2="Point%d" % n, group=group
            )
            board = DeliveryBoard.objects.create(
                permanence=cls.permanence, delivery_point=point
            )
            cls.boards.append(board)
            member_user = User.objects.create_user(
                username="membre%d@example.com" % n, password="x"
            )
            member = Customer.objects.create(
                user=member_user,
                short_basket_name="Membre%d" % n,
                may_order=True,
                group_id=group.id,
            )
            cls.members.append(member)

        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.offer_item = cls.product.offeritem_set.get(permanence=cls.permanence)
        for member in cls.members:
            CustomerInvoice.get_or_create_invoice(
                permanence_id=cls.permanence.id,
                customer_id=member.id,
                status=SaleStatus.OPENED,
            )
            purchase, updated = create_or_update_one_cart_item(
                customer=member,
                offer_item_id=cls.offer_item.id,
                q_order=D("2"),
                comment="",
            )
            assert updated

    def test_closing_one_delivery_point_leaves_the_other_open(self):
        board1, board2 = self.boards
        member1, member2 = self.members

        # Partial closure of the first delivery point only
        task_order.close_order(
            self.permanence.id,
            everything=False,
            deliveries_id=(board1.id,),
            send_mail=False,
        )
        self.permanence.refresh_from_db()
        # The permanence stays open: the second delivery point still works
        self.assertEqual(self.permanence.status, SaleStatus.OPENED)

        board1.refresh_from_db()
        board2.refresh_from_db()
        self.assertEqual(board1.status, SaleStatus.SEND)
        self.assertEqual(board1.highest_status, SaleStatus.SEND)
        self.assertEqual(board2.status, SaleStatus.OPENED)

        # Only the customers of the closed delivery point are blocked
        invoice1 = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=member1.id
        )
        invoice2 = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=member2.id
        )
        self.assertEqual(invoice1.status, SaleStatus.SEND)
        self.assertEqual(invoice2.status, SaleStatus.OPENED)
        purchase2, updated = create_or_update_one_cart_item(
            customer=member2,
            offer_item_id=self.offer_item.id,
            q_order=D("1"),
            comment="",
        )
        # The still-open delivery point keeps accepting orders
        self.assertTrue(updated)

    def test_completing_the_closure_moves_the_permanence(self):
        board1, board2 = self.boards
        # Partial first, then complete
        task_order.close_order(
            self.permanence.id,
            everything=False,
            deliveries_id=(board1.id,),
            send_mail=False,
        )
        task_order.close_order(
            self.permanence.id,
            everything=True,
            deliveries_id=(board1.id, board2.id),
            send_mail=False,
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
        board1.refresh_from_db()
        board2.refresh_from_db()
        self.assertEqual(board1.status, SaleStatus.SEND)
        self.assertEqual(board2.status, SaleStatus.SEND)
