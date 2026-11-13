"""The confirm screens of the admin actions (opening and closing the
orders, generating a permanence) are dressed with the layout of the
Django admin: the native submit-row, never a custom button style.
These screens carry big email previews below the buttons, which makes
them fragile to rework: their rendering is pinned here.
"""
import datetime
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repanier.const import OrderUnit, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class ConfirmScreenLayoutTest(TestCase):
    def build_and_login(self):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        self.user = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        self.client.force_login(user=self.user)
        self.producer = Producer.objects.create(short_profile_name="Ferme")
        self.product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Produit",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        self.product.is_into_offer = True
        self.product.save()
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.PLANNED,
            highest_status=SaleStatus.PLANNED,
        )
        self.permanence.producers.add(self.producer)

    def assert_admin_layout(self, name):
        url = reverse(name, args=[self.permanence.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('<div class="submit-row">', html)
        self.assertIn('class="default"', html)
        # The custom button style is gone, even from the screens with
        # email previews
        self.assertNotIn("repanier-submit-info", html)

    def test_the_open_order_confirm_screen_uses_the_admin_layout(self):
        self.build_and_login()
        self.assert_admin_layout("admin:permanence-open-order")

    def test_the_generate_permanence_confirm_screen_uses_the_admin_layout(self):
        self.build_and_login()
        self.assert_admin_layout("admin:generate-permanence")

    def test_the_close_order_confirm_screen_uses_the_admin_layout(self):
        self.build_and_login()
        task_order.open_order(self.permanence.id, send_mail=False)
        self.permanence.refresh_from_db()
        self.assert_admin_layout("admin:permanence-close-order")
