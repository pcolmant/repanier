from django.contrib.auth.models import User
from django.test import TestCase

from repanier.admin.customer import CustomerResource, CustomerWithUserDataForm
from repanier.models.customer import Customer
from repanier.models.configuration import Configuration


class CaseInsensitiveEmailUniquenessTest(TestCase):
    """The sign in matches the e-mail addresses case insensitively:
    two accounts whose addresses differ by case only would open the
    same door - the creation and the import must both refuse the
    variant from now on."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        cls.user = User.objects.create_user(
            username="dupont@example.com", email="dupont@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Dupont", may_order=True
        )

    def test_the_admin_form_refuses_a_case_variant(self):
        form = CustomerWithUserDataForm(
            data={
                "short_basket_name": "Titi",
                "email": "DUPONT@EXAMPLE.COM",
                "user": self.user.id,
                "language": "fr",
                "login_attempt_counter": 0,
                "membership_fee_valid_until": "2026-01-01",
                "date_balance": "2026-01-01",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_the_import_refuses_a_case_variant(self):
        instance = Customer(
            short_basket_name="Titi", user=User(email="DUPONT@EXAMPLE.COM")
        )
        with self.assertRaises(ValueError):
            CustomerResource().before_save_instance(instance, row={})

    def test_the_import_refuses_the_email_of_a_staff(self):
        # The staff and superuser addresses take part in the check,
        # exactly like in the admin form: one address, one account,
        # whatever the role
        User.objects.create_user(
            username="boss@example.com",
            email="boss@example.com",
            password="x",
            is_staff=True,
        )
        instance = Customer(short_basket_name="Titi", user=User(email="boss@example.com"))
        with self.assertRaises(ValueError):
            CustomerResource().before_save_instance(instance, row={})

    def test_a_reimport_never_rewrites_the_username(self):
        # A customer aligned on the e-mail convention (by the admin
        # form or by normalize_usernames) is re-imported from the CSV
        # of the coordination: the username - the key of the sign in
        # area - must not return to the short name. The display name
        # alone follows the file.
        CustomerResource().before_save_instance(
            self.customer, row={}, dry_run=False, using_transactions=False
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "dupont@example.com")
        # The rest of the user profile did follow the re-import
        self.assertEqual(self.user.last_name, "Dupont")

    def test_the_import_normalizes_the_email_to_lowercase(self):
        instance = Customer(
            short_basket_name="Titi", user=User(email="TITI@EXAMPLE.COM")
        )
        CustomerResource().before_save_instance(instance, row={})
        created = User.objects.get(username="Titi")
        self.assertEqual(created.email, "titi@example.com")
