"""Business tests of the Repanier-specific adjustment mechanisms.

- The membership fee ("cotisation"): a product the group forces onto
  members who place an order while no longer up to date with their
  membership. close_order() adds it automatically and extends the
  membership validity.
- Products ordered by the piece but billed by weight (PC_KG, e.g.
  sausages): the interface shows an ESTIMATED price (pieces x average
  weight x price per kg); at distribution time the treasurer replaces
  the invoiced quantity with the actual weight, and the customer is
  billed on the real weight.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import DECIMAL_ZERO, OrderUnit, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal


def build_journey_to_send(product_kwargs=None, customer_kwargs=None):
    """Open a permanence, order one product, close it. Returns the actors."""
    Configuration.objects.create(
        group_name="Test Group",
        name="100",
        bank_account="BE99 9999 9999 9999",
        currency="100",
    )
    user = User.objects.create_user(
        username="client@example.com", email="client@example.com", password="x"
    )
    customer = Customer.objects.create(
        user=user, short_basket_name="Client", may_order=True, **(customer_kwargs or {})
    )
    producer = Producer.objects.create(short_profile_name="Ferme")
    permanence = Permanence.objects.create(
        permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
    )
    permanence.producers.add(producer)
    defaults = {
        "long_name_v2": "Produit",
        "order_unit": "100",
        "producer_unit_price": D("2.50"),
        "vat_level": Vat.VAT_100,
        "stock": D("99"),
    }
    defaults.update(product_kwargs or {})
    product = Product.objects.create(producer=producer, **defaults)
    product.is_into_offer = True
    product.save()
    Task = task_order
    Task.open_order(permanence.id, send_mail=False)
    offer_item = Product.objects.get(id=product.id).offeritem_set.get(
        permanence=permanence
    )
    CustomerInvoice.get_or_create_invoice(
        permanence_id=permanence.id, customer_id=customer.id, status=SaleStatus.OPENED
    )
    return customer, producer, permanence, offer_item, product


class MembershipFeeForcedAtCloseTest(TestCase):
    def test_outdated_member_is_charged_the_fee_at_close(self):
        customer, producer, permanence, offer_item, product = build_journey_to_send(
            customer_kwargs={"membership_fee_valid_until": datetime.date(2010, 1, 1)}
        )
        # The group charges a 10.00 membership fee valid 12 months
        Configuration.objects.update(
            membership_fee=D("10.00"), membership_fee_duration=D("12")
        )
        # Re-trigger the post_save signal so the settings are refreshed
        configuration = Configuration.objects.first()
        configuration.save()

        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        self.assertTrue(updated)
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )

        # The membership fee product has been forced into the order
        fee_purchase = Purchase.objects.filter(
            permanence_id=permanence.id,
            customer_id=customer.id,
            offer_item__order_unit=OrderUnit.MEMBERSHIP_FEE,
        ).get()
        self.assertEqual(fee_purchase.quantity_ordered, D("1"))
        self.assertEqual(fee_purchase.selling_price.amount, D("10.00"))

        # And the membership is valid again, for 12 months
        customer.refresh_from_db()
        today = datetime.date.today()
        self.assertGreaterEqual(customer.membership_fee_valid_until, today)
        self.assertLessEqual(
            customer.membership_fee_valid_until,
            today + datetime.timedelta(days=367),
        )

    def test_up_to_date_member_is_not_charged(self):
        customer, producer, permanence, offer_item, product = build_journey_to_send(
            customer_kwargs={
                "membership_fee_valid_until": datetime.date.today()
                + datetime.timedelta(days=30)
            }
        )
        Configuration.objects.update(
            membership_fee=D("10.00"), membership_fee_duration=D("12")
        )
        configuration = Configuration.objects.first()
        configuration.save()

        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        self.assertFalse(
            Purchase.objects.filter(
                permanence_id=permanence.id,
                customer_id=customer.id,
                offer_item__order_unit=OrderUnit.MEMBERSHIP_FEE,
            ).exists()
        )

    def test_no_fee_when_group_does_not_charge_one(self):
        # Default configuration: no membership fee (0) -> nothing forced
        customer, producer, permanence, offer_item, product = build_journey_to_send(
            customer_kwargs={"membership_fee_valid_until": datetime.date(2010, 1, 1)}
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        self.assertFalse(
            Purchase.objects.filter(
                permanence_id=permanence.id,
                customer_id=customer.id,
                offer_item__order_unit=OrderUnit.MEMBERSHIP_FEE,
            ).exists()
        )


class PcKgWeightBillingTest(TestCase):
    """Ordered by the piece, billed by weight - sausages, cordons bleus..."""

    def _order_two_sausages(self):
        return build_journey_to_send(
            product_kwargs={
                "long_name_v2": "Saucisses",
                "order_unit": "140",  # PC_KG: per piece, billed per kg
                "producer_unit_price": D("15.00"),  # per kg
                "unit_deposit": DECIMAL_ZERO,
                "order_average_weight": D("0.500"),  # kg per piece
            }
        )

    def test_estimated_price_is_weight_based(self):
        customer, producer, permanence, offer_item, product = self._order_two_sausages()
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("2"), comment=""
        )
        self.assertTrue(updated)
        purchase.refresh_from_db()
        # Ordered 2 pieces; the pre_save signal bills an ESTIMATION:
        # 2 x 0.500 kg x 15.00/kg = 15.00
        self.assertEqual(purchase.quantity_ordered, D("2"))
        self.assertEqual(purchase.selling_price.amount, D("15.00"))

    def test_distribution_bills_the_actual_weight(self):
        customer, producer, permanence, offer_item, product = self._order_two_sausages()
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("2"), comment=""
        )
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        purchase.refresh_from_db()
        # At SEND, send_to_producer copies the estimated weight into
        # quantity_invoiced (ordered pieces x average weight)
        self.assertEqual(purchase.quantity_invoiced, D("1.000"))

        # At distribution, the scale says 1.05 kg: the treasurer adjusts
        # the invoiced quantity (exactly what the correction screens do)
        purchase.quantity_invoiced = D("1.050")
        purchase.save()
        purchase.refresh_from_db()
        # Billed on the ACTUAL weight: 1.05 kg x 15.00 = 15.75
        self.assertEqual(purchase.selling_price.amount, D("15.75"))

        permanence.calculate_order_amount()
        invoice = CustomerInvoice.objects.get(
            permanence_id=permanence.id, customer_id=customer.id
        )
        self.assertEqual(invoice.get_total_price_with_tax().amount, D("15.75"))
