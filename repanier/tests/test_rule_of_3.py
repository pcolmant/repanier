"""Tests of the rule of 3, a signature of Repanier.

The rule of 3 spreads what the producer actually billed to the group
over the customers' purchases, at pro rata, so that the sum invoiced to
the customers matches the producer bill to the cent. The last purchase
absorbs the rounding residue.

repanier.tools.distribute_rule_of_3 holds the algorithm; the
OfferItemSend admin screen (distribution: correct a product for the
whole permanence) delegates to it.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from repanier.const import DECIMAL_ZERO, OrderUnit, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item, distribute_rule_of_3

D = Decimal


class DistributeRuleOf3PureTest(SimpleTestCase):
    """Unit tests of the pure distribution algorithm, no database."""

    # The canonical example: 10 kg ordered, the producer bills 10 kg
    # but delivers 10.5 kg. Purchases of 4 kg, 3 kg and 3.5 kg at
    # 3.00 €/kg; the target is the producer bill of 30.00 €.
    QUANTITIES = [D("4"), D("3"), D("3.5")]
    UNIT_PRICES = [D("3.00")] * 3
    LINE_TOTALS = [D("12.00"), D("9.00"), D("10.50")]

    def test_distributes_at_pro_rata_last_purchase_absorbs_the_residue(self):
        new_quantities = distribute_rule_of_3(
            quantities=self.QUANTITIES,
            line_totals=self.LINE_TOTALS,
            unit_prices=self.UNIT_PRICES,
            target=D("30.00"),
        )
        self.assertEqual(new_quantities, [D("3.8095"), D("2.8571"), D("3.3333")])
        # No cent is lost: the recomputed line totals sum to the target
        line_totals = [
            (q * p).quantize(D("0.01"))
            for q, p in zip(new_quantities, self.UNIT_PRICES)
        ]
        self.assertEqual(sum(line_totals), D("30.00"))

    def test_target_already_reached_is_a_noop(self):
        self.assertIsNone(
            distribute_rule_of_3(
                quantities=self.QUANTITIES,
                line_totals=self.LINE_TOTALS,
                unit_prices=self.UNIT_PRICES,
                target=D("31.50"),
            )
        )

    def test_no_target_is_a_noop(self):
        self.assertIsNone(
            distribute_rule_of_3(
                quantities=self.QUANTITIES,
                line_totals=self.LINE_TOTALS,
                unit_prices=self.UNIT_PRICES,
                target=None,
            )
        )

    def test_empty_set_is_a_noop(self):
        self.assertIsNone(
            distribute_rule_of_3(
                quantities=[], line_totals=[], unit_prices=[], target=D("10.00")
            )
        )

    def test_zero_source_with_a_target_is_a_noop(self):
        # Purchases with no current amount (free products) but a
        # non zero target: dividing by zero must be avoided.
        self.assertIsNone(
            distribute_rule_of_3(
                quantities=[D("1"), D("2")],
                line_totals=[DECIMAL_ZERO, DECIMAL_ZERO],
                unit_prices=[DECIMAL_ZERO, DECIMAL_ZERO],
                target=D("10.00"),
            )
        )

    def test_zero_target_zeroes_every_quantity(self):
        new_quantities = distribute_rule_of_3(
            quantities=self.QUANTITIES,
            line_totals=self.LINE_TOTALS,
            unit_prices=self.UNIT_PRICES,
            target=DECIMAL_ZERO,
        )
        self.assertEqual(new_quantities, [DECIMAL_ZERO] * 3)

    def test_single_purchase_absorbs_everything(self):
        new_quantities = distribute_rule_of_3(
            quantities=[D("5")],
            line_totals=[D("10.00")],
            unit_prices=[D("2.00")],
            target=D("8.00"),
        )
        self.assertEqual(new_quantities, [D("4")])
        self.assertEqual((new_quantities[0] * D("2.00")).quantize(D("0.01")), D("8.00"))

    def test_zero_unit_price_on_last_line_gives_a_zero_quantity(self):
        new_quantities = distribute_rule_of_3(
            quantities=[D("1"), D("2")],
            line_totals=[D("3.00"), DECIMAL_ZERO],
            unit_prices=[D("3.00"), DECIMAL_ZERO],
            target=D("4.50"),
        )
        self.assertEqual(new_quantities, [D("1.5"), DECIMAL_ZERO])

    def test_ratio_rounding_is_applied_when_requested(self):
        # The per customer screen passes RoundUpTo.FOUR_DECIMALS
        new_quantities = distribute_rule_of_3(
            quantities=self.QUANTITIES,
            line_totals=self.LINE_TOTALS,
            unit_prices=self.UNIT_PRICES,
            target=D("30.00"),
            ratio_rounding=D("0.0001"),
        )
        # ratio = 30 / 31.50 rounded to 0.9524; the first two quantities
        # follow the rounded ratio, the last purchase absorbs the
        # (bigger) residue and the total still reaches the target.
        self.assertEqual(new_quantities, [D("3.8096"), D("2.8572"), D("3.3333")])

    def test_over_delivery_spreads_the_surplus(self):
        # The producer delivers MORE than ordered and bills all of it:
        # the customers receive (and pay) more than ordered.
        new_quantities = distribute_rule_of_3(
            quantities=self.QUANTITIES,
            line_totals=self.LINE_TOTALS,
            unit_prices=self.UNIT_PRICES,
            target=D("33.00"),
        )
        self.assertEqual(new_quantities, [D("4.1905"), D("3.1429"), D("3.6667")])
        line_totals = [
            (q * p).quantize(D("0.01"))
            for q, p in zip(new_quantities, self.UNIT_PRICES)
        ]
        self.assertEqual(sum(line_totals), D("33.00"))


class RuleOf3ThroughPurchasesTest(TestCase):
    """End to end: the treasurer applies the rule of 3 after the
    distribution, as the OfferItemSend admin screen does."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.customers = []
        for index, name in enumerate(["Anne", "Bernard", "Chantal"]):
            user = User.objects.create_user(
                username=f"{name.lower()}@example.com",
                email=f"{name.lower()}@example.com",
                password="x",
            )
            cls.customers.append(
                Customer.objects.create(user=user, short_basket_name=name, may_order=True)
            )
        cls.producer = Producer.objects.create(short_profile_name="Ferme")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.permanence.producers.add(cls.producer)
        product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Pommes de terre",
            order_unit=OrderUnit.KG,
            producer_unit_price=D("3.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        product.is_into_offer = True
        product.save()
        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.offer_item = Product.objects.get(id=product.id).offeritem_set.get(
            permanence=cls.permanence
        )
        for customer, quantity in zip(cls.customers, [D("4"), D("3"), D("3.5")]):
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
            assert updated

    def test_producer_bill_spread_over_the_customers_to_the_cent(self):
        self.permanence = Permanence.objects.get(id=self.permanence.id)
        task_order.close_order(
            self.permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        # After close_order, purchases at SEND status are reloaded from
        # the database: quantity_invoiced == quantity_ordered (KG).
        purchases = list(
            Purchase.objects.filter(offer_item_id=self.offer_item.id).order_by(
                "customer__short_basket_name"
            )
        )
        self.assertEqual(len(purchases), 3)
        self.assertEqual(
            [p.quantity_invoiced for p in purchases], [D("4"), D("3"), D("3.5")]
        )
        self.assertEqual(
            sum(p.purchase_price.amount for p in purchases), D("31.50")
        )

        # The producer delivered 10.5 kg but bills 10 kg: 30.00 €.
        offer_item = OfferItem.objects.get(id=self.offer_item.id)
        new_quantities = distribute_rule_of_3(
            quantities=[p.quantity_invoiced for p in purchases],
            line_totals=[p.purchase_price.amount for p in purchases],
            unit_prices=[
                offer_item.producer_unit_price.amount for _ in purchases
            ],
            target=D("30.00"),
        )
        self.assertIsNotNone(new_quantities)
        for purchase, quantity_invoiced in zip(purchases, new_quantities):
            purchase.quantity_invoiced = quantity_invoiced
            purchase.save()

        # The customers together are invoiced the producer bill exactly
        self.assertEqual(
            sum(p.purchase_price.amount for p in Purchase.objects.filter(
                offer_item_id=self.offer_item.id
            )),
            D("30.00"),
        )
        # Each customer paid pro rata of what (s)he received
        invoiced = [
            p.purchase_price.amount
            for p in Purchase.objects.filter(offer_item_id=self.offer_item.id).order_by(
                "customer__short_basket_name"
            )
        ]
        self.assertEqual(invoiced, [D("11.43"), D("8.57"), D("10.00")])
