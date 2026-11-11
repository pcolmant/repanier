"""Business tests of permanence status transitions (the closure pipeline).

task_order.close_order() runs the full synchronous closure chain:
OPENED -> WAIT_FOR_CLOSED -> CLOSED -> WAIT_FOR_SEND -> SEND,
moving purchases, customer invoices and producer invoices along,
and copying ordered quantities into invoiced quantities
(Permanence.send_to_producer).
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal


class ClosureJourneyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # On a real site, repanier.apps.ready() boots this configuration via
        # the admin UI. In tests, create it so the closure pipeline reads
        # the same settings a production site would have.
        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        cls.user = User.objects.create_user(
            username="customer@example.com", email="customer@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Tester", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme Test")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            highest_status=SaleStatus.OPENED,
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Pommes",
            order_unit="100",
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        cls.offer_item = cls.product.get_or_create_offer_item(cls.permanence)
        cls.customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=cls.customer, offer_item_id=cls.offer_item.id, q_order=D("3"), comment=""
        )
        assert updated
        cls.purchase = purchase

    def test_close_order_moves_everything_to_send(self):
        task_order.close_order(
            self.permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
        # The highest remembered status advanced too
        self.assertEqual(self.permanence.highest_status, SaleStatus.SEND)

        # Purchases are now invoiced: quantity_invoiced = quantity_ordered
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, SaleStatus.SEND)
        self.assertEqual(self.purchase.quantity_invoiced, D("3"))

        # Invoices follow the permanence
        self.customer_invoice.refresh_from_db()
        self.assertEqual(self.customer_invoice.status, SaleStatus.SEND)
        producer_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        )
        self.assertEqual(producer_invoice.status, SaleStatus.SEND)

        # Ordering is closed: a new attempt through the AJAX entry point
        # finds no purchase order status anymore (status moved to SEND)
        refused, updated = create_or_update_one_cart_item(
            customer=self.customer,
            offer_item_id=self.offer_item.id,
            q_order=D("1"),
            comment="",
        )
        self.assertFalse(updated)

    def test_ordered_amount_is_no_longer_modifiable_after_send(self):
        # create_or_update_one_purchase refuses non batch updates once
        # the purchase status has moved to SEND: the AJAX entry point no
        # longer accepts customer edits.
        task_order.close_order(
            self.permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        self.purchase.refresh_from_db()
        self.purchase.set_quantity(D("9"))
        # set_quantity writes quantity_invoiced when status >= WAIT_FOR_SEND
        self.assertEqual(self.purchase.quantity_invoiced, D("9"))
        self.assertEqual(self.purchase.quantity_ordered, D("3"))


class SetStatusGuardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="guard@example.com", email="guard@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Guard", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Guard Prod")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            highest_status=SaleStatus.OPENED,
        )

    def test_transition_from_wrong_old_status_raises(self):
        with self.assertRaises(ValueError):
            # The permanence is OPENED, not PLANNED
            self.permanence.set_status(
                old_status=SaleStatus.PLANNED, new_status=SaleStatus.WAIT_FOR_CLOSED
            )

    def test_transition_to_same_status_raises(self):
        with self.assertRaises(ValueError):
            self.permanence.set_status(
                old_status=SaleStatus.OPENED, new_status=SaleStatus.OPENED
            )

    def test_back_to_scheduled_keeps_highest_status(self):
        self.permanence.set_status(
            old_status=SaleStatus.OPENED, new_status=SaleStatus.PLANNED
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)
        # Going back does not erase where the permanence has been
        self.assertEqual(self.permanence.highest_status, SaleStatus.OPENED)

    def test_highest_status_only_moves_forward(self):
        self.permanence.set_status(
            old_status=SaleStatus.OPENED, new_status=SaleStatus.WAIT_FOR_CLOSED
        )
        self.permanence.set_status(
            old_status=SaleStatus.WAIT_FOR_CLOSED, new_status=SaleStatus.CLOSED
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.CLOSED)
        self.assertEqual(self.permanence.highest_status, SaleStatus.CLOSED)
        # A backward transition keeps highest_status
        self.permanence.set_status(
            old_status=SaleStatus.CLOSED, new_status=SaleStatus.PLANNED
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.highest_status, SaleStatus.CLOSED)
