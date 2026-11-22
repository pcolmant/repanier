from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse
from repanier.views.poll import poll_vote


class PollOpenEndedResponseTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="poll-member",
            email="poll-member@example.com",
            password="test-password",
        )
        customer = Customer.objects.create(
            user=user,
            short_basket_name="Poll member",
        )
        poll = Poll.objects.create(title="Open discussion")
        self.response = PollResponse.objects.create(poll=poll, customer=customer)
        self.factory = RequestFactory()

    def post(self, data):
        request = self.factory.post("/", data)
        request.user = AnonymousUser()
        request.session = {}
        request._messages = []
        return request

    def vote(self, request):
        response = HttpResponse()
        with patch("repanier.views.poll.render", return_value=response) as render:
            result = poll_vote(request, self.response.token)
        return result, render.call_args.args[2]

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_comment_is_a_complete_response_when_poll_has_no_choices(self, _enabled):
        request = self.post({"comment": "I support this proposal."})

        result, context = self.vote(request)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["saved"])
        self.response.refresh_from_db()
        self.assertEqual(self.response.comment, "I support this proposal.")
        self.assertIsNone(self.response.choice)
        self.assertIsNotNone(self.response.answered_at)

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_open_ended_response_cannot_be_empty(self, _enabled):
        request = self.post({"comment": "   "})

        result, context = self.vote(request)

        self.assertEqual(result.status_code, 200)
        self.response.refresh_from_db()
        self.assertIsNone(self.response.answered_at)
        self.assertFalse(context["saved"])
        self.assertIsNotNone(context["error_message"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_poll_with_choices_still_requires_a_choice(self, _enabled):
        PollChoice.objects.create(poll=self.response.poll, label="Yes")
        request = self.post({"comment": "I would choose yes."})

        result, context = self.vote(request)

        self.assertEqual(result.status_code, 200)
        self.response.refresh_from_db()
        self.assertIsNone(self.response.answered_at)
        self.assertFalse(context["saved"])
        self.assertIsNotNone(context["error_message"])

    @patch("repanier.views.poll.is_new_poll_enabled", return_value=True)
    def test_poll_with_choices_still_accepts_a_selected_choice(self, _enabled):
        choice = PollChoice.objects.create(poll=self.response.poll, label="Yes")
        request = self.post({"choices": str(choice.pk), "comment": "With a comment."})

        result, context = self.vote(request)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(context["saved"])
        self.response.refresh_from_db()
        self.assertEqual(self.response.choice, choice)
        self.assertEqual(self.response.comment, "With a comment.")
        self.assertIsNotNone(self.response.answered_at)
