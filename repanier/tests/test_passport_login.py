"""The login door of the passport: a member logged out everywhere
still owns his password on his home site.

The dance asks the home site to vouch for him: the target sends the
browser to the home site login page with a family return URL, the
home site stamps a one minute signed token once the member signed
in (or reuses the session he still owns), and the target opens the
door exactly like a passport arrival. The password never leaves the
home site and never travels through a browser.
"""
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.passport_login import (
    build_passport_login_token,
    get_login_signer,
    read_passport_login_token,
)

FAMILY_HOSTS = ["gasath.repanier.be", "courtcircuit.repanier.be"]
ARRIVE = "http://courtcircuit.repanier.be/fr/passport/arrive/"
EMPTY_PHONE = ""

FAMILY_HOSTS = ["gasath.repanier.be", "courtcircuit.repanier.be"]
ARRIVE = "http://courtcircuit.repanier.be/fr/passport/arrive/"

MOCK_PROFILE = {
    "email": "louis@example.com",
    "short_basket_name": "Louis",
    "long_basket_name": "Louis Etienne",
    "language": "fr",
    "phone1": "0476 98 76 54",
    "phone2": EMPTY_PHONE,
    "bank_account1": "BE12 3456 7890 1234",
    "bank_account2": "BE98 7654 3210 9876",
    "address": "Rue du Pavillon 14",
    "city": "Charleroi",
    "may_order": True,
}


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=FAMILY_HOSTS + ["testserver"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class PassportLoginJourneyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The mirror of the home site on the target, accepting the
        # passport members.
        cls.mirror_user = User.objects.create_user(
            username="group-gasath@example.com",
            email="group-gasath@example.com",
            password="x",
        )
        cls.mirror_group = Customer.objects.create(
            user=cls.mirror_user,
            short_basket_name="gasath",
            is_group=True,
            accepts_passport_members=True,
        )
        # A member of the home site, with his home password.
        cls.hugo = User.objects.create_user(
            username="hugo@example.com",
            email="hugo@example.com",
            password="le-beau-mot-de-passe-de-hugo",
        )
        cls.hugo_customer = Customer.objects.create(
            user=cls.hugo, short_basket_name="Hugo", may_order=True
        )

    def _sign_in_on_the_home_site(self, password, next_url=ARRIVE):
        # One browser for everything, like a member who hops.
        return self.client.post(
            "/fr/passport/login/",
            {
                "username": "hugo@example.com",
                "password": password,
                "next": next_url,
                "this_is_the_login_form": "1",
            },
            HTTP_HOST="gasath.repanier.be",
        )

    def test_the_home_site_vouches_with_a_one_minute_token(self):
        response = self._sign_in_on_the_home_site(
            "le-beau-mot-de-passe-de-hugo"
        )
        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertTrue(location.startswith(ARRIVE + "?token="))
        token = parse_qs(urlsplit(location).query)["token"][0]
        # The token says who the member is, and which home vouches.
        self.assertEqual(
            read_passport_login_token(token),
            ("hugo@example.com", "gasath"),
        )
        # The sign in also opened the home session of the member.
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), self.hugo.id
        )

    def test_a_wrong_password_vouches_for_nobody(self):
        response = self._sign_in_on_the_home_site("un-mauvais-mot-de-passe")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)
        self.assertFalse(self.client.session.keys())

    def test_a_return_target_outside_the_family_goes_nowhere(self):
        response = self._sign_in_on_the_home_site(
            "le-beau-mot-de-passe-de-hugo",
            next_url="https://evil.example.be/pocket",
        )
        # The dance refuses to send the member anywhere else: back to
        # the classical sign in of his home site, no token minted.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/fr/repanier/go_repanier/")
        self.assertFalse(self.client.session.keys())

    def test_the_same_session_vouches_without_a_password(self):
        # The member still owns his session on his home site.
        self.client.login(
            username="hugo@example.com", password="le-beau-mot-de-passe-de-hugo"
        )
        self.client.get("/dummy/", HTTP_HOST="gasath.repanier.be")
        response = self.client.get(
            "/fr/passport/login/",
            {"next": ARRIVE, "email": "hugo@example.com"},
            HTTP_HOST="gasath.repanier.be",
        )
        self.assertEqual(response.status_code, 302)
        token = parse_qs(urlsplit(response["Location"]).query)["token"][0]
        self.assertEqual(
            read_passport_login_token(token),
            ("hugo@example.com", "gasath"),
        )

    def test_the_door_opens_for_an_existing_member(self):
        # What a home site sends: the browser returns with the token.
        token = build_passport_login_token("hugo@example.com", "gasath")
        self.hugo_customer.refresh_from_db()
        self.assertIsNone(self.hugo_customer.group_id)
        response = self.client.get(
            "/fr/passport/arrive/", {"token": token},
            HTTP_HOST="courtcircuit.repanier.be",
        )
        # The door opened, and the arrival placed the member in the
        # mirror group of his home, like every passport arrival.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), self.hugo.id
        )
        self.hugo_customer.refresh_from_db()
        self.assertEqual(self.hugo_customer.group_id, self.mirror_group.id)

    def test_the_door_enrols_a_new_member(self):
        token = build_passport_login_token("louis@example.com", "gasath")
        self.assertFalse(
            User.objects.filter(email="louis@example.com").exists()
        )
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            fetch.return_value = dict(MOCK_PROFILE)
            response = self.client.get(
                "/fr/passport/arrive/", {"token": token},
                HTTP_HOST="courtcircuit.repanier.be",
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        louis = User.objects.get(email="louis@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), louis.id)
        customer = Customer.objects.get(user_id=louis.id)
        # The profile of the home site honoured to the field.
        self.assertEqual(customer.short_basket_name, "Louis")
        self.assertEqual(customer.address, "Rue du Pavillon 14")
        self.assertTrue(customer.may_order)
        # The member lands directly in his mirror group.
        self.assertEqual(customer.group_id, self.mirror_group.id)

    def test_a_forged_token_opens_no_door(self):
        # A token from another salt, and a plain tampered one.
        forged = get_login_signer().sign("thief@example.com|gasath") + "x"
        for token in ("", forged, "not-a-token"):
            client = Client()
            response = client.get(
                "/fr/passport/arrive/", {"token": token},
                HTTP_HOST="courtcircuit.repanier.be",
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "/fr/repanier/go_repanier/")
            self.assertFalse(client.session.keys())

    def test_coming_home_does_not_open_the_door(self):
        # The token names this very site as the home: the cookie
        # alone opens the door, the dance never loops on itself.
        token = build_passport_login_token("hugo@example.com", "courtcircuit")
        client = Client()
        response = client.get(
            "/fr/passport/arrive/", {"token": token},
            HTTP_HOST="courtcircuit.repanier.be",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/fr/repanier/go_repanier/")
        self.assertFalse(client.session.keys())

    def test_no_mirror_still_opens_an_existing_member(self):
        # The mirror gates the enrolment, never a member who already
        # owns his account here: the passport opens existing accounts,
        # this dance follows it.
        Customer.objects.filter(id=self.mirror_group.id).update(
            accepts_passport_members=False
        )
        token = build_passport_login_token("hugo@example.com", "gasath")
        client = Client()
        response = client.get(
            "/fr/passport/arrive/", {"token": token},
            HTTP_HOST="courtcircuit.repanier.be",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(client.session["_auth_user_id"]), self.hugo.id)

    def test_no_mirror_enrols_nobody(self):
        Customer.objects.filter(id=self.mirror_group.id).update(
            accepts_passport_members=False
        )
        token = build_passport_login_token("louis@example.com", "gasath")
        with patch("repanier.middleware.fetch_passport_profile") as fetch:
            client = Client()
            response = client.get(
                "/fr/passport/arrive/", {"token": token},
                HTTP_HOST="courtcircuit.repanier.be",
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/fr/repanier/go_repanier/")
        self.assertFalse(client.session.keys())
        self.assertEqual(fetch.call_count, 0)
        self.assertFalse(User.objects.filter(email="louis@example.com").exists())

    def test_a_locked_member_vouches_for_nobody(self):
        # The login lock applies to the dance exactly as it applies
        # to the classical sign in.
        from django.utils import timezone

        Customer.objects.filter(id=self.hugo_customer.id).update(
            login_locked_on=timezone.now()
        )
        response = self._sign_in_on_the_home_site(
            "le-beau-mot-de-passe-de-hugo"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)
        self.assertFalse(self.client.session.keys())

    def test_the_login_screen_shows_the_passport_door(self):
        response = self.client.get(
            "/fr/repanier/go_repanier/", HTTP_HOST="courtcircuit.repanier.be"
        )
        self.assertContains(response, "/fr/passport/request/")
        # A site on its own domain keeps the classical sign in.
        response = self.client.get("/fr/repanier/go_repanier/")
        self.assertNotContains(response, "/fr/passport/request/")

    def test_the_request_form_leads_to_the_home_site(self):
        response = self.client.get(
            "/fr/passport/request/", HTTP_HOST="courtcircuit.repanier.be"
        )
        self.assertContains(response, "gasath")
        response = self.client.post(
            "/fr/passport/request/",
            {"email": "louis@example.com", "home": "gasath"},
            HTTP_HOST="courtcircuit.repanier.be",
        )
        self.assertEqual(response.status_code, 302)
        location = urlsplit(response["Location"])
        self.assertEqual(location.scheme, "https")
        self.assertEqual(location.netloc, "gasath.repanier.be")
        self.assertEqual(location.path, "/fr/passport/login/")
        query = parse_qs(location.query)
        self.assertEqual(query["email"], ["louis@example.com"])
        self.assertEqual(
            query["next"],
            ["http://courtcircuit.repanier.be/fr/passport/arrive/"],
        )

    def test_a_home_out_of_the_list_leads_nowhere(self):
        response = self.client.post(
            "/fr/passport/request/",
            {"email": "louis@example.com", "home": "evil"},
            HTTP_HOST="courtcircuit.repanier.be",
        )
        # The home comes back signed by the member's choice, but the
        # authority stays server side: the form refuses it - the
        # apostrophe escapes in the response, assert around it.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez votre site")
        self.assertContains(response, "dans la liste.")
