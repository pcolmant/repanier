"""Tests of the order confirmation box (template based rendering).

CustomerInvoice.get_html_my_order_confirmation now renders
repanier/order_confirmation_box.html instead of building the markup in
Python. These tests lock the visible behavior of the box: which buttons
appear, when they are disabled, and the messages around them.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import translation

from repanier.const import DECIMAL_ZERO, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import create_or_update_one_cart_item

D = Decimal

# The box is only displayed starting from an order: the test suite
# otherwise runs fr translations, these tests assert on msgids.
MUST_CONFIRM = override_settings(REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=True)
NO_MUST_CONFIRM = override_settings(REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=False)


class ConfirmationBoxFixtureMixin:
    @classmethod
    def build_fixture(cls, with_purchase=True, order_confirm_send=False):
        """Open a permanence and return its actors, with our without purchase."""
        user = User.objects.create_user(
            username="confirm@example.com", email="confirm@example.com", password="x"
        )
        customer = Customer.objects.create(
            user=user, short_basket_name="Confirm", may_order=True
        )
        producer = Producer.objects.create(short_profile_name="Ferme")
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            highest_status=SaleStatus.OPENED,
        )
        permanence.producers.add(producer)
        customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=customer.id,
            status=SaleStatus.OPENED,
        )
        if with_purchase:
            product = Product.objects.create(
                producer=producer,
                long_name_v2="Pommes",
                order_unit="100",
                producer_unit_price=D("2.50"),
                vat_level=Vat.VAT_100,
                stock=D("99"),
            )
            product.is_into_offer = True
            product.save()
            offer_item = product.get_or_create_offer_item(permanence)
            purchase, _ = create_or_update_one_cart_item(
                customer=customer, offer_item_id=offer_item.id, q_order=D("3"), comment=""
            )
        if order_confirm_send:
            customer_invoice.refresh_from_db()
            customer_invoice.is_order_confirm_send = True
            customer_invoice.save()
        return customer_invoice, permanence

    def _confirmation_box(self, customer_invoice, permanence, is_basket):
        with translation.override("en"):
            fragment = customer_invoice.get_html_my_order_confirmation(
                permanence=permanence, is_basket=is_basket
            )["#span_btn_confirm_order"]
        self.maxDiff = None
        return fragment


@NO_MUST_CONFIRM
class ConfirmationBoxWithoutForcedConfirmationTest(
    ConfirmationBoxFixtureMixin, TestCase
):
    def test_order_page_without_confirmation_step_shows_nothing(self):
        customer_invoice, permanence = self.build_fixture()
        self.assertEqual(self._confirmation_box(customer_invoice, permanence, False), "")

    def test_basket_page_shows_a_confirm_button_and_the_history_link(self):
        customer_invoice, permanence = self.build_fixture()
        fragment = self._confirmation_box(customer_invoice, permanence, True)
        self.assertIn('id="btn_confirm_order"', fragment)
        self.assertIn("Receive an email containing this order summary.", fragment)
        self.assertIn('target="_blank"', fragment)
        self.assertIn("History", fragment)
        # No warnings and no go to basket link when the group does not
        # force the confirmation.
        self.assertNotIn("Unconfirmed orders will be canceled.", fragment)
        self.assertNotIn("confirmation step of my order", fragment)

    def test_basket_without_purchase_disables_the_confirm_button(self):
        customer_invoice, permanence = self.build_fixture(with_purchase=False)
        fragment = self._confirmation_box(customer_invoice, permanence, True)
        self.assertIn('class="btn btn-info disabled"', fragment)


@MUST_CONFIRM
class ConfirmationBoxWithForcedConfirmationTest(ConfirmationBoxFixtureMixin, TestCase):
    def test_order_page_shows_the_go_to_basket_link_and_the_warning(self):
        customer_invoice, permanence = self.build_fixture()
        fragment = self._confirmation_box(customer_invoice, permanence, False)
        # The order url is i18n prefixed: compute it in the same language
        # as the one used to render the fragment.
        with translation.override("en"):
            order_url = permanence.get_order_url()
        self.assertIn(
            'href="{url}?is_basket=yes" class="btn btn-info"'.format(url=order_url),
            fragment,
        )
        self.assertIn("➜ Go to the confirmation step of my order.", fragment)
        self.assertIn("Unconfirmed orders will be canceled.", fragment)
        # No confirm button on the order page itself
        self.assertNotIn('id="btn_confirm_order"', fragment)

    def test_basket_page_shows_the_confirm_button_and_the_warning(self):
        customer_invoice, permanence = self.build_fixture()
        fragment = self._confirmation_box(customer_invoice, permanence, True)
        self.assertIn('id="btn_confirm_order"', fragment)
        self.assertIn(
            "➜ Confirm this order and receive an email containing its summary.",
            fragment,
        )
        self.assertIn("Unconfirmed orders will be canceled.", fragment)

    def test_closed_permanence_locks_the_go_to_basket_link(self):
        customer_invoice, permanence = self.build_fixture()
        # The lock is read on the invoice status: an invoice no longer
        # open (the permanence is being closed) locks the confirm step.
        customer_invoice.status = SaleStatus.WAIT_FOR_CLOSED
        customer_invoice.save()
        fragment = self._confirmation_box(customer_invoice, permanence, False)
        self.assertIn('class="btn btn-info disabled"', fragment)

    def test_order_already_confirmed_shows_the_email_notice_only_once(self):
        customer_invoice, permanence = self.build_fixture(order_confirm_send=True)
        fragment = self._confirmation_box(customer_invoice, permanence, True)
        self.assertIn("An email containing this order summary has been sent to", fragment)
        self.assertIn("History", fragment)
        # Everything confirm-ish disappears
        self.assertNotIn('id="btn_confirm_order"', fragment)
        self.assertNotIn("Unconfirmed orders will be canceled.", fragment)
        self.assertNotIn("confirmation step of my order", fragment)
