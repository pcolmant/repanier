"""A book born after the invoicing of its round must not stay unstamped.

The order page creates the `CustomerInvoice` lazily: a member who
re-opens the order page of an already invoiced round gets an empty
book, born after the stamping. Ten years of such visits left books
flagged by the closure audit (stamped with anchor None): the stamp
must be carried at birth instead.
"""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.tests.test_accounting_chain import AccountingJourneyMixin


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=False,
)
class LateBookStampTest(AccountingJourneyMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def test_a_late_visit_on_an_invoiced_round_stamps_the_book(self):
        user = User.objects.create_user(
            username="late@example.com", email="late@example.com", password="x"
        )
        Customer.objects.create(
            user=user, short_basket_name="Late", may_order=True
        )
        self.client.login(username="late@example.com", password="x")
        response = self.client.get(
            reverse("repanier:order_init_ajax"),
            {"pe": self.permanence.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        late_book = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer__user=user
        )
        self.assertEqual(
            late_book.invoice_sort_order, self.permanence.invoice_sort_order
        )

    def test_a_visit_while_the_round_sells_does_not_stamp(self):
        opened = Permanence.objects.create(
            permanence_date=datetime.date.today() + datetime.timedelta(days=7),
            status=SaleStatus.OPENED,
        )
        user = User.objects.create_user(
            username="early@example.com", email="early@example.com", password="x"
        )
        Customer.objects.create(
            user=user, short_basket_name="Early", may_order=True
        )
        self.client.login(username="early@example.com", password="x")
        response = self.client.get(
            reverse("repanier:order_init_ajax"),
            {"pe": opened.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        early_book = CustomerInvoice.objects.get(
            permanence_id=opened.id, customer__user=user
        )
        self.assertIsNone(early_book.invoice_sort_order)
