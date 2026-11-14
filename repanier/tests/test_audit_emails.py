"""The email audit of the member accounts.

Read only command, walked over the member accounts of the site: the
findings it reports are the blockers of the email only login - and
later of matching social accounts on the verified email:
accounts sharing an email, accounts without a usable email, and the
accounts still opened by name instead of by email.
"""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from repanier.models.customer import Customer


class AuditEmailsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def _customer(self, username, email, last_name, may_order=True):
        user = User.objects.create_user(
            username=username,
            email=email,
            password="x",
            first_name="",
            last_name=last_name,
        )
        return Customer.objects.create(
            user=user, short_basket_name=last_name, may_order=may_order
        )

    def call(self):
        out = StringIO()
        err = StringIO()
        exit_code = 0
        try:
            call_command("audit_emails", stdout=out, stderr=err)
        except SystemExit as exit_signal:
            exit_code = exit_signal.code
        return exit_code, out.getvalue(), err.getvalue()

    def test_a_clean_member_base_exits_zero(self):
        self._customer("alice@example.com", "alice@example.com", "alice")
        exit_code, out, err = self.call()
        self.assertEqual(exit_code, 0)
        self.assertIn("1 member accounts audited", out)
        self.assertIn("0 findings", out)
        self.assertEqual(err, "")

    def test_an_inactive_or_non_ordering_member_is_out_of_scope(self):
        self._customer("alice@example.com", "alice@example.com", "alice")
        self._customer(
            "bob@example.com", "bob@example.com", "bob", may_order=False
        )
        exit_code, out, err = self.call()
        self.assertEqual(exit_code, 0)
        self.assertIn("1 member accounts audited", out)

    def test_a_shared_email_is_a_finding(self):
        self._customer("alice@example.com", "alice@example.com", "alice")
        self._customer("bob@example.com", "alice@example.com", "bob")
        exit_code, out, err = self.call()
        self.assertEqual(exit_code, 1)
        self.assertIn("Shared email alice@example.com: alice, bob", err)

    def test_a_member_without_a_usable_email_is_a_finding(self):
        self._customer("alice", "", "alice")
        self._customer("bob", "bob at example dot com", "bob")
        exit_code, out, err = self.call()
        self.assertEqual(exit_code, 1)
        self.assertIn("No usable email for alice (username alice)", err)
        self.assertIn("No usable email for bob (username bob)", err)

    def test_a_member_signing_in_by_name_is_a_finding(self):
        self._customer("alice", "alice@example.com", "alice")
        exit_code, out, err = self.call()
        # The email is unique and usable: only the legacy name login
        # remains, and it blocks the email only sign in.
        self.assertEqual(exit_code, 1)
        self.assertIn(
            "Signs in by name, not by email: alice (username alice, email "
            "alice@example.com)",
            err,
        )

    def test_a_group_account_is_counted_but_audited_like_a_member(self):
        user = User.objects.create_user(
            username="group@example.com",
            email="group@example.com",
            password="x",
            last_name="group",
        )
        Customer.objects.create(
            user=user,
            short_basket_name="group",
            may_order=True,
            is_group=True,
        )
        exit_code, out, err = self.call()
        self.assertEqual(exit_code, 0)
        self.assertIn("1 member accounts audited (1 group accounts)", out)
