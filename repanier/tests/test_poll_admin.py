from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from repanier.admin.poll import MIN_DELETE_AGE, PollAdmin
from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse


class PollAdminTest(TestCase):
    def setUp(self):
        self.admin = PollAdmin(Poll, admin.site)
        self.admin.message_user = Mock()
        self.factory = RequestFactory()
        user = User.objects.create_user(
            username="poll-admin-test-member",
            email="poll-admin-test@example.com",
            password="test-password",
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Poll admin member",
        )

    def request(self):
        request = self.factory.post("/admin/")
        request.user = SimpleNamespace(customer_id=self.customer.pk)
        return request

    def test_send_actions_accept_open_ended_polls(self):
        action_cases = (
            ("send_test_poll_to_me", "poll-test-email-"),
            ("send_poll_emails", "poll-invitation-"),
            ("remind_unanswered_members", "poll-reminder-"),
        )
        for action_name, expected_task_prefix in action_cases:
            with self.subTest(action=action_name):
                poll = Poll.objects.create(title=f"Poll {action_name}")
                action = getattr(self.admin, action_name)
                with (
                    patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
                    patch("repanier.admin.poll.start_background_task") as start_task,
                ):
                    action(self.request(), Poll.objects.filter(pk=poll.pk))

                self.assertEqual(start_task.call_count, 1)
                self.assertTrue(
                    start_task.call_args.args[0].startswith(expected_task_prefix)
                )
                poll.refresh_from_db()
                self.assertIsNotNone(poll.email_send_started_at)

    def test_send_actions_reject_a_poll_with_only_one_choice(self):
        action_names = (
            "send_test_poll_to_me",
            "send_poll_emails",
            "remind_unanswered_members",
        )
        for action_name in action_names:
            with self.subTest(action=action_name):
                poll = Poll.objects.create(title=f"One choice {action_name}")
                PollChoice.objects.create(poll=poll, label="Only choice")
                with (
                    patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
                    patch("repanier.admin.poll.start_background_task") as start_task,
                ):
                    getattr(self.admin, action_name)(
                        self.request(), Poll.objects.filter(pk=poll.pk)
                    )

                start_task.assert_not_called()
                poll.refresh_from_db()
                self.assertIsNone(poll.email_send_started_at)

    def test_send_action_requires_exactly_one_poll(self):
        first = Poll.objects.create(title="First")
        second = Poll.objects.create(title="Second")

        with (
            patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
            patch("repanier.admin.poll.start_background_task") as start_task,
        ):
            self.admin.send_poll_emails(
                self.request(), Poll.objects.filter(pk__in=[first.pk, second.pk])
            )

        start_task.assert_not_called()

    def test_poll_with_two_choices_can_be_sent(self):
        poll = Poll.objects.create(title="Valid choice poll")
        PollChoice.objects.create(poll=poll, label="Yes")
        PollChoice.objects.create(poll=poll, label="No")

        with (
            patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
            patch("repanier.admin.poll.start_background_task") as start_task,
        ):
            self.admin.send_poll_emails(
                self.request(), Poll.objects.filter(pk=poll.pk)
            )

        start_task.assert_called_once()

    def test_poll_admin_permissions_are_disabled_with_poll_feature(self):
        request = self.factory.get("/admin/")
        request.user = User(is_active=True, is_staff=True, is_superuser=True)
        poll = Poll.objects.create(title="Feature disabled")

        with patch("repanier.admin.poll.is_new_poll_enabled", return_value=False):
            self.assertFalse(self.admin.has_module_permission(request))
            self.assertFalse(self.admin.has_view_permission(request, poll))
            self.assertFalse(self.admin.has_add_permission(request))
            self.assertFalse(self.admin.has_change_permission(request, poll))
            self.assertFalse(self.admin.has_delete_permission(request, poll))

    def test_reminder_action_rejects_closed_poll(self):
        poll = Poll.objects.create(
            title="Closed",
            deadline=timezone.now() - timedelta(seconds=1),
        )

        with (
            patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
            patch("repanier.admin.poll.start_background_task") as start_task,
        ):
            self.admin.remind_unanswered_members(
                self.request(), Poll.objects.filter(pk=poll.pk)
            )

        start_task.assert_not_called()

    def test_export_action_requires_one_poll_and_returns_xlsx_response(self):
        poll = Poll.objects.create(title="Export")
        export_response = object()
        with (
            patch("repanier.admin.poll.is_new_poll_enabled", return_value=True),
            patch(
                "repanier.admin.poll.export_poll_xlsx",
                return_value=export_response,
            ) as export,
        ):
            result = self.admin.export_results_xlsx(
                self.request(), Poll.objects.filter(pk=poll.pk)
            )
            self.assertIs(result, export_response)
            export.assert_called_once_with(poll)

            result = self.admin.export_results_xlsx(
                self.request(), Poll.objects.none()
            )
            self.assertIsNone(result)
            export.assert_called_once()

    @patch("repanier.admin.poll.is_new_poll_enabled", return_value=True)
    def test_results_summary_for_open_ended_poll_counts_answers(self, _enabled):
        poll = Poll.objects.create(title="Open discussion")
        answered = PollResponse.objects.create(
            poll=poll,
            customer=self.customer,
            comment="I agree",
            answered_at=timezone.now(),
        )
        another_user = User.objects.create_user(
            username="poll-unanswered",
            email="poll-unanswered@example.com",
            password="test-password",
        )
        another_customer = Customer.objects.create(
            user=another_user,
            short_basket_name="Unanswered",
        )
        PollResponse.objects.create(poll=poll, customer=another_customer)

        summary = str(self.admin.results_board(poll))

        self.assertIn("1 / 2", summary)
        self.assertIn("1", summary)
        self.assertEqual(answered.comment, "I agree")

    def test_choice_results_count_multiple_votes_correctly(self):
        poll = Poll.objects.create(title="Multiple choice results", allow_multiple=True)
        first = PollChoice.objects.create(poll=poll, label="First")
        second = PollChoice.objects.create(poll=poll, label="Second")
        response = PollResponse.objects.create(
            poll=poll,
            customer=self.customer,
            choice=first,
            answered_at=timezone.now(),
        )
        response.choices.set([first, second])

        summary = str(self.admin.results_board(poll))

        self.assertIn("First", summary)
        self.assertIn("Second", summary)
        self.assertEqual(summary.count(">1<"), 2)

    def test_poll_cannot_be_deleted_until_one_year_old(self):
        poll = Poll.objects.create(title="Recent poll")
        request = self.factory.get("/admin/")
        request.user = User(is_active=True, is_staff=True, is_superuser=True)

        with patch("repanier.admin.poll.is_new_poll_enabled", return_value=True):
            self.assertFalse(self.admin.has_delete_permission(request, poll))

        Poll.objects.filter(pk=poll.pk).update(
            created_at=timezone.now() - MIN_DELETE_AGE
        )
        poll.refresh_from_db()
        with patch("repanier.admin.poll.is_new_poll_enabled", return_value=True):
            self.assertTrue(self.admin.has_delete_permission(request, poll))
