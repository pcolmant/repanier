# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.models import get_current_site
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.db import transaction
from django.utils import timezone
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool
from repanier.const import *
from repanier.settings import *
from repanier.email import email_alert
from repanier.email import email_offer
from repanier.email import email_order
from repanier.models import Customer
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import Product
from repanier.models import Purchase
from repanier.tools import recalculate_order_amount
from repanier.tools import update_or_create_purchase
import thread


@transaction.atomic
def open(permanence_id, current_site_name):
    permanence = Permanence.objects.get(id=permanence_id)
    # 1- Deactivate all offer item of this permanence
    # Not needed, already done in 'back_to_previous_status'

    # 2 - Activate all offer item depending on selection in the admin
    producers_in_this_permanence = Producer.objects.filter(
        permanence=permanence_id, is_active=True)

    for product in Product.objects.filter(
            producer__in=producers_in_this_permanence, is_active=True, is_into_offer=True,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT).order_by():
        offer_item = OfferItem.objects.filter(product_id=product.id, permanence_id=permanence_id).order_by().first()
        if offer_item:
            offer_item.is_active = True
            offer_item.limit_to_alert_order_quantity = product.producer.limit_to_alert_order_quantity
            offer_item.customer_alert_order_quantity = product.customer_alert_order_quantity
            offer_item.save(
                update_fields=['is_active', 'limit_to_alert_order_quantity', 'customer_alert_order_quantity'])
        else:
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product=product,
                limit_to_alert_order_quantity=product.producer.limit_to_alert_order_quantity,
                customer_alert_order_quantity=product.customer_alert_order_quantity
            )

    # 3 - Activate purchased products even if not in selected in the admin
    for purchase in Purchase.objects.filter(permanence_id=permanence_id,
                                            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT).exclude(quantity=0).order_by():
        offer_item = OfferItem.objects.filter(product_id=purchase.product_id,
                                              permanence_id=permanence_id).order_by().first()
        if offer_item:
            offer_item.is_active = True
            offer_item.limit_to_alert_order_quantity = product.producer.limit_to_alert_order_quantity
            offer_item.customer_alert_order_quantity = product.customer_alert_order_quantity
            offer_item.save(
                update_fields=['is_active', 'limit_to_alert_order_quantity', 'customer_alert_order_quantity'])
        else:
            OfferItem.objects.create(
                permanence_id=permanence_id,
                product=product,
                limit_to_alert_order_quantity=product.producer.limit_to_alert_order_quantity,
                customer_alert_order_quantity=product.customer_alert_order_quantity
            )

    # 4 - Generate cache
    departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                    product__offeritem__permanence_id=permanence.id).distinct()
    if REPANIER_DISPLAY_PRODUCERS_ON_ORDER_FORM:
        producer_set = Producer.objects.filter(permanence=permanence_id)
    else:
        producer_set = Producer.objects.none()
    cur_language = translation.get_language()
    # try:
    #     for language in settings.LANGUAGES:
    #         translation.activate(language[0])
    #         if permanence.has_translation(language[0]):
    #             permanence.cache_part_d = render_to_string('repanier/cache_part_d.html',
    #                {'producer_set': producer_set, 'departementforcustomer_set': departementforcustomer_set})
    #         permanence.save()
    #         for offer_item in OfferItem.objects.filter(permanence_id=permanence_id).order_by():
    #             if offer_item.has_translation(language[0]):
    #                 offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html', {'offer': offer_item})
    #                 offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html', {'offer': offer_item})
    #                 offer_item.cache_part_c = render_to_string('repanier/cache_part_c.html', {'offer': offer_item})
    #                 offer_item.save()
    # finally:
    #     translation.activate(cur_language)
    try:
        for language in settings.LANGUAGES:
            translation.activate(language[0])
            permanence.cache_part_d = render_to_string('repanier/cache_part_d.html',
               {'producer_set': producer_set, 'departementforcustomer_set': departementforcustomer_set})
            permanence.save()
            for offer_item in OfferItem.objects.filter(permanence_id=permanence_id).order_by():
                offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html', {'offer': offer_item})
                offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html', {'offer': offer_item})
                offer_item.cache_part_c = render_to_string('repanier/cache_part_c.html', {'offer': offer_item})
                offer_item.save()
    finally:
        translation.activate(cur_language)

    # 5 - Calculate the Purchase 'sum' for each customer
    recalculate_order_amount(permanence_id, send_to_producer=False)
    email_offer.send(permanence_id, current_site_name)
    menu_pool.clear()
    permanence.status = PERMANENCE_OPENED
    permanence.save(update_fields=['status'])


def admin_back_to_planned(request, queryset):
    user_message = _("The status of this permanence prohibit you to go back to planned.")
    user_message_level = messages.ERROR
    for permanence in queryset[:1]:
        if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
            if permanence.status == PERMANENCE_SEND:
                # Restore qty
                for purchase in Purchase.objects.filter(permanence_id=permanence.id).order_by():
                    if purchase.quantity_send_to_producer != DECIMAL_ZERO:
                        purchase.quantity = purchase.quantity_send_to_producer
                        purchase.save(update_fields=['quantity'])
            OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=False)
            permanence.status = PERMANENCE_PLANNED
            permanence.save(update_fields=['status'])
            menu_pool.clear()
            user_message = _("The permanence is back to planned.")
            user_message_level = messages.INFO
    return user_message, user_message_level


def admin_open_and_send(request, queryset):
    current_site = get_current_site(request)
    user_message = _("The status of this permanence prohibit you to open and send offers.")
    user_message_level = messages.ERROR
    now = timezone.now()
    for permanence in queryset[:1]:
        if permanence.status == PERMANENCE_PLANNED:
            permanence.status = PERMANENCE_WAIT_FOR_OPEN
            permanence.is_updated_on = now
            permanence.save(update_fields=['status', 'is_updated_on'])
            # open(permanence.id, current_site.name)
            thread.start_new_thread(open, (permanence.id, current_site.name))
            user_message = _("The offers are being generated.")
            user_message_level = messages.INFO
        elif permanence.status == PERMANENCE_WAIT_FOR_OPEN:
            # On demand 15 minutes after the previous attempt, go back to previous status and send alert email
            # use only timediff, -> timezone conversion not needed
            timediff = now - permanence.is_updated_on
            if timediff.total_seconds() > (30 * 60):
                thread.start_new_thread(email_alert.send, (permanence, current_site.name))
                permanence.status = PERMANENCE_PLANNED
                permanence.save(update_fields=['status'])
                user_message = _(
                    "The action has been canceled by the system and an email send to the site administrator.")
                user_message_level = messages.WARNING
            else:
                user_message = _("Action refused by the system. Please, retry in %d minutes.") % (
                    31 - (int(timediff.total_seconds()) / 60))
                user_message_level = messages.WARNING
    return user_message, user_message_level


@transaction.atomic
def automatically_closed():
    # now = timezone.localtime(timezone.now())
    current_site_name = Site.objects.get_current().name
    translation.activate("fr")
    something_to_close = False
    for permanence in Permanence.objects.filter(
            status=PERMANENCE_OPENED,
            automatically_closed=True):
        permanence.status = PERMANENCE_WAIT_FOR_SEND
        permanence.save(update_fields=['status'])
        # close.delay(permanence.id, current_site_name)
        close(permanence.id, current_site_name)
        something_to_close = True
    return something_to_close


@transaction.atomic
def close(permanence_id, current_site_name):
    permanence = Permanence.objects.get(id=permanence_id)
    # Deposit
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=True,
                                               product__order_unit=PRODUCT_ORDER_UNIT_DEPOSIT).order_by():
        for customer in Customer.objects.filter(purchase__permanence_id=permanence_id).distinct().order_by():
            update_or_create_purchase(
                customer=customer,
                p_offer_item_id=offer_item.id,
                p_value_id="0",
                close_orders=True
            )
    # Subscription
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=True,
                                               product__order_unit=PRODUCT_ORDER_UNIT_SUBSCRIPTION).order_by():
        for customer in Customer.objects.filter(is_active=True, may_order=True,
                                                represent_this_buyinggroup=False).order_by():
            update_or_create_purchase(
                customer=customer,
                p_offer_item_id=offer_item.id,
                p_value_id="1",
                close_orders=True
            )
    # Transport
    for offer_item in OfferItem.objects.filter(permanence_id=permanence_id, is_active=True,
                                               product__order_unit=PRODUCT_ORDER_UNIT_TRANSPORTATION).order_by():
        for customer in Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by():
            update_or_create_purchase(
                customer=customer,
                p_offer_item_id=offer_item.id,
                p_value_id="1",
                close_orders=True
            )
    #
    recalculate_order_amount(permanence_id, send_to_producer=True)
    email_order.send(permanence_id, current_site_name)
    menu_pool.clear()
    permanence.status=PERMANENCE_SEND
    permanence.save(update_fields=['status'])


def admin_close_and_send(request, queryset):
    user_message = _("The status of this permanence prohibit you to close it.")
    user_message_level = messages.ERROR
    current_site = get_current_site(request)
    now = timezone.now()
    for permanence in queryset[:1]:
        if permanence.status == PERMANENCE_OPENED:
            permanence.status = PERMANENCE_WAIT_FOR_SEND
            permanence.is_updated_on = now
            permanence.save(update_fields=['status', 'is_updated_on'])
            thread.start_new_thread(close, (permanence.id, current_site.name))
            # close(permanence.id, current_site.name)
            user_message = _("The orders are being closed.")
            user_message_level = messages.INFO
        elif permanence.status == PERMANENCE_WAIT_FOR_SEND:
            # On demand 30 minutes after the previous attempt, go back to previous status and send alert email
            # use only timediff, -> timezone conversion not needed
            timediff = now - permanence.is_updated_on
            if timediff.total_seconds() > (30 * 60):
                thread.start_new_thread(email_alert.send, (permanence, current_site.name))
                permanence.status = PERMANENCE_OPENED
                permanence.save(update_fields=['status'])
                user_message = _(
                    "The action has been canceled by the system and an email send to the site administrator.")
                user_message_level = messages.WARNING
            else:
                user_message = _("Action refused by the system. Please, retry in %d minutes.") % (
                    31 - (int(timediff.total_seconds()) / 60))
                user_message_level = messages.WARNING
    return user_message, user_message_level

