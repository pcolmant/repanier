from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from repanier.models.customer import Customer
from repanier.models.configuration import Configuration


class NormalizeUsernamesTest(TestCase):
    """The sign in reads the e-mail address only: the username is a
    leftover of the import (the short name of the member). The
    command aligns every ordering member on the e-mail shape - a dry
    run first, and the collisions never break the run."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # Admin shape: username == e-mail, nothing to do
        cls.email_shaped = User.objects.create_user(
            username="dupont@example.com", email="dupont@example.com", password="x"
        )
        Customer.objects.create(
            user=cls.email_shaped, short_basket_name="Dupont", may_order=True
        )
        # Import shape: username == short name, the case to normalize,
        # with a trailing space and an uppercase e-mail on top
        cls.import_shaped = User.objects.create_user(
            username="Titi Laleur ", email="TITI@EXAMPLE.COM", password="x"
        )
        Customer.objects.create(
            user=cls.import_shaped, short_basket_name="Titi", may_order=True
        )
        # An account without usable e-mail: reported, skipped
        no_email = User.objects.create_user(
            username="SansEmail", email="", password="x"
        )
        Customer.objects.create(
            user=no_email, short_basket_name="Sans", may_order=True
        )
        # A collision pair: normalizing Tata would steal the username
        # of Tutu - Tata is reported and skipped, nothing breaks
        cls.tata = User.objects.create_user(
            username="tata", email="tata@example.com", password="x"
        )
        Customer.objects.create(
            user=cls.tata, short_basket_name="Tata", may_order=True
        )
        tutu = User.objects.create_user(
            username="tata@example.com", email="tutu@example.com", password="x"
        )
        Customer.objects.create(
            user=tutu, short_basket_name="Tutu", may_order=True
        )

    def test_the_dry_run_touches_nothing_and_reports(self):
        with self.assertRaises(SystemExit):
            call_command("normalize_usernames", stdout=StringIO(), stderr=StringIO())
        self.import_shaped.refresh_from_db()
        self.assertEqual(self.import_shaped.username, "Titi Laleur ")

    def test_the_apply_normalizes_the_import_shaped_username(self):
        call_command(
            "normalize_usernames", "--apply", stdout=StringIO(), stderr=StringIO()
        )
        self.import_shaped.refresh_from_db()
        self.assertEqual(self.import_shaped.username, "titi@example.com")

    def test_a_collision_is_skipped_without_breaking_the_run(self):
        call_command(
            "normalize_usernames", "--apply", stdout=StringIO(), stderr=StringIO()
        )
        self.tata.refresh_from_db()
        # The username of Tutu is untouched, Tata stays as imported
        self.assertEqual(self.tata.username, "tata")

    def test_an_account_without_usable_email_is_reported_and_skipped(self):
        stderr = StringIO()
        call_command("normalize_usernames", "--apply", stdout=StringIO(), stderr=stderr)
        # The command says what it skipped and why, so the
        # coordination can fix the mail address in the CSV
        self.assertIn("skipped, no usable e-mail", stderr.getvalue())
        user = User.objects.get(email="")
        self.assertEqual(user.username, "SansEmail")

    def test_the_email_shaped_username_stays(self):
        call_command(
            "normalize_usernames", "--apply", stdout=StringIO(), stderr=StringIO()
        )
        self.email_shaped.refresh_from_db()
        self.assertEqual(self.email_shaped.username, "dupont@example.com")
