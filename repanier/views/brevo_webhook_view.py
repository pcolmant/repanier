import json
import logging
from secrets import compare_digest

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from repanier.const import EMPTY_STRING, EmailDeliveryStatus
from repanier.models.customer import Customer
from repanier.models.emaillog import EmailLog

logger = logging.getLogger(__name__)

BREVO_EVENT_TO_STATUS = {
    "delivered": EmailDeliveryStatus.DELIVERED,
    "opened": EmailDeliveryStatus.OPENED,
    "unique_opened": EmailDeliveryStatus.OPENED,
    "soft_bounce": EmailDeliveryStatus.SOFT_BOUNCE,
    "deferred": EmailDeliveryStatus.SOFT_BOUNCE,
    "error": EmailDeliveryStatus.SEND_ERROR,
    "hard_bounce": EmailDeliveryStatus.HARD_BOUNCE,
    "invalid_email": EmailDeliveryStatus.HARD_BOUNCE,
    "blocked": EmailDeliveryStatus.BLOCKED,
    "spam": EmailDeliveryStatus.SPAM,
}

EMAIL_VALIDITY_BY_STATUS = {
    EmailDeliveryStatus.DELIVERED: True,
    EmailDeliveryStatus.OPENED: True,
    EmailDeliveryStatus.HARD_BOUNCE: False,
    EmailDeliveryStatus.BLOCKED: False,
}

UNSUBSCRIBE_STATUSES = {
    EmailDeliveryStatus.HARD_BOUNCE,
    EmailDeliveryStatus.BLOCKED,
    EmailDeliveryStatus.SPAM,
}

# Only allow progress: retries and delayed callbacks must not erase a later
# delivery state. A temporary failure can still be followed by delivery.
STATUS_PRECEDENCE = {
    EmailDeliveryStatus.SENT: 0,
    EmailDeliveryStatus.SEND_ERROR: 0,
    EmailDeliveryStatus.SOFT_BOUNCE: 1,
    EmailDeliveryStatus.DELIVERED: 2,
    EmailDeliveryStatus.OPENED: 3,
    EmailDeliveryStatus.HARD_BOUNCE: 4,
    EmailDeliveryStatus.BLOCKED: 4,
    EmailDeliveryStatus.SPAM: 5,
}


def _normalize_message_id(raw_value):
    if not raw_value:
        return EMPTY_STRING
    value = str(raw_value).strip()
    if not value.startswith("<"):
        value = f"<{value}>"
    return value


def _normalize_brevo_event(event_data):
    event_name = event_data.get("event")
    if not isinstance(event_name, str):
        return None
    event_name = event_name.lower()
    status = BREVO_EVENT_TO_STATUS.get(event_name)
    if status is None:
        return None

    email = event_data.get("email")
    if not isinstance(email, str):
        return None
    return {
        "status": status,
        "message_id": _normalize_message_id(event_data.get("message-id")),
        "email": email.strip().lower(),
        "reason": str(
            event_data.get("reason")
            or event_data.get("response")
            or EMPTY_STRING
        )[:255],
    }


@csrf_exempt
@require_POST
def brevo_webhook_view(request, token=EMPTY_STRING):
    expected_token = getattr(settings, "REPANIER_SETTINGS_BREVO_WEBHOOK_TOKEN", EMPTY_STRING)
    if not expected_token or not compare_digest(token, expected_token):
        return HttpResponseForbidden("Invalid webhook token")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    events = body if isinstance(body, list) else [body]

    for event_data in events:
        if not isinstance(event_data, dict):
            continue

        normalized = _normalize_brevo_event(event_data)
        if not normalized:
            continue

        email_log = None
        if normalized["message_id"] and normalized["email"]:
            email_log = EmailLog.objects.filter(
                message_id=normalized["message_id"],
                recipient_email__iexact=normalized["email"],
            ).first()

        if email_log is None:
            continue

        status = normalized["status"]
        previous_statuses = [
            previous for previous, priority in STATUS_PRECEDENCE.items()
            if priority < STATUS_PRECEDENCE[status]
        ]
        with transaction.atomic():
            updated = EmailLog.objects.filter(
                id=email_log.id, status__in=previous_statuses
            ).update(
                status=status,
                reason=normalized["reason"],
                updated_at=timezone.now(),
            )
            if not updated or not email_log.customer_id:
                continue
            if status not in EMAIL_VALIDITY_BY_STATUS and status not in UNSUBSCRIBE_STATUSES:
                continue

            current_customer = Customer.objects.filter(
                id=email_log.customer_id,
                user__email__iexact=normalized["email"],
            )
            if current_customer.select_for_update(of=("self",)).only("pk").first() is None:
                continue

            if status in UNSUBSCRIBE_STATUSES:
                current_customer.update(subscribe_to_email=False)
            if status not in EMAIL_VALIDITY_BY_STATUS:
                continue

            # A delayed result for an older message must not replace a newer result.
            newer_result = EmailLog.objects.filter(
                customer_id=email_log.customer_id,
                recipient_email__iexact=normalized["email"],
                status__in=EMAIL_VALIDITY_BY_STATUS,
            ).filter(
                Q(created_at__gt=email_log.created_at)
                | Q(created_at=email_log.created_at, pk__gt=email_log.pk)
            )
            if not newer_result.exists():
                current_customer.update(valid_email=EMAIL_VALIDITY_BY_STATUS[status])
    return HttpResponse(status=204)
