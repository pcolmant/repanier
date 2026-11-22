from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import translation
from django.utils import timezone

from repanier.admin.poll import (
    _render_invitation_for_customer,
    _reserve_poll_email_send,
    _send_poll_emails_worker,
)
from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollResponse


class PollEmailWorkerTest(TestCase):
    def setUp(self):
        self.poll = Poll.objects.create(title="Poll invitation")
        self.eligible = self.create_customer("eligible")
        self.unsubscribed = self.create_customer("unsubscribed", subscribe_to_email=False)
        self.cannot_order = self.create_customer("cannot-order", may_order=False)
        self.inactive = self.create_customer("inactive", is_active=False)
        self.buying_group = self.create_customer(
            "buying-group", represent_this_buyinggroup=True
        )

    def create_customer(self, name, **kwargs):
        user = User.objects.create_user(
            username=name,
            email=f"{name}@example.com",
            password="test-password",
        )
        return Customer.objects.create(
            user=user,
            short_basket_name=name,
            **kwargs,
        )

    def reserve(self):
        return _reserve_poll_email_send(self.poll.pk)

    @staticmethod
    def email_result(address="recipient@example.com"):
        email = Mock()
        email.send_email.return_value = {address}
        return email

    @patch("repanier.admin.poll.render_to_string", return_value="<p>Invitation</p>")
    @patch("repanier.admin.poll.reverse", return_value="/poll/token/")
    def test_invitation_builds_member_specific_link_and_email(
        self, reverse_url, render_template
    ):
        response = PollResponse.objects.create(
            poll=self.poll,
            customer=self.eligible,
        )

        email = _render_invitation_for_customer(
            self.eligible,
            self.poll,
            response,
            "https://example.com/",
        )

        self.assertEqual(email.subject, self.poll.title)
        self.assertEqual(email.to, [self.eligible.user.email])
        self.assertEqual(email.html_body, "<p>Invitation</p>")
        reverse_url.assert_called_once_with(
            "repanier:poll_vote", kwargs={"token": str(response.token)}
        )
        self.assertEqual(
            render_template.call_args.args[1]["form_url"],
            "https://example.com/poll/token/",
        )

    @patch("repanier.admin.poll.render_to_string", return_value="<p>Reminder</p>")
    @patch("repanier.admin.poll.reverse", return_value="/poll/token/")
    def test_reminder_uses_reminder_subject_and_context(self, _reverse_url, render_template):
        response = PollResponse.objects.create(
            poll=self.poll,
            customer=self.eligible,
        )

        with translation.override(self.eligible.language):
            email = _render_invitation_for_customer(
                self.eligible,
                self.poll,
                response,
                "https://example.com",
                is_reminder=True,
            )

        self.assertTrue(email.subject.startswith("["))
        self.assertTrue(email.subject.endswith(self.poll.title))
        self.assertTrue(render_template.call_args.args[1]["is_reminder"])

    @patch("repanier.admin.poll.render_to_string")
    def test_invitation_is_not_built_without_a_member_email(self, render_template):
        self.eligible.user.email = ""
        response = PollResponse.objects.create(
            poll=self.poll,
            customer=self.eligible,
        )

        email = _render_invitation_for_customer(
            self.eligible,
            self.poll,
            response,
            "https://example.com/",
        )

        self.assertIsNone(email)
        render_template.assert_not_called()

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_invitation_sends_only_to_active_subscribed_members_who_may_order(
        self, render_invitation
    ):
        render_invitation.return_value = self.email_result()
        lease = self.reserve()

        _send_poll_emails_worker(
            self.poll.pk,
            "https://example.com/",
            mark_sent=True,
            lease_started_at=lease,
        )

        self.assertEqual(render_invitation.call_count, 1)
        render_invitation.assert_called_once()
        self.assertEqual(render_invitation.call_args.args[0], self.eligible)
        self.assertEqual(
            list(
                PollResponse.objects.filter(poll=self.poll).values_list(
                    "customer_id", flat=True
                )
            ),
            [self.eligible.pk],
        )
        self.poll.refresh_from_db()
        self.assertIsNotNone(self.poll.sent_at)
        self.assertIsNone(self.poll.email_send_started_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_failed_delivery_does_not_mark_invitation_as_sent(self, render_invitation):
        email = self.email_result()
        email.send_email.return_value = set()
        render_invitation.return_value = email
        lease = self.reserve()

        _send_poll_emails_worker(
            self.poll.pk,
            "https://example.com/",
            mark_sent=True,
            lease_started_at=lease,
        )

        self.poll.refresh_from_db()
        self.assertIsNone(self.poll.sent_at)
        self.assertIsNone(self.poll.email_send_started_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_successful_invitation_to_one_member_marks_poll_sent(self, render_invitation):
        render_invitation.return_value = self.email_result()
        lease = self.reserve()

        _send_poll_emails_worker(
            self.poll.pk,
            "https://example.com/",
            only_customer_id=self.eligible.pk,
            mark_sent=True,
            lease_started_at=lease,
        )

        self.assertEqual(PollResponse.objects.filter(poll=self.poll).count(), 1)
        self.poll.refresh_from_db()
        self.assertIsNone(self.poll.sent_at)
        self.assertIsNone(self.poll.email_send_started_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_reminder_only_targets_unanswered_subscribed_non_group_responses(
        self, render_invitation
    ):
        unanswered = [
            PollResponse.objects.create(poll=self.poll, customer=self.eligible),
            PollResponse.objects.create(poll=self.poll, customer=self.unsubscribed),
            PollResponse.objects.create(poll=self.poll, customer=self.cannot_order),
            PollResponse.objects.create(poll=self.poll, customer=self.inactive),
            PollResponse.objects.create(poll=self.poll, customer=self.buying_group),
        ]
        answered_at = timezone.now()
        unanswered[2].answered_at = answered_at
        unanswered[2].save(update_fields=["answered_at"])
        render_invitation.return_value = self.email_result()
        lease = self.reserve()

        _send_poll_emails_worker(
            self.poll.pk,
            "https://example.com/",
            is_reminder=True,
            lease_started_at=lease,
        )

        self.assertEqual(render_invitation.call_count, 2)
        self.assertCountEqual(
            [call.args[0].pk for call in render_invitation.call_args_list],
            [self.eligible.pk, self.inactive.pk],
        )
        self.assertTrue(
            all(call.kwargs["is_reminder"] for call in render_invitation.call_args_list)
        )
        self.poll.refresh_from_db()
        self.assertIsNone(self.poll.sent_at)
        self.assertIsNone(self.poll.email_send_started_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_debug_mode_stops_after_first_success(self, render_invitation):
        render_invitation.return_value = self.email_result()
        lease = self.reserve()

        _send_poll_emails_worker(
            self.poll.pk,
            "https://example.com/",
            mark_sent=True,
            stop_on_first_in_debug=True,
            lease_started_at=lease,
        )

        render_invitation.assert_called_once()
        self.poll.refresh_from_db()
        self.assertIsNotNone(self.poll.sent_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_worker_failure_releases_its_poll_lock(self, render_invitation):
        render_invitation.side_effect = RuntimeError("render failed")
        lease = self.reserve()

        with self.assertRaisesMessage(RuntimeError, "render failed"):
            _send_poll_emails_worker(
                self.poll.pk,
                "https://example.com/",
                only_customer_id=self.eligible.pk,
                lease_started_at=lease,
            )

        self.poll.refresh_from_db()
        self.assertIsNone(self.poll.email_send_started_at)

    @patch("repanier.admin.poll._render_invitation_for_customer")
    def test_worker_without_matching_lease_does_not_send(self, render_invitation):
        _send_poll_emails_worker(self.poll.pk, "https://example.com/")

        render_invitation.assert_not_called()
        self.assertFalse(PollResponse.objects.filter(poll=self.poll).exists())
