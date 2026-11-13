"""The password reset mail.

The reset mail is the only mail a locked out customer receives: it
must carry the reset link in a shape every mail reader understands -
a branded button for the html view, and the bare address as plain
text, so the strip_tags alternative and text only readers keep a
working link. Transactional mails ignore the unsubscribe flag: a
customer who stopped the announcements still receives his reset link.
"""
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext, override

from repanier.models.customer import Customer

# The site of the tests runs with the French catalog; the mails render
# in the language of the request path.
RESET_URL = "http://example.com/fr/repanier/password_reset/"


# The reset view redirects and the form posts are plain http in the
# test client; the real site stays https only.
@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class PasswordResetMailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="locked@example.com", email="locked@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="LockedOut", may_order=True
        )

    def _reset_link(self):
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        token = default_token_generator.make_token(self.user)
        return "/fr/repanier/password_reset/{}/{}/".format(uid, token)

    def test_the_reset_mail_carries_the_link_twice(self):
        response = self.client.post(
            "/fr/repanier/password_reset/", data={"email": "locked@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(message.to, ["locked@example.com"])
        html = message.alternatives[0][0]
        # The reset link: once in the button href, once as bare text
        # for the strip_tags plain alternative.
        self.assertIn('style="background-color: #198754', html)
        self.assertEqual(html.count('href="' + RESET_URL), 1)
        self.assertEqual(html.count(RESET_URL), 2)
        # The text alternative keeps a working address.
        self.assertIn("/fr/repanier/password_reset/", message.body)

    def test_the_security_note_reassures_the_rightful_owner(self):
        self.client.post(
            "/fr/repanier/password_reset/", data={"email": "locked@example.com"}
        )
        html = mail.outbox[0].alternatives[0][0]
        with override("fr"):
            expected = gettext(
                "If you did not ask for a new password, you can ignore this email: "
                "your current password keeps working."
            )
        self.assertIn(expected, html)

    def test_an_unsubscribed_customer_still_receives_the_reset_mail(self):
        Customer.objects.filter(id=self.customer.id).update(subscribe_to_email=False)
        response = self.client.post(
            "/fr/repanier/password_reset/", data={"email": "locked@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        # Transactional mail: no unsubscribe machinery on the reset mail.
        self.assertNotIn("List-Unsubscribe", mail.outbox[0].extra_headers)

    def test_the_confirmation_mail_after_reset_mentions_the_group(self):
        # The stock confirm view answers the reset link with a redirect
        # to the set password form (the token lives in the session from
        # there on): the confirm form post lands on that set password
        # url, not on the token url.
        self.client.get(self._reset_link())
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        set_password_url = "/fr/repanier/password_reset/{}/set-password/".format(uid)
        response = self.client.post(
            set_password_url,
            data={
                "new_password1": "S0me-sturdy-pass!",
                "new_password2": "S0me-sturdy-pass!",
            },
        )
        self.assertIn(response.status_code, (301, 302))
        # The confirm form sends its own mail: the "password reset done"
        # notice, addressed to the reset account and carrying the
        # identity of the group.
        self.assertEqual(len(mail.outbox), 1)
        confirmation = mail.outbox[0]
        self.assertEqual(confirmation.to, ["locked@example.com"])
        self.assertIn("example.com", confirmation.subject)
        self.assertIn("example.com", confirmation.alternatives[0][0])
