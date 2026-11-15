from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.utils import translation
from django.utils.translation import get_language

from repanier.email.email import in_customer_language
from repanier.models.customer import Customer


class CustomerLanguageTest(TestCase):
    """The site is multilingual (in the ini,
    DJANGO_SETTINGS_LANGUAGE=fr-nl), but the sending process runs in
    the language of the site: without care, every member receives his
    mails in French whatever his profile says. The decorator
    activates Customer.language for the whole build and send of a
    member's mail - the subject, the body, the lazy labels of the
    attachments - and restores the previous language on the way out.
    """

    def test_the_decorator_speaks_the_language_of_the_customer(self):
        customer = Customer(language="nl")

        @in_customer_language
        def probe(the_customer):
            return get_language()

        self.assertEqual(probe(customer), "nl")

    def test_the_decorator_restores_the_previous_language(self):
        customer = Customer(language="en")
        with translation.override("fr"):

            @in_customer_language
            def probe(the_customer):
                return get_language()

            self.assertEqual(probe(customer), "en")
            self.assertEqual(translation.get_language(), "fr")

    def test_the_order_confirmation_mail_is_decorated(self):
        from repanier.email.email_order import export_order_2_1_customer

        # functools.wraps keeps the name and marks the wrap
        self.assertEqual(
            export_order_2_1_customer.__name__, "export_order_2_1_customer"
        )
        self.assertTrue(hasattr(export_order_2_1_customer, "__wrapped__"))


class CustomerLanguageFieldTest(TestCase):
    """The language of a member lives on his Customer - set at his
    creation, copied by the family enrolment, read by his mails -
    and until now invisible: nobody could see it nor correct it. The
    customer screen of the admin shows it now, next to the
    subscription to the mails."""

    @classmethod
    def setUpTestData(cls):
        cls.member_user = User.objects.create_user(
            username="melanie@example.com", email="melanie@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.member_user, short_basket_name="Mélanie", language="nl"
        )

    def test_the_customer_screen_shows_the_language(self):
        from repanier.admin.customer import CustomerWithUserDataAdmin

        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(
            username="admin@example.com", email="admin@example.com", password="x"
        )
        admin_instance = CustomerWithUserDataAdmin(Customer, admin.site)
        fieldsets = admin_instance.get_fieldsets(request, self.customer)
        fields = [
            field
            for _label, config in fieldsets
            for field in config["fields"]
        ]
        self.assertIn("language", fields)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    LANGUAGES=[("fr", "français"), ("nl", "Nederlands")],
)
class MyProfileLanguageTest(TestCase):
    """The member decides himself, on the "My data" screen: his
    language travels with his page. His sign in e-mail stays on the
    screen, for memory only - a member touching it could lock
    himself out of his own account, so the field never leaves
    read-only mode and the posted values never reach the account."""

    @classmethod
    def setUpTestData(cls):
        from repanier.models.configuration import Configuration

        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.member_user = User.objects.create_user(
            username="melanie@example.com", email="melanie@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.member_user, short_basket_name="Mélanie", language="fr"
        )

    def test_the_screen_shows_the_language_and_a_read_only_email(self):
        self.client.force_login(self.member_user)
        response = self.client.get("/fr/repanier/me/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("id_language", html)
        self.assertIn("melanie@example.com", html)
        self.assertIn('required disabled aria-describedby="id_email1_helptext"', html)

    def test_the_member_changes_his_language_but_never_his_email(self):
        self.client.force_login(self.member_user)
        response = self.client.post(
            "/fr/repanier/me/",
            data={
                "long_basket_name": "Mélanie D",
                "language": "nl",
                "phone1": "0477 11 22 33",
                "email1": "pirate@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.member_user.refresh_from_db()
        self.assertEqual(self.customer.language, "nl")
        # The posted e-mail is a wish, not a command: the account
        # keeps the e-mail - and the username - it signed in with.
        self.assertEqual(self.member_user.email, "melanie@example.com")
        self.assertEqual(self.member_user.username, "melanie@example.com")

    def test_a_language_out_of_the_site_choices_never_passes(self):
        self.client.force_login(self.member_user)
        response = self.client.post(
            "/fr/repanier/me/",
            data={
                "long_basket_name": "Mélanie D",
                "language": "klingon",
                "phone1": "0477 11 22 33",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.language, "klingon")


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=["testserver", "courtcircuit.repanier.be"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
    LANGUAGES=[("fr", "Français"), ("nl", "Nederlands")],
)
class SessionLanguageCookieTest(TestCase):
    """The site speaks the language of the member it just welcomed.

    Every opening of a member session - a sign in by hand, a passport
    arrival, the passport login door - plants his language as a host
    only cookie: each site keeps its own, the future visits follow
    him. A language this site does not run changes nothing: the CMS
    and the browser stay in charge, the fallback of the site applies.
    """

    @classmethod
    def setUpTestData(cls):
        from repanier.models.configuration import Configuration

        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.member_user = User.objects.create_user(
            username="melanie@example.com",
            email="melanie@example.com",
            password="le-mot-de-passe-de-melanie",
        )
        cls.customer = Customer.objects.create(
            user=cls.member_user,
            short_basket_name="Mélanie",
            may_order=True,
            language="fr",
        )
    def _sign_in_by_hand(self):
        return self.client.post(
            "/fr/repanier/go_repanier/",
            {
                "username": "melanie@example.com",
                "password": "le-mot-de-passe-de-melanie",
                "this_is_the_login_form": "1",
                "next": "/",
            },
        )

    def test_the_sign_in_plants_the_language_of_the_member(self):
        response = self._sign_in_by_hand()
        self.assertEqual(response.status_code, 302)
        cookie = response.cookies[settings.LANGUAGE_COOKIE_NAME]
        self.assertEqual(cookie.value, "fr")

    def test_an_unknown_language_here_keeps_the_cms_in_charge(self):
        # A member arriving from a multilingual home keeps a language
        # this site does not run (a restored dump may carry
        # anything): the sign in never copies it - the CMS keeps
        # planting the language of the pages it renders.
        Customer.objects.filter(id=self.customer.id).update(language="sv")
        response = self._sign_in_by_hand()
        self.assertEqual(response.status_code, 302)
        cookie = response.cookies.get(settings.LANGUAGE_COOKIE_NAME)
        self.assertNotEqual((cookie.value if cookie else None), "sv")

    def test_a_passport_arrival_plants_the_language_too(self):
        # The same block runs for every opening of a member session:
        # here, the passport of the family opens the door - on a real
        # page, because an unprefixed 404 is swapped into a redirect
        # by the locale middleware, cookies and all.
        Customer.objects.filter(id=self.customer.id).update(language="nl")
        from repanier.middleware import PASSPORT_COOKIE, get_passport_signer

        self.client.cookies[PASSPORT_COOKIE] = get_passport_signer().sign(
            "melanie@example.com|gasath"
        )
        response = self.client.get(
            "/fr/repanier/go_repanier/", HTTP_HOST="courtcircuit.repanier.be"
        )
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "nl"
        )
