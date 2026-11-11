"""Tests of the notification flash card and the basket button fragments.

Both now render from templates (repanier/notification_card.html and
repanier/my_basket.html) instead of building markup strings in Python.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings

from repanier.models.notification import Notification
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


class NotificationFlashCardTest(TestCase):
    def test_empty_notification_renders_nothing(self):
        self.assertEqual(
            Notification.objects.create().get_html_notification_card_display(), ""
        )

    def test_notification_renders_from_the_template_escaped(self):
        notification = Notification.objects.create(
            notification_v2="Welcome aboard!"
        )
        fragment = notification.get_html_notification_card_display()
        self.assertIn('class="card card-flash"', fragment)
        self.assertIn("Welcome aboard!", fragment)
        self.assertIn('class="card-close"', fragment)
        self.assertIn("flash=0", fragment)

    def test_notification_content_is_not_injected_as_html(self):
        # The rich text content is escaped: an html payload in the
        # notification must not produce a live tag.
        notification = Notification.objects.create(
            notification_v2="<img src=x onerror=alert(1)>"
        )
        fragment = notification.get_html_notification_card_display()
        self.assertIn("&lt;img", fragment)
        self.assertNotIn("<img src=x", fragment)
