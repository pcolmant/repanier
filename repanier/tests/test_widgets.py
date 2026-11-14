from django.test import TestCase
from django.utils import translation

from repanier.fields.RepanierMoneyField import FormRepanierMoneyField


class RepanierMoneyWidgetTest(TestCase):
    """The money fields of the admin carry a calculator: the icon tells
    the coordinator that the field computes, the tooltip tells him how."""

    def test_the_money_field_shows_the_calculator(self):
        widget = FormRepanierMoneyField().widget
        html = widget.render(name="unit_price", value="3,50")
        # The icon sits right before the input, attached to the field
        self.assertIn("repanier-money-input-calculator", html)
        self.assertIn("fa-solid fa-calculator", html)
        self.assertLess(
            html.index("repanier-money-input-calculator"),
            html.index("repanier-money-input-field"),
        )
        # The raw typing keeps the on the fly computation of the field
        self.assertIn('oninput="this.value=evaluateAsFloat(this.value)"', html)

    def test_the_tooltip_follows_the_admin_language(self):
        widget = FormRepanierMoneyField().widget
        with translation.override("fr"):
            html = widget.render(name="unit_price", value="3,50")
        self.assertIn("Calculatrice", html)
