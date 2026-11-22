from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import Http404
from django.http import HttpResponse
from django.template.loader import get_template
from django.test import RequestFactory, TestCase
from django.utils import timezone

from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse
from repanier.views.poll import poll_vote


class PollVoteTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="poll-voter",
            email="poll-voter@example.com",
            password="test-password",
        )
        customer = Customer.objects.create(user=user, short_basket_name="Poll voter")
        self.poll = Poll.objects.create(title="Poll test")
        self.response = PollResponse.objects.create(poll=self.poll, customer=customer)
        self.factory = RequestFactory()

    def request(self, method="get", data=None):
        request = getattr(self.factory, method)("/", data or {})
        request.user = AnonymousUser()
        request.session = {}
        request._messages = []
        return request

    def vote(self, request):
        response = HttpResponse()
        with patch("repanier.views.poll.render", return_value=response) as render:
            result = poll_vote(request, self.response.token)
        return result, render.call_args.args[2]

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=False)
    def test_feature_disabled_returns_404(self, _enabled):
        with self.assertRaises(Http404):
            poll_vote(self.request(), self.response.token)

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_unknown_token_returns_404(self, _enabled):
        with self.assertRaises(Http404):
            poll_vote(self.request(), "00000000-0000-0000-0000-000000000000")

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_get_displays_poll_description_and_choice_options(self, _enabled):
        self.poll.description = "<p>Context for the poll</p>"
        self.poll.save(update_fields=["description"])
        first = PollChoice.objects.create(poll=self.poll, label="First", order=1)
        second = PollChoice.objects.create(poll=self.poll, label="Second", order=2)

        result, context = self.vote(self.request())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(context["poll"], self.poll)
        self.assertEqual(context["choices"], [first, second])
        self.assertFalse(context["allow_multiple"])
        self.assertFalse(context["closed"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_get_open_ended_poll_shows_required_response_without_choices(self, _enabled):
        result, context = self.vote(self.request())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(context["choices"], [])
        self.assertFalse(context["has_choices"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_post_accepts_a_choice_without_optional_comment(self, _enabled):
        choice = PollChoice.objects.create(poll=self.poll, label="Yes")

        result, context = self.vote(
            self.request("post", {"choices": str(choice.pk)})
        )

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["saved"])
        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, choice)
        self.assertEqual(self.response.comment, "")
        self.assertTrue(self.response.choices.filter(pk=choice.pk).exists())
        self.assertIsNotNone(self.response.answered_at)

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_multiple_choice_poll_saves_all_choices_and_first_primary_choice(
        self, _enabled
    ):
        self.poll.allow_multiple = True
        self.poll.save(update_fields=["allow_multiple"])
        first = PollChoice.objects.create(poll=self.poll, label="First", order=1)
        second = PollChoice.objects.create(poll=self.poll, label="Second", order=2)

        result, context = self.vote(
            self.request(
                "post",
                {"choices": [str(first.pk), str(second.pk)], "comment": "Details"},
            ),
        )

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["saved"])
        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, first)
        self.assertCountEqual(
            self.response.choices.values_list("pk", flat=True), [first.pk, second.pk]
        )
        self.assertEqual(self.response.comment, "Details")

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_single_choice_poll_uses_only_first_selected_choice(self, _enabled):
        first = PollChoice.objects.create(poll=self.poll, label="First", order=1)
        second = PollChoice.objects.create(poll=self.poll, label="Second", order=2)

        self.vote(self.request("post", {"choices": [str(first.pk), str(second.pk)]}))

        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, first)
        self.assertEqual(list(self.response.choices.all()), [first])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_missing_choice_does_not_save_even_with_comment(self, _enabled):
        PollChoice.objects.create(poll=self.poll, label="Yes")

        result, context = self.vote(
            self.request("post", {"comment": "A comment alone is not a vote"})
        )

        self.response.refresh_from_db()
        self.assertIsNone(self.response.answered_at)
        self.assertFalse(context["saved"])
        self.assertIsNotNone(context["error_message"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_invalid_or_foreign_choice_ids_are_ignored(self, _enabled):
        PollChoice.objects.create(poll=self.poll, label="Yes")
        other_poll = Poll.objects.create(title="Another poll")
        foreign_choice = PollChoice.objects.create(poll=other_poll, label="Foreign")

        result, context = self.vote(
            self.request("post", {"choices": str(foreign_choice.pk)})
        )

        self.assertEqual(result.status_code, 200)
        self.response.refresh_from_db()
        self.assertIsNone(self.response.answered_at)
        self.assertIsNotNone(context["error_message"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_invalid_submission_does_not_overwrite_existing_response(self, _enabled):
        choice = PollChoice.objects.create(poll=self.poll, label="Yes")
        old_answered_at = timezone.now() - timedelta(hours=1)
        self.response.choice = choice
        self.response.comment = "Existing comment"
        self.response.answered_at = old_answered_at
        self.response.save()
        self.response.choices.set([choice])

        self.vote(self.request("post", {"comment": "Invalid replacement"}))

        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, choice)
        self.assertEqual(self.response.comment, "Existing comment")
        self.assertEqual(self.response.answered_at, old_answered_at)

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_member_can_update_an_existing_answer_before_deadline(self, _enabled):
        first = PollChoice.objects.create(poll=self.poll, label="First")
        second = PollChoice.objects.create(poll=self.poll, label="Second")
        self.response.choice = first
        self.response.comment = "Old comment"
        self.response.answered_at = timezone.now() - timedelta(hours=1)
        self.response.save()
        self.response.choices.set([first])

        self.vote(
            self.request("post", {"choices": str(second.pk), "comment": "Updated"})
        )

        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, second)
        self.assertEqual(self.response.comment, "Updated")
        self.assertEqual(list(self.response.choices.all()), [second])
        self.assertGreater(self.response.answered_at, timezone.now() - timedelta(minutes=1))

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_closed_poll_is_read_only_even_when_posted(self, _enabled):
        choice = PollChoice.objects.create(poll=self.poll, label="Yes")
        self.poll.deadline = timezone.now() - timedelta(seconds=1)
        self.poll.save(update_fields=["deadline"])
        self.response.choice = choice
        self.response.comment = "Saved answer"
        self.response.answered_at = timezone.now() - timedelta(hours=1)
        self.response.save()
        self.response.choices.set([choice])

        result, context = self.vote(
            self.request("post", {"comment": "Replacement", "choices": ""})
        )

        self.assertEqual(result.status_code, 200)
        self.response.refresh_from_db()
        self.assertTrue(context["closed"])
        self.assertEqual(self.response.choice, choice)
        self.assertEqual(self.response.comment, "Saved answer")

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_closed_unanswered_poll_displays_no_response_message(self, _enabled):
        self.poll.deadline = timezone.now() - timedelta(seconds=1)
        self.poll.save(update_fields=["deadline"])

        result, context = self.vote(self.request())

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["closed"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_closed_open_ended_poll_shows_saved_comment_as_response(self, _enabled):
        self.poll.deadline = timezone.now() - timedelta(seconds=1)
        self.poll.save(update_fields=["deadline"])
        self.response.comment = "My recorded response"
        self.response.answered_at = timezone.now() - timedelta(hours=1)
        self.response.save(update_fields=["comment", "answered_at"])

        result, context = self.vote(self.request())

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["closed"])
        self.assertEqual(context["poll_response"].comment, "My recorded response")

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_preexisting_single_choice_response_is_marked_selected(self, _enabled):
        choice = PollChoice.objects.create(poll=self.poll, label="Yes")
        self.response.choice = choice
        self.response.answered_at = timezone.now()
        self.response.save(update_fields=["choice", "answered_at"])

        result, context = self.vote(self.request())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(context["selected_choices"], [choice])

    def test_poll_response_template_compiles(self):
        self.assertIsNotNone(get_template("repanier/poll_confirm.html"))
