from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
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
