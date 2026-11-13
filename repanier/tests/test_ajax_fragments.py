"""Tests of the basket button fragment.

It renders from a template (repanier/my_basket.html) instead of building
markup strings in Python.
"""
from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from repanier.tools import my_basket

D = Decimal


class Amount:
    """Stand-in for a RepanierMoney with the parts my_basket reads."""

    def __init__(self, amount):
        self.amount = amount

    def __str__(self):
        return str(self.amount)


@override_settings(REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=False)
class MyBasketTemplateTest(SimpleTestCase):
    def test_positive_amount_shows_a_check_icon(self):
        json_dict = my_basket(True, Amount(D("10.00")))
        self.assertIn('class="bi bi-cart"', json_dict["#my_basket"])
        self.assertIn('class="bi bi-check-lg"', json_dict["#my_basket"])
        # The same fragment feeds both injection points
        self.assertEqual(json_dict["#my_basket"], json_dict["#prepared_amount_visible_xs"])
        self.assertNotIn("bi-exclamation-circle", json_dict["#my_basket"])

    def test_zero_amount_shows_no_icon_at_all(self):
        json_dict = my_basket(True, Amount(D("0")))
        self.assertIn('class="bi bi-cart"', json_dict["#my_basket"])
        self.assertNotIn("bi-check-lg", json_dict["#my_basket"])
        self.assertNotIn("bi-exclamation-circle", json_dict["#my_basket"])

    @override_settings(REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=True)
    def test_pending_confirmation_shows_the_confirm_icons(self):
        json_dict = my_basket(False, Amount(D("10.00")))
        self.assertIn('class="bi bi-exclamation-circle"', json_dict["#my_basket"])
        self.assertIn('class="bi bi-floppy"', json_dict["#my_basket"])
        self.assertNotIn("bi-check-lg", json_dict["#my_basket"])

    @override_settings(REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=True)
    def test_already_confirmed_shows_the_check_icon(self):
        json_dict = my_basket(True, Amount(D("10.00")))
        self.assertIn('class="bi bi-check-lg"', json_dict["#my_basket"])
        self.assertNotIn("bi-exclamation-circle", json_dict["#my_basket"])
