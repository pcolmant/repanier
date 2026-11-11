"""Tests of the login view redirect sanitization (CodeQL CWE-601).

The ?next= target is remote data: an external URL may never reach the
redirection, and a same-origin absolute URL is reduced to its path.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from repanier.models.customer import Customer

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
