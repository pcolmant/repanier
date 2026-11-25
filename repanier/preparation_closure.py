from django.db import transaction
from django.utils import timezone

from repanier.const import DECIMAL_ZERO, PreparationOrigin, PreparationStatus
from repanier.models.preparation import (
    DepositReceipt,
    PreparationSyncEvent,
)
from repanier.models.purchase import Purchase


class ParcelDisposition:
    NOT_IN_BL = "not_in_bl"
    LOST_IN_TRANSIT = "lost_in_transit"


@transaction.atomic
def promote_preparation_to_accounting(permanence, *, user=None, parcel_dispositions=None):
    if getattr(permanence, "is_demo", False):
        return {"status": "rejected", "reason": "demo_permanence"}
    if not getattr(permanence, "preparation_enabled", False):
        return {"status": "applied", "reason": "mobile_preparation_not_used"}

    purchases = (
        Purchase.objects.select_for_update()
        .filter(permanence=permanence)
        .select_related("offer_item")
    )
    unresolved = purchases.exclude(preparation_status=PreparationStatus.VALIDATED)
    unresolved_ids = list(unresolved.values_list("id", flat=True))
    if unresolved_ids:
        return {
            "status": "rejected",
            "reason": "preparation_not_validated",
            "purchase_ids": unresolved_ids,
        }

    if isinstance(parcel_dispositions, str):
        import json

        try:
            parcel_dispositions = json.loads(parcel_dispositions)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "invalid_parcel_dispositions"}
    dispositions = {} if parcel_dispositions is None else parcel_dispositions
    if not isinstance(dispositions, dict):
        return {"status": "rejected", "reason": "invalid_parcel_dispositions"}
    for event in PreparationSyncEvent.objects.filter(
        permanence=permanence,
        operation="parcel_disposition",
        status=PreparationSyncEvent.STATUS_APPLIED,
    ).select_related("purchase"):
        purchase_id = event.purchase_id
        disposition = event.payload.get("disposition")
        if purchase_id is not None and disposition in {
            ParcelDisposition.NOT_IN_BL,
            ParcelDisposition.LOST_IN_TRANSIT,
        }:
            dispositions.setdefault(str(purchase_id), disposition)
    for purchase in purchases:
        disposition = dispositions.get(str(purchase.id), ParcelDisposition.NOT_IN_BL)
        if disposition not in (ParcelDisposition.NOT_IN_BL, ParcelDisposition.LOST_IN_TRANSIT):
            return {
                "status": "rejected",
                "reason": "invalid_parcel_disposition",
                "purchase_id": purchase.id,
            }
    for purchase in purchases:
        if purchase.substitution_targets.exists():
            purchase.quantity_invoiced = DECIMAL_ZERO
        elif purchase.origin == PreparationOrigin.SUBSTITUTION:
            quantity = (
                purchase.quantity_received
                if purchase.quantity_received is not None
                else purchase.quantity_prepared
            )
            purchase.quantity_invoiced = quantity
        else:
            quantity = (
                purchase.quantity_received
                if purchase.quantity_received is not None
                else purchase.quantity_prepared
            )
            purchase.quantity_invoiced = quantity

        disposition = dispositions.get(str(purchase.id), ParcelDisposition.NOT_IN_BL)
        if disposition == ParcelDisposition.LOST_IN_TRANSIT:
            purchase.quantity_invoiced = DECIMAL_ZERO
        purchase.save(update_fields=["quantity_invoiced"])

    for event in PreparationSyncEvent.objects.select_for_update().filter(
        permanence=permanence,
        status=PreparationSyncEvent.STATUS_APPLIED,
        accounting_status="",
    ):
        event.accounting_status = "applied"
        event.accounting_applied_at = timezone.now()
        event.validated_by = getattr(user, "customer", None)
        event.validated_at = event.validated_at or timezone.now()
        event.save(
            update_fields=[
                "accounting_status",
                "accounting_applied_at",
                "validated_by",
                "validated_at",
            ]
        )

    newly_applied_receipts = list(
        DepositReceipt.objects.select_for_update().filter(
        permanence=permanence,
        status=PreparationSyncEvent.STATUS_APPLIED,
        accounting_status="",
        )
    )
    for receipt in newly_applied_receipts:
        receipt.accounting_status = "applied"
        receipt.accounting_applied_at = timezone.now()
        receipt.save(update_fields=["accounting_status", "accounting_applied_at"])

    permanence.calculate_order_amount()

    return {
        "status": "applied",
        "uuid_count": PreparationSyncEvent.objects.filter(
            permanence=permanence,
            accounting_status="applied",
        ).count(),
    }
