from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse


class PollModelTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="poll-model-member",
            email="poll-model@example.com",
            password="test-password",
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Poll model member",
        )

    def test_poll_without_deadline_is_open(self):
        self.assertTrue(Poll.objects.create(title="No deadline").is_open)

    def test_poll_with_future_deadline_is_open(self):
        poll = Poll.objects.create(
            title="Future deadline",
            deadline=timezone.now() + timedelta(days=1),
        )

        self.assertTrue(poll.is_open)

    def test_poll_with_past_deadline_is_closed(self):
        poll = Poll.objects.create(
            title="Past deadline",
            deadline=timezone.now() - timedelta(seconds=1),
        )

        self.assertFalse(poll.is_open)

    def test_deadline_is_inclusive_at_the_current_time(self):
        deadline = timezone.now()
        poll = Poll.objects.create(title="Deadline now", deadline=deadline)

        with patch("repanier.models.poll.timezone.now", return_value=deadline):
            self.assertTrue(poll.is_open)

    def test_choices_are_ordered_by_order_then_primary_key(self):
        poll = Poll.objects.create(title="Ordered choices")
        later = PollChoice.objects.create(poll=poll, label="Later", order=2)
        first = PollChoice.objects.create(poll=poll, label="First", order=1)
        tied = PollChoice.objects.create(poll=poll, label="Tied", order=1)

        self.assertEqual(list(poll.choices.all()), [first, tied, later])

    def test_customer_can_only_have_one_response_per_poll(self):
        poll = Poll.objects.create(title="Unique response")
        PollResponse.objects.create(poll=poll, customer=self.customer)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PollResponse.objects.create(poll=poll, customer=self.customer)

    def test_response_token_is_unique_and_not_editable(self):
        poll = Poll.objects.create(title="Unique token")
        first = PollResponse.objects.create(poll=poll, customer=self.customer)
        other_user = User.objects.create_user(
            username="poll-model-other",
            email="poll-model-other@example.com",
            password="test-password",
        )
        other_customer = Customer.objects.create(
            user=other_user,
            short_basket_name="Other member",
        )
        second = PollResponse.objects.create(poll=poll, customer=other_customer)

        self.assertNotEqual(first.token, second.token)
        self.assertFalse(PollResponse._meta.get_field("token").editable)
