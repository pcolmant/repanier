import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from repanier.const import EmailDeliveryStatus, EmailNature
from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.models.emaillog import EmailLog
from repanier.views.brevo_webhook_view import brevo_webhook_view


@override_settings(REPANIER_SETTINGS_BREVO_WEBHOOK_TOKEN="secret")
class BrevoWebhookTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="brevo", email="member@example.org")
        self.customer = Customer.objects.create(
            user=user, short_basket_name="Brevo", valid_email=True
        )
        # Customer's pre_save signal resets this field when the address changes.
        Customer.objects.filter(pk=self.customer.pk).update(valid_email=True)
        self.log = EmailLog.objects.create(
            customer=self.customer,
            recipient_email=user.email,
            message_id="<test@example.org>",
        )

    def post(self, event="delivered", token="secret", **overrides):
        payload = {
            "event": event,
            "message-id": "test@example.org",
            "email": "member@example.org",
            **overrides,
        }
        request = RequestFactory().post(
            "/", data=json.dumps(payload), content_type="application/json"
        )
        return brevo_webhook_view(request, token=token)

    def test_missing_or_incorrect_secret_is_rejected(self):
        self.assertEqual(self.post(token="wrong").status_code, 403)
        with override_settings(REPANIER_SETTINGS_BREVO_WEBHOOK_TOKEN=""):
            self.assertEqual(self.post().status_code, 403)
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, EmailDeliveryStatus.SENT)

    def test_bcc_bounce_and_unknown_message_do_not_invalidate_member(self):
        self.post("hard_bounce", email="copy@example.org")
        self.post("hard_bounce", **{"message-id": "unknown@example.org"})
        self.log.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.log.status, EmailDeliveryStatus.SENT)
        self.assertTrue(self.customer.valid_email)

    def test_delayed_events_and_duplicates_preserve_opened_status(self):
        self.post("opened")
        self.log.refresh_from_db()
        updated_at = self.log.updated_at
        self.post("delivered")
        self.post("soft_bounce")
        self.post("opened")
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, EmailDeliveryStatus.OPENED)
        self.assertEqual(self.log.updated_at, updated_at)

    def test_temporary_failure_can_recover_and_updates_timestamp(self):
        past = timezone.now() - timedelta(days=1)
        EmailLog.objects.filter(pk=self.log.pk).update(updated_at=past)
        self.post("soft_bounce")
        self.post("delivered")
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, EmailDeliveryStatus.DELIVERED)
        self.assertGreater(self.log.updated_at, past)

    def test_matching_hard_bounce_invalidates_current_address(self):
        self.post("hard_bounce", reason="Unknown mailbox")
        self.customer.refresh_from_db()
        self.log.refresh_from_db()
        self.assertFalse(self.customer.valid_email)
        self.assertEqual(self.log.error_reason, "Unknown mailbox")

    def test_old_address_bounce_does_not_invalidate_new_address(self):
        User.objects.filter(pk=self.customer.user_id).update(email="new@example.org")
        self.post("hard_bounce")
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.valid_email)

    def test_malformed_event_fields_are_ignored(self):
        self.assertEqual(self.post(event=123).status_code, 204)
        self.assertEqual(self.post(email=123).status_code, 204)

    @override_settings(DEBUG=False, REPANIER_SETTINGS_BCC_ALL_EMAIL_TO="")
    def test_smtp_completion_does_not_overwrite_webhook_status(self):
        def send_and_deliver(message):
            log = EmailLog.objects.get(message_id=message.extra_headers["Message-ID"])
            self.post("opened", **{"message-id": log.message_id})
            return 1

        email = RepanierEmail(
            subject="Opening", html_body="Hello", to=["member@example.org"],
            email_nature=EmailNature.OPENING, show_customer_may_unsubscribe=False,
            send_even_if_unsubscribed=True,
        )
        with patch.object(RepanierEmail, "send", send_and_deliver):
            email.send_email()
        log = EmailLog.objects.get(message_id=email.extra_headers["Message-ID"])
        self.assertEqual(log.nature, EmailNature.OPENING)
        self.assertEqual(log.status, EmailDeliveryStatus.OPENED)

    def test_no_send_returns_a_pair(self):
        should_send, message = RepanierEmail.send_email_to_who(False, False)
        self.assertFalse(should_send)
        self.assertTrue(message)

    @override_settings(DEBUG=False, REPANIER_SETTINGS_BCC_ALL_EMAIL_TO="")
    def test_smtp_completion_does_not_undo_hard_bounce(self):
        def send_and_bounce(message):
            self.post(
                "hard_bounce", **{"message-id": message.extra_headers["Message-ID"]}
            )
            return 1

        email = RepanierEmail(
            subject="Test", html_body="Hello", to=["member@example.org"],
            show_customer_may_unsubscribe=False, send_even_if_unsubscribed=True,
        )
        with patch.object(RepanierEmail, "send", send_and_bounce):
            email.send_email()
        self.customer.refresh_from_db()
        log = EmailLog.objects.get(message_id=email.extra_headers["Message-ID"])
        self.assertFalse(self.customer.valid_email)
        self.assertEqual(log.status, EmailDeliveryStatus.HARD_BOUNCE)
