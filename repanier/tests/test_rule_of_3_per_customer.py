"""Tests of the rule of 3 on the per customer screen.

The per customer admin screen (distribution: correct one customer across
a producer purchases) now delegates to the pure
repanier.tools.distribute_rule_of_3, with the deposit accounted in the
unit price of the distribution: the invoiced line amounts are
(unit price + deposit) x quantity, so the residue conversion must use the
same unit price as the accumulation.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from repanier.admin.rule_of_3_per_customer import get_invoiced_unit_price
from repanier.const import DECIMAL_ZERO, RoundUpTo, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item, distribute_rule_of_3

D = Decimal


class DistributeRuleOf3DepositTest(SimpleTestCase):
    """The deposit belongs to the invoiced amount: the same unit price
    feeds the accumulation and the residue conversion."""

    # Two invoiced lines of 3.00 (2.00 price + 1.00 deposit) per unit.
    QUANTITIES = [D("1"), D("1")]
    UNIT_PRICES = [D("3.00")] * 2
    LINE_TOTALS = [D("3.00")] * 2

    def test_the_distribution_reaches_the_target_with_deposits(self):
        new_quantities = distribute_rule_of_3(
            quantities=self.QUANTITIES,
            line_totals=self.LINE_TOTALS,
            unit_prices=self.UNIT_PRICES,
            target=D("9.00"),
        )
        self.assertEqual(new_quantities, [D("1.5"), D("1.5")])
        line_totals = [
            (q * p).quantize(D("0.01"))
            for q, p in zip(new_quantities, self.UNIT_PRICES)
        ]
        # Without the deposit in the unit price, the old embedded
        # algorithm produced 11.25 here (residue divided by 2.00).
        self.assertEqual(sum(line_totals), D("9.00"))


class RuleOf3PerCustomerEndToEndTest(TestCase):
    """Open a permanence, order deposit bearing products, close it, then
    apply the rule of 3 exactly as the per customer admin screen does."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        user = User.objects.create_user(
            username="deposit@example.com", email="deposit@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=user, short_basket_name="Deposit", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.permanence.producers.add(cls.producer)
        cls.products = []
        for name, price, deposit in [
            ("Bouteilles", D("2.00"), D("1.00")),
            ("Bocaux", D("4.00"), D("0.50")),
        ]:
            product = Product.objects.create(
                producer=cls.producer,
                long_name_v2=name,
                order_unit="100",
                producer_unit_price=price,
                unit_deposit=deposit,
                vat_level=Vat.VAT_100,
                stock=D("99"),
            )
            product.is_into_offer = True
            product.save()
            cls.products.append(product)
        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.offer_items = [
            Product.objects.get(id=product.id).offeritem_set.get(
                permanence=cls.permanence
            )
            for product in cls.products
        ]
        CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )
        for offer_item, quantity in zip(cls.offer_items, [D("3"), D("2")]):
            purchase, updated = create_or_update_one_cart_item(
                customer=cls.customer,
                offer_item_id=offer_item.id,
                q_order=quantity,
                comment="",
            )
            assert updated

    def test_deposit_bearing_lines_reach_the_producer_bill_to_the_cent(self):
        task_order.close_order(
            self.permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        purchases = list(
            Purchase.objects.filter(customer_id=self.customer.id).order_by(
                "offer_item__long_name_v2"
            )
        )
        self.assertEqual(len(purchases), 2)
        # 2 jars: (4.00 + 0.50) x 2 = 9.00
        # 3 bottles: (2.00 + 1.00) x 3 = 9.00
        # (ordered by long_name_v2: Bocaux before Bouteilles)
        self.assertEqual(
            [p.purchase_price.amount for p in purchases], [D("9.00"), D("9.00")]
        )
        # The treasurer enters the producer bill of 13.00
        target = D("13.00")
        quantities = [p.quantity_invoiced for p in purchases]
        line_totals = [p.purchase_price.amount for p in purchases]
        unit_prices = [get_invoiced_unit_price(p, False) for p in purchases]
        self.assertEqual(unit_prices, [D("4.50"), D("3.00")])
        new_quantities = distribute_rule_of_3(
            quantities=quantities,
            line_totals=line_totals,
            unit_prices=unit_prices,
            target=target,
            ratio_rounding=RoundUpTo.FOUR_DECIMALS,
        )
        self.assertIsNotNone(new_quantities)
        for purchase, quantity_invoiced in zip(purchases, new_quantities):
            purchase.quantity_invoiced = quantity_invoiced
            purchase.save()
        invoiced = [
            p.purchase_price.amount
            for p in Purchase.objects.filter(customer_id=self.customer.id).order_by(
                "offer_item__long_name_v2"
            )
        ]
        # The deposit is included in every step of the distribution, so
        # the customer is charged the producer bill exactly.
        self.assertEqual(sum(invoiced), target)
        # Bocaux: 6.50 (pro rata line), Bouteilles: 6.50 (residue line)
        self.assertEqual(invoiced, [D("6.50"), D("6.50")])
