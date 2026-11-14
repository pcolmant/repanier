"""Tests of the login view redirect sanitization (CodeQL CWE-601).

The ?next= target is remote data: an external URL may never reach the
redirection, and a same-origin absolute URL is reduced to its path.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils.html import escape
from django.utils.translation import gettext, override

from repanier.models.customer import Customer
from repanier.models.configuration import Configuration

# The login view redirects the browser; in these settings the site uses
# https only, which would turn every assertion below into a 301.
@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class LoginRedirectSanitizationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        # RepanierAuthBackend requires a customer
        Customer.objects.create(user=cls.user, short_basket_name="LoginTest", may_order=True)

    def _get(self, next_url):
        self.client.login(username="client@example.com", password="x")
        return self.client.get("/fr/repanier/go_repanier/", data={"next": next_url})

    def test_external_next_is_rejected(self):
        response = self._get("https://evil.example.com/path?a=1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_same_origin_url_is_reduced_to_its_path(self):
        response = self._get("http://testserver/some/page?x=1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/some/page?x=1")

    def test_relative_next_is_kept_untouched(self):
        response = self._get("/orders/next")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/orders/next")

    def test_no_next_falls_back_to_login_redirect_url(self):
        response = self._get("")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_self_reference_is_caught_by_the_loop_guard(self):
        # Any go_repanier/?next=... whose target mentions go_repanier is
        # cut off by the admin_filter_middleware anti loop protection
        # before the view itself (bot protection, pre-existing).
        response = self._get("/fr/repanier/go_repanier/?next=/x&next=/y")
        self.assertEqual(response.status_code, 400)

    def test_duplicated_next_is_rejected_by_the_sanitizer(self):
        # Without the go_repanier trigger, the loop with several next=
        # falls back to the login redirect url.
        response = self._get("/some/page?next=/x&next=/y")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_javascript_scheme_is_rejected(self):
        response = self._get("javascript:alert(1)")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_query_only_target_keeps_the_default_page(self):
        # A target without a path (?flash=0) would redirect to the
        # current page: keep the login redirect url to avoid a loop.
        response = self._get("?flash=0")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")


class SslRedirectTest(TestCase):
    def test_http_requests_are_upgraded_to_https(self):
        # The next tests disable SECURE_SSL_REDIRECT only to observe what
        # the view computes; the real site must stay https only.
        response = self.client.get("/fr/repanier/go_repanier/", data={"next": "/x"})
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class ToolbarEditParamTest(TestCase):
    """The login of a superuser redirects with the toolbar edit mode
    on. Its url parameter used to be read through get_cms_setting,
    which crashed the login of every superuser on the sites whose cms
    version carries other defaults - the KeyError of the incident."""

    def _redirect_of(self, user, **overrides):
        with override_settings(**overrides):
            self.client.force_login(user=user)
            return self.client.get("/fr/repanier/go_repanier/", data={"next": "/next/page"})

    def test_the_superuser_redirect_carries_the_edit_param(self):
        boss = User.objects.create_superuser(
            username="boss@example.com", email="boss@example.com", password="x"
        )
        response = self._redirect_of(boss)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/next/page?edit")

    def test_an_overridden_edit_param_is_honored(self):
        boss = User.objects.create_superuser(
            username="boss@example.com", email="boss@example.com", password="x"
        )
        response = self._redirect_of(boss, CMS_TOOLBAR_URL__EDIT_ON="on")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/next/page?on")


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class LoginAttemptCounterTest(TestCase):
    """The attempt counter slows down guessing on a wrong password -
    it never locks a correct password out: an administrator resetting a
    password by hand does not run the mail reset flow, and no code
    path cleared the counter left behind by the failures."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.user = User.objects.create_user(
            username="locked@example.com", email="locked@example.com", password="right-password"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Locked", may_order=True
        )
        # Four failed attempts left the account at the lock threshold
        Customer.objects.filter(id=cls.customer.id).update(login_attempt_counter=5)

    def _post_login(self, password):
        return self.client.post(
            "/fr/repanier/go_repanier/",
            data={"username": "locked@example.com", "password": password},
            follow=True,
        )

    def test_a_correct_password_opens_the_locked_account(self):
        response = self._post_login("right-password")
        # The login view redirects the customer: the session is his,
        # not the login screen again
        self.assertNotIn("go_repanier", response.request["PATH_INFO"])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_attempt_counter, 0)

    def test_a_wrong_password_still_tells_to_reset(self):
        response = self._post_login("wrong-password")
        self.assertEqual(response.status_code, 200)
        # The login screen carries the guidance of the counter, in the
        # language of the request.
        with override("fr"):
            message = gettext(
                "You must now first reset your password because you tried to log in "
                "too many times without success."
            )
        # The template escapes the message: compare the escaped form.
        self.assertContains(response, escape(message))
        # And the counter did not grow past its cap
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_attempt_counter, 6)
