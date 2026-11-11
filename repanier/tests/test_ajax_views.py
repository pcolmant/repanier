"""Tests of the AJAX endpoints the order screen relies on.

These run through Django's test client - i.e. the full middleware stack
(locale prefixes, ssl redirect) and the decorators (login_required,
require_GET, never_cache) included.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext

from repanier.const import SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase

D = Decimal

# Production settings force an https redirect and the locale middleware
# prepends the language to every not-yet-prefixed URL: the HTTP test
# client needs the ssl redirect off and follows the locale redirect.


class AjaxFixtureMixin:
    @classmethod
    def build_fixture(cls, username="client@example.com"):
        cls.user = User.objects.create_user(
            username=username, email=username, password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="ClientTest", may_order=True
        )
        cls.producer = Producer.objects.create(short_profile_name="Ferme Ajax")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="Poires",
            order_unit="100",  # PC
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        cls.offer_item = cls.product.get_or_create_offer_item(cls.permanence)
        cls.customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CustomerNameAjaxTest(TestCase):
    def test_anonymous_gets_anonymous_label(self):
        response = self.client.get(reverse("repanier:order_name"), follow=True)
        self.assertEqual(response.status_code, 200)
        # Same translation context as the view (fr with these test settings)
        self.assertEqual(response.content.decode("utf-8"), str(gettext("Anonymous")))

    def test_logged_user_gets_username(self):
        user = User.objects.create_user(
            username="nomade@example.com", email="nomade@example.com", password="x"
        )
        Customer.objects.create(user=user, short_basket_name="Nomade", may_order=True)
        # RepanierAuthBackend authenticates by email (or last name)
        self.client.login(username="nomade@example.com", password="x")
        response = self.client.get(reverse("repanier:order_name"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "nomade@example.com")


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class MyBalanceAjaxTest(TestCase):
    def test_customer_without_history_gets_history_label(self):
        user = User.objects.create_user(
            username="balance@example.com", email="balance@example.com", password="x"
        )
        Customer.objects.create(user=user, short_basket_name="Balance", may_order=True)
        self.client.login(username="balance@example.com", password="x")
        response = self.client.get(reverse("repanier:my_balance"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), str(gettext("History")))


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class OrderAjaxTest(AjaxFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        # go_repanier (rendered when following redirects) requires the
        # configuration record a real site always has
        from repanier.models.configuration import Configuration

        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        cls.build_fixture()
        # run the real opening flow: it creates the orderable offer items
        # and the producer invoices, exactly as on a production site
        from repanier.task import task_order

        cls.permanence.set_status(
            old_status=SaleStatus.OPENED, new_status=SaleStatus.PLANNED
        )
        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.offer_item = cls.product.offeritem_set.get(permanence=cls.permanence)

    def _order(self, value):
        self.client.login(username="client@example.com", password="x")
        return self.client.get(
            reverse("repanier:order_ajax"),
            {"offer_item": self.offer_item.id, "value": value},
            follow=True,
        )

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            reverse("repanier:order_ajax"),
            {"offer_item": self.offer_item.id, "value": 2},
        )
        self.assertEqual(response.status_code, 302)
        redirect_target = response["Location"]
        self.assertIn("/repanier/go_repanier/", redirect_target)
        # Nothing was ordered
        self.assertEqual(Purchase.objects.count(), 0)

    def test_superuser_without_customer_gets_404(self):
        # The only way to reach the 404 branch through the real stack:
        # a user authenticated without any Customer record - only a
        # superuser can be (RepanierAuthBackend refuses everyone else)
        User.objects.create_user(
            username="admin@example.com", password="x", is_superuser=True
        )
        self.client.force_login(
            User.objects.get(username="admin@example.com"),
            backend="repanier.auth_backend.RepanierAuthBackend",
        )
        response = self.client.get(
            reverse("repanier:order_ajax"),
            {"offer_item": self.offer_item.id, "value": 2},
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Purchase.objects.count(), 0)

    def test_order_two_pieces_via_ajax(self):
        response = self._order(2)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # The response updates the select box of the ordered item
        self.assertIn("#offer_item{}".format(self.offer_item.id), data)

        # value=2 with min=step=1 means "quantity = 2" (see
        # create_or_update_one_cart_item)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.quantity_ordered, D("2"))
        self.assertEqual(purchase.selling_price.amount, D("5.40"))

        # The customer invoice reflects the new amount
        invoice = CustomerInvoice.objects.get(id=self.customer_invoice.id)
        self.assertEqual(invoice.get_total_price_with_tax().amount, D("5.40"))

    def test_cannot_order_when_permanence_is_closed(self):
        # Move the permanence out of the orderable statuses
        self.permanence.set_status(
            old_status=SaleStatus.OPENED, new_status=SaleStatus.CLOSED
        )
        response = self._order(2)
        self.assertEqual(response.status_code, 200)
        # Nothing was ordered: the endpoint answers with an empty update
        self.assertEqual(Purchase.objects.count(), 0)
        self.assertEqual(response.json(), {})
