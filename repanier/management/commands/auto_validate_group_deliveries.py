import datetime
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from repanier.const import PreparationStatus, SaleStatus
from repanier.models.permanence import Permanence
from repanier.models.preparation import PreparationSyncEvent
from repanier.models.purchase import Purchase


def event_quantity_discrepancy(purchase, events):
    for event in events:
        if event.operation not in ("prepare", "receive"):
            continue
        try:
            quantity = Decimal(str(event.payload["quantity"]))
            if not quantity.is_finite() or quantity != purchase.quantity_ordered:
                return "quantity discrepancy recorded in synchronization event"
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return "ambiguous quantity in synchronization event"
    return None


def discrepancy_reason(purchase, events, cutoff):
    handoff = next((e for e in events if e.operation == "hand_to_group"), None)
    received = next((e for e in events if e.operation == "receive"), None)
    if any(e.operation == "parcel_disposition" for e in events):
        return "parcel discrepancy/dispute"
    if purchase.substitution_source_id or purchase.substitution_targets.exists():
        return "substitution requires manual review"
    if handoff is None or received is None:
        return "ambiguous handover or receipt: missing synchronization event"
    handoff_date = (
        timezone.localtime(handoff.server_timestamp).date()
        if timezone.is_aware(handoff.server_timestamp)
        else handoff.server_timestamp.date()
    )
    if handoff_date > cutoff:
        return "handover delay not elapsed"
    if received.server_timestamp > handoff.server_timestamp:
        return "receipt after handover requires manual review"
    if (
        purchase.quantity_received != purchase.quantity_ordered
        or purchase.quantity_prepared != purchase.quantity_ordered
        or purchase.quantity_invoiced != purchase.quantity_ordered
    ):
        return "quantity discrepancy (ordered, prepared, received or invoiced)"
    return event_quantity_discrepancy(purchase, events)


class Command(BaseCommand):
    help = "Validate completed group deliveries after a configurable delay."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=2,
            help="Number of days after distribution before tacit validation.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List candidate permanences without changing them.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 0:
            raise CommandError("--days must be non-negative.")
        dry_run = options["dry_run"]
        now = timezone.now()
        today = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
        cutoff = today - datetime.timedelta(days=days)

        candidate_ids = list(Permanence.objects.filter(
            status=SaleStatus.SEND,
            permanence_date__lte=cutoff,
            is_demo=False,
            preparation_enabled=True,
            purchase__preparation_status=PreparationStatus.HANDED_TO_GROUP,
        ).order_by("id").values_list("id", flat=True).distinct())

        eligible = skipped = blocked = 0
        for permanence_id in candidate_ids:
            with transaction.atomic():
                permanence = Permanence.objects.select_for_update().filter(
                    pk=permanence_id, status=SaleStatus.SEND,
                    permanence_date__lte=cutoff, is_demo=False,
                    preparation_enabled=True,
                ).first()
                if permanence is None:
                    continue
                if permanence.preparation_sync_events.exclude(
                    status=PreparationSyncEvent.STATUS_APPLIED
                ).exists():
                    blocked += 1
                    self.stderr.write(
                        f"Permanence {permanence_id}: pending due to conflict/dispute "
                        "or unapplied synchronization event."
                    )
                    continue
                if permanence.preparation_sync_events.filter(
                    status=PreparationSyncEvent.STATUS_APPLIED,
                    operation="parcel_disposition", purchase__isnull=True,
                ).exists():
                    blocked += 1
                    self.stderr.write(
                        f"Permanence {permanence_id}: pending due to unassigned parcel discrepancy."
                    )
                    continue
                purchases = Purchase.objects.select_for_update().filter(
                    permanence=permanence,
                    preparation_status=PreparationStatus.HANDED_TO_GROUP,
                    customer_invoice__delivery__delivery_point__group__isnull=False,
                )
                groups = defaultdict(list)
                for purchase in purchases.select_related("customer_invoice"):
                    groups[purchase.customer_invoice.delivery_id].append(purchase)
                for delivery_id, group_purchases in groups.items():
                    if permanence.preparation_sync_events.filter(
                        status=PreparationSyncEvent.STATUS_APPLIED,
                        operation="parcel_disposition",
                        purchase__customer_invoice__delivery_id=delivery_id,
                    ).exists():
                        skipped += len(group_purchases)
                        self.stderr.write(
                            f"Permanence {permanence_id}, delivery {delivery_id}: "
                            "pending - parcel discrepancy/dispute."
                        )
                        continue
                    reasons = []
                    other_purchases = Purchase.objects.select_for_update().filter(
                        permanence=permanence, customer_invoice__delivery_id=delivery_id
                    ).exclude(pk__in=[purchase.pk for purchase in group_purchases])
                    for other in other_purchases:
                        if other.preparation_status != PreparationStatus.VALIDATED:
                            reasons.append((other.pk, "ambiguous group line not yet handed over or validated"))
                        elif (
                            other.quantity_received != other.quantity_ordered
                            or other.quantity_prepared != other.quantity_ordered
                            or other.quantity_invoiced != other.quantity_ordered
                        ):
                            reasons.append((other.pk, "quantity discrepancy on validated group line"))
                        elif other.substitution_source_id or other.substitution_targets.exists():
                            reasons.append((other.pk, "substitution requires manual review"))
                        else:
                            events = other.preparation_sync_events.filter(
                                status=PreparationSyncEvent.STATUS_APPLIED,
                                operation__in=["prepare", "receive"],
                            )
                            reason = event_quantity_discrepancy(other, events)
                            if reason:
                                reasons.append((other.pk, reason))
                    for purchase in group_purchases:
                        events = list(purchase.preparation_sync_events.filter(
                            status=PreparationSyncEvent.STATUS_APPLIED,
                            operation__in=["hand_to_group", "receive", "prepare", "parcel_disposition"],
                        ).order_by("-server_timestamp", "-id"))
                        reason = discrepancy_reason(purchase, events, cutoff)
                        if reason:
                            reasons.append((purchase.pk, reason))
                    if reasons:
                        skipped += len(group_purchases)
                        for purchase_id, reason in reasons:
                            self.stderr.write(
                                f"Permanence {permanence_id}, delivery {delivery_id}, "
                                f"purchase {purchase_id}: pending - {reason}."
                            )
                        continue
                    for purchase in group_purchases:
                        eligible += 1
                        self.stdout.write(
                            f"Permanence {permanence_id}, purchase {purchase.pk}: "
                            f"{'candidate' if dry_run else 'validated'}."
                        )
                        if not dry_run:
                            # A normal save recalculates financial aggregates in pre_save.
                            Purchase.objects.filter(pk=purchase.pk).update(
                                preparation_status=PreparationStatus.VALIDATED,
                            )
        self.stdout.write(
            f"{eligible} purchase(s) {'candidate(s)' if dry_run else 'validated'}; "
            f"{skipped} requiring manual review; {blocked} permanence(s) blocked."
        )
