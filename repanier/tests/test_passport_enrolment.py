import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase, override_settings

from repanier.middleware import (
    PASSPORT_COOKIE,
    get_passport_signer,
)
from repanier.models.customer import Customer
from repanier.models.configuration import Configuration
from repanier.passport_network import get_network_signer

FAMILY_HOSTS = ["gasath.repanier.be", "courtcircuit.repanier.be", "pigal.repanier.be"]

MOCK_PROFILE = {
    "email": "damien@example.com",
    "short_basket_name": "Damien",
    "long_basket_name": "Damien Valls",
    "language": "fr",
    "phone1": "0476 12 34 56",
    "phone2": "02 345 67 89",
    "bank_account1": "BE12 3456 7890 1234",
    "bank_account2": "BE98 7654 3210 9876",
    "address": "Rue du Pavillon 12",
    "city": "Bruxelles",
    "may_order": False,
}


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=FAMILY_HOSTS + ["testserver"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class PassportEnrolmentTest(TestCase):
    """The family enrolment: a member arriving with a valid passport
    on a site where he owns no account, whose home site owns a mirror
    group here which accepts him, is registered from the profile of
    his home site - fetched server to server - and lands directly in
    his mirror group, without any form to fill in. The personal data
    never travels through the browser, and nothing here reconnects
    anybody anywhere."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The home site of the arriving member owns its mirror group
        # here, and the mirror accepts the passport members.
        cls.mirror_user = User.objects.create_user(
            username="group-gasath", email="group-gasath@example.com", password="x"
        )
        cls.mirror_group = Customer.objects.create(
            user=cls.mirror_user,
            short_basket_name="gasath",
            is_group=True,
            accepts_passport_members=True,
        )
        # A namesake of the arriving member already lives here: the
        # enrolment unfolds the short names instead of colliding.
        cls.local_user = User.objects.create_user(
            username="local-carine@example.com",
            email="local-carine@example.com",
            password="x",
        )
        Customer.objects.create(user=cls.local_user, short_basket_name="Carine")

    def _arrive_with_a_passport_from(self, origin, email):
        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "{}|{}".format(email, origin)
        )
        return self.client.get("/dummy/", HTTP_HOST="courtcircuit.repanier.be")

    def test_the_arrival_enrols_the_member_from_his_home_profile(self):
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = dict(MOCK_PROFILE)
            response = self._arrive_with_a_passport_from(
                "gasath", "damien@example.com"
            )
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args[0], ("gasath", "damien@example.com"))
        # The session opened for the freshly registered member
        user = User.objects.get(email="damien@example.com")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), user.id
        )
        customer = Customer.objects.get(user_id=user.id)
        # The account follows the conventions of the sign up: the
        # username is the e-mail, the last name the short name.
        self.assertEqual(user.username, "damien@example.com")
        self.assertEqual(user.last_name, customer.short_basket_name)
        # The short names unfold : a Carine already lives here, but
        # no Damien - the arriving Damien keeps his own name.
        self.assertEqual(customer.short_basket_name, "Damien")
        # The profile of the home site is honoured to the field.
        self.assertEqual(customer.long_basket_name, "Damien Valls")
        self.assertEqual(customer.language, "fr")
        self.assertEqual(customer.phone1, "0476 12 34 56")
        self.assertEqual(customer.phone2, "02 345 67 89")
        self.assertEqual(customer.bank_account1, "BE12 3456 7890 1234")
        self.assertEqual(customer.bank_account2, "BE98 7654 3210 9876")
        self.assertEqual(customer.address, "Rue du Pavillon 12")
        # The city follows the local convention: stored upper case.
        self.assertEqual(customer.city, "BRUXELLES")
        # The may-order trust of the home site travels with him.
        self.assertFalse(customer.may_order)
        # The member lands directly in the mirror group of his home.
        self.assertEqual(customer.group_id, self.mirror_group.id)
        # And the passport he leaves with still names his home.
        morsel = self.client.cookies[PASSPORT_COOKIE]
        self.assertEqual(
            get_passport_signer().unsign(morsel.value, max_age=None),
            "damien@example.com|gasath",
        )

    def test_a_short_name_collision_folds_the_home_site_into_the_name(self):
        profile = dict(MOCK_PROFILE)
        profile["email"] = "carine@example.com"
        profile["short_basket_name"] = "Carine"
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = profile
            self._arrive_with_a_passport_from("gasath", "carine@example.com")
        customer = Customer.objects.get(user__email="carine@example.com")
        self.assertEqual(customer.short_basket_name, "Carine (gasath)")

    def test_without_a_mirror_group_nobody_is_enrolled(self):
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            self._arrive_with_a_passport_from("pigal", "damien@example.com")
            self.assertEqual(fetch.call_count, 0)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(User.objects.filter(email="damien@example.com").exists())

    def test_a_mirror_group_which_refuses_enrols_nobody(self):
        Customer.objects.filter(id=self.mirror_group.id).update(
            accepts_passport_members=False
        )
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            self._arrive_with_a_passport_from("gasath", "damien@example.com")
            self.assertEqual(fetch.call_count, 0)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_existing_account_is_never_enrolled_again(self):
        User.objects.create_user(
            username="staff-damien@example.com",
            email="damien@example.com",
            password="x",
            is_staff=True,
        )
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            self._arrive_with_a_passport_from("gasath", "damien@example.com")
            self.assertEqual(fetch.call_count, 0)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_unreachable_home_site_leaves_the_site_as_it_was(self):
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = None
            response = self._arrive_with_a_passport_from(
                "gasath", "damien@example.com"
            )
        # The page is served, the member simply is not signed in.
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(User.objects.filter(email="damien@example.com").exists())

    def test_a_profile_with_the_wrong_email_enrols_nobody(self):
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = dict(MOCK_PROFILE)
            self._arrive_with_a_passport_from("gasath", "other@example.com")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(User.objects.filter(email="other@example.com").exists())

    def test_a_broken_enrolment_is_repaired_on_the_next_arrival(self):
        # A first enrolment broke between the user and the customer:
        # the user arrived, the customer never did.
        User.objects.create_user(
            username="damien@example.com", email="damien@example.com", password="x"
        )
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = dict(MOCK_PROFILE)
            self._arrive_with_a_passport_from("gasath", "damien@example.com")
        user = User.objects.get(email="damien@example.com")
        customer = Customer.objects.get(user_id=user.id)
        self.assertEqual(customer.group_id, self.mirror_group.id)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=FAMILY_HOSTS + ["testserver"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class PassportProfileEndpointTest(TestCase):
    """The profile endpoint answers only a site holding the family
    key, with the profile of an active member - group, staff and
    superuser stay out, and everything answers 404: the endpoint
    never confirms whether an account exists."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.user = User.objects.create_user(
            username="melanie@example.com", email="melanie@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user,
            short_basket_name="Mélanie",
            long_basket_name="Mélanie Dagneaux",
            phone1="0477 11 22 33",
            bank_account1="BE11 1111 1111 1111",
            address="Chaussée de Mons 1",
            city="Halle",
        )
        staff_user = User.objects.create_user(
            username="staff@example.com", email="staff@example.com", password="x",
            is_staff=True,
        )
        Customer.objects.create(user=staff_user, short_basket_name="Staff N")

    def _ask(self, email):
        token = get_network_signer().sign("{}|courtcircuit".format(email))
        body = json.dumps({"token": token})
        return self.client.post(
            "/fr/passport/profile/", data=body, content_type="application/json"
        )

    def _extract_profile(self, response):
        payload = json.loads(response.content.decode("utf-8"))
        blob = payload["passport_profile"]
        return json.loads(get_network_signer().unsign(blob, max_age=60))

    def test_the_endpoint_answers_the_profile_of_a_member(self):
        response = self._ask("melanie@example.com")
        self.assertEqual(response.status_code, 200)
        profile = self._extract_profile(response)
        self.assertEqual(profile["email"], "melanie@example.com")
        self.assertEqual(profile["short_basket_name"], "Mélanie")
        self.assertEqual(profile["long_basket_name"], "Mélanie Dagneaux")
        self.assertEqual(profile["phone1"], "0477 11 22 33")
        self.assertEqual(profile["bank_account1"], "BE11 1111 1111 1111")
        self.assertEqual(profile["address"], "Chaussée de Mons 1")
        # The city follows the storage convention of the source site.
        self.assertEqual(profile["city"], "HALLE")
        self.assertTrue(profile["may_order"])

    def test_the_endpoint_stays_silent_on_everything_else(self):
        # No account
        self.assertEqual(self._ask("nobody@example.com").status_code, 404)
        # A staff account
        self.assertEqual(self._ask("staff@example.com").status_code, 404)
        # A tampered token
        response = self.client.post(
            "/fr/passport/profile/",
            data='{"token": "not-a-token"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        # A GET
        response = self.client.get("/fr/passport/profile/")
        self.assertEqual(response.status_code, 405)
        # Garbage bodies never raise
        for body in ("", "not json", "{}"):
            response = self.client.post(
                "/fr/passport/profile/", data=body, content_type="application/json"
            )
            self.assertEqual(response.status_code, 404)
        # A token signed with the wrong key
        stranger = signing.TimestampSigner(
            key="not-the-family-key", salt="repanier/1905/passport-network"
        )
        response = self.client.post(
            "/fr/passport/profile/",
            data='{"token": "%s"}'
            % stranger.sign("melanie@example.com|courtcircuit"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
