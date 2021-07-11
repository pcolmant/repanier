import logging

from django.db import transaction

logger = logging.getLogger(__name__)

from repanier.const import *
from repanier.email import email_offer
from repanier.email import email_order
from repanier.models.box import Box
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.invoice import ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import reorder_offer_items, debug_parameters
from repanier.tools import reorder_purchases


@transaction.atomic
def automatically_open():
    something_to_open = False
    for permanence in Permanence.objects.filter(
        status=PERMANENCE_PLANNED, automatically_closed=True
    ):
        permanence.set_status(
            old_status=PERMANENCE_PLANNED, new_status=PERMANENCE_WAIT_FOR_OPEN
        )
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
    permanence.set_status(
        old_status=PERMANENCE_PLANNED, new_status=PERMANENCE_WAIT_FOR_OPEN
    )

    # Create offer items which can be purchased depending on selection in the admin
    producers_in_this_permanence = (
        Producer.objects.filter(permanence=permanence, is_active=True)
        .only("id")
    )
    product_queryset = Product.objects.filter(
        producer__in=producers_in_this_permanence, is_box=False, is_into_offer=True
    )
    for product in product_queryset:
        product.get_or_create_offer_item(permanence)
    boxes_in_this_permanence = (
        Box.objects.filter(permanence=permanence, is_active=True)
        .only("id")
    )
    for box in boxes_in_this_permanence:
        box.get_or_create_offer_item(permanence)
    # Calculate the sort order of the order display screen
    reorder_offer_items(permanence.id)
    # Calculate the Purchase 'sum' for each customer
    permanence.recalculate_order_amount()

    # 3 - Keep only producer with offer items which can be ordered
    permanence.producers.clear()
    for offer_item in (
        OfferItemReadOnly.objects.filter(permanence_id=permanence.id, may_order=True)
        .order_by("producer_id")
        .distinct("producer_id")
    ):
        permanence.producers.add(offer_item.producer_id)

    for producer in permanence.producers.all():
        producer_invoice = ProducerInvoice.objects.filter(
            permanence_id=permanence.id, producer_id=producer.id
        )
        if not producer_invoice.exists():
            ProducerInvoice.objects.create(
                permanence_id=permanence.id,
                producer_id=producer.id,
                status=PERMANENCE_WAIT_FOR_OPEN,
            )

    if send_mail:
        email_offer.send_open_order(permanence_id)
    permanence.set_status(
        old_status=PERMANENCE_WAIT_FOR_OPEN, new_status=PERMANENCE_OPENED
    )


def back_to_scheduled(permanence):
    permanence.back_to_scheduled()
    permanence.set_status(old_status=PERMANENCE_OPENED, new_status=PERMANENCE_PLANNED)


@transaction.atomic
def automatically_closed():
    something_to_close = False
    for permanence in Permanence.objects.filter(
        status=PERMANENCE_OPENED, automatically_closed=True
    ):
        if permanence.with_delivery_point:
            deliveries_id = list(
                DeliveryBoard.objects.filter(
                    permanence_id=permanence.id, status=PERMANENCE_OPENED
                )
                .values_list("id", flat=True)
            )
        else:
            deliveries_id = ()
        close_order(
            permanence.id, everything=True, deliveries_id=deliveries_id, send_mail=True
        )
        something_to_close = True
    return something_to_close


# Important : no @transaction.atomic because otherwise the "clock" in **permanence.get_html_status_display()**
# won't works on the admin screen. The clock is based on the permanence.status state.
@debug_parameters
def close_order(permanence_id, everything=True, deliveries_id=(), send_mail=True):
    # Be careful : use permanece_id, deliveries_id, ... and not objects
    # for the "thread" processing

    permanence = (
        Permanence.objects.filter(id=permanence_id, status=PERMANENCE_OPENED)
        .first()
    )
    if permanence is None:
        return
    if permanence.with_delivery_point:
        if len(deliveries_id) == 0:
            return

    permanence.set_status(
        old_status=PERMANENCE_OPENED,
        new_status=PERMANENCE_WAIT_FOR_CLOSED,
        everything=everything,
        deliveries_id=deliveries_id,
    )
    permanence.close_order(
        everything=everything, deliveries_id=deliveries_id, send_mail=send_mail
    )
    permanence.set_status(
        old_status=PERMANENCE_WAIT_FOR_CLOSED,
        new_status=PERMANENCE_CLOSED,
        everything=everything,
        deliveries_id=deliveries_id,
    )
    permanence.set_status(
        old_status=PERMANENCE_CLOSED,
        new_status=PERMANENCE_WAIT_FOR_SEND,
        everything=everything,
        deliveries_id=deliveries_id,
    )
    permanence.recalculate_order_amount(send_to_producer=True)
    reorder_purchases(permanence.id)
    if send_mail:
        email_order.email_order(
            permanence.id, everything=everything, deliveries_id=deliveries_id
        )
    permanence.set_status(
        old_status=PERMANENCE_WAIT_FOR_SEND,
        new_status=PERMANENCE_SEND,
        everything=everything,
        deliveries_id=deliveries_id,
    )
