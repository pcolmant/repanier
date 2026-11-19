import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from repanier.const import EmailDeliveryStatus
from repanier.models.emaillog import EmailLog


class Command(BaseCommand):
    help = "Purge old EmailLog entries while keeping anomalies longer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=6,
            help="Retention in months for normal email logs (default: 6).",
        )
        parser.add_argument(
            "--anomaly-months",
            type=int,
            default=18,
            help="Retention in months for bounce/spam/error logs (default: 18).",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        normal_cutoff = now - datetime.timedelta(days=options["months"] * 30)
        anomaly_cutoff = now - datetime.timedelta(days=options["anomaly_months"] * 30)

        anomaly_statuses = [
            EmailDeliveryStatus.SEND_ERROR,
            EmailDeliveryStatus.HARD_BOUNCE,
            EmailDeliveryStatus.BLOCKED,
            EmailDeliveryStatus.SPAM,
        ]

        deleted_normal, _ = EmailLog.objects.filter(
            created_at__lt=normal_cutoff
        ).exclude(status__in=anomaly_statuses).delete()

        deleted_anomalies, _ = EmailLog.objects.filter(
            created_at__lt=anomaly_cutoff,
            status__in=anomaly_statuses,
        ).delete()

        self.stdout.write(
            f"Deleted {deleted_normal} normal log(s) and {deleted_anomalies} anomaly log(s)."
        )