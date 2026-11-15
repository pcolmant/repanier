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
        # The token carries the e-mail address and the subdomain of
        # the site which welcomed the member, nothing else
        self.assertEqual(
            get_passport_signer().unsign(morsel.value, max_age=None),
            "carine@example.com|gasath",
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

    def _group(self, short_basket_name, accepts_passport_members=False):
        group_user = User.objects.create_user(
            username="group-{}".format(short_basket_name),
            email="group-{}@example.com".format(short_basket_name),
            password="x",
        )
        return Customer.objects.create(
            user=group_user,
            short_basket_name=short_basket_name,
            is_group=True,
            accepts_passport_members=accepts_passport_members,
        )

    def _arrive_from(self, origin):
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com|{}".format(origin)
        )
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")

    def _refresh_customer(self):
        return Customer.objects.get(id=self.customer.id)

    def test_an_arrival_attaches_the_mirror_group_of_the_home_site(self):
        group = self._group("GasAth", accepts_passport_members=True)
        self._arrive_from("gasath")
        # Placed in the mirror group: the local coordination never
        # placed the member anywhere, the passport does it by default
        # - the group may wear any case, the subdomain matches anyway
        self.assertEqual(self._refresh_customer().group_id, group.id)

    def test_an_arrival_attaches_nothing_to_a_group_which_does_not_accept(self):
        # The mirror group exists but the coordination never opened
        # the door: the passport respects the validation
        self._group("GasAth", accepts_passport_members=False)
        self._arrive_from("gasath")
        self.assertIsNone(self._refresh_customer().group)

    def test_an_arrival_never_overwrites_a_group_set_by_the_coordination(self):
        self._group("GasAth", accepts_passport_members=True)
        other = self._group("Other Group")
        Customer.objects.filter(id=self.customer.id).update(group=other)
        self._arrive_from("gasath")
        # The coordination already decided: the passport does not touch it
        self.assertEqual(self._refresh_customer().group_id, other.id)

    def test_an_arrival_without_mirror_group_attaches_nothing(self):
        self._group("Another Group")
        self._arrive_from("gasath")
        self.assertIsNone(self._refresh_customer().group)

    def test_an_ambiguous_mirror_group_attaches_nothing(self):
        self._group("GasAth", accepts_passport_members=True)
        self._group("gasath", accepts_passport_members=True)
        self._arrive_from("gasath")
        self.assertIsNone(self._refresh_customer().group)

    def test_coming_home_attaches_nothing(self):
        self._group("Courtcircuit")
        # The origin carries the subdomain of this site itself: even
        # with a mirror group wearing it, coming home attaches nothing
        self._arrive_from("courtcircuit")
        self.assertIsNone(self._refresh_customer().group)

    def test_a_passport_without_origin_opens_the_session_and_attaches_nothing(self):
        self._group("GasAth", accepts_passport_members=True)
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com"
        )
        self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), self.user.id
        )
        self.assertIsNone(self._refresh_customer().group)

    def test_a_classic_sign_in_with_a_valid_passport_repairs_the_account(self):
        group = self._group("GasAth", accepts_passport_members=True)
        # A member registered on this site for years, signed in by
        # hand while his browser carries his passport: the account is
        # repaired like a fresh passport arrival
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "carine@example.com|gasath"
        )
        self._sign_in_on("courtcircuit.repanier.be")
        self.assertEqual(self._refresh_customer().group_id, group.id)

    def test_a_classic_sign_in_with_somebody_elses_passport_repairs_nothing(self):
        self._group("GasAth", accepts_passport_members=True)
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "somebodyelse@example.com|gasath"
        )
        self._sign_in_on("courtcircuit.repanier.be")
        self.assertIsNone(self._refresh_customer().group)

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
