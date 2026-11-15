from unittest.mock import patch

import json

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from repanier.models.customer import Customer
from repanier.models.configuration import Configuration
from repanier.passport_network import get_network_signer, verify_passport_member

FAMILY_HOSTS = ["gasath.repanier.be", "courtcircuit.repanier.be"]

HAPPY_MEMBER = json.dumps({"member": True})
GONE_MEMBER = json.dumps({"member": False})


def _verify_token(email):
    return get_network_signer().sign("{}|passport-audit".format(email))


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    ALLOWED_HOSTS=FAMILY_HOSTS + ["testserver"],
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class PassportVerifyEndpointTest(TestCase):
    """The home site answers the family routine: is this e-mail
    still one of my active members? The question travels signed
    with the family key, and even the negative answer comes signed -
    a site which stays silent is never confused with a site which
    says no."""

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
        Customer.objects.create(user=cls.user, short_basket_name="Mélanie")

    def _ask(self, email):
        body = json.dumps({"token": _verify_token(email)})
        return self.client.post(
            "/fr/passport/verify/", data=body, content_type="application/json"
        )

    def _answer(self, response):
        payload = json.loads(response.content.decode("utf-8"))
        blob = payload["passport_member"]
        return json.loads(get_network_signer().unsign(blob, max_age=60))["member"]

    def test_an_active_member_answers_yes(self):
        response = self._ask("melanie@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._answer(response))

    def test_everybody_else_answers_no(self):
        for email in ("nobody@example.com", "staff@example.com", "group@example.com"):
            response = self._ask(email)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(self._answer(response))

    def test_an_incomprehensible_question_stays_silent(self):
        for body in ("", "not json", "{}", '{"token": "x"}'):
            response = self.client.post(
                "/fr/passport/verify/", data=body, content_type="application/json"
            )
            self.assertEqual(response.status_code, 404)


@override_settings(
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class VerifyPassportMemberTest(TestCase):
    """The family client of the routine: True, False, or the silence
    of a home site which cannot answer. The distinction is the
    whole point: silence is never a departure."""

    class _FakeResponse:
        def __init__(self, payload):
            self._body = payload.encode("utf-8") if isinstance(payload, str) else payload

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _answer(self, payload):
        return patch(
            "repanier.passport_network.urllib_request.urlopen",
            return_value=self._FakeResponse(payload),
        )

    def _payload(self, answer):
        return json.dumps(
            {"passport_member": get_network_signer().sign(answer)}
        )

    def test_a_member_at_home_answers_true(self):
        with self._answer(self._payload(HAPPY_MEMBER)):
            self.assertIs(
                verify_passport_member("gasath", "melanie@example.com"), True
            )

    def test_a_gone_member_answers_false(self):
        with self._answer(self._payload(GONE_MEMBER)):
            self.assertIs(
                verify_passport_member("gasath", "melanie@example.com"), False
            )

    def test_silence_answers_none(self):
        from urllib.error import HTTPError

        with patch(
            "repanier.passport_network.urllib_request.urlopen",
            side_effect=HTTPError("url", 500, "boom", {}, None),
        ):
            self.assertIsNone(
                verify_passport_member("gasath", "melanie@example.com")
            )
        with patch(
            "repanier.passport_network.urllib_request.urlopen",
            side_effect=Exception("network down"),
        ):
            self.assertIsNone(
                verify_passport_member("gasath", "melanie@example.com")
            )

    def test_an_answer_off_key_answers_none(self):
        from django.core import signing

        stranger = signing.TimestampSigner(
            key="not-the-family-key", salt="repanier/1905/passport-network"
        )
        payload = json.dumps({"passport_member": stranger.sign(GONE_MEMBER)})
        with self._answer(payload):
            self.assertIsNone(
                verify_passport_member("gasath", "melanie@example.com")
            )

    def test_a_subdomain_out_of_the_family_never_reaches_the_network(self):
        with self._answer("{}") as urlopen:
            for bad_subdomain in ("Bad_Sub", "a.b", ""):
                self.assertIsNone(
                    verify_passport_member(bad_subdomain, "member@example.com")
                )
            urlopen.assert_not_called()


@override_settings(
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY="shared-family-key",
)
class PassportAuditCommandTest(TestCase):
    """The nightly routine: every member placed here by the passport
    is asked about at his home site. The audit is read only - the
    findings reach the coordination by mail, and only when there
    are findings."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        mirror_user = User.objects.create_user(
            username="group-gasath", email="group-gasath@example.com", password="x"
        )
        cls.mirror_group = Customer.objects.create(
            user=mirror_user,
            short_basket_name="gasath",
            is_group=True,
            accepts_passport_members=True,
        )
        for short_name in ("Damien", "Carine", "Mélanie"):
            member_email = "{}@example.com".format(short_name.lower())
            member_user = User.objects.create_user(
                username=member_email,
                email=member_email,
                password="x",
            )
            Customer.objects.create(
                user=member_user,
                short_basket_name=short_name,
                group=cls.mirror_group,
            )

    def _audit(self, answers):
        # The network answers per e-mail: Damien stays at home,
        # Carine left, Mélanie's home site stays silent.
        def fake_verify(subdomain, email):
            return answers.get(email)

        from io import StringIO

        stdout = StringIO()
        with patch(
            "repanier.management.commands.passport_audit.verify_passport_member",
            side_effect=fake_verify,
        ):
            call_command("passport_audit", stdout=stdout)
        return stdout.getvalue()

    def test_the_audit_reports_the_findings_by_mail(self):
        output = self._audit(
            {
                "damien@example.com": True,
                "carine@example.com": False,
                "m\u00e9lanie@example.com": None,
            }
        )
        self.assertIn("3 members", output)
        self.assertIn("1 still at home, 1 gone, 1 silent", output)
        self.assertIn("gone  : [gasath] Carine (carine@example.com)", output)
        self.assertIn(
            "silent: [gasath] Mélanie (m\u00e9lanie@example.com)", output
        )
        # Read only: the accounts never moved.
        self.assertEqual(Customer.objects.filter(group=self.mirror_group).count(), 3)
        # The findings reach the coordination, once.
        self.assertEqual(len(mail.outbox), 1)
        report = mail.outbox[0]
        self.assertIn("carine@example.com", report.body)
        self.assertIn("m\u00e9lanie@example.com", report.body)

    def test_a_quiet_night_sends_no_mail(self):
        output = self._audit(
            {
                "damien@example.com": True,
                "carine@example.com": True,
                "m\u00e9lanie@example.com": True,
            }
        )
        self.assertIn("nothing to report, no mail sent.", output)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_single_member_audit_stays_on_him(self):
        from io import StringIO

        stdout = StringIO()
        with patch(
            "repanier.management.commands.passport_audit.verify_passport_member",
            return_value=True,
        ):
            call_command("passport_audit", "--email=damien@example.com", stdout=stdout)
        self.assertIn("1 members", stdout.getvalue())
        self.assertIn("1 still at home, 0 gone, 0 silent", stdout.getvalue())
