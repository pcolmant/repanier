"""Unit tests for RepanierMoney, the money value type of the whole core."""
from decimal import Decimal

from django.test import TestCase

from repanier.fields.RepanierMoneyField import (
    RepanierMoney,
    FormRepanierMoneyField,
)


class RepanierMoneyTest(TestCase):
    def test_init_from_types(self):
        self.assertEqual(RepanierMoney(Decimal("2.50")).amount, Decimal("2.50"))
        self.assertEqual(RepanierMoney(2.5).amount, Decimal("2.5"))
        self.assertEqual(RepanierMoney("3.15").amount, Decimal("3.15"))
        self.assertEqual(RepanierMoney().amount, Decimal("0"))

    def test_arithmetic(self):
        total = RepanierMoney(Decimal("1.10")) + RepanierMoney(Decimal("2.20"))
        self.assertEqual(total.amount, Decimal("3.30"))
        diff = RepanierMoney(Decimal("5.00")) - RepanierMoney(Decimal("2.20"))
        self.assertEqual(diff.amount, Decimal("2.80"))

    def test_comparison(self):
        self.assertTrue(RepanierMoney(Decimal("2")) == RepanierMoney(Decimal("2.00")))
        self.assertTrue(RepanierMoney(Decimal("1.99")) < RepanierMoney(Decimal("2")))
        self.assertTrue(RepanierMoney(Decimal("0")) == Decimal("0"))

    def test_rounding_half_up(self):
        money = RepanierMoney(Decimal("2.345"))
        self.assertEqual(money.amount.quantize(Decimal("0.01")), Decimal("2.35"))


class FormRepanierMoneyFieldTest(TestCase):
    def test_to_python(self):
        field = FormRepanierMoneyField()
        value = field.to_python("2,75")
        self.assertEqual(value.amount, Decimal("2.75"))

    def test_prepare_value(self):
        field = FormRepanierMoneyField()
        self.assertEqual(field.prepare_value(RepanierMoney(Decimal("2.75"))), Decimal("2.75"))
