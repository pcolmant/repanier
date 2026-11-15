from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from repanier.middleware import (
    PASSPORT_COOKIE,
    PASSPORT_DOMAIN,
    get_passport_signer,
)
from repanier.models.customer import Customer
from repanier.models.configuration import Configuration

FAMILY_HOSTS = ["gasath.repanier.be", "courtcircuit.repanier.be"]


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=FAMILY_HOSTS + ["colibera.be", "testserver"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class RepanierPassportTest(TestCase):
    """A sign in on one site of the repanier.be family opens the member
    sessions on the other sites: a signed cookie on the parent domain,
    an own local session on every site - the lock and the inactive
    accounts stay out."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.user = User.objects.create_user(
            username="carine@example.com", email="carine@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Carine", may_order=True
        )

    def _sign_in_on(self, host):
        return self.client.post(
            "/fr/repanier/go_repanier/",
            data={"username": "carine@example.com", "password": "x"},
            HTTP_HOST=host,
            follow=True,
        )

    def test_a_login_sets_the_passport_on_the_parent_domain(self):
        self._sign_in_on("gasath.repanier.be")
        morsel = self.client.cookies.get(PASSPORT_COOKIE)
        self.assertIsNotNone(morsel)
        self.assertEqual(morsel["domain"], PASSPORT_DOMAIN)
        self.assertTrue(morsel["secure"])
        self.assertTrue(morsel["httponly"])
        # The token carries the e-mail address, nothing else
        self.assertEqual(
            get_passport_signer().unsign(morsel.value, max_age=None),
            "carine@example.com",
        )

    def test_a_login_outside_the_family_sets_no_passport(self):
        self._sign_in_on("colibera.be")
        self.assertIsNone(self.client.cookies.get(PASSPORT_COOKIE))

    def test_the_passport_opens_the_session_on_another_site(self):
        passport = get_passport_signer().sign("carine@example.com")
        self.client.cookies[PASSPORT_COOKIE] = passport
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")
        # The local session opened, identified by the local account
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), self.user.id
        )

    def test_a_tampered_passport_opens_nothing(self):
        self.client.cookies[PASSPORT_COOKIE] = (
            get_passport_signer().sign("carine@example.com") + "tampered"
        )
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_locked_account_stays_locked_for_the_passport(self):
        from django.utils import timezone

        Customer.objects.filter(id=self.customer.id).update(
            login_locked_on=timezone.now()
        )
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com"
        )
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_passport_without_local_account_opens_nothing(self):
        User.objects.filter(id=self.user.id).update(is_active=False)
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com"
        )
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_logout_closes_the_whole_family(self):
        self._sign_in_on("gasath.repanier.be")
        self.client.cookies.pop(PASSPORT_COOKIE, None)
        # simulate the passport which arrived from the other site...
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com"
        )
        response = self.client.get(
            "/fr/repanier/leave_repanier/", HTTP_HOST="gasath.repanier.be"
        )
        # ... the response schedules the deletion of the family cookie
        self.assertEqual(response.cookies[PASSPORT_COOKIE].value, "")
