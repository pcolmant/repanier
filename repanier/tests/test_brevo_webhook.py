import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
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

    def test_success_validates_current_address(self):
        for event in ("delivered", "opened"):
            with self.subTest(event=event):
                Customer.objects.filter(pk=self.customer.pk).update(valid_email=False)
                self.post(event)
                self.customer.refresh_from_db()
                self.assertTrue(self.customer.valid_email)

    def test_soft_bounce_leaves_current_validity_unchanged(self):
        Customer.objects.filter(pk=self.customer.pk).update(valid_email=None)
        self.post("soft_bounce")
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.valid_email)

    def test_delayed_result_for_older_message_preserves_newer_result(self):
        newer = EmailLog.objects.create(
            customer=self.customer,
            recipient_email=self.log.recipient_email,
            message_id="<newer@example.org>",
        )
        self.post("hard_bounce", **{"message-id": newer.message_id})
        self.post("delivered")
        self.customer.refresh_from_db()
        self.log.refresh_from_db()
        self.assertFalse(self.customer.valid_email)
        self.assertEqual(self.log.status, EmailDeliveryStatus.DELIVERED)

    @override_settings(DEBUG=False, REPANIER_SETTINGS_BCC_ALL_EMAIL_TO="")
    def test_smtp_acceptance_leaves_current_validity_unchanged(self):
        Customer.objects.filter(pk=self.customer.pk).update(valid_email=False)
        email = RepanierEmail(
            subject="Test",
            html_body="Hello",
            to=["member@example.org"],
            send_even_if_unsubscribed=True,
        )
        with patch.object(RepanierEmail, "send", return_value=1):
            email.send_email()
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.valid_email)

    def test_customer_save_preserves_validity_without_an_address_change(self):
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.valid_email)

    def test_address_change_resets_validity_even_if_stale_customer_is_saved(self):
        user = self.customer.user
        user.email = "new@example.org"
        user.save(update_fields=["email"])
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.valid_email)

    def test_permanent_failures_and_spam_unsubscribe_without_resubscribing(self):
        for event in ("hard_bounce", "invalid_email", "blocked", "spam"):
            with self.subTest(event=event):
                Customer.objects.filter(pk=self.customer.pk).update(
                    valid_email=True, subscribe_to_email=True
                )
                failed_log = EmailLog.objects.create(
                    customer=self.customer,
                    recipient_email=self.log.recipient_email,
                    message_id=f"<failed-{event}@example.org>",
                )
                self.post(event, **{"message-id": failed_log.message_id})
                self.customer.refresh_from_db()
                self.assertFalse(self.customer.subscribe_to_email)
                self.assertEqual(self.customer.valid_email, event == "spam")

                newer_log = EmailLog.objects.create(
                    customer=self.customer,
                    recipient_email=self.log.recipient_email,
                    message_id=f"<{event}@example.org>",
                )
                self.post("delivered", **{"message-id": newer_log.message_id})
                self.customer.refresh_from_db()
                self.assertFalse(self.customer.subscribe_to_email)
                self.assertTrue(self.customer.valid_email)

    def test_admin_can_correct_address_and_resubscribe_after_brevo_bounce(self):
        self.assertEqual(self.post("hard_bounce").status_code, 204)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.valid_email)
        self.assertFalse(self.customer.subscribe_to_email)

        corrected_address = "corrected@example.org"
        request = RequestFactory().post("/", {
            "short_basket_name": self.customer.short_basket_name,
            "email": corrected_address,
            "language": self.customer.language,
            "subscribe_to_email": "on",
            "price_list_multiplier": self.customer.price_list_multiplier,
            "membership_fee_valid_until": self.customer.membership_fee_valid_until.isoformat(),
        })
        request.user = User(is_active=True, is_staff=True)
        request.user.is_order_manager = True
        request.user.is_invoice_manager = False
        customer_admin = admin.site._registry[Customer]
        form_class = customer_admin.get_form(request, self.customer, change=True)
        form = form_class(request.POST, instance=self.customer)
        self.assertTrue(form.is_valid(), form.errors)
        customer = customer_admin.save_form(request, form, change=True)
        customer_admin.save_model(request, customer, form, change=True)

        customer.refresh_from_db()
        self.assertEqual(customer.user.email, corrected_address)
        self.assertTrue(customer.subscribe_to_email)
        self.assertIsNone(customer.valid_email)

    def test_anonymizing_a_subscribed_customer_unsubscribes_them(self):
        self.customer.may_order = False
        self.customer.subscribe_to_email = True
        self.customer.save(update_fields=["may_order", "subscribe_to_email"])
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.subscribe_to_email)

        self.customer.anonymize()

        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_anonymized)
        self.assertFalse(self.customer.subscribe_to_email)
        self.assertIs(self.customer.valid_email, False)

    def test_matching_hard_bounce_invalidates_current_address(self):
        self.post("hard_bounce", reason="Unknown mailbox")
        self.customer.refresh_from_db()
        self.log.refresh_from_db()
        self.assertFalse(self.customer.valid_email)
        self.assertEqual(self.log.error_reason, "Unknown mailbox")

    def test_old_address_bounce_does_not_invalidate_new_address(self):
        Customer.objects.filter(pk=self.customer.pk).update(subscribe_to_email=True)
        User.objects.filter(pk=self.customer.user_id).update(email="new@example.org")
        self.post("hard_bounce")
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.valid_email)
        self.assertTrue(self.customer.subscribe_to_email)

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
