from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from repanier.admin.poll import (
    POLL_SEND_LEASE,
    _refresh_poll_email_send,
    _release_poll_email_send,
    _reserve_poll_email_send,
)
from repanier.models.poll import Poll


class PollEmailTaskLockTest(TestCase):
    def setUp(self):
        self.poll = Poll.objects.create(title="Test poll")

    def test_only_one_active_email_task_can_reserve_a_poll(self):
        lease = _reserve_poll_email_send(self.poll.pk)

        self.assertIsNotNone(lease)
        self.assertIsNone(_reserve_poll_email_send(self.poll.pk))

    def test_expired_lock_can_be_reclaimed_without_old_owner_releasing_it(self):
        expired_lease = timezone.now() - POLL_SEND_LEASE - timedelta(seconds=1)
        Poll.objects.filter(pk=self.poll.pk).update(
            email_send_started_at=expired_lease
        )

        new_lease = _reserve_poll_email_send(self.poll.pk)

        self.assertIsNotNone(new_lease)
        _release_poll_email_send(self.poll.pk, expired_lease)
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.email_send_started_at, new_lease)

    def test_worker_can_refresh_and_release_its_lease(self):
        lease = _reserve_poll_email_send(self.poll.pk)
        refreshed_lease = _refresh_poll_email_send(self.poll.pk, lease)

        self.assertIsNotNone(refreshed_lease)
        _release_poll_email_send(self.poll.pk, refreshed_lease)
        self.poll.refresh_from_db()
        self.assertIsNone(self.poll.email_send_started_at)
