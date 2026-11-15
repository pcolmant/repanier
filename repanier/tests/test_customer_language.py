from django.test import TestCase
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
