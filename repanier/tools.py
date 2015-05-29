# -*- coding: utf-8
from __future__ import unicode_literals
from django.template.loader import render_to_string
from django.utils import translation
from const import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from models import repanier_settings
from django.utils.formats import number_format
from django.db import transaction
import models


def ignore_exception(exception=Exception, default_val=0):
    """Returns a decorator that ignores an exception raised by the function it
    decorates.

    Using it as a decorator:

    @ignore_exception(ValueError)
    def my_function():
    pass

    Using it as a function wrapper:

    int_try_parse = ignore_exception(ValueError)(int)
    """
    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except exception:
                return default_val
        return wrapper
    return decorator

sint = ignore_exception(ValueError)(int)
# print sint("Hello World") # prints 0
# print sint("1340") # prints 1340


def get_allowed_mail_extension():
    allowed_mail_extension = "@%s" % settings.ALLOWED_HOSTS[0]
    cut_index = len(settings.ALLOWED_HOSTS[0]) - 1
    point_counter = 0
    while cut_index >= 0:
        if settings.ALLOWED_HOSTS[0][cut_index] == ".":
            point_counter += 1
            if point_counter == 2:
                allowed_mail_extension = "@%s" % settings.ALLOWED_HOSTS[0][cut_index + 1:]
                break
        cut_index -= 1
    return allowed_mail_extension


def send_email(email=None):
    if settings.DEBUG:
        if repanier_settings["TEST_MODE"]:
            coordinator = models.Staff.objects.filter(is_coordinator=True, is_active=True).order_by().first()
            if coordinator is not None:
                email.to = [coordinator.user.email]
            else:
                email.to = [v for k, v in settings.ADMINS]
            email.cc = []
            email.bcc = []
            email.send()
        else:
            pass
    elif repanier_settings["TEST_MODE"]:
        coordinator = models.Staff.objects.filter(is_coordinator=True, is_active=True).order_by().first()
        if coordinator is not None:
            email.to = [coordinator.user.email]
        else:
            email.to = [v for k, v in settings.ADMINS]
        email.cc = []
        email.bcc = []
        email.send()
    else:
        email.send()


def get_signature(is_reply_to_order_email=False, is_reply_to_invoice_email=False):
    sender_email = None
    sender_function = ""
    signature = ""
    cc_email_staff = []
    for staff in models.Staff.objects.filter(is_active=True).order_by():
        cc_email_staff.append(staff.user.email)
        if (is_reply_to_order_email and staff.is_reply_to_order_email) \
                or (is_reply_to_invoice_email and staff.is_reply_to_invoice_email):
            sender_email = staff.user.email
            sender_function = staff.long_name
            r = staff.customer_responsible
            if r:
                if r.long_basket_name:
                    signature = "%s - %s" % (r.long_basket_name, r.phone1)
                else:
                    signature = "%s - %s" % (r.short_basket_name, r.phone1)
                if r.phone2 and len(r.phone2) > 0:
                    signature += " / %s" % (r.phone2,)
    if sender_email is None:
        sender_email = "no-reply" + get_allowed_mail_extension()
    return sender_email, sender_function, signature, cc_email_staff


LENGTH_BY_PREFIX = [
    (0xC0, 2),  # first byte mask, total codepoint length
    (0xE0, 3),
    (0xF0, 4),
    (0xF8, 5),
    (0xFC, 6),
]


def codepoint_length(first_byte):
    if first_byte < 128:
        return 1  # ASCII
    for mask, length in LENGTH_BY_PREFIX:
        if first_byte & 0xF0 == mask:
            return length
        elif first_byte & 0xF8 == 0xF8:
            return length
    assert False, 'Invalid byte %r' % first_byte


def cap_to_bytes_length(unicode_text, byte_limit):
    utf8_bytes = unicode_text.encode("utf8") # .encode('UTF-8', 'replace')
    cut_index = 0
    while cut_index < len(utf8_bytes):
        step = codepoint_length(ord(utf8_bytes[cut_index]))
        if cut_index + step > byte_limit:
            # can't go a whole codepoint further, time to cut
            return utf8_bytes[:cut_index] + '...'
        else:
            cut_index += step
    return utf8_bytes


def cap(s, l):
    if s is not None:
        if not isinstance(s, basestring):
            s = str(s)
        # if isinstance(s, unicode):
        #     s = cap_to_bytes_length(s, l - 4)
        # else:
        s = s if len(s) <= l else s[0:l - 4] + '...'
        return s
    else:
        return None


def get_invoice_unit(order_unit=PRODUCT_ORDER_UNIT_PC, qty=0):
    if order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
        unit = _("/ kg")
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        unit = _("/ l")
    else:
        if qty < 2:
            unit = _("/ piece")
        else:
            unit = _("/ pieces")
    return unit


def get_preparator_unit(order_unit=PRODUCT_ORDER_UNIT_PC):
    # Used when producing the preparation list.
    if order_unit in [PRODUCT_ORDER_UNIT_PC, PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                      PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        unit = _("Piece(s) :")
    elif order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
        unit = _("€ or kg :")
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        unit = _("L :")
    else:
        unit = _("Kg :")
    return unit


def get_display(qty=0, order_average_weight=0, order_unit=PRODUCT_ORDER_UNIT_PC, price=None,
                for_customer=True):
    # if for_customer:
    # if for_customer is not None:
    if qty == DECIMAL_ZERO:
        base_unit = unit = ""
    elif qty < 2:
        base_unit = _('piece')
        unit = "(%s)" % (_('piece'))
    else:
        base_unit = _('pieces')
        unit = "(%s)" % (_('pieces'))
    # else:
    #     base_unit = unit = ""
    magnitude = 1
    if order_unit == PRODUCT_ORDER_UNIT_KG:
        if for_customer:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 1:
                base_unit = _('kg')
                unit = "(%s)" % (_('gr'))
                magnitude = 1000
            else:
                base_unit = _('kg')
                unit = "(%s)" % (_('kg'))
        else:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            else:
                base_unit = _('kg')
                unit = "(%s)" % (_('kg'))
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        if for_customer:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 1:
                base_unit = _('l')
                unit = "(%s)" % (_('cl'))
                magnitude = 100
            else:
                base_unit = _('l')
                unit = "(%s)" % (_('l'))
        else:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            else:
                base_unit = _('l')
                unit = "(%s)" % (_('l'))
    elif order_unit in [PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG]:
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
        if order_unit == PRODUCT_ORDER_UNIT_PC_KG and price is not None:
            price *= order_average_weight
        if average_weight < 1:
            average_weight_unit = _('gr')
            average_weight *= 1000
        else:
            average_weight_unit = _('kg')
        decimal = 3
        if average_weight == int(average_weight):
            decimal = 0
        elif average_weight * 10 == int(average_weight * 10):
            decimal = 1
        elif average_weight * 100 == int(average_weight * 100):
            decimal = 2
        tilde = ''
        if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            tilde = '~'
        if for_customer:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 2:
                base_unit = _('piece')
                unit = "(%s %s%s%s)" % (_('piece'), tilde, number_format(average_weight, decimal), average_weight_unit)
            else:
                base_unit = _('pieces')
                unit = "(%s %s%s%s)" % (_('pieces'), tilde, number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 2:
                base_unit = ""
                unit = "(%s%s%s)" % (tilde, number_format(average_weight, decimal), average_weight_unit)
            else:
                base_unit = ""
                unit = "(%s%s%s)" % (tilde, number_format(average_weight, decimal), average_weight_unit)
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
        if average_weight < 1:
            average_weight_unit = _('cl')
            average_weight *= 100
        else:
            average_weight_unit = _('l')
        decimal = 3
        if average_weight == int(average_weight):
            decimal = 0
        elif average_weight * 10 == int(average_weight * 10):
            decimal = 1
        elif average_weight * 100 == int(average_weight * 100):
            decimal = 2
        if for_customer:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 2:
                base_unit = _('piece')
                unit = "(%s =%s%s)" % (_('piece'), number_format(average_weight, decimal), average_weight_unit)
            else:
                base_unit = _('pieces')
                unit = "(%s =%s%s)" % (_('pieces'), number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                base_unit = unit = ""
            elif qty < 2:
                base_unit = ""
                unit = "(%s%s)" % (number_format(average_weight, decimal), average_weight_unit)
            else:
                base_unit = ""
                unit = "(%s%s)" % (number_format(average_weight, decimal), average_weight_unit)
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
            if qty == DECIMAL_ZERO:
                unit = ""
            elif qty < 2:
                if average_weight < 2:
                    base_unit = _('piece')
                    unit = "(%s =%s %s)" % (_('piece'), number_format(average_weight, 0), _('pc'))
                else:
                    base_unit = _('piece')
                    unit = "(%s =%s %s)" % (_('piece'), number_format(average_weight, 0), _('pcs'))
            else:
                if average_weight < 2:
                    base_unit = _('pieces')
                    unit = "(%s =%s %s)" % (_('pieces'), number_format(average_weight, 0), _('pc'))
                else:
                    base_unit = _('pieces')
                    unit = "(%s =%s %s)" % (_('pieces'), number_format(average_weight, 0), _('pcs'))
        else:
            if average_weight == DECIMAL_ZERO:
                base_unit = unit = ""
            elif average_weight < 2:
                base_unit = ""
                unit = '(%s %s)' % (number_format(average_weight, 0), _('pc'))
            else:
                base_unit = ""
                unit = '(%s %s)' % (number_format(average_weight, 0), _('pcs'))
    if price is not None:
        price = Decimal(price * qty).quantize(TWO_DECIMALS)
        price_display = " = %s" % (number_format(price, 2))
    else:
        price = DECIMAL_ZERO
        price_display = ""
    qty *= magnitude
    decimal = 3
    if qty == int(qty):
        decimal = 0
    elif qty * 10 == int(qty * 10):
        decimal = 1
    elif qty * 100 == int(qty * 100):
        decimal = 2
    if for_customer:
        qty_display = "%s %s" % (number_format(qty, decimal), unit)
    else:
        qty_display = "%s" % (unit)
    return qty_display, price_display, base_unit, unit, price


def get_user_order_amount(permanence_id, customer_id=None, user=None):
    a_total_price_with_tax = DECIMAL_ZERO
    if user is not None and not user.is_anonymous():
        customer_invoice = models.CustomerInvoice.objects.filter(
            permanence_id=permanence_id,
            customer__user=user).order_by().only("total_price_with_tax").first()
        if customer_invoice is not None:
            a_total_price_with_tax = customer_invoice.total_price_with_tax
    if customer_id is not None:
        customer_invoice = models.CustomerInvoice.objects.filter(
            permanence_id=permanence_id,
            customer_id=customer_id).order_by().only("total_price_with_tax").first()
        if customer_invoice is not None:
            a_total_price_with_tax = customer_invoice.total_price_with_tax
    return number_format(a_total_price_with_tax, 2)


def recalculate_order_amount(permanence_id=None,
                             permanence_status=None,
                             customer_id=None,
                             offer_item_queryset=None,
                             send_to_producer=False,
                             migrate=False):
    if permanence_id is not None:
        if send_to_producer or migrate:
            models.ProducerInvoice.objects.filter(permanence_id=permanence_id)\
                .update(total_price_with_tax=DECIMAL_ZERO)
            models.CustomerInvoice.objects.filter(permanence_id=permanence_id)\
                .update(total_price_with_tax=DECIMAL_ZERO)
            models.CustomerProducerInvoice.objects.filter(permanence_id=permanence_id)\
                .update(
                    total_purchase_with_tax=DECIMAL_ZERO,
                    total_selling_with_tax=DECIMAL_ZERO
                )
            models.OfferItem.objects.filter(permanence_id=permanence_id)\
                .update(
                    quantity_invoiced=DECIMAL_ZERO,
                    total_purchase_with_tax=DECIMAL_ZERO,
                    total_selling_with_tax=DECIMAL_ZERO
                )
            for offer_item in models.OfferItem.objects.filter(permanence_id=permanence_id, is_active=True, manage_stock=True)\
                    .exclude(add_2_stock=DECIMAL_ZERO).order_by():
                # Recalculate the total_price_with_tax of ProducerInvoice and
                # the total_purchase_with_tax of OfferItem
                # taking into account "add_2_stock"
                # offer_item.previous_stock = DECIMAL_ZERO
                offer_item.previous_add_2_stock = DECIMAL_ZERO
                offer_item.save()
        if customer_id is None:
            if offer_item_queryset is not None:
                if permanence_status < PERMANENCE_SEND:
                    purchase_set = models.PurchaseOpenedForUpdate.objects\
                        .filter(permanence_id=permanence_id, offer_item__in=offer_item_queryset)\
                        .order_by()
                else:
                    purchase_set = models.PurchaseClosedForUpdate.objects\
                        .filter(permanence_id=permanence_id, offer_item__in=offer_item_queryset)\
                        .order_by()
            else:
                if permanence_status < PERMANENCE_SEND:
                    purchase_set = models.PurchaseOpenedForUpdate.objects\
                        .filter(permanence_id=permanence_id)\
                        .order_by()
                else:
                    purchase_set = models.PurchaseClosedForUpdate.objects\
                        .filter(permanence_id=permanence_id)\
                        .order_by()
        else:
            if permanence_status < PERMANENCE_SEND:
                purchase_set = models.PurchaseOpenedForUpdate.objects\
                    .filter(permanence_id=permanence_id, customer_id=customer_id)\
                    .order_by()
            else:
                purchase_set = models.PurchaseClosedForUpdate.objects\
                    .filter(permanence_id=permanence_id, customer_id=customer_id)\
                    .order_by()

        for purchase in purchase_set:
            # Recalcuate the total_price_with_tax of ProducerInvoice,
            # the total_price_with_tax of CustomerInvoice,
            # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
            # and quantity_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
            if migrate:
                purchase.previous_quantity_invoiced = DECIMAL_ZERO
                purchase.previous_purchase_price = DECIMAL_ZERO
                purchase.previous_selling_price = DECIMAL_ZERO
            if send_to_producer:
                purchase.previous_quantity_invoiced = DECIMAL_ZERO
                purchase.previous_purchase_price = DECIMAL_ZERO
                purchase.previous_selling_price = DECIMAL_ZERO
                offer_item = purchase.offer_item
                if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                    purchase.quantity_invoiced = (purchase.quantity_ordered * offer_item.order_average_weight)\
                        .quantize(FOUR_DECIMALS)
                    if offer_item.wrapped:
                        purchase.quantity_for_preparation_sort_order = DECIMAL_ZERO
                    else:
                        purchase.quantity_for_preparation_sort_order = purchase.quantity_ordered
                else:
                    purchase.quantity_invoiced = purchase.quantity_ordered
                    purchase.quantity_for_preparation_sort_order = DECIMAL_ZERO
            purchase.save()

def find_customer(user=None, customer_id=None):
    customer = None
    try:
        customer_set = None
        if user is not None:
            customer_set = models.Customer.objects.filter(
                id=user.customer.id, is_active=True, may_order=True).order_by()[:1]
        if customer_id is not None:
            customer_set = models.Customer.objects.filter(
                id=customer_id, is_active=True, may_order=True).order_by()[:1]
        if customer_set is not None:
            customer = customer_set[0]
    except:
        # user.customer doesn't exist -> the user is not a customer.
        pass
    return customer


@transaction.atomic
def update_or_create_purchase(user_id=None, customer=None, offer_item_id=None, value_id=None, close_orders=False):
    result = "ko"
    if offer_item_id is not None and value_id is not None:
        # try:
        if user_id is not None:
            # customer = find_customer(user=user)
            customer = models.Customer.objects.filter(user_id=user_id, is_active=True, may_order=True)\
                .only("id", "is_active", "vat_id")\
                .order_by().first()
        if customer is not None:
            offer_item = models.OfferItem.objects.select_for_update(nowait=False)\
                .filter(id=offer_item_id, is_active=True)\
                .order_by().first()
            if offer_item is not None:
                permanence = models.Permanence.objects.filter(id=offer_item.permanence_id)\
                    .only("status", "permanence_date")\
                    .order_by().first()
                # The close_orders flag is used because we need to forbid
                # customers to add purchases during the close_orders_async process
                # when the status is PERMANENCE_WAIT_FOR_SEND
                if (permanence.status == PERMANENCE_OPENED) or close_orders:
                    # The offer_item belong to an open permanence
                    purchase = models.PurchaseOpenedForUpdate.objects.filter(
                        offer_item_id=offer_item.id,
                        permanence_id=permanence.id,
                        customer_id=customer.id)\
                        .order_by().first()
                    if purchase is not None:
                        q_previous_order = purchase.quantity_ordered
                    else:
                        q_previous_order = DECIMAL_ZERO
                    q_min = offer_item.customer_minimum_order_quantity
                    if offer_item.limit_order_quantity_to_stock:
                        available = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
                        q_alert = min(available, offer_item.customer_alert_order_quantity)
                        if q_alert < DECIMAL_ZERO:
                            q_alert = DECIMAL_ZERO
                    else:
                        q_alert = offer_item.customer_alert_order_quantity
                    q_step = offer_item.customer_increment_order_quantity
                    if value_id == 0:
                        q_order = DECIMAL_ZERO
                    elif value_id == 1:
                        q_order = q_min
                    else:
                        if q_min < q_step:
                            # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                            # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                            if value_id == 2:
                                q_order = q_step
                            else:
                                q_order = q_step * ( value_id - 1 )
                        else:
                            # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                            # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                            q_order = q_min + q_step * ( value_id - 1 )
                    if q_order <= q_alert:
                        if purchase is not None:
                            purchase.quantity_ordered = q_order
                            purchase.save()
                        else:
                            if offer_item.vat_level in [VAT_200, VAT_300] \
                                    and customer.vat_id is not None \
                                    and len(customer.vat_id) > 0:
                                is_compensation = True
                            else:
                                is_compensation = False
                            models.PurchaseOpenedForUpdate.objects.create(
                                permanence_id=permanence.id,
                                permanence_date=permanence.permanence_date,
                                offer_item_id=offer_item.id,
                                producer_id=offer_item.producer_id,
                                customer_id=customer.id,
                                quantity_ordered=q_order,
                                invoiced_price_with_compensation=is_compensation
                            )
                        customer_invoice = models.CustomerInvoice.objects.filter(permanence_id=permanence.id,
                                           customer_id=customer.id)\
                            .only("total_price_with_tax")\
                            .order_by().first()
                        if customer_invoice is None:
                            result = "ok0"
                        else:
                            result = "ok" + number_format(customer_invoice.total_price_with_tax, 2)

                            # except:
                            # # user.customer doesn't exist -> the user is not a customer.
                            #   pass
        else:
            result = "ok0"
    return result


def clean_offer_item(permanence, queryset, reorder=False):
    cur_language = translation.get_language()
    for offer_item in queryset:
        offer_item.picture = offer_item.product.picture
        offer_item.reference = offer_item.product.reference
        offer_item.department_for_customer_id = offer_item.product.department_for_customer_id
        offer_item.producer_id = offer_item.product.producer_id
        offer_item.order_unit = offer_item.product.order_unit
        offer_item.wrapped = offer_item.product.wrapped
        offer_item.order_average_weight = offer_item.product.order_average_weight
        offer_item.placement = offer_item.product.placement
        offer_item.producer_price_are_wo_vat = offer_item.producer.producer_price_are_wo_vat
        offer_item.producer_vat = offer_item.product.producer_vat
        offer_item.customer_vat = offer_item.product.customer_vat
        offer_item.compensation = offer_item.product.compensation
        # if offer_item.producer.producer_price_are_wo_vat:
        #     offer_item.producer_unit_price = offer_item.product.producer_unit_price + offer_item.producer_vat
        # else:
        offer_item.producer_unit_price = offer_item.product.producer_unit_price
        offer_item.customer_unit_price = offer_item.product.customer_unit_price
        offer_item.unit_deposit = offer_item.product.unit_deposit
        offer_item.vat_level = offer_item.product.vat_level
        offer_item.limit_order_quantity_to_stock = offer_item.product.limit_order_quantity_to_stock
        offer_item.manage_stock = offer_item.producer.manage_stock
        offer_item.price_list_multiplier = offer_item.producer.price_list_multiplier
        offer_item.is_resale_price_fixed = offer_item.producer.is_resale_price_fixed
        offer_item.stock = offer_item.product.stock
        if reorder:
            offer_item.add_2_stock = DECIMAL_ZERO
        offer_item.customer_minimum_order_quantity = offer_item.product.customer_minimum_order_quantity
        offer_item.customer_increment_order_quantity = offer_item.product.customer_increment_order_quantity
        offer_item.customer_alert_order_quantity = offer_item.product.customer_alert_order_quantity
        offer_item.save()

    # Now got everything to calculate the sort order of the order display screen
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        translation.activate(language["code"])
        for offer_item in queryset:
            offer_item.long_name = offer_item.product.long_name
            offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html', {'offer': offer_item})
            offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html', {'offer': offer_item})
            offer_item.cache_part_c = render_to_string('repanier/cache_part_c.html', {'offer': offer_item})
            offer_item.cache_part_e = render_to_string('repanier/cache_part_e.html', {'offer': offer_item})
            offer_item.save_translations()
        if reorder:
            # The "order_by" of the queryset is only relevant after the previous "for" has been done.
            i = 0
            queryset = queryset.filter(
                translations__language_code=language["code"]
            ).order_by().order_by(
                "department_for_customer__tree_id",
                "department_for_customer__lft",
                "translations__long_name",
                "order_average_weight",
                "producer__short_profile_name"
            )
            for offer_item in queryset:
                offer_item.order_sort_order = i
                i += 1
                offer_item.save_translations()

        departementforcustomer_set = models.LUT_DepartmentForCustomer.objects.filter(
                        offeritem__permanence_id=permanence.id,
                        offeritem__order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT)\
            .order_by("tree_id", "lft")\
            .distinct("id", "tree_id", "lft")
        if departementforcustomer_set:
            pass
        if repanier_settings['DISPLAY_PRODUCERS_ON_ORDER_FORM']:
            producer_set = models.Producer.objects.filter(permanence=permanence.id).only("id", "short_profile_name")
        else:
            producer_set = None
        permanence.cache_part_d = render_to_string('repanier/cache_part_d.html',
           {'producer_set': producer_set, 'departementforcustomer_set': departementforcustomer_set})
        permanence.save_translations()
    translation.activate(cur_language)
