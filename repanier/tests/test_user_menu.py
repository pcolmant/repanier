"""Tests of the navbar user menu (the repanier_user tag).

The menu renders from repanier/user_menu.html instead of building markup
strings in Python: the tests pin the structure of both entries (anonymous
sign-in button, authenticated dropdown, basket shortcut) and the balance
item every customer sees.
"""
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.translation import gettext

from repanier.models.customer import Customer


def render_user_menu(request, permanence_id=0):
    tpl = Template(
        "{% load repanier_tags %}"
        "{% repanier_user permanence_id=permanence_id %}"
    )
    return tpl.render(
        Context({"request": request, "permanence_id": permanence_id})
    )


class UserMenuTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Client", may_order=True
        )

    def request_for(self, user, customer_id=None):
        request = RequestFactory().get("/dummy/")
        request.user = user
        # RepanierAuthBackend attaches customer_id to the authenticated
        # user (None for a staff without customer): emulate the same
        # state on a RequestFactory user, attribute always present.
        request.user.customer_id = customer_id
        return request

    def test_anonymous_gets_the_sign_in_button(self):
        html = render_user_menu(self.request_for(AnonymousUser()))
        # Same translation context as the rendered template (fr here)
        self.assertIn(str(gettext("Sign in")), html)
        self.assertIn(reverse("repanier:login_form"), html)
        self.assertIn('id="li_my_name"', html)
        # No dropdown, no basket, nothing authenticated-only
        self.assertNotIn("dropdown-menu", html)
        self.assertNotIn("li_my_basket", html)

    def test_authenticated_customer_gets_the_dropdown(self):
        request = self.request_for(self.user, customer_id=self.customer.id)
        html = render_user_menu(request)
        # The toggle carries the short name of the member, his display
        # identity - the username (an e-mail address since the e-mail
        # only sign in) never crowds the navbar
        self.assertIn(self.customer.short_basket_name, html)
        self.assertNotIn(self.user.username, html)
        self.assertIn(reverse("repanier:send_mail_to_coordinators_view"), html)
        self.assertIn(reverse("repanier:my_profile_view"), html)
        self.assertIn(
            reverse("repanier:customer_invoice_view", args=(0, self.customer.id)),
            html,
        )
        self.assertIn(reverse("repanier:logout"), html)
        # A customer without invoices sees the plain history entry
        self.assertIn(str(gettext("History")), html)
        # ... and the separator above the logout entry
        self.assertIn("dropdown-divider", html)

    def test_basket_shortcut_follows_the_permanence(self):
        request = self.request_for(self.user, customer_id=self.customer.id)
        with_basket = render_user_menu(request, permanence_id=7)
        self.assertIn("li_my_basket", with_basket)
        self.assertIn(
            reverse("repanier:order_view", args=(7,)) + "?is_basket=yes",
            with_basket,
        )
        without_basket = render_user_menu(request)
        self.assertNotIn("li_my_basket", without_basket)

    def test_who_is_who_entry_follows_the_setting(self):
        request = self.request_for(self.user, customer_id=self.customer.id)
        with patch("repanier.apps.REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO", True):
            html = render_user_menu(request)
            self.assertIn(reverse("repanier:who_is_who_view"), html)
        with patch("repanier.apps.REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO", False):
            html = render_user_menu(request)
            self.assertNotIn(reverse("repanier:who_is_who_view"), html)

    def test_a_staff_without_customer_keeps_the_username(self):
        staff = User.objects.create_user(
            username="boss@example.com", email="boss@example.com", password="x"
        )
        html = render_user_menu(self.request_for(staff))
        # Without a customer account the label falls back on the
        # e-mail address, keeping only the part before the @
        self.assertIn("boss", html)
        self.assertNotIn("boss@example.com", html)

    def test_a_member_with_a_long_short_name_keeps_the_username(self):
        lacome = User.objects.create_user(
            username="dupont@dm.be", email="dupont@dm.be", password="x"
        )
        customer = Customer.objects.create(
            user=lacome, short_basket_name="Dupont de la Motte Ruyter", may_order=True
        )
        html = render_user_menu(self.request_for(lacome, customer_id=customer.id))
        # A "short" name longer than the e-mail address buys nothing:
        # the navbar keeps the shorter label, the part before the @
        self.assertIn("dupont", html)
        self.assertNotIn("dupont@dm.be", html)
        self.assertNotIn("Dupont de la Motte Ruyter", html)

    def test_a_staff_member_always_carries_his_short_name(self):
        chef = User.objects.create_user(
            username="a@b.co", email="a@b.co", password="x", is_staff=True
        )
        responsibility = Customer.objects.create(
            user=chef, short_basket_name="Responsable Auxiliaire", may_order=True
        )
        request = self.request_for(chef, customer_id=responsibility.id)
        request.user.is_staff = True
        html = render_user_menu(request)
        # The staff roles identify by name, even longer than the e-mail
        self.assertIn("Responsable Auxiliaire", html)
        self.assertNotIn("a@b.co", html)
