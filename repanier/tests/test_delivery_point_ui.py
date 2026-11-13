"""Tests of the Bootstrap dropdown that replaced the delivery point select.

The order screen offers the delivery points through the same kind of
Bootstrap 5 dropdown as the quantity ones: the widget comes from
bootstrap5_delivery_dropdown.html (rendered by
CustomerInvoice.get_html_select_delivery_point), the menu is loaded by
HTMX from delivery_select_ajax and selecting an item calls delivery_ajax
through repanier/static/repanier/js/delivery_dropdown.js.
"""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.lut import LUT_DeliveryPoint
from repanier.models.permanence import Permanence


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=False,
)
class DeliveryPointDropdownTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from repanier.models.configuration import Configuration

        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        cls.user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="ClientTest", may_order=True
        )
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            with_delivery_point=True,
        )
        cls.market_point = LUT_DeliveryPoint.objects.create(
            short_name_v2="Marche"
        )
        cls.depot_point = LUT_DeliveryPoint.objects.create(short_name_v2="Depot")
        for point in (cls.market_point, cls.depot_point):
            DeliveryBoard.objects.create(
                permanence=cls.permanence,
                delivery_point=point,
                status=SaleStatus.OPENED,
            )
        CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )

    def _login(self):
        self.client.login(username="client@example.com", password="x")

    def test_order_init_renders_a_bootstrap_dropdown(self):
        self._login()
        response = self.client.get(
            reverse("repanier:order_init_ajax"),
            {"pe": self.permanence.id, "ba": "yes"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        fragment = response.json()["#span_btn_confirm_order"]
        # The widget is the Bootstrap dropdown known from the quantity
        # selection, not a native select anymore.
        self.assertIn('id="deliveryBtn"', fragment)
        self.assertIn('hx-target="#deliveryDropdownMenu"', fragment)
        self.assertIn("data-delivery-url", fragment)
        self.assertIn(reverse("repanier:delivery_ajax"), fragment)
        self.assertIn(reverse("repanier:delivery_select_ajax"), fragment)
        self.assertNotIn("<select", fragment)

    def test_order_init_carries_permanence_and_basket_flag(self):
        self._login()
        response = self.client.get(
            reverse("repanier:order_init_ajax"),
            {"pe": self.permanence.id, "ba": "yes"},
            follow=True,
        )
        fragment = response.json()["#span_btn_confirm_order"]
        self.assertIn('data-permanence="{}"'.format(self.permanence.id), fragment)
        # The JS builds the delivery_ajax URL from these data attributes
        self.assertIn('data-is-basket="yes"', fragment)

    def test_the_menu_is_loaded_by_htmx(self):
        self._login()
        response = self.client.get(
            reverse("repanier:delivery_select_ajax"),
            {"permanence": self.permanence.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        menu = response.content.decode("utf-8")
        self.assertIn('class="dropdown-item disabled"', menu)
        self.assertIn("Veuillez sélectionner un point de livraison", menu)
        for board in DeliveryBoard.objects.filter(permanence=self.permanence):
            self.assertIn(
                'selectDelivery({}, this)'.format(board.id), menu
            )

    def test_selecting_a_delivery_point_updates_the_invoice(self):
        self._login()
        board = DeliveryBoard.objects.get(
            permanence=self.permanence, delivery_point=self.market_point
        )
        response = self.client.get(
            reverse("repanier:delivery_ajax"),
            {
                "delivery": board.id,
                "permanence": self.permanence.id,
                "is_basket": "yes",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        invoice = CustomerInvoice.objects.get(
            permanence=self.permanence, customer=self.customer
        )
        self.assertEqual(invoice.delivery_id, board.id)
        # The confirmation box is refreshed with the updated dropdown
        fragment = response.json()["#span_btn_confirm_order"]
        self.assertIn('id="deliveryBtn"', fragment)
        self.assertIn("Marche", fragment)

    def test_without_any_open_delivery_point_the_dropdown_is_disabled(self):
        DeliveryBoard.objects.filter(permanence=self.permanence).delete()
        self._login()
        response = self.client.get(
            reverse("repanier:order_init_ajax"),
            {"pe": self.permanence.id, "ba": "yes"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        fragment = response.json()["#span_btn_confirm_order"]
        self.assertIn("disabled", fragment)
        self.assertIn("aucun point de livraison", fragment)
        # The customer can not order: the invoice is closed
        invoice = CustomerInvoice.objects.get(
            permanence=self.permanence, customer=self.customer
        )
        self.assertEqual(invoice.status, SaleStatus.CLOSED)

    def test_the_shared_script_is_loaded_from_static_files(self):
        from django.contrib.staticfiles import finders

        js_path = finders.find("repanier/js/delivery_dropdown.js")
        css_path = finders.find("repanier/css/delivery_dropdown.css")
        self.assertIsNotNone(js_path)
        self.assertIsNotNone(css_path)
        with open(js_path, encoding="utf-8") as f:
            js = f.read()
        # The basket flag propagation must survive in the shared script
        self.assertIn("function selectDelivery", js)
        self.assertIn("dataset.isBasket", js)
        self.assertIn("is_basket=yes", js)
