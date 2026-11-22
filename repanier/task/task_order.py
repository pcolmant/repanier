import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from repanier import apps
from repanier.models import Permanence
from repanier.const import SaleStatus
from repanier.email import email_offer
from repanier.email import email_order
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.invoice import ProducerInvoice
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import reorder_offer_items, debug_parameters
from repanier.tools import reorder_purchases


logger = logging.getLogger(__name__)


@transaction.atomic
def automatically_open():
    something_to_open = False
    for permanence in Permanence.objects.filter(
        status=SaleStatus.PLANNED, automatic_closing_date__isnull=False
    ):
        open_order(permanence.id)
        something_to_open = True
    return something_to_open


# @transaction.atomic
# Important : no @transaction.atomic because otherwise the "clock" in **permanence.get_html_status_display()**
# won't works on the admin screen. The clock is based on the permanence.status state.
def open_order(permanence_id, send_mail=True):
    # Be careful : use permanece_id, deliveries_id, ... and not objects
    # for the "thread" processing
    permanence = Permanence.objects.filter(id=permanence_id).first()
    if permanence is None:
        logger.warning("Cannot open missing permanence %s", permanence_id)
        return
    try:
        permanence.set_status(
            old_status=SaleStatus.PLANNED, new_status=SaleStatus.WAIT_FOR_OPEN
        )
    except ValueError:
        logger.info(
            "Skipping duplicate or stale open-order task for permanence %s",
            permanence_id,
        )
        return

    # Create offer items which can be purchased depending on selection in the admin
    producers_in_this_permanence = Producer.objects.filter(
        permanence=permanence, is_active=True
    ).only("id")
    product_queryset = Product.objects.filter(
        producer__in=producers_in_this_permanence, is_into_offer=True
    )
    for product in product_queryset:
        product.get_or_create_offer_item(permanence)

    # Calculate the sort order of the order display screen
    reorder_offer_items(permanence.id)
    # Calculate the Purchase 'sum' for each customer
    permanence.calculate_order_amount()

    # 3 - Keep only producer with offer items which can be ordered
    permanence.producers.clear()
    producer_ids = list(
        OfferItemReadOnly.objects.filter(permanence_id=permanence.id, may_order=True)
        .values_list("producer_id", flat=True)
        .distinct()
    )
    for producer_id in producer_ids:
        permanence.producers.add(producer_id)

    for producer in permanence.producers.all():
        producer_invoice = ProducerInvoice.objects.filter(
            permanence_id=permanence.id, producer_id=producer.id
        )
        if not producer_invoice.exists():
            ProducerInvoice.objects.create(
                permanence_id=permanence.id,
                producer_id=producer.id,
                status=SaleStatus.WAIT_FOR_OPEN,
            )

    if send_mail:
        email_offer.send_open_order(permanence_id)
    permanence.set_status(
        old_status=SaleStatus.WAIT_FOR_OPEN, new_status=SaleStatus.OPENED
    )


def back_to_scheduled(permanence):
    permanence.back_to_scheduled()
    permanence.set_status(old_status=SaleStatus.OPENED, new_status=SaleStatus.PLANNED)


def automatically_closed():
    now = timezone.now()
    reminder_hours = apps.REPANIER_SETTINGS_REMINDER_HOURS_BEFORE_CLOSING
    something_done = False

    # Send reminders during the configured window before closing.
    if apps.REPANIER_SETTINGS_AUTOMATIC_CLOSING_TIME is not None and reminder_hours > 0:
        reminder_delta = timedelta(hours=reminder_hours)
        for permanence in Permanence.objects.filter(
            status=SaleStatus.OPENED,
            automatic_closing_date__isnull=False,
            reminder_sent_at__isnull=True,
        ):
            closing_dt = permanence.get_automatic_closing_datetime()
            if closing_dt is None:
                continue
            reminder_dt = closing_dt - reminder_delta
            if reminder_dt <= now < closing_dt:
                from repanier.email.email_reminder import send_closing_reminders

                with transaction.atomic():
                    locked = Permanence.objects.select_for_update().filter(
                        id=permanence.id,
                        status=SaleStatus.OPENED,
                        reminder_sent_at__isnull=True,
                    ).first()
                    if locked is None:
                        continue
                    closing_dt = locked.get_automatic_closing_datetime()
                    now_for_reminder = timezone.now()
                    if closing_dt is None or not (
                        closing_dt - reminder_delta <= now_for_reminder < closing_dt
                    ):
                        continue
                    if send_closing_reminders(locked):
                        Permanence.objects.filter(id=locked.id).update(
                            reminder_sent_at=timezone.now()
                        )
                        something_done = True

    for permanence in Permanence.objects.filter(
        status=SaleStatus.OPENED,
        automatic_closing_date__isnull=False,
    ):
        closing_dt = permanence.get_automatic_closing_datetime()
        if closing_dt is None or timezone.now() < closing_dt:
            continue

        if permanence.with_delivery_point:
            deliveries_id = list(
                DeliveryBoard.objects.filter(
                    permanence_id=permanence.id, status=SaleStatus.OPENED
                ).values_list("id", flat=True)
            )
        else:
            deliveries_id = ()

        close_order(
            permanence.id, everything=True, deliveries_id=deliveries_id, send_mail=True
        )
        something_done = True

    return something_done


@transaction.atomic
def resend(permanence_id):
    something_to_resend = False
    if permanence_id is not None:
        permanence = Permanence.objects.filter(
            id=permanence_id,
            status=SaleStatus.WAIT_FOR_SEND
        ).first()
    else:
        permanence = None
    if permanence:
        if permanence.with_delivery_point:
            deliveries_id = list(
                DeliveryBoard.objects.filter(
                    permanence_id=permanence.id, status=SaleStatus.WAIT_FOR_SEND
                ).values_list("id", flat=True)
            )
        else:
            deliveries_id = ()
        send_order(
            permanence, everything=True, deliveries_id=deliveries_id, send_mail=True
        )
        something_to_resend = True
    return something_to_resend


# Important : no @transaction.atomic because otherwise the "clock" in **permanence.get_html_status_display()**
# won't works on the admin screen. The clock is based on the permanence.status state.
@debug_parameters
def close_order(permanence_id, everything=True, deliveries_id=(), send_mail=True):
    # Be careful : use permanece_id, deliveries_id, ... and not objects
    # for the "thread" processing

    permanence = Permanence.objects.filter(
        id=permanence_id, status=SaleStatus.OPENED
    ).first()
    if permanence is None:
        return
    if permanence.with_delivery_point:
        if len(deliveries_id) == 0:
            return

    try:
        permanence.set_status(
            old_status=SaleStatus.OPENED,
            new_status=SaleStatus.WAIT_FOR_CLOSED,
            everything=everything,
            deliveries_id=deliveries_id,
        )
    except ValueError:
        logger.info(
            "Skipping duplicate or stale close-order task for permanence %s",
            permanence_id,
        )
        return
    permanence.close_order(
        everything=everything, deliveries_id=deliveries_id, send_mail=send_mail
    )
    permanence.set_status(
        old_status=SaleStatus.WAIT_FOR_CLOSED,
        new_status=SaleStatus.CLOSED,
        everything=everything,
        deliveries_id=deliveries_id,
    )
    permanence.set_status(
        old_status=SaleStatus.CLOSED,
        new_status=SaleStatus.WAIT_FOR_SEND,
        everything=everything,
        deliveries_id=deliveries_id,
    )
    send_order(permanence, everything, deliveries_id, send_mail)


def send_order(permanence: Permanence, everything: bool, deliveries_id: Any, send_mail: bool):
    permanence.send_to_producer()
    permanence.calculate_order_amount()
    reorder_purchases(permanence.id)

    if send_mail:
        email_order.email_order(
            permanence.id, everything=everything, deliveries_id=deliveries_id
        )
    permanence.set_status(
        old_status=SaleStatus.WAIT_FOR_SEND,
        new_status=SaleStatus.SEND,
        everything=everything,
        deliveries_id=deliveries_id,
    )
