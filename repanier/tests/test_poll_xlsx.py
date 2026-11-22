from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django.utils import translation
from openpyxl import load_workbook

from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse
from repanier.xlsx.xlsx_poll import export_poll_xlsx


class PollXlsxExportTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="poll-export-member",
            email="poll-export@example.com",
            password="test-password",
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Export member",
        )

    def workbook_for(self, poll):
        with translation.override("en"):
            response = export_poll_xlsx(poll)
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        return response, workbook.active

    def test_open_ended_poll_export_includes_response_counts_and_comments(self):
        poll = Poll.objects.create(title="Open discussion")
        answered = PollResponse.objects.create(
            poll=poll,
            customer=self.customer,
            comment="I support the proposal.",
            answered_at=timezone.now(),
        )
        unanswered_user = User.objects.create_user(
            username="poll-export-unanswered",
            email="poll-export-unanswered@example.com",
            password="test-password",
        )
        unanswered_customer = Customer.objects.create(
            user=unanswered_user,
            short_basket_name="No response",
        )
        PollResponse.objects.create(poll=poll, customer=unanswered_customer)

        response, sheet = self.workbook_for(poll)

        self.assertIn("application/vnd.openxmlformats", response["Content-Type"])
        self.assertEqual(sheet["A7"].value, "Responses received")
        self.assertEqual(sheet["B7"].value, 1)
        self.assertEqual(sheet["C7"].value, "50.0%")
        self.assertEqual(sheet["A8"].value, "No response yet")
        self.assertEqual(sheet["B8"].value, 1)
        self.assertEqual(sheet["C12"].value, "Open-ended response")
        self.assertEqual(sheet["D12"].value, answered.comment)
        self.assertEqual(sheet["C13"].value, "No response yet")

    def test_choice_poll_export_includes_votes_and_unanswered_count(self):
        poll = Poll.objects.create(title="Choice poll")
        first = PollChoice.objects.create(poll=poll, label="First")
        PollChoice.objects.create(poll=poll, label="Second")
        response = PollResponse.objects.create(
            poll=poll,
            customer=self.customer,
            choice=first,
            answered_at=timezone.now(),
        )
        response.choices.set([first])

        _http_response, sheet = self.workbook_for(poll)

        self.assertEqual(sheet["A7"].value, "First")
        self.assertEqual(sheet["B7"].value, 1)
        self.assertEqual(sheet["A8"].value, "Second")
        self.assertEqual(sheet["B8"].value, 0)
        self.assertEqual(sheet["A9"].value, "No response yet")
        self.assertEqual(sheet["B9"].value, 0)
        self.assertEqual(sheet["C13"].value, "First")

    def test_export_with_no_invited_members_avoids_division_by_zero(self):
        poll = Poll.objects.create(title="No invitees")
        PollChoice.objects.create(poll=poll, label="First")

        _http_response, sheet = self.workbook_for(poll)

        self.assertEqual(sheet["B7"].value, 0)
        self.assertEqual(sheet["C7"].value, "0%")
        self.assertEqual(sheet["B8"].value, 0)

    def test_multiple_choice_export_counts_every_selected_choice(self):
        poll = Poll.objects.create(title="Multiple choices", allow_multiple=True)
        first = PollChoice.objects.create(poll=poll, label="First")
        second = PollChoice.objects.create(poll=poll, label="Second")
        response = PollResponse.objects.create(
            poll=poll,
            customer=self.customer,
            choice=first,
            answered_at=timezone.now(),
        )
        response.choices.set([first, second])

        _http_response, sheet = self.workbook_for(poll)

        self.assertEqual(sheet["B7"].value, 1)
        self.assertEqual(sheet["B8"].value, 1)
