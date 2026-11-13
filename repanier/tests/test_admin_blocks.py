"""Tests of the permanence admin blocks (producers, customers, board, status).

The four display fragments now render from templates
(repanier/permanence_*_block.html) instead of building markup strings in
Python: the tests pin the structure of each block and its empty variant.
"""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import gettext

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.lut import LUT_PermanenceRole
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer


class ProducersBlockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.producer_a = Producer.objects.create(short_profile_name="Ferme A")
        cls.producer_b = Producer.objects.create(short_profile_name="Ferme B")
        cls.permanence.producers.add(cls.producer_a, cls.producer_b)

    def test_planned_shows_links_with_or_without_the_export_button(self):
        without_download = self.permanence.get_producers(with_download=False)
        self.assertIn(
            'id="id_show_producers_{}"'.format(self.permanence.id), without_download
        )
        # The producer names are rendered with non breaking spaces
        self.assertIn("Ferme&nbsp;A", without_download)
        self.assertIn("Ferme&nbsp;B", without_download)
        # Each producer links to the product changelist filtered for him
        self.assertIn(
            "{}?producer={}".format(
                reverse("admin:repanier_product_changelist"),
                self.producer_b.id,
            ),
            without_download,
        )
        self.assertNotIn("fas fa-download", without_download)

        with_download = self.permanence.get_producers(with_download=True)
        self.assertIn(
            reverse(
                "admin:permanence-export-offer", args=[self.permanence.id]
            ),
            with_download,
        )
        self.assertIn("fas fa-download", with_download)

    def test_no_producer_shows_no_offer(self):
        empty = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        html = empty.get_producers(with_download=True)
        self.assertIn(str(gettext("No offer")), html)
        self.assertNotIn("repanier-button-row", html)


class CustomersBlockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        cls.user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="ClientTest", may_order=True
        )
        CustomerInvoice.get_or_create_invoice(
            permanence_id=cls.permanence.id,
            customer_id=cls.customer.id,
            status=SaleStatus.OPENED,
        )

    def test_opened_shows_the_eye_toggles_and_the_links(self):
        html = self.permanence.get_customers(with_download=True)
        # The counter starts hidden behind the eye toggle
        self.assertIn(
            'id="id_hide_customers_{}"'.format(self.permanence.id), html
        )
        self.assertIn(
            'id="id_show_customers_{}"'.format(self.permanence.id), html
        )
        self.assertIn("far fa-eye", html)
        self.assertIn("far fa-eye-slash", html)
        self.assertIn("> 1</a>", html)
        # Every customer links to the purchase changelist filtered for him
        self.assertIn(
            "{}?permanence={}&customer={}".format(
                reverse("admin:repanier_purchase_changelist"),
                self.permanence.id,
                self.customer.id,
            ),
            html,
        )
        # Opened permanences allow adding or exporting purchases
        self.assertIn(reverse("admin:repanier_purchase_add"), html)
        self.assertIn(
            reverse(
                "admin:permanence-export-customer-opened-order",
                args=[self.permanence.id],
            ),
            html,
        )
        # And the customers list itself
        self.assertIn("ClientTest", html)

    def test_without_download_the_export_button_is_removed(self):
        html = self.permanence.get_customers(with_download=False)
        self.assertNotIn("fas fa-download", html)

    def test_no_customer_shows_no_purchase(self):
        empty = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        html = empty.get_customers(with_download=True)
        self.assertIn(str(gettext("No purchase")), html)
        self.assertNotIn("repanier-button-row", html)


class BoardBlockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        cls.user = User.objects.create_user(
            username="board@example.com", email="board@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="BoardMember", may_order=True
        )

    def add_role(self, with_customer):
        role = LUT_PermanenceRole.objects.create(short_name_v2="Responsable")
        return PermanenceBoard.objects.create(
            permanence=self.permanence,
            permanence_role=role,
            customer=self.customer if with_customer else None,
        )

    def test_board_shows_the_roles_and_the_counters(self):
        self.add_role(with_customer=True)
        self.add_role(with_customer=False)
        html = self.permanence.get_board
        self.assertIn('id="id_hide_board_{}"'.format(self.permanence.id), html)
        self.assertIn('id="id_show_board_{}"'.format(self.permanence.id), html)
        self.assertIn("Responsable", html)
        self.assertIn("BoardMember", html)
        # One role without an assigned customer: displayed as "1 / 2"
        self.assertIn("1 / 2", html)

    def test_empty_board_shows_no_task(self):
        html = self.permanence.get_board
        self.assertIn(str(gettext("No task")), html)
        self.assertNotIn("repanier-button-row", html)


class StatusBlockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.stable = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        cls.refreshing = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.CLOSED
        )

    def test_stable_status_polls_nothing(self):
        html = self.stable.get_html_status_display()
        self.assertIn("wrap-text", html)
        # Only the page-reload check for the staff member who launched the task
        self.assertIn(
            "repanier_trigger_reload_{}".format(self.stable.id), html
        )
        self.assertNotIn("id_get_status_", html)

    def test_status_under_refresh_polls_the_ajax_endpoint(self):
        html = self.refreshing.get_html_status_display()
        self.assertIn('id="id_get_status_{}"'.format(self.refreshing.id), html)
        self.assertIn(
            reverse("repanier:display_status", args=(self.refreshing.id,)),
            html,
        )
        self.assertIn("django.jQuery", html)
