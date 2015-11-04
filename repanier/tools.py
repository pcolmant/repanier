# -*- coding: utf-8
from __future__ import unicode_literals
import datetime
from django.db.models import Sum
from django.utils import timezone
from django.http import Http404
from django.template.loader import render_to_string
from django.utils import translation
import apps
from const import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
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
sboolean = ignore_exception(ValueError)(bool)
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
        if apps.REPANIER_SETTINGS_TEST_MODE:
            email.to = [v for k, v in settings.ADMINS]
            email.cc = []
            email.bcc = []
            email.send()
        else:
            pass
    elif apps.REPANIER_SETTINGS_TEST_MODE:
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
        if (is_reply_to_order_email and staff.is_reply_to_order_email) \
                or (is_reply_to_invoice_email and staff.is_reply_to_invoice_email):
            cc_email_staff.append(staff.user.email)
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
        elif staff.is_coordinator:
            cc_email_staff.append(staff.user.email)

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


def permanence_ok_or_404(permanence):
    if permanence is None:
        raise Http404
    if permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
        if permanence.status in [PERMANENCE_DONE, PERMANENCE_ARCHIVED]:
            if permanence.permanence_date < (
                timezone.now() - datetime.timedelta(weeks=LIMIT_DISPLAYED_PERMANENCE)
            ).date():
                raise Http404
        else:
            raise Http404


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


def get_base_unit(qty=0, order_unit=PRODUCT_ORDER_UNIT_PC):
    if order_unit == PRODUCT_ORDER_UNIT_KG:
        if qty == DECIMAL_ZERO:
            base_unit = ""
        else:
            base_unit = _('kg')
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        if qty == DECIMAL_ZERO:
            base_unit = ""
        else:
            base_unit = _('l')
    else:
        if qty == DECIMAL_ZERO:
            base_unit = ""
        elif qty < 2:
            base_unit = _('piece')
        else:
            base_unit = _('pieces')
    return base_unit


def get_display(qty=0, order_average_weight=0, order_unit=PRODUCT_ORDER_UNIT_PC, price=None,
                for_customer=True):
    magnitude = None
    display_qty = True
    if order_unit == PRODUCT_ORDER_UNIT_KG:
        if qty == DECIMAL_ZERO:
            unit = ""
        elif for_customer and qty < 1:
            unit = "%s" % (_('gr'))
            magnitude = 1000
        else:
            unit = "%s" % (_('kg'))
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        if qty == DECIMAL_ZERO:
            unit = ""
        elif for_customer and qty < 1:
            unit = "%s" % (_('cl'))
            magnitude = 100
        else:
            unit = "%s" % (_('l'))
    elif order_unit in [PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG]:
        display_qty = order_average_weight != 1
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
                unit = ""
            else:
                if display_qty:
                    unit = "%s%s%s" % (tilde, number_format(average_weight, decimal), average_weight_unit)
                else:
                    unit = "%s%s %s" % (tilde, number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                unit = ""
            else:
                unit = "%s%s%s" % (tilde, number_format(average_weight, decimal), average_weight_unit)
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
        display_qty = order_average_weight != 1
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
                unit = ""
            else:
                if display_qty:
                    unit = "%s%s" % (number_format(average_weight, decimal), average_weight_unit)
                else:
                    unit = "%s %s" % (number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                unit = ""
            else:
                unit = "%s%s" % (number_format(average_weight, decimal), average_weight_unit)
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
        display_qty = order_average_weight != 1
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
            if qty == DECIMAL_ZERO:
                unit = ""
            else:
                if average_weight < 2:
                    pc_pcs = _('pc')
                else:
                    pc_pcs = _('pcs')
                if display_qty:
                    unit = "%s%s" % (number_format(average_weight, 0), pc_pcs)
                else:
                    unit = "%s %s" % (number_format(average_weight, 0), pc_pcs)
        else:
            if average_weight == DECIMAL_ZERO:
                unit = ""
            elif average_weight < 2:
                unit = '%s %s' % (number_format(average_weight, 0), _('pc'))
            else:
                unit = '%s %s' % (number_format(average_weight, 0), _('pcs'))
    else:
        if qty == DECIMAL_ZERO:
            unit = ""
        elif qty < 2:
            unit = "%s" % (_('piece'))
        else:
            unit = "%s" % (_('pieces'))
    if price is not None:
        price = Decimal(price * qty).quantize(TWO_DECIMALS)
        price_display = " = %s" % (number_format(price, 2))
    else:
        price_display = ""
    if magnitude is not None:
        qty *= magnitude
    decimal = 3
    if qty == int(qty):
        decimal = 0
    elif qty * 10 == int(qty * 10):
        decimal = 1
    elif qty * 100 == int(qty * 100):
        decimal = 2
    if for_customer:
        if display_qty:
            qty_display = "%s (%s)" % (number_format(qty, decimal), unit)
        else:
            qty_display = "%s" % (unit)
    else:
        qty_display = "(%s)" % (unit)
    return qty_display, price_display


def payment_message(customer):
    if apps.REPANIER_SETTINGS_INVOICE:
        result_set = models.CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence__status__gte=PERMANENCE_OPENED,
            permanence__status__lte=PERMANENCE_SEND
        ).order_by().aggregate(Sum('total_price_with_tax'))
        orders_amount = result_set["total_price_with_tax__sum"] \
            if result_set["total_price_with_tax__sum"] is not None else DECIMAL_ZERO
        result_set = models.BankAccount.objects.filter(
            customer_id=customer.id, customer_invoice__isnull=True
        ).order_by().aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
        bank_amount_in = result_set["bank_amount_in__sum"] \
            if result_set["bank_amount_in__sum"] is not None else DECIMAL_ZERO
        bank_amount_out = result_set["bank_amount_out__sum"] \
            if result_set["bank_amount_out__sum"] is not None else DECIMAL_ZERO
        bank_amount_not_invoiced = bank_amount_in - bank_amount_out
        customer_last_balance = "%s %s %s %s &euro;." % (
            _('The balance of your account as of'),
            customer.date_balance.strftime('%d-%m-%Y'), _('is'),
            number_format(customer.balance, 2))
        if orders_amount != DECIMAL_ZERO or bank_amount_not_invoiced != DECIMAL_ZERO:
            if orders_amount != DECIMAL_ZERO:
                unbilled_sales = "%s &euro;" % (
                    number_format(orders_amount, 2)
                )
            if bank_amount_not_invoiced != DECIMAL_ZERO:
                unrecognized_payments = "%s &euro;" % (
                    number_format(bank_amount_not_invoiced, 2)
                )
            if orders_amount == DECIMAL_ZERO:
                customer_on_hold_movement = "%s (%s)." % (
                    _("This balance does not take account of any unrecognized payments"),
                    unrecognized_payments
                )
            elif bank_amount_not_invoiced == DECIMAL_ZERO:
                customer_on_hold_movement = "%s (%s)." % (
                    _("This balance does not take account of any unbilled sales"),
                    unbilled_sales
                )
            else:
                customer_on_hold_movement = "%s (%s) %s (%s)." % (
                    _("This balance does not take account of any unrecognized payments"),
                    unrecognized_payments,
                    _("and any unbilled sales"),
                    unbilled_sales
                )
        else:
            customer_on_hold_movement = ""
        if apps.REPANIER_SETTINGS_BANK_ACCOUNT is not None:
            to_pay = orders_amount - customer.balance - bank_amount_not_invoiced
            if to_pay > DECIMAL_ZERO:
                customer_payment_needed = "%s %s &euro; %s (%s) %s \"%s\"." % (
                    _('Please pay'),
                    number_format(to_pay, 2),
                    _('to the bank account number'),
                    apps.REPANIER_SETTINGS_BANK_ACCOUNT,
                    _('with communication'),
                    customer.short_basket_name)
            else:
                customer_payment_needed = "%s." % (_('Your account balance is sufficient'))
        else:
            customer_payment_needed = ""
            customer_on_hold_movement = ""
    else:
        customer_last_balance = ""
        customer_payment_needed = ""
        customer_on_hold_movement = ""
    # print("----------------------")
    # import sys
    # import codecs
    # sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    # print basket_amount
    # print "%s" % customer_last_balance
    # print "%s" % customer_on_hold_movement
    # print "%s" % customer_payment_needed
    return customer_last_balance, customer_on_hold_movement, customer_payment_needed


def basket_amount(customer, permanence):
    result = models.CustomerInvoice.objects.filter(
        customer_id=customer.id, permanence_id=permanence.id
    ).order_by().only("total_price_with_tax").first()
    return number_format(result.total_price_with_tax if result is not None else DECIMAL_ZERO, 2)


def recalculate_order_amount(permanence_id=None,
                             permanence_status=None,
                             customer_id=None,
                             offer_item_queryset=None,
                             send_to_producer=False,
                             re_init=False):
    if permanence_id is not None:
        if send_to_producer or re_init:
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
                    purchase_set = models.PurchaseOpenedOrClosedForUpdate.objects \
                        .filter(permanence_id=permanence_id, offer_item__in=offer_item_queryset)\
                        .order_by()
                else:
                    purchase_set = models.PurchaseSendForUpdate.objects \
                        .filter(permanence_id=permanence_id, offer_item__in=offer_item_queryset)\
                        .order_by()
            else:
                if permanence_status < PERMANENCE_SEND:
                    purchase_set = models.PurchaseOpenedOrClosedForUpdate.objects \
                        .filter(permanence_id=permanence_id)\
                        .order_by()
                else:
                    purchase_set = models.PurchaseSendForUpdate.objects \
                        .filter(permanence_id=permanence_id)\
                        .order_by()
        else:
            if permanence_status < PERMANENCE_SEND:
                purchase_set = models.PurchaseOpenedOrClosedForUpdate.objects \
                    .filter(permanence_id=permanence_id, customer_id=customer_id)\
                    .order_by()
            else:
                purchase_set = models.PurchaseSendForUpdate.objects \
                    .filter(permanence_id=permanence_id, customer_id=customer_id)\
                    .order_by()

        for purchase in purchase_set:
            # Recalcuate the total_price_with_tax of ProducerInvoice,
            # the total_price_with_tax of CustomerInvoice,
            # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
            # and quantity_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
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
                elif offer_item.order_unit == PRODUCT_ORDER_UNIT_KG:
                    purchase.quantity_invoiced = purchase.quantity_ordered
                    if offer_item.wrapped:
                        purchase.quantity_for_preparation_sort_order = DECIMAL_ZERO
                    else:
                        purchase.quantity_for_preparation_sort_order = purchase.quantity_ordered
                else:
                    purchase.quantity_invoiced = purchase.quantity_ordered
                    purchase.quantity_for_preparation_sort_order = DECIMAL_ZERO
            elif re_init:
                purchase.previous_quantity_invoiced = DECIMAL_ZERO
                purchase.previous_purchase_price = DECIMAL_ZERO
                purchase.previous_selling_price = DECIMAL_ZERO
            purchase.save()


@transaction.atomic
def update_or_create_purchase(user_id=None, customer=None, offer_item_id=None, value_id=None, close_orders=False):
    result = "ko"
    if offer_item_id is not None and value_id is not None:
        # try:
        if user_id is not None:
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
                    purchase = models.PurchaseOpenedOrClosedForUpdate.objects.filter(
                        offer_item_id=offer_item.id,
                        permanence_id=permanence.id,
                        customer_id=customer.id)\
                        .order_by().first()
                    if purchase is not None:
                        q_previous_order = purchase.quantity_ordered
                    else:
                        q_previous_order = DECIMAL_ZERO
                    q_min = offer_item.customer_minimum_order_quantity
                    if permanence.status == PERMANENCE_OPENED and offer_item.limit_order_quantity_to_stock:
                        q_alert = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
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
                            models.PurchaseOpenedOrClosedForUpdate.objects.create(
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
    for offer_item in queryset.select_related("product", "producer"):
        offer_item.picture2 = offer_item.product.picture2
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
        offer_item.producer_pre_opening = offer_item.producer.producer_pre_opening
        offer_item.manage_stock = offer_item.producer.manage_stock
        offer_item.price_list_multiplier = offer_item.producer.price_list_multiplier
        offer_item.is_resale_price_fixed = offer_item.producer.is_resale_price_fixed
        offer_item.stock = offer_item.product.stock
        if reorder:
            offer_item.add_2_stock = DECIMAL_ZERO
        offer_item.customer_minimum_order_quantity = offer_item.product.customer_minimum_order_quantity
        offer_item.customer_increment_order_quantity = offer_item.product.customer_increment_order_quantity
        offer_item.customer_alert_order_quantity = offer_item.product.customer_alert_order_quantity
        offer_item.producer_order_by_quantity = offer_item.product.producer_order_by_quantity
        offer_item.save()

    # Now got everything to calculate the sort order of the order display screen
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        translation.activate(language["code"])
        for offer_item in queryset.select_related("product", "producer", "department_for_customer"):
            offer_item.long_name = offer_item.product.long_name
            offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_c = render_to_string('repanier/cache_part_c.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_e = render_to_string('repanier/cache_part_e.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.save_translations()
        if reorder:
            # The "order_by" of the queryset is only relevant after the previous "for" has been done.
            i = 0
            queryset = queryset.filter(
                translations__language_code=language["code"]
            ).order_by().order_by(
                "department_for_customer__tree_id",
                # "department_for_customer__lft",
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
        if apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
            producer_set = models.Producer.objects.filter(permanence=permanence.id).only("id", "short_profile_name")
        else:
            producer_set = None
        permanence.cache_part_d = render_to_string('repanier/cache_part_d.html',
           {'producer_set': producer_set, 'departementforcustomer_set': departementforcustomer_set})
        permanence.save_translations()
    translation.activate(cur_language)
