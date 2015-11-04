# -*- coding: utf-8 -*-
from decimal import getcontext, ROUND_HALF_UP
import uuid
from django.conf import settings
from django.contrib import messages
from django.template import TemplateSyntaxError
from django.template.loader import render_to_string
from django.db import transaction
from django.utils import timezone
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool
import repanier.apps
from repanier.const import *
from repanier.email import email_alert
from repanier.email import email_offer
from repanier.email import email_order
from repanier.models import Customer
from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import Product
from repanier.models import Purchase
from repanier.tools import recalculate_order_amount
from repanier.tools import update_or_create_purchase
from repanier.tools import clean_offer_item
import thread


def common_to_pre_open_and_open(permanence_id):
    getcontext().rounding = ROUND_HALF_UP
    # 1- Deactivate all offer item of this permanence
    # Not needed, already done in 'back_to_previous_status'
    # 2 - Delete unused purchases
    Purchase.objects.filter(offer_item__permanence_id=permanence_id, quantity_ordered=0,
                            quantity_invoiced=0).order_by().delete()
    # 3 - Activate offer items which can be purchased depending on selection in the admin
    producers_in_this_permanence = Producer.objects.filter(
        permanence=permanence_id, is_active=True).order_by().only("id")
    product_queryset = Product.objects.filter(
        producer__in=producers_in_this_permanence, is_into_offer=True
    ).order_by()
    OfferItem.objects.filter(product__in=product_queryset, permanence_id=permanence_id, is_active=False) \
        .order_by().update(is_active=True)
    for product in product_queryset:
        if not OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id) \
                .order_by().exists():
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product_id=product.id,
                producer_id=product.producer_id,
                is_active=True
            )
    # 4 - Activate purchased products even if not in selected in the admin
    OfferItem.objects.filter(
        purchase__permanence_id=permanence_id, is_active=False,
        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT
    ).order_by().update(is_active=True)
    # 5 - Deactivate technical offer items
    OfferItem.objects.filter(order_unit__gte=PRODUCT_ORDER_UNIT_DEPOSIT, permanence_id=permanence_id, is_active=True) \
        .order_by().update(is_active=False)
    # 6 - Create cache
    permanence = Permanence.objects.filter(id=permanence_id).order_by().first()
    queryset = OfferItem.objects.filter(permanence_id=permanence_id).order_by()
    clean_offer_item(permanence, queryset, reorder=True)
    # 7 - Calculate the Purchase 'sum' for each customer
    recalculate_order_amount(permanence_id=permanence_id,
                             permanence_status=PERMANENCE_OPENED,
                             send_to_producer=False)
    return permanence


@transaction.atomic
def pre_open_order(permanence_id):
    permanence = common_to_pre_open_and_open(permanence_id)
    # 1 - Allow access to the producer to his/her products into "pre order" status using random uuid4
    for producer in Producer.objects.filter(
        permanence=permanence_id, producer_pre_opening=True).only('offer_uuid').order_by():
        producer.offer_uuid = uuid.uuid4()
        producer.offer_filled = False
        producer.save(update_fields=['offer_uuid', 'offer_filled'])
    try:
        email_offer.send_pre_open_order(permanence_id)
        permanence.set_status(PERMANENCE_PRE_OPEN)
    except Exception as error_str:
        print("################################## pre_open_order")
        print error_str
        print("##################################")


@transaction.atomic
def open_order(permanence_id):
    permanence = common_to_pre_open_and_open(permanence_id)
    # 1 - Disallow access to the producer to his/her products no more into "pre order" status
    for producer in Producer.objects.filter(
        permanence=permanence_id, producer_pre_opening=True).only('offer_uuid', 'offer_filled').order_by():
        producer.offer_uuid = ''
        producer.save(update_fields=['offer_uuid',])
        if not producer.offer_filled:
            # Deactivate offer item if the producer as not reacted to the pre opening
            OfferItem.objects.filter(
                permanence_id=permanence_id, is_active=True,
                producer_id=producer.id
            ).update(is_active=False)
    # 2 - Deactivate offeritem whose stock is not > 0 and with order qty limited to this stock
    OfferItem.objects.filter(permanence_id=permanence_id, is_active=True,
                             limit_order_quantity_to_stock=True, stock__lte=0) \
        .order_by().update(is_active=False)
    # 3 - Keep only producer with active non technical offer items
    permanence.producers.clear()
    for offer_item in OfferItem.objects.filter(
            permanence_id=permanence.id,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
            is_active=True
        ).order_by():
            permanence.producers.add(offer_item.producer_id)

    try:
        if repanier.apps.REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER:
            email_offer.send_open_order(permanence_id)
        permanence.set_status(PERMANENCE_OPENED)
    except Exception as error_str:
        print("################################## open_order")
        print error_str
        print("##################################")


def admin_back_to_planned(request, queryset):
    user_message = _("The status of this permanence prohibit you to go back to planned.")
    user_message_level = messages.ERROR
    for permanence in queryset[:1]:
        if permanence.highest_status <= PERMANENCE_SEND \
                and permanence.status in [PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=False)
            permanence.producers.clear()
            for offer_item in OfferItem.objects.filter(
                    permanence_id=permanence.id
                ).exclude(
                    order_unit__in=[PRODUCT_ORDER_UNIT_SUBSCRIPTION, PRODUCT_ORDER_UNIT_DEPOSIT]
                ).order_by():
                permanence.producers.add(offer_item.producer_id)
            permanence.set_status(PERMANENCE_PLANNED)
            user_message = _("The permanence is back to planned.")
            user_message_level = messages.INFO
    return user_message, user_message_level


def admin_undo_back_to_planned(request, queryset):
    user_message = _("The status of this permanence prohibit you to go back to send.")
    user_message_level = messages.ERROR
    for permanence in queryset[:1]:
        if PERMANENCE_PLANNED == permanence.status \
                and permanence.highest_status in [PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=True)
            permanence.producers.clear()
            for offer_item in OfferItem.objects.filter(
                    permanence_id=permanence.id
                ).exclude(
                    order_unit__in=[PRODUCT_ORDER_UNIT_SUBSCRIPTION, PRODUCT_ORDER_UNIT_DEPOSIT]
                ).order_by():
                permanence.producers.add(offer_item.producer_id)
            if permanence.highest_status == PERMANENCE_PRE_OPEN:
                permanence.set_status(PERMANENCE_PRE_OPEN)
                user_message = _("The permanence is back to pre-opened.")
            elif permanence.highest_status == PERMANENCE_OPENED:
                permanence.set_status(PERMANENCE_OPENED)
                user_message = _("The permanence is back to open.")
            elif permanence.highest_status == PERMANENCE_CLOSED:
                close_order(permanence.id)
                user_message = _("The permanence is back to close.")
            else:
                # permanence.highest_status == PERMANENCE_SEND:
                close_order(permanence.id)
                send_order(permanence.id, send_email=False)
                user_message = _("The permanence is back to send.")
            user_message_level = messages.INFO
    return user_message, user_message_level


def admin_open_and_send(request, queryset):
    user_message = _("The status of this permanence prohibit you to open and send offers.")
    user_message_level = messages.ERROR
    now = timezone.now()
    for permanence in queryset[:1]:
        if permanence.status in [PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN]:
            producer_pre_opening = Producer.objects.filter(
                permanence__id=permanence.id, is_active=True, producer_pre_opening=True
            ).order_by()
            if producer_pre_opening.exists() and permanence.status == PERMANENCE_PLANNED:
                permanence_already_pre_opened = Permanence.objects.filter(
                    status__in=[PERMANENCE_WAIT_FOR_PRE_OPEN, PERMANENCE_PRE_OPEN]
                ).order_by("-is_updated_on").only("id").first()
                if permanence_already_pre_opened is not None:
                    user_message = _("A maximum of one permanence may be pre opened.")
                    user_message_level = messages.ERROR
                else:
                    permanence.highest_status = PERMANENCE_WAIT_FOR_PRE_OPEN
                    permanence.set_status(PERMANENCE_WAIT_FOR_PRE_OPEN)
                    # pre_open_order(permanence.id)
                    thread.start_new_thread(pre_open_order, (permanence.id,))
                    user_message = _("The offers are being generated.")
                    user_message_level = messages.INFO
            else:
                permanence.highest_status = PERMANENCE_WAIT_FOR_OPEN
                permanence.set_status(PERMANENCE_WAIT_FOR_OPEN)
                # open_order(permanence.id)
                thread.start_new_thread(open_order, (permanence.id,))
                user_message = _("The offers are being generated.")
                user_message_level = messages.INFO
        elif permanence.status in [PERMANENCE_WAIT_FOR_PRE_OPEN, PERMANENCE_WAIT_FOR_OPEN]:
            # On demand 15 minutes after the previous attempt, go back to previous status and send alert email
            # use only timediff, -> timezone conversion not needed
            timediff = now - permanence.is_updated_on
            if timediff.total_seconds() > (30 * 60):
                thread.start_new_thread(email_alert.send, (request, permanence))
                if permanence.status == PERMANENCE_WAIT_FOR_PRE_OPEN:
                    new_status = PERMANENCE_PLANNED
                else:
                    producer_pre_opening = Producer.objects.filter(
                        permanence__id=permanence.id, is_active=True, producer_pre_opening=True
                    ).order_by()
                    if producer_pre_opening:
                        new_status = PERMANENCE_PRE_OPEN
                    else:
                        new_status = PERMANENCE_PLANNED
                permanence.set_status(new_status)
                user_message = _(
                    "The action has been canceled by the system and an email send to the site administrator.")
                user_message_level = messages.WARNING
            else:
                user_message = _("Action refused by the system. Please, retry in %d minutes.") % (
                    30 - (int(timediff.total_seconds()) / 60))
                user_message_level = messages.WARNING
    return user_message, user_message_level


@transaction.atomic
def automatically_closed():
    translation.activate(settings.LANGUAGE_CODE)
    something_to_close = False
    for permanence in Permanence.objects.filter(
            status=PERMANENCE_OPENED,
            automatically_closed=True):
        permanence.set_status(PERMANENCE_WAIT_FOR_SEND)
        close_order(permanence.id)
        send_order(permanence.id)
        something_to_close = True
    return something_to_close


@transaction.atomic
def close_order(permanence_id):
    getcontext().rounding=ROUND_HALF_UP
    permanence = Permanence.objects.get(id=permanence_id)
    recalculate_needed = False
    # 1 - Round to multiple producer_order_by_quantity
    for offer_item in OfferItem.objects.filter(
            permanence_id=permanence_id, is_active=True,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
            manage_stock=True,
            producer_order_by_quantity__gt=0,
            quantity_invoiced__gt=0
    ).order_by():
        ratio = ((offer_item.quantity_invoiced - offer_item.stock) / offer_item.producer_order_by_quantity)
        if ratio > DECIMAL_ZERO:
            offer_item.add_2_stock = ((DECIMAL_ONE - (ratio - int(ratio))) * offer_item.producer_order_by_quantity).quantize(THREE_DECIMALS)
            offer_item.save()
    # 2 - Add Deposit
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=False,
                                               order_unit=PRODUCT_ORDER_UNIT_DEPOSIT).order_by():
        permanence.producers.add(offer_item.producer_id)
        offer_item.is_active = True
        offer_item.save(update_fields=['is_active'])
        recalculate_needed = True
        for customer in Customer.objects.filter(purchase__permanence_id=permanence_id).distinct().order_by():
            # value_id = 1 then 0 otherwise there is no change from previous qty => no purchase created
            update_or_create_purchase(
                customer=customer,
                offer_item_id=offer_item.id,
                value_id=1,
                close_orders=True
            )
            update_or_create_purchase(
                customer=customer,
                offer_item_id=offer_item.id,
                value_id=0,
                close_orders=True
            )
    # # 6 - Add deposit offer item if the product is into offer
    # # even if the producer is not selected into the permanence
    # product_queryset = Product.objects.filter(
    #     is_active=True, is_into_offer=True, order_unit=PRODUCT_ORDER_UNIT_DEPOSIT
    # ).order_by()
    # OfferItem.objects.filter(product__in=product_queryset, permanence_id=permanence_id, is_active=True) \
    #     .order_by().update(is_active=False)
    # for product in product_queryset:
    #     if not OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id) \
    #             .order_by().exists():
    #         OfferItem.objects.create(
    #             permanence_id=permanence_id,
    #             product_id=product.id,
    #             producer_id=product.producer_id,
    #             is_active=False
    #         )
    # 3 - Add Subscription
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=False,
                                               order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION).order_by():
        permanence.producers.add(offer_item.producer_id)
        offer_item.is_active = True
        offer_item.save(update_fields=['is_active'])
        recalculate_needed = True
        for customer in Customer.objects.filter(is_active=True, may_order=True,
                                                represent_this_buyinggroup=False).order_by():
            update_or_create_purchase(
                customer=customer,
                offer_item_id=offer_item.id,
                value_id=1,
                close_orders=True
            )
        # Do it only once
        offer_item.product.is_into_offer = False
        offer_item.product.save(update_fields=['is_into_offer'])
    # # 7 - Add subscription offer item if this came from the buying group,
    # # even if the group is not selected into this permanence
    # this_buying_group = Producer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().only("id")
    # product_queryset = Product.objects.filter(
    #     producer__in=this_buying_group, is_active=True, is_into_offer=True, order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION
    # ).order_by()
    # OfferItem.objects.filter(product__in=product_queryset, permanence_id=permanence_id, is_active=True) \
    #     .order_by().update(is_active=False)
    # for product in product_queryset:
    #     if not OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id) \
    #             .order_by().exists():
    #         OfferItem.objects.create(
    #             permanence_id=permanence_id,
    #             product_id=product.id,
    #             producer_id=product.producer_id,
    #             is_active=False
    #         )

    # 4 - Add Transport
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=False,
                                               order_unit=PRODUCT_ORDER_UNIT_TRANSPORTATION).order_by():
        permanence.producers.add(offer_item.producer_id)
        offer_item.is_active = True
        offer_item.save(update_fields=['is_active'])
        recalculate_needed = True
        buying_group = Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
        update_or_create_purchase(
            customer=buying_group,
            offer_item_id=offer_item.id,
            value_id=1,
            close_orders=True
        )

    # 5 - Refresh the Purchase 'sum' for each customer
    if recalculate_needed:
        recalculate_order_amount(permanence_id=permanence_id,
                                 permanence_status=PERMANENCE_CLOSED,
                                 send_to_producer=False)
    permanence.set_status(PERMANENCE_CLOSED)
    if not repanier.apps.REPANIER_SETTINGS_INVOICE:
        # Put send permanences to the done status, because they will "never" be invoiced
        for permanence in Permanence.objects.filter(status=PERMANENCE_SEND):
            permanence.set_status(PERMANENCE_DONE, update_payment_date=True)


@transaction.atomic
def send_order(permanence_id, send_email=True):
    getcontext().rounding=ROUND_HALF_UP
    permanence = Permanence.objects.get(id=permanence_id)
    # 1 - Refresh the Purchase 'sum' for each customer
    #     and move from quantity_ordered (@average weight) to quantity_invoiced
    recalculate_order_amount(permanence_id=permanence_id,
                         permanence_status=PERMANENCE_SEND,
                         send_to_producer=True)
    # 2 - Send mail
    # if not settings.DEBUG:
    if send_email:
        try:
            email_order.email_order(permanence_id)
        except Exception as error_str:
            print("################################## send_order")
            print error_str
            print("##################################")

    permanence.set_status(PERMANENCE_SEND)


def admin_close(request, queryset):
    user_message = _("The status of this permanence prohibit you to close it.")
    user_message_level = messages.ERROR
    now = timezone.now()
    for permanence in queryset[:1]:
        if permanence.status == PERMANENCE_OPENED:
            permanence.set_status(PERMANENCE_WAIT_FOR_CLOSED)
            thread.start_new_thread(close_order, (permanence.id,))
            # close_order(permanence.id)
            user_message = _("The orders are being closed.")
            user_message_level = messages.INFO
        elif permanence.status == PERMANENCE_WAIT_FOR_CLOSED:
            # On demand 30 minutes after the previous attempt, go back to previous status and send alert email
            # use only timediff, -> timezone conversion not needed
            timediff = now - permanence.is_updated_on
            if timediff.total_seconds() > (30 * 60):
                thread.start_new_thread(email_alert.send, (request, permanence))
                permanence.set_status(PERMANENCE_OPENED)
                user_message = _(
                    "The action has been canceled by the system and an email send to the site administrator.")
                user_message_level = messages.WARNING
            else:
                user_message = _("Action refused by the system. Please, retry in %d minutes.") % (
                    30 - (int(timediff.total_seconds()) / 60))
                user_message_level = messages.WARNING
    return user_message, user_message_level

def admin_send(request, queryset):
    user_message = _("The status of this permanence prohibit you to close it.")
    user_message_level = messages.ERROR
    now = timezone.now()
    for permanence in queryset[:1]:
        if permanence.status == PERMANENCE_CLOSED:
            permanence.set_status(PERMANENCE_WAIT_FOR_SEND)
            thread.start_new_thread(send_order, (permanence.id,))
            # send_order(permanence.id)
            user_message = _("The orders are being send.")
            user_message_level = messages.INFO
        elif permanence.status == PERMANENCE_WAIT_FOR_SEND:
            # On demand 30 minutes after the previous attempt, go back to previous status and send alert email
            # use only timediff, -> timezone conversion not needed
            timediff = now - permanence.is_updated_on
            if timediff.total_seconds() > (30 * 60):
                thread.start_new_thread(email_alert.send, (request, permanence))
                permanence.set_status(PERMANENCE_CLOSED)
                user_message = _(
                    "The action has been canceled by the system and an email send to the site administrator.")
                user_message_level = messages.WARNING
            else:
                user_message = _("Action refused by the system. Please, retry in %d minutes.") % (
                    30 - (int(timediff.total_seconds()) / 60))
                user_message_level = messages.WARNING
    return user_message, user_message_level
