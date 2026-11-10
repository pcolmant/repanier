"""Business-flow tests: a customer orders through the real entry point.

This exercises the exact chain used by the AJAX order views:
product -> offer item -> create_or_update_one_cart_item -> purchase
pre_save signal (price computation + invoice bookkeeping) ->
invoice aggregation.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import DECIMAL_ZERO, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import create_or_update_one_cart_item

D = Decimal


class PurchaseFlowTestMixin:
    """Fixture helpers shared by the purchase flow test cases."""

    @classmethod
    def build_fixture(cls):
        cls.user = User.objects.create_user(
            username="customer@example.com", email="customer@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Tester", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme Test")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Pommes",
            order_unit="100",  # PC
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,  # 0%
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        cls.offer_item = cls.product.get_or_create_offer_item(cls.permanence)
        # The order page ensures the customer invoice exists first:
        cls.customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )

    def order(self, q_order):
        return create_or_update_one_cart_item(
            customer=self.customer,
            offer_item_id=self.offer_item.id,
            q_order=q_order,
            comment="",
        )


class PurchaseCreationTest(PurchaseFlowTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_fixture()

    def test_order_creates_purchase_and_invoices(self):
        purchase, updated = self.order(D("3"))
        self.assertTrue(updated)
        self.assertIsNotNone(purchase)

        # One purchase for (customer, offer item)
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity_ordered, D("3"))
        # (unit price + deposit) x quantity, both computed by the pre_save
        # signal from the offer item (customer price is derived from the
        # producer price by product.recalculate_prices).
        self.assertEqual(purchase.customer_invoice_id, self.customer_invoice.id)
        self.assertEqual(purchase.producer_invoice_id, purchase.producer_invoice_id)
        self.assertIsNotNone(purchase.producer_invoice_id)
        self.assertIsNotNone(purchase.customer_producer_invoice_id)

        # Creating the purchase auto-created the three invoices
        self.assertTrue(
            ProducerInvoice.objects.filter(
                permanence_id=self.permanence.id, producer_id=self.producer.id
            ).exists()
        )
        self.assertTrue(
            CustomerProducerInvoice.objects.filter(
                permanence_id=self.permanence.id,
                customer_id=self.customer.id,
                producer_id=self.producer.id,
            ).exists()
        )

    def test_purchase_price_is_unit_plus_deposit_times_quantity(self):
        purchase, _ = self.order(D("3"))
        purchase.refresh_from_db()
        unit_price = purchase.offer_item.customer_unit_price.amount
        unit_deposit = purchase.offer_item.unit_deposit.amount
        self.assertEqual(purchase.selling_price.amount, (unit_price + unit_deposit) * D("3"))

    def test_ordering_zero_quantity_creates_an_empty_purchase(self):
        # A zero quantity is stored as a zero purchase row (it is how a
        # customer clears an entry of the cart), not ignored
        purchase, updated = self.order(DECIMAL_ZERO)
        self.assertTrue(updated)
        self.assertIsNotNone(purchase)
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity_ordered, DECIMAL_ZERO)
        self.assertEqual(purchase.selling_price.amount, DECIMAL_ZERO)

    def test_descendant_quantity_above_stock_is_refused(self):
        # get_q_alert() with plenty of stock: no order yet -> q_alert = stock
        purchase, updated = self.order(D("3"))
        self.assertTrue(updated)
        # Now request far more than the 99 in stock
        beyond_stock, updated = self.order(D("500"))
        self.assertFalse(updated)
        beyond_stock.refresh_from_db()
        # The previous quantity is preserved
        self.assertEqual(beyond_stock.quantity_ordered, D("3"))

    def test_order_refused_without_open_invoice(self):
        # An invoice with a status other than the requested one means the
        # permanence is not open for this customer
        other_user = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        other_customer = Customer.objects.create(
            user=other_user, short_basket_name="Autre", may_order=True
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=other_customer,
            offer_item_id=self.offer_item.id,
            q_order=D("1"),
            comment="",
        )
        self.assertFalse(updated)
        self.assertIsNone(purchase)


class PurchaseUpdateTest(PurchaseFlowTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_fixture()

    def test_reordering_updates_quantity_and_totals(self):
        self.order(D("2"))
        purchase, updated = self.order(D("5"))
        self.assertTrue(updated)
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity_ordered, D("5"))
        invoice = CustomerInvoice.objects.get(id=self.customer_invoice.id)
        invoice.calculate_order_amount()
        unit_price = purchase.offer_item.customer_unit_price.amount
        deposit = purchase.offer_item.unit_deposit.amount
        self.assertEqual(invoice.total_price_with_tax.amount, (unit_price + deposit) * D("5"))

    def test_aggregation_matches_manual_sum(self):
        self.order(D("2"))
        self.order(D("1"))  # same purchase updated, not a duplicate
        from repanier.models.purchase import Purchase

        self.assertEqual(Purchase.objects.count(), 1)

        self.permanence.calculate_order_amount()
        self.customer_invoice.refresh_from_db()
        purchase = Purchase.objects.get()
        self.assertEqual(
            self.customer_invoice.total_price_with_tax.amount,
            purchase.selling_price.amount,
        )
        producer_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.producer.id
        )
        self.assertEqual(
            producer_invoice.total_price_with_tax.amount,
            purchase.purchase_price.amount,
        )
        cpi = CustomerProducerInvoice.objects.get(
            permanence_id=self.permanence.id,
            customer_id=self.customer.id,
            producer_id=self.producer.id,
        )
        self.assertEqual(cpi.total_selling_with_tax.amount, purchase.selling_price.amount)
        self.assertEqual(cpi.total_purchase_with_tax.amount, purchase.purchase_price.amount)
