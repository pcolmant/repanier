"""The offer toggle of the products screen.

Switching a product in or out of offer must stay instant on a big
group: the toggle runs a surgical recalculation of the offer items of
that product only, never the whole permanence. The purchases do not
move, so every invoice aggregate stays as it was - the toggle never
touches the accounting. This is pinned here, against an open
permanence with real baskets.
"""
import datetime
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from repanier.const import BankMovement, OrderUnit, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
)
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

CUSTOMERS = 12


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class IsIntoOfferToggleTest(TestCase):
    """An open permanence, CUSTOMERS baskets with the product."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The bank anchor required at close time
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Account opening",
        )
        cls.staff = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme A")
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Poires",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.permanence.producers.add(cls.producer)
        task_order.open_order(cls.permanence.id, send_mail=False)
        for index in range(CUSTOMERS):
            user = User.objects.create_user(
                username="client{}@example.com".format(index),
                email="client{}@example.com".format(index),
                password="x",
            )
            customer = Customer.objects.create(
                user=user, short_basket_name="Client{}".format(index), may_order=True
            )
            CustomerInvoice.get_or_create_invoice(
                permanence_id=cls.permanence.id,
                customer_id=customer.id,
                status=SaleStatus.OPENED,
            )
            offer_item = cls.product.offeritem_set.get(permanence=cls.permanence)
            purchase, updated = create_or_update_one_cart_item(
                customer=customer,
                offer_item_id=offer_item.id,
                q_order=D("1"),
                comment="",
            )
            assert updated and purchase is not None

    def get_aggregates(self):
        """The aggregates the full recalculation maintains; the toggle
        must leave every one of them untouched."""
        customer_invoices = {}
        customer_producer_invoices = {}
        for customer in Customer.objects.all():
            invoice = CustomerInvoice.objects.get(
                permanence_id=self.permanence.id, customer_id=customer.id
            )
            customer_invoices[customer.id] = (
                invoice.delta_price_with_tax.amount,
                invoice.delta_vat.amount,
            )
            customer_producer_invoice = CustomerProducerInvoice.objects.get(
                permanence_id=self.permanence.id,
                customer_id=customer.id,
                producer_id=self.producer.id,
            )
            customer_producer_invoices[customer.id] = (
                customer_producer_invoice.total_purchase_with_tax.amount,
                customer_producer_invoice.total_selling_with_tax.amount,
            )
        return customer_invoices, customer_producer_invoices

    def test_the_toggle_never_touches_the_basket_aggregates(self):
        before_customers, before_producers = self.get_aggregates()
        self.client.force_login(user=self.staff)
        url = reverse("repanier:is_into_offer", args=[self.product.id])
        # The surgical toggle runs on a bounded query budget: with
        # 12 open baskets the full recalculation would need more
        # than 100 queries, the surgical one stays far below 40
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertLessEqual(len(queries), 40)
        self.assertEqual(response.status_code, 200)
        # The product is out of offer, its offer item too
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_into_offer)
        offer_item = OfferItemReadOnly.objects.get(
            permanence_id=self.permanence.id, product_id=self.product.id
        )
        self.assertFalse(offer_item.may_order)
        # Nothing of the baskets moved: the aggregates did not move
        after_customers, after_producers = self.get_aggregates()
        self.assertEqual(before_customers, after_customers)
        self.assertEqual(before_producers, after_producers)
        # The full recalculation of the permanence finds nothing to fix
        # either: the surgical path left nothing behind
        self.permanence.calculate_order_amount()
        final_customers, final_producers = self.get_aggregates()
        self.assertEqual(before_customers, final_customers)
        self.assertEqual(before_producers, final_producers)
        # Toggling back restores the offer
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_into_offer)
        offer_item.refresh_from_db()
        self.assertTrue(offer_item.may_order)


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class IsIntoOfferToggleWithoutPermanenceTest(TestCase):
    """The products of the next round, before anything gets opened:
    the toggle concerns no permanence at all."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.staff = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme A")
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Poires",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()

    def test_the_toggle_touches_nothing_and_clears_no_cache(self):
        self.client.force_login(user=self.staff)
        url = reverse("repanier:is_into_offer", args=[self.product.id])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertLessEqual(len(queries), 25)
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_into_offer)
        # No offer item was ever created: without a permanence, there
        # is nothing to offer - the toggle also left the site cache
        # alone, wiping it for nothing was the old behavior
        self.assertFalse(
            OfferItemReadOnly.objects.filter(product_id=self.product.id).exists()
        )
