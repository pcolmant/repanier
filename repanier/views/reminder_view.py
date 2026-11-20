from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from repanier import apps
from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.permanence import Permanence
from repanier.models.permanence_reminder import PermanenceReminder
from repanier.tools import get_repanier_template_name


@never_cache
@transaction.atomic
def reminder_view(request, token):
    template_name = get_repanier_template_name("reminder_confirmed.html")
    try:
        permanence_id, customer_id = PermanenceReminder.parse_token(token)
    except (signing.BadSignature, signing.SignatureExpired, ValueError):
        return render(request, template_name, context={"status": "invalid"})

    permanence = Permanence.objects.select_for_update().filter(id=permanence_id).first()
    customer = Customer.objects.filter(
        id=customer_id,
        represent_this_buyinggroup=False,
        may_order=True,
    ).first()

    if permanence is None or customer is None:
        return render(request, template_name, context={"status": "invalid"})

    if permanence.status != SaleStatus.OPENED:
        return render(
            request,
            template_name,
            context={"status": "closed", "permanence": permanence, "customer": customer},
        )

    closing_dt = permanence.get_automatic_closing_datetime()
    reminder_hours = apps.REPANIER_SETTINGS_REMINDER_HOURS_BEFORE_CLOSING
    if closing_dt is None or reminder_hours <= 0:
        return render(request, template_name, context={"status": "invalid"})

    reminder_dt = closing_dt - timedelta(hours=reminder_hours)
    if permanence.reminder_sent_at is not None or timezone.now() >= reminder_dt:
        return render(
            request,
            template_name,
            context={"status": "reminder_unavailable", "permanence": permanence},
        )

    PermanenceReminder.objects.get_or_create(
        permanence=permanence,
        customer=customer,
    )
    customer_label = (
        getattr(customer, "long_basket_name", None)
        or getattr(customer, "short_basket_name", None)
        or str(customer)
    )

    return render(
        request,
        template_name,
        context={
            "status": "ok",
            "permanence": permanence,
            "customer": customer,
            "customer_label": customer_label,
            "closing_dt": closing_dt,
            "reminder_dt": reminder_dt,
            "reminder_hours": reminder_hours,
        },
    )