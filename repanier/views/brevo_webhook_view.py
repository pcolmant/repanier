import json
import logging
from secrets import compare_digest

from django.conf import settings
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
    "hard_bounce": EmailDeliveryStatus.HARD_BOUNCE,
    "invalid_email": EmailDeliveryStatus.HARD_BOUNCE,
    "blocked": EmailDeliveryStatus.BLOCKED,
    "spam": EmailDeliveryStatus.SPAM,
}

INVALID_EMAIL_STATUSES = {
    EmailDeliveryStatus.HARD_BOUNCE,
    EmailDeliveryStatus.BLOCKED,
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

        if email_log is not None:
            previous_statuses = [
                status for status, priority in STATUS_PRECEDENCE.items()
                if priority < STATUS_PRECEDENCE[normalized["status"]]
            ]
            updated = EmailLog.objects.filter(
                id=email_log.id, status__in=previous_statuses
            ).update(
                status=normalized["status"],
                error_reason=normalized["reason"],
                updated_at=timezone.now(),
            )
            if updated and normalized["status"] in INVALID_EMAIL_STATUSES and email_log.customer_id:
                Customer.objects.filter(
                    id=email_log.customer_id,
                    user__email__iexact=normalized["email"],
                ).update(
                    valid_email=False
                )
    return HttpResponse(status=204)
