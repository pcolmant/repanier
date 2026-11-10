"""Business journey test: a permanence goes from PLANNED to SEND.

This is the full lifecycle through the real entry points:
open_order() bootstraps the offer items and the producer invoices,
the customer orders via the AJAX path, close_order() runs the whole
closure pipeline.

This journey only became testable once open_order() stopped using the
PostgreSQL-only .distinct("producer_id") (now a portable
values_list().distinct()).
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal


class OrderJourneyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # The configuration record a real site always has (required by
        # close_order and the login page)
        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        cls.user = User.objects.create_user(
            username="voyage@example.com", email="voyage@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Voyageur", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme Voyage")
        # Start scheduled, like a permanence freshly created in the admin
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Navets",
            order_unit="100",  # PC
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()

    def test_planned_to_send_lifecycle(self):
        # --- open the permanence -------------------------------------
        task_order.open_order(self.permanence.id, send_mail=False)

        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.OPENED)
        self.assertEqual(self.permanence.highest_status, SaleStatus.OPENED)

        # open_order created the orderable offer item
        offer_item = OfferItemReadOnly.objects.get(
            permanence_id=self.permanence.id, product_id=self.product.id
        )
        self.assertTrue(offer_item.may_order)

        # and the producer invoice of every producer with an orderable offer
        producer_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        )
        self.assertEqual(producer_invoice.status, SaleStatus.OPENED)

        # The customer order page callback creates the customer invoice
        customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=self.permanence.id,
            customer_id=self.customer.id,
            status=SaleStatus.OPENED,
        )

        # --- order then close ----------------------------------------
        purchase, updated = create_or_update_one_cart_item(
            customer=self.customer, offer_item_id=offer_item.id, q_order=D("3"), comment=""
        )
        self.assertTrue(updated)

        task_order.close_order(
            self.permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)

        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity_invoiced, D("3"))
        self.assertEqual(purchase.selling_price.amount, D("8.10"))

        customer_invoice.refresh_from_db()
        self.assertEqual(customer_invoice.status, SaleStatus.SEND)
        self.assertEqual(customer_invoice.get_total_price_with_tax().amount, D("8.10"))

    def test_back_to_scheduled_after_opening(self):
        task_order.open_order(self.permanence.id, send_mail=False)
        # back_to_scheduled is the admin "reopen for edition" path
        task_order.back_to_scheduled(self.permanence)

        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)
        # highest_status keeps the memory of the opening
        self.assertEqual(self.permanence.highest_status, SaleStatus.OPENED)

        # The offer items are no longer orderable
        offer_item = OfferItemReadOnly.objects.get(
            permanence_id=self.permanence.id, product_id=self.product.id
        )
        self.assertFalse(offer_item.may_order)

    def test_open_order_excludes_products_not_in_offer(self):
        not_in_offer = Product.objects.create(
            producer=self.producer,
            long_name_v2="Fraises",
            order_unit="100",
            producer_unit_price=D("6.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        not_in_offer.is_into_offer = False
        not_in_offer.save()
        task_order.open_order(self.permanence.id, send_mail=False)
        self.assertEqual(
            OfferItemReadOnly.objects.filter(
                permanence_id=self.permanence.id, product_id=not_in_offer.id
            ).count(),
            0,
        )
