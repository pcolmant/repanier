"""Business tests of the VAT and price-list computation matrix.

The customer prices are always derived by Item.recalculate_prices():

producer_price_are_wo_vat = True:
    producer_vat = producer_price x rate
    customer_price = (producer_price x price_list_multiplier) + customer_vat
    customer_vat = (producer_price x multiplier) x rate

producer_price_are_wo_vat = False (VAT included in the producer price):
    producer_vat = producer_price - (producer_price / (1 + rate))
    customer_price = producer_price x multiplier (VAT still included)
    customer_vat = customer_price - (customer_price / (1 + rate))

The whole chain is then re-asserted at purchase level through the
pre_save signal: selling price, purchase price, VAT of both sides.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import DECIMAL_ZERO, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import create_or_update_one_cart_item

D = Decimal


def default_fixture(producer_kwargs=None):
    """Build a minimal orderable offer with a parametrized producer."""
    user = User.objects.create_user(
        username="c-%s@example.com" % Permanence.objects.count(), password="x"
    )
    customer = Customer.objects.create(
        user=user, short_basket_name="C%s" % user.pk, may_order=True
    )
    producer = Producer.objects.create(
        short_profile_name="Prod%s" % Producer.objects.count(), **(producer_kwargs or {})
    )
    permanence = Permanence.objects.create(
        permanence_date=datetime.date.today(), status=SaleStatus.OPENED
    )
    permanence.producers.add(producer)
    return customer, producer, permanence


class VatIncludedMatrixTest(TestCase):
    def _order_one(self, price, vat_level, multiplier, wo_vat):
        customer, producer, permanence = default_fixture(
            {
                "price_list_multiplier": multiplier,
                "producer_price_are_wo_vat": wo_vat,
            }
        )
        product = Product.objects.create(
            producer=producer,
            long_name_v2="Produit",
            order_unit="100",
            producer_unit_price=price,
            vat_level=vat_level,
            stock=D("99"),
        )
        product.is_into_offer = True
        product.save()
        offer_item = product.get_or_create_offer_item(permanence)
        CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id, customer_id=customer.id, status=SaleStatus.OPENED
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        self.assertTrue(updated)
        return product, offer_item, purchase

    def test_vat_included_producer_price(self):
        # producer price 3.63 TTC, VAT 21%, multiplier 1: net = 3.00
        product, offer_item, purchase = self._order_one(
            D("3.63"), Vat.VAT_600, D("1"), wo_vat=False
        )
        self.assertEqual(product.producer_vat.amount, D("0.63"))
        self.assertEqual(product.customer_unit_price.amount, D("3.63"))
        self.assertEqual(product.customer_vat.amount, D("0.63"))
        # Purchase level
        self.assertEqual(purchase.purchase_price.amount, D("3.63"))
        self.assertEqual(purchase.selling_price.amount, D("3.63"))
        self.assertEqual(purchase.producer_vat.amount, D("0.63"))
        self.assertEqual(purchase.customer_vat.amount, D("0.63"))

    def test_vat_included_with_price_list_multiplier(self):
        # producer price 2.12 TTC, VAT 6%, multiplier 1.25 -> 2.65
        product, offer_item, purchase = self._order_one(
            D("2.12"), Vat.VAT_400, D("1.25"), wo_vat=False
        )
        self.assertEqual(product.producer_vat.amount, D("0.12"))
        self.assertEqual(product.customer_unit_price.amount, D("2.65"))
        self.assertEqual(product.customer_vat.amount, D("0.15"))
        self.assertEqual(purchase.selling_price.amount, D("2.65"))
        self.assertEqual(purchase.purchase_price.amount, D("2.12"))

    def test_wo_vat_producer_price(self):
        # producer price 2.00 HT, VAT 6%, multiplier 1.25:
        # customer price = 2.50 + 0.15 = 2.65
        product, offer_item, purchase = self._order_one(
            D("2.00"), Vat.VAT_400, D("1.25"), wo_vat=True
        )
        self.assertEqual(product.producer_vat.amount, D("0.12"))
        self.assertEqual(product.customer_unit_price.amount, D("2.65"))
        self.assertEqual(product.customer_vat.amount, D("0.15"))
        self.assertEqual(purchase.selling_price.amount, D("2.65"))
        self.assertEqual(purchase.purchase_price.amount, D("2.00"))

    def test_zero_vat_level(self):
        # VAT_100 is 0%: prices pass through unchanged whatever the mode
        product, offer_item, purchase = self._order_one(
            D("2.00"), Vat.VAT_100, D("1.5"), wo_vat=True
        )
        self.assertEqual(product.producer_vat.amount, DECIMAL_ZERO)
        self.assertEqual(product.customer_unit_price.amount, D("3.00"))
        self.assertEqual(product.customer_vat.amount, DECIMAL_ZERO)
        self.assertEqual(purchase.selling_price.amount, D("3.00"))
        self.assertEqual(purchase.customer_vat.amount, DECIMAL_ZERO)

    def test_invoice_aggregates_the_vat_of_the_chain(self):
        product, offer_item, purchase = self._order_one(
            D("2.00"), Vat.VAT_400, D("1.25"), wo_vat=True
        )
        customer_invoice = purchase.customer_invoice
        permanence = purchase.permanence
        permanence.calculate_order_amount()
        customer_invoice.refresh_from_db()
        self.assertEqual(customer_invoice.total_price_with_tax.amount, D("2.65"))
        self.assertEqual(customer_invoice.total_vat.amount, D("0.15"))
