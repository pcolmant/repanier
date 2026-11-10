"""Business tests of invoice calculation: transport and cash rounding.

The transport rules (CustomerInvoice.calculate_order_transport):
- transport applies only when the customer is the one charged
- no transport on an empty order
- with a minimum for free transport, the charged transport is capped
  by the remaining amount up to that minimum and by the transport itself

The rounding rule (CustomerInvoice.calculate_order_rounding):
- only active when REPANIER_SETTINGS_ROUND_INVOICES is true (Belgian law)
- adjusts delta_price_with_tax so the grand total is a cash-roundable amount
"""
import datetime
from decimal import Decimal
from itertools import count

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from repanier.const import DECIMAL_ZERO, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import create_or_update_one_cart_item

D = Decimal
_counter = count()


def build_orders_with_total(total):
    """Order products so that the customer invoice totals `total` exactly."""
    n = next(_counter)
    user = User.objects.create_user(
        username="c1-%d@example.com" % n, email="c1-%d@example.com" % n, password="x"
    )
    customer = Customer.objects.create(
        user=user, short_basket_name="C1-%d" % n, may_order=True
    )
    producer = Producer.objects.create(short_profile_name="Prod-%d" % n)
    permanence = Permanence.objects.create(
        permanence_date=datetime.date.today(), status=SaleStatus.OPENED
    )
    permanence.producers.add(producer)
    product = Product.objects.create(
        producer=producer,
        long_name_v2="Produit",
        order_unit="100",
        producer_unit_price=total,
        vat_level=Vat.VAT_100,
        stock=D("99"),
    )
    product.is_into_offer = True
    product.save()
    offer_item = product.get_or_create_offer_item(permanence)
    invoice = CustomerInvoice.get_or_create_invoice(
        permanence_id=permanence.id, customer_id=customer.id, status=SaleStatus.OPENED
    )
    purchase, updated = create_or_update_one_cart_item(
        customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
    )
    assert updated and purchase is not None
    return invoice


class TransportTest(TestCase):
    def _invoice_with(self, total, transport, min_transport):
        invoice = build_orders_with_total(total)
        invoice.transport = transport
        invoice.min_transport = min_transport
        invoice.calculate_order_amount()
        return invoice

    def test_no_transport(self):
        invoice = self._invoice_with(D("10.00"), DECIMAL_ZERO, DECIMAL_ZERO)
        self.assertEqual(invoice.delta_transport.amount, DECIMAL_ZERO)

    def test_simple_transport_applied(self):
        invoice = self._invoice_with(D("10.00"), D("3.00"), DECIMAL_ZERO)
        self.assertEqual(invoice.delta_transport.amount, D("3.00"))

    def test_no_transport_on_empty_order(self):
        invoice = build_orders_with_total(D("10.00"))
        # Remove the order: the invoice exists but is empty
        from repanier.models.purchase import Purchase

        Purchase.objects.all().delete()
        invoice = CustomerInvoice.objects.get(id=invoice.id)
        invoice.transport = D("3.00")
        invoice.calculate_order_amount()
        self.assertEqual(invoice.delta_transport.amount, DECIMAL_ZERO)

    def test_transport_applied_on_small_order(self):
        invoice = self._invoice_with(D("0.01"), D("3.00"), DECIMAL_ZERO)
        self.assertEqual(invoice.delta_transport.amount, D("3.00"))

    def test_transport_capped_by_minimum_for_free(self):
        # total 10, min 12, transport 3: only 2 needed to reach the minimum
        invoice = self._invoice_with(D("10.00"), D("3.00"), D("12.00"))
        self.assertEqual(invoice.delta_transport.amount, D("2.00"))

    def test_transport_capped_by_transport_amount(self):
        # total 10, min 50, transport 3: stays at 3 (transport caps it)
        invoice = self._invoice_with(D("10.00"), D("3.00"), D("50.00"))
        self.assertEqual(invoice.delta_transport.amount, D("3.00"))


class RoundingTest(TestCase):
    @override_settings(REPANIER_SETTINGS_ROUND_INVOICES=True)
    def test_belgian_rounding_applied_to_grand_total(self):
        for total, expected_delta in [
            ("10.03", "0.02"),  # -> 10.05
            ("10.08", "0.02"),  # -> 10.10
            ("10.01", "-0.01"),  # -> 10.00
            ("10.05", "0.00"),  # already roundable
        ]:
            with self.subTest(total=total):
                invoice = build_orders_with_total(D(total))
                invoice.calculate_order_amount()
                self.assertEqual(invoice.delta_price_with_tax.amount, D(expected_delta))
                # The grand total is a multiple of 0.05
                grand = (
                    invoice.total_price_with_tax.amount
                    + invoice.delta_price_with_tax.amount
                )
                self.assertEqual(grand % D("0.05"), DECIMAL_ZERO)

    @override_settings(REPANIER_SETTINGS_ROUND_INVOICES=False)
    def test_no_rounding_when_disabled(self):
        invoice = build_orders_with_total(D("10.03"))
        invoice.calculate_order_amount()
        self.assertEqual(invoice.delta_price_with_tax.amount, DECIMAL_ZERO)


class GroupTransportTest(TestCase):
    """A member of a group is not charged transport on his own invoice."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="g1@example.com", email="g1@example.com", password="x"
        )
        self.customer = Customer.objects.create(
            user=self.user, short_basket_name="G1", may_order=True
        )
        self.producer = Producer.objects.create(short_profile_name="ProdG")
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        self.product = Product.objects.create(
            producer=self.producer,
            long_name_v2="ProduitG",
            order_unit="100",
            producer_unit_price=D("10.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        self.product.is_into_offer = True
        self.product.save()
        self.offer_item = self.product.get_or_create_offer_item(self.permanence)
        self.permanence.producers.add(self.producer)

    def test_no_transport_when_invoice_of_group_member(self):
        invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=self.permanence.id,
            customer_id=self.customer.id,
            status=SaleStatus.OPENED,
        )
        # Another customer is charged for this one (group member)
        other = User.objects.create_user(
            username="g2@example.com", email="g2@example.com", password="x"
        )
        Responsible = Customer
        responsible = Responsible.objects.create(
            user=other, short_basket_name="G2", may_order=True
        )
        invoice.customer_charged_id = responsible.id
        invoice.transport = D("5.00")  # even so
        invoice.save()
        purchase, updated = create_or_update_one_cart_item(
            customer=self.customer, offer_item_id=self.offer_item.id, q_order=D("1"), comment=""
        )
        self.assertTrue(updated)
        invoice = CustomerInvoice.objects.get(id=invoice.id)
        invoice.calculate_order_amount()
        # Not the charged customer: no transport line
        self.assertEqual(invoice.delta_transport.amount, DECIMAL_ZERO)
