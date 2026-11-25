import hashlib
import decimal
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from repanier.const import PreparationOrigin, PreparationStatus
from repanier.const import SaleStatus
from repanier.models.preparation import (
    PermanencePreparationAccess,
    PreparationSyncEvent,
)
from repanier.models.permanence import Permanence
from repanier.models.purchase import Purchase


PREPARATION_TOKEN_SALT = "repanier.permanent.preparation"
DEFAULT_TOKEN_MAX_AGE = 60 * 60 * 24 * 7

PARCEL_NOT_IN_BL = "not_in_bl"
PARCEL_LOST_IN_TRANSIT = "lost_in_transit"


def parse_preparation_quantity(value):
    try:
        quantity = Decimal(str(value))
    except (decimal.InvalidOperation, KeyError, TypeError, ValueError):
        return None
    if not quantity.is_finite() or quantity < Decimal("0"):
        return None
    return quantity


def timestamps_in_older_order(candidate, latest):
    try:
        if timezone.is_naive(candidate):
            candidate = timezone.make_aware(
                candidate,
                timezone.get_current_timezone(),
            )
        if timezone.is_naive(latest):
            latest = timezone.make_aware(
                latest,
                timezone.get_current_timezone(),
            )
        return candidate < latest
    except (TypeError, ValueError, OverflowError):
        return False


def make_preparation_token(permanence_id):
    signer = signing.TimestampSigner(salt=PREPARATION_TOKEN_SALT)
    opaque = uuid.uuid4().hex
    signed = signer.sign(f"{permanence_id}:{opaque}")
    token_hash = hashlib.sha256(signed.encode("utf-8")).hexdigest()
    expires_at = timezone.now() + timedelta(seconds=DEFAULT_TOKEN_MAX_AGE)
    PermanencePreparationAccess.objects.update_or_create(
        permanence_id=permanence_id,
        defaults={
            "token_hash": token_hash,
            "expires_at": expires_at,
            "revoked_at": None,
        },
    )
    return signed


def revoke_preparation_access(permanence_id):
    PermanencePreparationAccess.objects.filter(
        permanence_id=permanence_id
    ).update(revoked_at=timezone.now())


def resolve_preparation_token(token, max_age=DEFAULT_TOKEN_MAX_AGE):
    signer = signing.TimestampSigner(salt=PREPARATION_TOKEN_SALT)
    try:
        raw = signer.unsign(token, max_age=max_age)
        permanence_str, _opaque = raw.split(":", 1)
        permanence_id = int(permanence_str)
    except (signing.BadSignature, signing.SignatureExpired, ValueError):
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    access = (
        PermanencePreparationAccess.objects.select_related("permanence")
        .filter(permanence_id=permanence_id, token_hash=token_hash)
        .first()
    )
    if access is None or not access.is_valid():
        return None
    if not access.permanence.preparation_enabled:
        return None
    if access.permanence.status not in (
        SaleStatus.SEND,
        SaleStatus.WAIT_FOR_INVOICED,
        SaleStatus.INVOICED,
    ):
        return None
    return access.permanence


@transaction.atomic
def apply_preparation_sync(permanence, event_payload, validated_by=None):
    permanence = (
        Permanence.objects.select_for_update()
        .filter(pk=permanence.pk)
        .first()
        or permanence
    )
    try:
        event_uuid = uuid.UUID(str(event_payload["uuid"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        return {
            "status": PreparationSyncEvent.STATUS_REJECTED,
            "reason": "invalid_uuid",
        }

    existing = PreparationSyncEvent.objects.select_for_update().filter(
        permanence=permanence,
        uuid=event_uuid,
    ).first()
    if existing is not None:
        return {
            "status": existing.status,
            "reason": existing.conflict_reason,
            "uuid": str(existing.uuid),
            "idempotent": True,
        }

    operation = str(event_payload.get("operation", "")).strip()
    purchase_id = event_payload.get("purchase_id")
    try:
        client_timestamp = event_payload["client_timestamp"]
    except KeyError:
        client_timestamp = timezone.now()
    if isinstance(client_timestamp, str):
        parsed_timestamp = parse_datetime(client_timestamp)
        if parsed_timestamp is None:
            event = PreparationSyncEvent(
                permanence=permanence,
                uuid=event_uuid,
                client_timestamp=timezone.now(),
                operation=operation,
                payload=event_payload,
                status=PreparationSyncEvent.STATUS_REJECTED,
                conflict_reason="invalid_client_timestamp",
            )
            try:
                event.save()
            except IntegrityError:
                existing = PreparationSyncEvent.objects.select_for_update().filter(
                    permanence=permanence,
                    uuid=event_uuid,
                ).first()
                if existing is not None:
                    return {
                        "status": existing.status,
                        "reason": existing.conflict_reason,
                        "uuid": str(existing.uuid),
                        "idempotent": True,
                    }
                raise
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        client_timestamp = parsed_timestamp

    try:
        event = PreparationSyncEvent.objects.create(
            permanence=permanence,
            uuid=event_uuid,
            client_timestamp=client_timestamp,
            operation=operation,
            payload=event_payload,
            status=PreparationSyncEvent.STATUS_CREATED,
        )
    except IntegrityError:
        existing = PreparationSyncEvent.objects.select_for_update().filter(
            permanence=permanence,
            uuid=event_uuid,
        ).first()
        if existing is not None:
            return {
                "status": existing.status,
                "reason": existing.conflict_reason,
                "uuid": str(existing.uuid),
                "idempotent": True,
            }
        raise

    if operation not in {
        "prepare",
        "receive",
        "hand_to_group",
        "validate",
        "substitute",
        "express_request",
        "deposit_receipt",
        "parcel_disposition",
    }:
        event.status = PreparationSyncEvent.STATUS_REJECTED
        event.conflict_reason = "unknown_operation"
        event.save(update_fields=["status", "conflict_reason"])
        return {
            "status": event.status,
            "reason": event.conflict_reason,
            "uuid": str(event.uuid),
        }

    if permanence.status != SaleStatus.SEND:
        # Offline queues may sync late: once the permanence left the closing
        # state, nothing may be created or changed in the accounting books.
        event.status = PreparationSyncEvent.STATUS_REJECTED
        event.conflict_reason = "permanence_closed"
        event.save(update_fields=["status", "conflict_reason"])
        return {
            "status": event.status,
            "reason": event.conflict_reason,
            "uuid": str(event.uuid),
        }

    if operation == "express_request":
        if permanence.is_demo:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "demo_not_allowed"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        quantity = parse_preparation_quantity(
            event_payload.get("quantity")
        )
        if quantity is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "invalid_quantity"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        from repanier.models.offeritem import OfferItem
        from repanier.models.customer import Customer
        from repanier.models.invoice import (
            CustomerInvoice,
            ProducerInvoice,
            CustomerProducerInvoice,
        )
        offer_item = OfferItem.objects.select_for_update().filter(
            id=event_payload.get("offer_item_id"),
            permanence_id=permanence.id,
        ).first()
        customer = Customer.objects.filter(
            id=event_payload.get("customer_id")
        ).first()
        if offer_item is None or customer is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "express_target_not_found"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        existing = Purchase.objects.filter(
            permanence=permanence,
            offer_item=offer_item,
            customer=customer,
            is_box_content=False,
        ).first()
        if existing is not None:
            event.status = PreparationSyncEvent.STATUS_CONFLICT
            event.conflict_reason = "express_purchase_already_exists"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        customer_invoice = CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=customer.id,
            status=permanence.status,
        )
        producer_invoice = ProducerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            producer_id=offer_item.producer_id,
            status=permanence.status,
        )
        customer_producer_invoice = CustomerProducerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=customer.id,
            producer_id=offer_item.producer_id,
        )
        purchase = Purchase.objects.create(
            permanence=permanence,
            offer_item=offer_item,
            producer=offer_item.producer,
            customer=customer,
            customer_invoice=customer_invoice,
            producer_invoice=producer_invoice,
            customer_producer_invoice=customer_producer_invoice,
            status=permanence.status,
            quantity_ordered=Decimal("0"),
            quantity_prepared=quantity,
            quantity_received=quantity,
            preparation_status=PreparationStatus.PREPARED,
            origin=PreparationOrigin.EXPRESS_REQUEST,
        )
        event.purchase = purchase
        event.status = PreparationSyncEvent.STATUS_APPLIED
        event.save(update_fields=["purchase", "status"])
        return {
            "status": event.status,
            "uuid": str(event.uuid),
            "purchase_id": purchase.id,
        }

    if operation == "deposit_receipt":
        if permanence.is_demo:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "demo_not_allowed"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        from repanier.accounting_policy import AccountingPolicy
        if not AccountingPolicy.use_deposits():
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "deposits_disabled"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        from repanier.models.preparation import DepositContainerType, DepositReceipt
        from repanier.models.customer import Customer
        if not event_payload.get("container_type_id"):
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "missing_container_type"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        container_type = DepositContainerType.objects.select_for_update().filter(
            id=event_payload["container_type_id"],
            is_active=True,
        ).first()
        if container_type is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "unknown_container_type"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        customer = None
        customer_id = event_payload.get("customer_id")
        if customer_id:
            customer = Customer.objects.filter(id=customer_id).first()

        try:
            returned = int(event_payload.get("returned_count", 0))
            missing = int(event_payload.get("missing_count", 0))
        except (TypeError, ValueError, OverflowError):
            returned = missing = -1
        if returned < 0 or missing < 0:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "invalid_deposit_count"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        net = returned - missing
        credit = (
            container_type.unit_credit.amount * Decimal(net)
        ).quantize(Decimal("0.01"))

        receipt = DepositReceipt.objects.create(
            uuid=event_uuid,
            permanence=permanence,
            customer=customer,
            container_type=container_type,
            returned_count=returned,
            missing_count=missing,
            credit_amount=credit,
            status=PreparationSyncEvent.STATUS_APPLIED,
            client_timestamp=client_timestamp,
        )
        event.status = PreparationSyncEvent.STATUS_APPLIED
        event.save(update_fields=["status"])
        return {
            "status": event.status,
            "uuid": str(event.uuid),
            "receipt_id": receipt.id,
            "credit_amount": str(receipt.credit_amount.amount),
        }

    if operation == "parcel_disposition":
        purchase_id = event_payload.get("purchase_id")
        disposition = event_payload.get("disposition")
        if disposition not in {PARCEL_NOT_IN_BL, PARCEL_LOST_IN_TRANSIT}:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "invalid_parcel_disposition"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        purchase = (
            Purchase.objects.select_for_update()
            .filter(id=purchase_id, permanence_id=permanence.id)
            .first()
        )
        if purchase is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "purchase_not_in_permanence"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        if permanence.is_demo:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "demo_links_real_accounting"
            event.save(update_fields=["purchase", "status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        event.purchase = purchase
        event.status = PreparationSyncEvent.STATUS_APPLIED
        event.save(update_fields=["purchase", "status"])
        return {
            "status": event.status,
            "uuid": str(event.uuid),
            "purchase_id": purchase.id,
            "disposition": disposition,
        }

    purchase = (
        Purchase.objects.select_for_update()
        .filter(id=purchase_id, permanence_id=permanence.id)
        .first()
    )
    if purchase is None:
        event.status = PreparationSyncEvent.STATUS_REJECTED
        event.conflict_reason = "purchase_not_in_permanence"
        event.save(update_fields=["status", "conflict_reason"])
        return {
            "status": event.status,
            "reason": event.conflict_reason,
            "uuid": str(event.uuid),
        }

    event.purchase = purchase

    if operation == "substitute":
        if permanence.is_demo:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "demo_not_allowed"
            event.save(update_fields=["status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }
        target_offer_item_id = event_payload.get("target_offer_item_id")
        source_purchase = purchase
        from repanier.models.offeritem import OfferItem
        target_offer_item = OfferItem.objects.select_for_update().filter(
            id=target_offer_item_id,
            permanence_id=permanence.id,
        ).first()
        if source_purchase is None or target_offer_item is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "substitution_target_not_found"
            event.save(update_fields=["purchase", "status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        target_purchase = Purchase.objects.select_for_update().filter(
            permanence=permanence,
            customer=source_purchase.customer,
            offer_item=target_offer_item,
            is_box_content=False,
        ).first()

        quantity = parse_preparation_quantity(
            event_payload.get("quantity")
        )
        if quantity is None:
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "invalid_quantity"
            event.save(update_fields=["purchase", "status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

        source_purchase.quantity_prepared = Decimal("0")
        source_purchase.quantity_received = Decimal("0")
        source_purchase.preparation_status = PreparationStatus.VALIDATED
        source_purchase.save(
            update_fields=[
                "quantity_prepared",
                "quantity_received",
                "preparation_status",
            ]
        )

        if target_purchase is None:
            target_purchase = Purchase.objects.create(
                permanence=permanence,
                offer_item=target_offer_item,
                producer=target_offer_item.producer,
                customer=source_purchase.customer,
                customer_invoice=source_purchase.customer_invoice,
                producer_invoice=source_purchase.producer_invoice,
                customer_producer_invoice=source_purchase.customer_producer_invoice,
                status=permanence.status,
                quantity_ordered=source_purchase.quantity_ordered,
                quantity_prepared=quantity,
                quantity_received=quantity,
                preparation_status=PreparationStatus.PREPARED,
                origin=PreparationOrigin.SUBSTITUTION,
                substitution_source=source_purchase,
            )
        else:
            target_purchase.quantity_prepared = (
                target_purchase.quantity_prepared + quantity
            )
            target_purchase.quantity_received = (
                target_purchase.quantity_received + quantity
            )
            target_purchase.preparation_status = PreparationStatus.PREPARED
            target_purchase.origin = PreparationOrigin.SUBSTITUTION
            target_purchase.substitution_source = source_purchase
            target_purchase.save(
                update_fields=[
                    "quantity_prepared",
                    "quantity_received",
                    "preparation_status",
                    "origin",
                    "substitution_source",
                ]
            )

        event.status = PreparationSyncEvent.STATUS_APPLIED
        event.save(update_fields=["purchase", "status"])
        return {
            "status": event.status,
            "uuid": str(event.uuid),
            "source_purchase_id": source_purchase.id,
            "target_purchase_id": target_purchase.id,
        }

    if permanence.is_demo:
        if (
            purchase.customer_invoice_id
            and purchase.customer_invoice.permanence_id != permanence.id
        ):
            event.status = PreparationSyncEvent.STATUS_REJECTED
            event.conflict_reason = "demo_links_real_accounting"
            event.save(update_fields=["purchase", "status", "conflict_reason"])
            return {
                "status": event.status,
                "reason": event.conflict_reason,
                "uuid": str(event.uuid),
            }

    latest_applied = (
        PreparationSyncEvent.objects.filter(
            permanence=permanence,
            purchase=purchase,
            status=PreparationSyncEvent.STATUS_APPLIED,
        )
        .order_by("-client_timestamp", "-server_timestamp")
        .first()
    )
    if latest_applied is not None:
        try:
            if timestamps_in_older_order(
                client_timestamp,
                latest_applied.client_timestamp,
            ):
                event.status = PreparationSyncEvent.STATUS_CONFLICT
                event.conflict_reason = "obsolete_event"
                event.save(update_fields=["purchase", "status", "conflict_reason"])
                return {
                    "status": event.status,
                    "reason": event.conflict_reason,
                    "uuid": str(event.uuid),
                }
        except TypeError:
            pass

    try:
        if operation == "prepare":
            quantity = parse_preparation_quantity(
                event_payload.get("quantity")
            )
            if quantity is None:
                raise ValueError
            purchase.quantity_prepared = quantity
            purchase.preparation_status = PreparationStatus.PREPARED
        elif operation == "receive":
            quantity = parse_preparation_quantity(
                event_payload.get("quantity")
            )
            if quantity is None:
                raise ValueError
            purchase.quantity_received = quantity
        elif operation == "hand_to_group":
            purchase.preparation_status = PreparationStatus.HANDED_TO_GROUP
        elif operation == "validate":
            purchase.preparation_status = PreparationStatus.VALIDATED
            quantity = parse_preparation_quantity(
                event_payload.get("quantity", purchase.quantity_prepared)
            )
            if quantity is None:
                raise ValueError
            purchase.quantity_received = quantity
    except (KeyError, ValueError, decimal.InvalidOperation):
        event.status = PreparationSyncEvent.STATUS_REJECTED
        event.conflict_reason = "invalid_quantity"
        event.save(update_fields=["status", "conflict_reason"])
        return {
            "status": event.status,
            "reason": event.conflict_reason,
            "uuid": str(event.uuid),
        }

    purchase.save(
        update_fields=[
            "quantity_prepared",
            "quantity_received",
            "preparation_status",
        ]
    )
    event.status = PreparationSyncEvent.STATUS_APPLIED
    update_fields = ["purchase", "status"]
    if operation == "validate":
        event.validated_by = validated_by
        event.validated_at = timezone.now()
        update_fields.extend(["validated_by", "validated_at"])
    event.save(update_fields=update_fields)
    return {
        "status": event.status,
        "uuid": str(event.uuid),
        "purchase_id": purchase.id,
    }
