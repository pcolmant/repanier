# -*- coding: utf-8 -*-
import datetime
import thread
import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.const import *
from repanier.email import email_offer
from repanier.email import email_order
from repanier.email.email_order import export_order_2_1_customer
from repanier.models import Customer, BoxContent, DeliveryBoard, CustomerInvoice
from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import Producer, ProducerInvoice
from repanier.models import Product
from repanier.models import Purchase
from repanier.tools import clean_offer_item, update_or_create_purchase, get_signature
from repanier.tools import recalculate_order_amount, create_or_update_one_purchase, get_or_create_offer_item, \
    add_months, \
    reorder_offer_items


@transaction.atomic
def automatically_pre_open():
    translation.activate(settings.LANGUAGE_CODE)
    something_to_pre_open = False
    max_3_days_in_the_future = (timezone.now() + datetime.timedelta(days=3)).date()
    for permanence in Permanence.objects.filter(
            status=PERMANENCE_PLANNED,
            permanence_date__lte=max_3_days_in_the_future,
            automatically_closed=True):
        producers = list(Producer.objects.filter(is_active=True, producer_pre_opening=True).only('id').order_by('?'))
        permanence.producers.add(*producers)
        permanence.set_status(PERMANENCE_WAIT_FOR_PRE_OPEN)
        pre_open_order(permanence.id)
        something_to_pre_open = True
    return something_to_pre_open


@transaction.atomic
def automatically_open():
    translation.activate(settings.LANGUAGE_CODE)
    something_to_open = False
    for permanence in Permanence.objects.filter(
            status=PERMANENCE_PRE_OPEN,
            automatically_closed=True):
        permanence.set_status(PERMANENCE_WAIT_FOR_OPEN)
        open_order(permanence.id)
        something_to_open = True
    return something_to_open


def common_to_pre_open_and_open(permanence_id):
    getcontext().rounding = ROUND_HALF_UP
    # 1- Deactivate all offer item of this permanence
    OfferItem.objects.filter(
        permanence_id=permanence_id
    ).order_by('?').update(
        is_active=False, may_order=False, is_box=False, is_box_content=False
    )
    # 2 - Delete unused purchases
    # Purchase.objects.filter(permanence_id=permanence_id, quantity_ordered=0,
    #                         quantity_invoiced=0).order_by('?').delete()
    # 3 - Activate offer items which can be purchased depending on selection in the admin
    producers_in_this_permanence = Producer.objects.filter(
        permanence=permanence_id, is_active=True).order_by('?').only("id")
    product_queryset = Product.objects.filter(
        producer__in=producers_in_this_permanence, is_into_offer=True
    ).order_by('?').only("id", "producer_id")

    OfferItem.objects.filter(product__in=product_queryset, permanence_id=permanence_id) \
        .order_by('?').update(is_active=True, may_order=True)
    for product in product_queryset:
        if not OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id) \
                .order_by('?').exists():
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product_id=product.id,
                producer_id=product.producer_id,
                is_box=False,
                is_box_content=False,
                is_active=True,
                may_order=True
            )
    # 4 - Add composition products
    product_queryset = Product.objects.filter(
        is_box=True, is_into_offer=True
    ).order_by('?').only("id", "producer_id")
    OfferItem.objects.filter(product__in=product_queryset, permanence_id=permanence_id) \
        .order_by('?').update(is_active=True, may_order=True)
    for product in product_queryset:
        offer_item = OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id).order_by('?').first()
        if offer_item is None:
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product_id=product.id,
                producer_id=product.producer_id,
                is_box=True,
                is_box_content=False,
                is_active=True,
                may_order=True
            )
        else:
            offer_item.is_box = True
            offer_item.is_active = True
            offer_item.save(update_fields=["is_active", "is_box"])
        for box_content in BoxContent.objects.filter(box=product.id).select_related("product__producer").order_by(
                '?'):
            box_offer_item = OfferItem.objects.filter(product_id=box_content.product_id,
                                                      permanence_id=permanence_id).order_by('?').first()
            if box_offer_item is None:
                OfferItem.objects.create(
                    permanence_id=permanence_id,
                    product_id=box_content.product_id,
                    producer_id=box_content.product.producer_id,
                    is_box=False,
                    is_box_content=True,
                    is_active=True,
                    may_order=False
                )
            else:
                box_offer_item.is_box_content = True
                box_offer_item.is_active = True
                box_offer_item.save(update_fields=["is_active", "is_box_content"])
    # 6 - Add subscriptions even if the producer is not selected
    product_queryset = Product.objects.filter(
        order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION, is_into_offer=True,
        producer__represent_this_buyinggroup=True
    ).order_by('?').only("id", "producer_id")
    for product in product_queryset:
        if not OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id) \
                .order_by('?').exists():
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product_id=product.id,
                producer_id=product.producer_id,
                is_box=False,
                is_box_content=False,
            )
    # 7 - Activate purchased products even if not in selected in the admin
    OfferItem.objects.filter(
        purchase__permanence_id=permanence_id, is_active=False,
        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT
    ).order_by('?').update(is_active=True)
    # 8 - Create cache
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    offer_item_qs = OfferItem.objects.filter(permanence_id=permanence_id).order_by('?')
    clean_offer_item(permanence, offer_item_qs, reset_add_2_stock=True)
    # 9 - calculate the sort order of the order display screen
    reorder_offer_items(permanence_id)
    # 10 - Deactivate technical offer items
    OfferItem.objects.filter(order_unit__gte=PRODUCT_ORDER_UNIT_DEPOSIT, permanence_id=permanence_id) \
        .order_by('?').update(is_active=False, may_order=False)
    # 11 - Calculate the Purchase 'sum' for each customer
    recalculate_order_amount(
        permanence_id=permanence_id,
        all_producers=True,
        send_to_producer=False
    )
    return permanence


@transaction.atomic
def pre_open_order(permanence_id):
    permanence = common_to_pre_open_and_open(permanence_id)
    # 1 - Allow access to the producer to his/her products into "pre order" status using random uuid4
    for producer in Producer.objects.filter(
            permanence=permanence_id, producer_pre_opening=True
    ).only('offer_uuid').order_by('?'):
        producer.offer_uuid = uuid.uuid4()
        producer.offer_filled = False
        producer.save(update_fields=['offer_uuid', 'offer_filled'])
    try:
        email_offer.send_pre_open_order(permanence_id)
        permanence.set_status(PERMANENCE_PRE_OPEN)
    except Exception as error_str:
        print("################################## pre_open_order")
        print(error_str)
        print("##################################")


@transaction.atomic
def open_order(permanence_id):
    permanence = common_to_pre_open_and_open(permanence_id)
    # 1 - Disallow access to the producer to his/her products no more into "pre order" status
    for producer in Producer.objects.filter(
            permanence=permanence_id, producer_pre_opening=True).only('offer_uuid', 'offer_filled').order_by('?'):
        producer.offer_uuid = EMPTY_STRING
        producer.save(update_fields=['offer_uuid', ])
        if not producer.offer_filled:
            # Deactivate offer item if the producer as not reacted to the pre opening
            OfferItem.objects.filter(
                permanence_id=permanence_id, is_active=True,
                producer_id=producer.id
            ).update(is_active=False)
    # 3 - Keep only producer with active non technical offer items
    permanence.producers.clear()
    for offer_item in OfferItem.objects.filter(
            permanence_id=permanence.id,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
            is_active=True
    ).order_by('?'):
        permanence.producers.add(offer_item.producer_id)

    try:
        if repanier.apps.REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER:
            email_offer.send_open_order(permanence_id)
        permanence.set_status(PERMANENCE_OPENED)
    except Exception as error_str:
        print("################################## open_order")
        print(error_str)
        print("##################################")


def admin_back_to_planned(request, permanence):
    permanence.producers.clear()
    for offer_item in OfferItem.objects.filter(
            permanence_id=permanence.id,
            is_active=True,
            may_order=True
    ).exclude(
        order_unit__in=[PRODUCT_ORDER_UNIT_SUBSCRIPTION, PRODUCT_ORDER_UNIT_DEPOSIT]
    ).order_by('?'):
        permanence.producers.add(offer_item.producer_id)
    OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=False)
    permanence.set_status(PERMANENCE_PLANNED)
    user_message = _("The permanence is back to planned.")
    user_message_level = messages.INFO
    return user_message, user_message_level


def admin_undo_back_to_planned(request, permanence):
    user_message = _("Action canceled by the system.")
    user_message_level = messages.ERROR
    if PERMANENCE_PLANNED == permanence.status \
            and permanence.highest_status in [PERMANENCE_PRE_OPEN, PERMANENCE_OPENED]:
        OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=True)
        permanence.producers.clear()
        for offer_item in OfferItem.objects.filter(
                permanence_id=permanence.id
        ).exclude(
            order_unit__in=[PRODUCT_ORDER_UNIT_SUBSCRIPTION, PRODUCT_ORDER_UNIT_DEPOSIT]
        ).order_by('?'):
            permanence.producers.add(offer_item.producer_id)
        if permanence.highest_status == PERMANENCE_PRE_OPEN:
            permanence.set_status(PERMANENCE_PRE_OPEN)
            user_message = _("The permanence is back to pre-opened.")
        elif permanence.highest_status == PERMANENCE_OPENED:
            permanence.set_status(PERMANENCE_OPENED)
            user_message = _("The permanence is back to open.")
        user_message_level = messages.INFO
    return user_message, user_message_level


def admin_open_and_send(request, permanence):
    producer_pre_opening = Producer.objects.filter(
        permanence__id=permanence.id, is_active=True, producer_pre_opening=True
    ).order_by('?')
    if producer_pre_opening.exists() and permanence.status == PERMANENCE_PLANNED:
        permanence_already_pre_opened = Permanence.objects.filter(
            status__in=[PERMANENCE_WAIT_FOR_PRE_OPEN, PERMANENCE_PRE_OPEN]
        ).order_by("-is_updated_on").only("id").first()
        if permanence_already_pre_opened is not None:
            user_message = _("A maximum of one permanence may be pre opened.")
            user_message_level = messages.ERROR
        else:
            permanence.set_status(PERMANENCE_WAIT_FOR_PRE_OPEN)
            # pre_open_order(permanence.id)
            thread.start_new_thread(pre_open_order, (permanence.id,))
            user_message = _("The offers are being generated.")
            user_message_level = messages.INFO
    else:
        permanence.set_status(PERMANENCE_WAIT_FOR_OPEN)
        # open_order(permanence.id)
        thread.start_new_thread(open_order, (permanence.id,))
        user_message = _("The offers are being generated.")
        user_message_level = messages.INFO
    return user_message, user_message_level


@transaction.atomic
def automatically_closed():
    translation.activate(settings.LANGUAGE_CODE)
    something_to_close = False
    if repanier.apps.REPANIER_SETTINGS_CLOSE_WO_SENDING:
        for permanence in Permanence.objects.filter(
                status=PERMANENCE_OPENED,
                automatically_closed=True):
            if permanence.with_delivery_point:
                deliveries_id = DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status=PERMANENCE_OPENED
                ).values_list('id', flat=True).order_by("id")
            else:
                deliveries_id = None
            close_send_order(permanence.id, all_producers=True, deliveries_id=deliveries_id, send=False)
            something_to_close = True
    else:
        for permanence in Permanence.objects.filter(
                status__in=[PERMANENCE_OPENED, PERMANENCE_CLOSED],
                automatically_closed=True):
            if permanence.with_delivery_point:
                deliveries_id = DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status__in=[PERMANENCE_OPENED, PERMANENCE_CLOSED]
                ).values_list('id', flat=True).order_by("id")
            else:
                deliveries_id = None
            close_send_order(permanence.id, all_producers=True, deliveries_id=deliveries_id, send=True)
            something_to_close = True
    return something_to_close


@transaction.atomic
def close_order_delivery(permanence, delivery, all_producers, producers_id=None):
    today = timezone.now().date()
    getcontext().rounding = ROUND_HALF_UP
    # 0 - Delete unused purchases
    # No need to select : customer_invoice__delivery = delivery
    # Purchase.objects.filter(permanence_id=permanence.id, quantity_ordered=0,
    #                         quantity_invoiced=0).order_by('?').delete()
    if repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        purchase_qs = Purchase.objects.filter(
            permanence_id=permanence.id,
            customer_invoice__delivery=delivery,
            customer_invoice__is_order_confirm_send=False,
            is_box_content=False
        ).exclude(
            quantity_ordered=DECIMAL_ZERO
        ).order_by('customer_invoice')
        if not all_producers:
            # This may never be the but, but...
            purchase_qs = purchase_qs.filter(producer_id__in=producers_id)
        customer_invoice_id_save = -1
        for purchase in purchase_qs.select_related("customer", "offer_item"):
            if customer_invoice_id_save != purchase.customer_invoice_id:
                customer_invoice_id_save =purchase.customer_invoice_id
                # This order has been cancelled
                # filename = force_filename("%s - %s.xlsx" % (_("Canceled order"), permanence))
                filename = "{0}-{1}.xlsx".format(
                    slugify(_("Canceled order")),
                    slugify(permanence)
                )
                sender_email, sender_function, signature, cc_email_staff = get_signature(
                    is_reply_to_order_email=True)
                export_order_2_1_customer(
                    purchase.customer, filename, permanence, sender_email,
                    sender_function, signature,
                    cancel_order=True)
            update_or_create_purchase(
                customer=purchase.customer,
                offer_item_id=purchase.offer_item.id,
                value_id=DECIMAL_ZERO,
                batch_job=True
            )
    if all_producers:
        # 1 - Do not round to multiple producer_order_by_quantity
        # 2 - Do not add Transport
        membership_fee_product = Product.objects.filter(is_membership_fee=True, is_active=True).order_by('?').first()
        membership_fee_product.producer_unit_price = repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE
        # Update the prices
        membership_fee_product.save()
        membership_fee_offer_item = get_or_create_offer_item(permanence, membership_fee_product.id,
                                                             membership_fee_product.producer_id)
        for customer in Customer.objects.filter(
                is_active=True, may_order=True,
                customerinvoice__permanence_id=permanence.id,
                customerinvoice__delivery=delivery,
                customerinvoice__total_price_with_tax__gt=DECIMAL_ZERO,
                represent_this_buyinggroup=False
        ).order_by('?'):
            # 3 - Add Deposit
            for offer_item in OfferItem.objects.filter(permanence_id=permanence.id,  # is_active=False,
                                                       order_unit=PRODUCT_ORDER_UNIT_DEPOSIT).order_by('?'):
                permanence.producers.add(offer_item.producer_id)
                create_or_update_one_purchase(customer, offer_item, 1, None, True, is_box_content=False)
                create_or_update_one_purchase(customer, offer_item, 0, None, True, is_box_content=False)
            # 4 - Add Membership fee Subscription
            if repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION > 0:
                # There is a membership fee
                if customer.membership_fee_valid_until < today:
                    permanence.producers.add(membership_fee_offer_item.producer_id)
                    create_or_update_one_purchase(customer, membership_fee_offer_item, 1, None, True,
                                                  is_box_content=False)
                    customer.membership_fee_valid_until = add_months(
                        customer.membership_fee_valid_until,
                        repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION
                    )
                    customer.save(update_fields=['membership_fee_valid_until', ])
        # 5 - Add Common participation Subscription
        for offer_item in OfferItem.objects.filter(
                permanence_id=permanence.id, is_membership_fee=False,
                order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION).order_by('?'):
            for customer in Customer.objects.filter(is_active=True, may_order=True,
                                                    represent_this_buyinggroup=False).order_by('?'):
                permanence.producers.add(offer_item.producer_id)
                create_or_update_one_purchase(customer, offer_item, 1, None, True, is_box_content=False)
    # 6 - Refresh the Purchase 'sum'
    recalculate_order_amount(
        permanence_id=permanence.id,
        all_producers=all_producers,
        producers_id=producers_id,
        send_to_producer=False
    )
    delivery.set_status(PERMANENCE_CLOSED, all_producers, producers_id)


@transaction.atomic
def close_order(permanence, all_producers, producers_id=None):
    getcontext().rounding = ROUND_HALF_UP
    today = timezone.now().date()

    if repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        # 0 - Cancel unconfirmed purchases
        purchase_qs = Purchase.objects.filter(
            permanence_id=permanence.id,
            customer_invoice__is_order_confirm_send=False,
            is_box_content=False
        ).exclude(
            quantity_ordered=DECIMAL_ZERO
        ).order_by('customer_invoice')
        if not all_producers:
            purchase_qs = purchase_qs.filter(producer_id__in=producers_id)
        customer_invoice_id_save = -1
        for purchase in purchase_qs.select_related("customer", "offer_item"):
            if customer_invoice_id_save != purchase.customer_invoice_id:
                customer_invoice_id_save = purchase.customer_invoice_id
                # This order has been cancelled
                # filename = force_filename("%s - %s.xlsx" % (_("Canceled order"), permanence))
                filename = "{0}-{1}.xlsx".format(
                    slugify(_("Canceled order")),
                    slugify(permanence)
                )
                sender_email, sender_function, signature, cc_email_staff = get_signature(
                    is_reply_to_order_email=True)
                export_order_2_1_customer(
                    purchase.customer, filename, permanence, sender_email,
                    sender_function, signature,
                    cancel_order=True)
            update_or_create_purchase(
                customer=purchase.customer,
                offer_item_id=purchase.offer_item.id,
                value_id=DECIMAL_ZERO,
                batch_job=True
            )
    # else:
        # 0 - Delete unused purchases
        # purchase_qs = Purchase.objects.filter(permanence_id=permanence.id, quantity_ordered=0,
        #                     quantity_invoiced=0).order_by('?').delete()
        # if not all_producers:
        #     purchase_qs = purchase_qs.filter(producer_id__in=producers_id)
        # purchase_qs.delete()
    # 1 - Round to multiple producer_order_by_quantity
    offer_item_qs = OfferItem.objects.filter(
        permanence_id=permanence.id,
        is_active=True,
        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
        producer_order_by_quantity__gt=1,
        quantity_invoiced__gt=0
    ).order_by('?')
    if not all_producers:
        offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
    for offer_item in offer_item_qs:
        # It's possible to round the ordered qty even If we do not manage stock
        if offer_item.manage_replenishment:
            needed = (offer_item.quantity_invoiced - offer_item.stock)
        else:
            needed = offer_item.quantity_invoiced
        if needed > DECIMAL_ZERO:
            offer_item.add_2_stock = offer_item.producer_order_by_quantity - (
            needed % offer_item.producer_order_by_quantity)
            offer_item.save()
    # 2 - Add Transport
    offer_item_qs = OfferItem.objects.filter(
        permanence_id=permanence.id,
        is_active=False,
        order_unit=PRODUCT_ORDER_UNIT_TRANSPORTATION
    ).order_by('?')
    if not all_producers:
        offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
    for offer_item in offer_item_qs:
        buying_group = Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by('?').first()
        create_or_update_one_purchase(buying_group, offer_item, 1, None, True, is_box_content=False)
    membership_fee_product = Product.objects.filter(is_membership_fee=True, is_active=True).order_by('?').first()
    membership_fee_product.producer_unit_price = repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE
    # Update the prices
    membership_fee_product.save()
    membership_fee_offer_item = get_or_create_offer_item(
        permanence, membership_fee_product.id,
        membership_fee_product.producer_id
    )
    for customer in Customer.objects.filter(
            is_active=True,
            may_order=True,
            customerinvoice__permanence_id=permanence.id,
            customerinvoice__total_price_with_tax__gt=DECIMAL_ZERO,
            represent_this_buyinggroup=False
    ).order_by('?'):
        # 3 - Add Deposit
        offer_item_qs = OfferItem.objects.filter(
            permanence_id=permanence.id,
            order_unit=PRODUCT_ORDER_UNIT_DEPOSIT
        ).order_by('?')
        if not all_producers:
            offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
        for offer_item in offer_item_qs:
            create_or_update_one_purchase(customer, offer_item, 1, None, True, is_box_content=False)
            create_or_update_one_purchase(customer, offer_item, 0, None, True, is_box_content=False)
        # 4 - Add Add Membership fee Subscription
        if repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION > 0:
            # There is a membership fee
            if customer.membership_fee_valid_until < today:
                permanence.producers.add(membership_fee_offer_item.producer_id)
                create_or_update_one_purchase(customer, membership_fee_offer_item, 1, None, True, is_box_content=False)
                while customer.membership_fee_valid_until < today:
                    # Do not pay the membership fee if no order passed during a certain amount of time
                    customer.membership_fee_valid_until = add_months(
                        customer.membership_fee_valid_until,
                        repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION
                    )
                customer.save(update_fields=['membership_fee_valid_until', ])

    # 5 - Add Common participation Subscription
    if all_producers:
        for offer_item in OfferItem.objects.filter(
                permanence_id=permanence.id, is_membership_fee=False,
                order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION
        ).order_by('?'):
            for customer in Customer.objects.filter(
                    is_active=True, may_order=True,
                    represent_this_buyinggroup=False
            ).order_by('?'):
                permanence.producers.add(offer_item.producer_id)
                create_or_update_one_purchase(customer, offer_item, 1, None, True, is_box_content=False)
        # Disable subscription for next permanence
        Product.objects.filter(
            order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION, is_into_offer=True, is_membership_fee=False
        ).order_by('?').update(is_into_offer=False)

        permanence.set_status(PERMANENCE_CLOSED, allow_downgrade=False)
        if not repanier.apps.REPANIER_SETTINGS_INVOICE and repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT is None:
            # No Invoice and no bank_account --> auto archive
            # Put send permanences to the done status, because they will "never" be invoiced
            for permanence in Permanence.objects.filter(status=PERMANENCE_SEND):
                permanence.set_status(PERMANENCE_ARCHIVED, update_payment_date=True)
    else:
        permanence.set_status(PERMANENCE_CLOSED, all_producers=all_producers, producers_id=producers_id)
    # 6 - Refresh the Purchase 'sum' for each customer
    recalculate_order_amount(
        permanence_id=permanence.id,
        all_producers=all_producers,
        producers_id=producers_id,
        send_to_producer=False,
    )


@transaction.atomic
def send_order(permanence, all_producers, producers_id=None, deliveries_id=None):
    getcontext().rounding = ROUND_HALF_UP
    recalculate_order_amount(
        permanence_id=permanence.id,
        all_producers=all_producers,
        producers_id=producers_id,
        send_to_producer=True
    )
    try:
        email_order.email_order(permanence.id, all_producers, closed_deliveries_id=deliveries_id, producers_id=producers_id)
    except Exception as error_str:
        print("################################## send_order")
        print(error_str)
        print("##################################")


def close_send_order(permanence_id, all_producers, producers_id=None, deliveries_id=None, send=False):
    # Be carefull : use permanece_id, deliveries_id, ... and not objects
    # for the "trhread" processing
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    if permanence is not None:
        if permanence.with_delivery_point:
            # Delete CLOSED orders without any delivery point
            # Those orders are created in tools.my_order_confirmation when a customer want to place an order
            # but there is no more available delivery point for him
            # or when the customer has not selected any delivery point
            # qs = CustomerInvoice.objects.filter(
            #     permanence_id=permanence.id, status=PERMANENCE_CLOSED, delivery__isnull=True
            # ).order_by('?')
            # Purchase.objects.filter(
            #     customer_invoice__in=qs
            # ).order_by('?').delete()
            # qs.delete()
            qs = DeliveryBoard.objects.filter(
                permanence_id=permanence.id,
                status=PERMANENCE_OPENED,
                id__in=deliveries_id
            ).order_by('?')

            for delivery in qs:
                delivery.set_status(PERMANENCE_WAIT_FOR_CLOSED, all_producers, producers_id=producers_id)
                close_order_delivery(permanence, delivery, all_producers, producers_id=producers_id)
            if DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status=PERMANENCE_OPENED
            ).order_by('?').count() == 0:
                # The whole permanence must be closed
                permanence.set_status(PERMANENCE_WAIT_FOR_CLOSED, allow_downgrade=False)
                close_order(permanence, all_producers=True)
        else:
            if permanence.status == PERMANENCE_OPENED:
                permanence.set_status(PERMANENCE_WAIT_FOR_CLOSED, all_producers=all_producers,
                                      producers_id=producers_id)
                close_order(permanence, all_producers, producers_id=producers_id)
        if send:
            if permanence.with_delivery_point:
                send_deliveries_id = []
                qs = DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status=PERMANENCE_CLOSED,
                    id__in=deliveries_id
                ).order_by('?')
                for delivery in qs:
                    delivery.set_status(PERMANENCE_WAIT_FOR_SEND, all_producers, producers_id=producers_id)
                    send_deliveries_id.append(delivery.id)
                send_order(permanence, all_producers, producers_id=producers_id, deliveries_id=send_deliveries_id)
                qs = DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status=PERMANENCE_WAIT_FOR_SEND,
                    id__in=deliveries_id
                ).order_by('?')
                for delivery in qs:
                    delivery.set_status(PERMANENCE_SEND, all_producers, producers_id=producers_id)
                if DeliveryBoard.objects.filter(
                        permanence_id=permanence.id,
                        status__gte=PERMANENCE_OPENED,
                        status__lte=PERMANENCE_CLOSED
                ).order_by('?').count() == 0:
                    permanence.set_status(PERMANENCE_SEND)
            elif permanence.status == PERMANENCE_CLOSED or not all_producers:
                # Don't send if PERMANENCE_WAIT_FOR_CLOSED
                permanence.set_status(PERMANENCE_WAIT_FOR_SEND, all_producers=all_producers, producers_id=producers_id)
                send_order(permanence, all_producers, producers_id=producers_id)
                permanence.set_status(PERMANENCE_SEND, all_producers=all_producers, producers_id=producers_id)


def admin_close(permanence_id, all_producers=False, deliveries_id=None, producers_id=None):
    # close_send_order(permanence_id, deliveries_id, False, False)
    thread.start_new_thread(close_send_order, (permanence_id, all_producers, producers_id, deliveries_id, False))
    user_message = _("The orders are being closed.")
    user_message_level = messages.INFO
    return user_message, user_message_level


def admin_send(permanence_id, all_producers=False, deliveries_id=None, producers_id=None):
    # close_send_order(permanence_id, deliveries_id, True)
    thread.start_new_thread(close_send_order, (permanence_id, all_producers, producers_id, deliveries_id, True))
    user_message = _("The orders are being send.")
    user_message_level = messages.INFO
    return user_message, user_message_level
