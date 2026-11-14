"""Tests of the login view redirect sanitization (CodeQL CWE-601).

The ?next= target is remote data: an external URL may never reach the
redirection, and a same-origin absolute URL is reduced to its path.
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils.html import escape
from django.core import mail
from django.utils import timezone
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

    def test_a_wrong_password_locks_a_legacy_counter(self):
        """The reset guidance of the old counter is gone: a wrong
        password on an account left above the threshold by the
        production incident locks the account for a quarter of an
        hour - and the owner is warned once."""
        Customer.objects.filter(id=self.customer.id).update(login_attempt_counter=5)
        response = self._post_login("wrong-password")
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.login_locked_on)
        # The lock mail warns the owner - once per lock episode
        self.assertEqual(len(mail.outbox), 1)


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class LoginTemporaryLockTest(TestCase):
    """Three failed attempts close the account for a quarter of an
    hour, correct password included - the guesser waits, the
    legitimate user reads when the door reopens and receives one
    warning mail per lock episode."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.user = User.objects.create_user(
            username="toto@example.com", email="toto@example.com", password="right-password"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Toto", may_order=True
        )

    def _post_login(self, password):
        return self.client.post(
            "/fr/repanier/go_repanier/",
            data={"username": "toto@example.com", "password": password},
            follow=True,
        )

    def _lock_message(self):
        with override("fr"):
            return escape(
                gettext(
                    "Your account is locked after too many failed attempts: try "
                    "again in %(minutes)d minutes, or ask for a new password right now."
                ).replace("%(minutes)d", "15")
            )

    def test_two_failures_stay_harmless(self):
        self._post_login("wrong-1")
        self._post_login("wrong-2")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_attempt_counter, 2)
        self.assertIsNone(self.customer.login_locked_on)
        # The third attempt is the good one: the door opens
        response = self._post_login("right-password")
        self.assertNotIn("go_repanier", response.request["PATH_INFO"])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_attempt_counter, 0)

    def test_the_third_failure_locks_and_mails_once(self):
        self._post_login("wrong-1")
        self._post_login("wrong-2")
        response = self._post_login("wrong-3")
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.login_locked_on)
        # The screen tells when the door reopens
        self.assertContains(response, self._lock_message())
        # The warning mail leaves once per lock episode, carrying the
        # caps lock guidance and the link to the password reset
        self.assertEqual(len(mail.outbox), 1)
        locked_mail = mail.outbox[0]
        self.assertEqual(locked_mail.to, ["toto@example.com"])
        self.assertEqual(
            locked_mail.subject.count(settings.REPANIER_SETTINGS_GROUP_NAME), 1
        )
        self.assertIn("/repanier/password_reset/", locked_mail.alternatives[0][0])
        self.assertNotIn("List-Unsubscribe", locked_mail.extra_headers)
        # Transactional: an unsubscribed member is warned too
        Customer.objects.filter(id=self.customer.id).update(subscribe_to_email=False)
        mail.outbox.clear()

    def test_during_the_lock_even_the_correct_password_waits(self):
        self._post_login("wrong-1")
        self._post_login("wrong-2")
        self._post_login("wrong-3")
        self.assertEqual(len(mail.outbox), 1)
        self.customer.refresh_from_db()
        locked_on = self.customer.login_locked_on
        # The correct password bounces during the lock, without a new
        # mail and without growing anything
        response = self._post_login("right-password")
        self.assertContains(response, self._lock_message())
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_locked_on, locked_on)
        self.assertEqual(len(mail.outbox), 1)

    def test_the_lock_expires_and_the_door_reopens(self):
        self._post_login("wrong-1")
        self._post_login("wrong-2")
        self._post_login("wrong-3")
        # Sixteen minutes later: the counter and the lock are gone
        Customer.objects.filter(id=self.customer.id).update(
            login_locked_on=timezone.now() - timezone.timedelta(minutes=16)
        )
        response = self._post_login("right-password")
        self.assertNotIn("go_repanier", response.request["PATH_INFO"])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.login_attempt_counter, 0)
        self.assertIsNone(self.customer.login_locked_on)

    def test_a_legacy_counter_locks_on_the_next_failure(self):
        """The production incident left counters above the threshold
        without any lock timestamp: the first new failure after the
        temporary lock chantier locks - and the owner is warned."""
        Customer.objects.filter(id=self.customer.id).update(login_attempt_counter=5)
        response = self._post_login("wrong-1")
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.login_locked_on)
        self.assertContains(response, self._lock_message())
        self.assertEqual(len(mail.outbox), 1)
        response = self._post_login("right-password")
        # The legacy customer with the correct password still enters -
        # until he fails once again, which is now locked
        # (the previous post locked the account)
        self.assertContains(response, self._lock_message())
