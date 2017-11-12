# -*- coding: utf-8
import calendar
import datetime
import json
from urllib.request import urlopen

from django.conf import settings
from django.core import urlresolvers
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils.datetime_safe import new_datetime
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from six import string_types

from repanier import apps
from repanier.const import *
from repanier.email.email import RepanierEmail


def sboolean(str_val, default_val=False):
    try:
        return bool(str_val)
    except:
        return default_val


def sint(str_val, default_val=0):
    try:
        return int(str_val)
    except:
        return default_val


def next_row(query_iterator):
    try:
        return next(query_iterator)
    except StopIteration:
        # No rows were found, so do nothing.
        return


def emails_of_testers():
    from repanier.models.staff import Staff

    tester_qs = Staff.objects.filter(is_tester=True, is_active=True).order_by("id")
    testers = []
    for tester in tester_qs:
        testers.append(tester.user.email)
    return list(set(testers))


def send_test_email(host=None, port=None, host_user=None, host_password=None, use_tls=None):
    if host and port:
        to = emails_of_testers()
        if len(to) == 0:
            to = host_user
        # Avoid : string payload expected: <class 'django.utils.functional.__proxy__'>
        subject = "{}".format(_("Test from Repanier"))
        body = "{}".format(_("The mail is correctly configured on your Repanier website"))
        email = RepanierEmail(
            subject=subject,
            html_content=body,
            from_email=host_user,
            to=to,
            test_connection=True
        )
        email.from_email = host_user
        email.host = host
        email.port = port
        email.host_user = host_user
        email.host_password = host_password
        email.use_tls = use_tls
        email.use_ssl = not use_tls
        return email.send_email()
    else:
        return False


def send_email_to_who(is_email_send, board=False):
    from repanier.apps import REPANIER_SETTINGS_TEST_MODE
    if not is_email_send:
        if board:
            if REPANIER_SETTINGS_TEST_MODE:
                return True, _("This email will be sent to the following tester(s) : {}.").format(", ".join(emails_of_testers()))
            else:
                if settings.DEBUG:
                    return False, _("No email will be sent.")
                else:
                    return True, _("This email will be sent to the staff.")
        else:
            return False, _("No email will be sent.")
    else:
        if REPANIER_SETTINGS_TEST_MODE:
            return True, _("This email will be sent to the following tester(s) : {}.").format(", ".join(emails_of_testers()))
        else:
            if settings.DEBUG:
                return False, _("No email will be sent.")
            else:
                if board:
                    return True, _("This email will be sent to the preparation team and the staff.")
                else:
                    return True, _("This email will be sent to customers or producers depending of the case.")


def send_sms(sms_nr=None, sms_msg=None):
    try:
        if sms_nr is not None and sms_msg is not None:
            valid_nr = "0"
            i = 0
            while i < len(sms_nr) and not sms_nr[i] == '4':
                i += 1
            while i < len(sms_nr):
                if '0' <= sms_nr[i] <= '9':
                    valid_nr += sms_nr[i]
                i += 1
            if len(valid_nr) == 10 \
                    and apps.REPANIER_SETTINGS_SMS_GATEWAY_MAIL is not None \
                    and len(apps.REPANIER_SETTINGS_SMS_GATEWAY_MAIL) > 0:
                # Send SMS with free gateway : Sms Gateway - Android.
                email = RepanierEmail(
                    valid_nr,
                    html_content=sms_msg,
                    from_email="no-reply@repanier.be",
                    to=[apps.REPANIER_SETTINGS_SMS_GATEWAY_MAIL, ],
                    unsubscribe=False
                )
                email.send_email()
    except:
        pass


def get_signature(is_reply_to_order_email=False, is_reply_to_invoice_email=False):
    from repanier.models.staff import Staff

    sender_email = None
    sender_function = EMPTY_STRING
    signature = EMPTY_STRING
    cc_email_staff = []
    for staff in Staff.objects.filter(is_active=True).order_by('?'):
        if (is_reply_to_order_email and staff.is_reply_to_order_email) \
                or (is_reply_to_invoice_email and staff.is_reply_to_invoice_email):
            cc_email_staff.append(staff.user.email)
            sender_email = staff.user.email
            sender_function = staff.safe_translation_getter(
                'long_name', any_language=True, default=EMPTY_STRING
            )
            r = staff.customer_responsible
            if r:
                if r.long_basket_name:
                    signature = "{} - {}".format(r.long_basket_name, r.phone1)
                else:
                    signature = "{} - {}".format(r.short_basket_name, r.phone1)
                if r.phone2 and len(r.phone2.strip()) > 0:
                    signature += " / {}".format(r.phone2)
        elif staff.is_coordinator:
            cc_email_staff.append(staff.user.email)

    if sender_email is None:
        sender_email = settings.DEFAULT_FROM_EMAIL
    return sender_email, sender_function, signature, cc_email_staff


def get_board_composition(permanence_id):
    from repanier.models.permanenceboard import PermanenceBoard

    board_composition = EMPTY_STRING
    board_composition_and_description = EMPTY_STRING
    for permanenceboard in PermanenceBoard.objects.filter(
            permanence=permanence_id).order_by(
        "permanence_role__tree_id",
        "permanence_role__lft"
    ):
        r = permanenceboard.permanence_role
        c = permanenceboard.customer
        if c is not None:
            if c.phone2 is not None:
                c_part = "<b>{}</b>, {}, {}".format(c.long_basket_name, c.phone1, c.phone2)
            else:
                c_part = "<b>{}</b>, {}".format(c.long_basket_name, c.phone1)
            member = "<b>{}</b> : {}, {}<br>".format(r.short_name, c_part, c.user.email)
            board_composition += member
            board_composition_and_description += "{}{}<br>".format(member, r.description)

    return mark_safe(board_composition), mark_safe(board_composition_and_description)


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
    utf8_bytes = unicode_text
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
        if not isinstance(s, string_types):
            s = str(s)
        s = s if len(s) <= l else s[0:l - 4] + '...'
        return s
    else:
        return


def permanence_ok_or_404(permanence):
    if permanence is None:
        raise Http404
    if permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
        if permanence.status in [PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
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


def get_reverse_invoice_unit(unit):
    # reverse of tools get_invoice_unit
    if unit == _("/ kg"):
        order_unit = PRODUCT_ORDER_UNIT_KG
    elif unit == _("/ l"):
        order_unit = PRODUCT_ORDER_UNIT_LT
    else:
        order_unit = PRODUCT_ORDER_UNIT_PC
    return order_unit


def get_preparator_unit(order_unit=PRODUCT_ORDER_UNIT_PC):
    # Used when producing the preparation list.
    if order_unit in [PRODUCT_ORDER_UNIT_PC, PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                      PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        unit = _("Piece(s) :")
    elif order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
        unit = _("{} or kg :").format(apps.REPANIER_SETTINGS_CURRENCY_DISPLAY)
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        unit = _("L :")
    else:
        unit = _("Kg :")
    return unit


def get_base_unit(qty=0, order_unit=PRODUCT_ORDER_UNIT_PC, status=None, producer=False):
    if order_unit == PRODUCT_ORDER_UNIT_KG or (
                        status >= PERMANENCE_SEND and order_unit == PRODUCT_ORDER_UNIT_PC_KG and not producer
    ):
        if qty == DECIMAL_ZERO:
            base_unit = EMPTY_STRING
        else:
            base_unit = _('kg')
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        if qty == DECIMAL_ZERO:
            base_unit = EMPTY_STRING
        else:
            base_unit = _('l')
    else:
        if qty == DECIMAL_ZERO:
            base_unit = EMPTY_STRING
        elif qty < 2:
            base_unit = _('piece')
        else:
            base_unit = _('pieces')
    return base_unit


def payment_message(customer, permanence):
    from repanier.apps import REPANIER_SETTINGS_INVOICE
    from repanier.models.invoice import CustomerInvoice

    customer_invoice = CustomerInvoice.objects.filter(
        customer_id=customer.id,
        permanence_id=permanence.id
    ).order_by('?').first()

    total_price_with_tax = customer_invoice.get_total_price_with_tax()
    customer_order_amount = \
        _('The amount of your order is %(amount)s.') % {
            'amount': total_price_with_tax
        }
    if customer.balance.amount != DECIMAL_ZERO:
        if customer.balance.amount < DECIMAL_ZERO:
            balance = "<font color=\"#bd0926\">{}</font>".format(customer.balance)
        else:
            balance = "{}".format(customer.balance)
        customer_last_balance = \
            _('The balance of your account as of %(date)s is %(balance)s.') % {
                'date'   : customer.date_balance.strftime(settings.DJANGO_SETTINGS_DATE),
                'balance': balance
            }
    else:
        customer_last_balance = EMPTY_STRING

    if customer_invoice.customer_id != customer_invoice.customer_charged_id:
        customer_on_hold_movement = EMPTY_STRING
        customer_payment_needed = '<font color="#51a351">{}</font>'.format(
            _('Invoices for this delivery point are sent to %(name)s who is responsible for collecting the payments.') % {
                'name': customer_invoice.customer_charged.long_basket_name
            }
        )
    else:
        bank_not_invoiced = customer.get_bank_not_invoiced()
        order_not_invoiced = customer.get_order_not_invoiced()

        customer_on_hold_movement = customer.get_on_hold_movement_html(
            bank_not_invoiced, order_not_invoiced, total_price_with_tax
        )
        if REPANIER_SETTINGS_INVOICE:
            payment_needed = - (customer.balance - order_not_invoiced + bank_not_invoiced)
        else:
            payment_needed = total_price_with_tax

        bank_account_number = apps.REPANIER_SETTINGS_BANK_ACCOUNT
        if bank_account_number is not None:
            if payment_needed.amount > DECIMAL_ZERO:
                if permanence.short_name:
                    communication = "{} ({})".format(customer.short_basket_name, permanence.short_name)
                else:
                    communication = customer.short_basket_name
                group_name = apps.REPANIER_SETTINGS_GROUP_NAME
                customer_payment_needed = '<br><font color="#bd0926">{}</font>'.format(
                    _('Please pay %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s.') % {
                        'payment': payment_needed,
                        'name': group_name,
                        'number': bank_account_number,
                        'communication': communication
                    }
                )

            else:
                if customer.balance.amount != DECIMAL_ZERO:
                    customer_payment_needed = '<br><font color="#51a351">{}.</font>'.format(_('Your account balance is sufficient'))
                else:
                    customer_payment_needed = EMPTY_STRING
        else:
            customer_payment_needed = EMPTY_STRING

    return customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount


def display_selected_value(offer_item, quantity_ordered, is_open=True):
    option_dict = {
        'id': "#offer_item{}".format(offer_item.id),
    }
    if offer_item.may_order:
        if quantity_ordered <= DECIMAL_ZERO:
            if is_open:
                q_min = offer_item.customer_minimum_order_quantity
                if offer_item.limit_order_quantity_to_stock:
                    q_alert = offer_item.stock - offer_item.quantity_invoiced
                    if q_alert < DECIMAL_ZERO:
                        q_alert = DECIMAL_ZERO
                else:
                    q_alert = offer_item.customer_alert_order_quantity
                if q_min <= q_alert:
                    label = "---"
                else:
                    label = _("Sold out")
            else:
                label = _("Closed")
            option_dict["html"] = "<option value=\"0\" selected>{}</option>".format(label)

        else:
            unit_price_amount = offer_item.customer_unit_price.amount + offer_item.unit_deposit.amount
            display = offer_item.get_display(
                qty=quantity_ordered,
                order_unit=offer_item.order_unit,
                unit_price_amount=unit_price_amount,
                for_order_select=True
            )
            option_dict["html"] = '<option value="{}" selected>{}</option>'.format(quantity_ordered, display)
    else:
        option_dict["html"] = EMPTY_STRING
    return option_dict


def display_selected_box_value(offer_item, quantity_ordered):
    # Select one purchase
    if quantity_ordered > DECIMAL_ZERO:
        qty_display = offer_item.get_display(
            qty=quantity_ordered,
            order_unit=offer_item.order_unit,
            for_order_select=True,
            without_price_display=True
        )
    else:
        qty_display = "---"
    option_dict = {
        'id'  : "#box_offer_item{}".format(offer_item.id),
        'html': "<option value=\"0\" selected>☑ {} {}</option>".format(
                qty_display, BOX_UNICODE
        )
    }
    return option_dict


def create_or_update_one_purchase(
        customer_id, offer_item,
        permanence_date=None, status=PERMANENCE_OPENED, q_order=None,
        batch_job=False, is_box_content=False, comment=EMPTY_STRING):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
    from repanier.models.purchase import Purchase
    from repanier.models.permanence import Permanence
    from repanier.models.invoice import CustomerInvoice
    # The batch_job flag is used because we need to forbid
    # customers to add purchases during the close_orders_async or other batch_job process
    # when the status is PERMANENCE_WAIT_FOR_SEND
    purchase = Purchase.objects.filter(
        customer_id=customer_id,
        offer_item_id=offer_item.id,
        is_box_content=is_box_content
    ).order_by('?').first()
    if batch_job:
        if purchase is None:
            permanence_date = permanence_date or Permanence.objects.filter(
                id=offer_item.permanence_id).only("permanence_date").order_by('?').first().permanence_date
            purchase = Purchase.objects.create(
                permanence_id=offer_item.permanence_id,
                permanence_date=permanence_date,
                offer_item_id=offer_item.id,
                producer_id=offer_item.producer_id,
                customer_id=customer_id,
                quantity_ordered=q_order if status < PERMANENCE_SEND else DECIMAL_ZERO,
                quantity_invoiced=q_order if status >= PERMANENCE_SEND else DECIMAL_ZERO,
                is_box_content=is_box_content,
                status=status,
                comment=comment
            )
        else:
            purchase.set_comment(comment)
            if status < PERMANENCE_SEND:
                purchase.quantity_ordered = q_order
            else:
                purchase.quantity_invoiced = q_order
            purchase.save()
        return purchase, True
    else:
        permanence_is_opened = CustomerInvoice.objects.filter(
            permanence_id=offer_item.permanence_id,
            customer_id=customer_id,
            status=status
        ).order_by('?').exists()
        if permanence_is_opened:
            if offer_item.limit_order_quantity_to_stock:
                if purchase is not None:
                    q_previous_order = purchase.quantity_ordered
                else:
                    q_previous_order = DECIMAL_ZERO
                q_alert = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
                if is_box_content and q_alert < q_order:
                    # Select one purchase
                    non_box_purchase = Purchase.objects.filter(
                        customer_id=customer_id,
                        offer_item_id=offer_item.id,
                        is_box_content=False
                    ).order_by('?').first()
                    if non_box_purchase is not None:
                        tbd_qty = min(q_order - q_alert, non_box_purchase.quantity_ordered)
                        tbk_qty = non_box_purchase.quantity_ordered - tbd_qty
                        non_box_purchase.quantity_ordered = tbk_qty
                        non_box_purchase.save()
                        q_alert += tbd_qty
            else:
                if is_box_content:
                    q_alert = q_order
                else:
                    q_alert = offer_item.customer_alert_order_quantity
            if purchase is not None:
                purchase.set_comment(comment)
                if q_order <= q_alert:
                    if not REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS or purchase.quantity_confirmed <= q_order:
                        purchase.quantity_ordered = q_order
                        purchase.save()
                    else:
                        purchase.quantity_ordered = purchase.quantity_confirmed
                        purchase.save()
                else:
                    return purchase, False
            else:
                permanence = Permanence.objects.filter(id=offer_item.permanence_id) \
                    .only("permanence_date") \
                    .order_by('?').first()
                purchase = Purchase.objects.create(
                    permanence_id=offer_item.permanence_id,
                    permanence_date=permanence.permanence_date,
                    offer_item_id=offer_item.id,
                    producer_id=offer_item.producer_id,
                    customer_id=customer_id,
                    quantity_ordered=q_order,
                    quantity_invoiced=DECIMAL_ZERO,
                    is_box_content=is_box_content,
                    status=status,
                    comment=comment
                )
            return purchase, True
        else:
            return purchase, False

@transaction.atomic
def create_or_update_one_cart_item(customer, offer_item_id, q_order=None, value_id=None,
                                   is_basket=False, batch_job=False, comment=EMPTY_STRING):
    from repanier.models.box import BoxContent
    from repanier.models.offeritem import OfferItem
    from repanier.models.purchase import Purchase

    # from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
    to_json = []
    offer_item = OfferItem.objects.select_for_update(nowait=False) \
        .filter(id=offer_item_id, is_active=True, may_order=True) \
        .order_by('?').select_related("producer").first()
    if offer_item is not None:
        if q_order is None:
            # Transform value_id into a q_order.
            # This is done here and not in the order_ajax to avoid to access twice to offer_item
            q_min = offer_item.customer_minimum_order_quantity
            q_step = offer_item.customer_increment_order_quantity
            if value_id <= 0:
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
                        q_order = q_step * (value_id - 1)
                else:
                    # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                    # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                    q_order = q_min + q_step * (value_id - 1)
        if q_order < DECIMAL_ZERO:
            q_order = DECIMAL_ZERO
        is_box_updated = True
        if offer_item.is_box:
            # Select one purchase
            purchase = Purchase.objects.filter(
                customer_id=customer.id,
                offer_item_id=offer_item.id,
                is_box_content=False
            ).order_by('?').first()
            if purchase is not None:
                delta_q_order = q_order - purchase.quantity_ordered
            else:
                delta_q_order = q_order
            with transaction.atomic():
                sid = transaction.savepoint()
                # This code executes inside a transaction.
                for content in BoxContent.objects.filter(
                    box=offer_item.product_id
                ).only(
                    "product_id", "content_quantity"
                ).order_by('?'):
                    box_offer_item = OfferItem.objects.filter(
                        product_id=content.product_id,
                        permanence_id=offer_item.permanence_id
                    ).order_by('?').select_related("producer").first()
                    if box_offer_item is not None:
                        # Select one purchase
                        purchase = Purchase.objects.filter(
                            customer_id=customer.id,
                            offer_item_id=box_offer_item.id,
                            is_box_content=True
                        ).order_by('?').first()
                        if purchase is not None:
                            quantity_ordered = purchase.quantity_ordered + delta_q_order * content.content_quantity
                        else:
                            quantity_ordered = delta_q_order * content.content_quantity
                        if quantity_ordered < DECIMAL_ZERO:
                            quantity_ordered = DECIMAL_ZERO
                        purchase, is_box_updated = create_or_update_one_purchase(
                            customer.id, box_offer_item, q_order=quantity_ordered,
                            batch_job=batch_job, is_box_content=True
                        )
                    else:
                        is_box_updated = False
                    if not is_box_updated:
                        break
                if is_box_updated:
                    transaction.savepoint_commit(sid)
                else:
                    transaction.savepoint_rollback(sid)
        if not offer_item.is_box or is_box_updated:
            return create_or_update_one_purchase(
                customer.id, offer_item, q_order=q_order, batch_job=batch_job,
                is_box_content=False, comment=comment
            )
        elif not batch_job:
            # Select one purchase
            purchase = Purchase.objects.filter(
                customer_id=customer.id,
                offer_item_id=offer_item.id,
                is_box_content=False
            ).order_by('?').first()
            return purchase, False


def my_basket(is_order_confirm_send, order_amount, to_json):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
    if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS and not is_order_confirm_send:
        if order_amount.amount <= DECIMAL_ZERO:
            msg_confirm = EMPTY_STRING
        else:
            msg_confirm = "<span class=\"glyphicon glyphicon-exclamation-sign\"></span>&nbsp;<span class=\"glyphicon glyphicon-floppy-remove\"></span>"
        msg_html = "{order_amount}&nbsp;&nbsp;&nbsp;{msg_confirm}".format(
            order_amount=order_amount,
            msg_confirm=msg_confirm
        )
    else:
        if order_amount.amount <= DECIMAL_ZERO:
            msg_confirm = cart_content = EMPTY_STRING
        else:
            msg_confirm = '<span class="glyphicon glyphicon-ok"></span>'
            cart_content = '<div class="cart-line-3" style="background-color: #E5E9EA"></div>'
        msg_html = """
        <div class="icon-cart" style="float: left">
            <div class="cart-line-1" style="background-color: #fff"></div>
            <div class="cart-line-2" style="background-color: #fff"></div>
            {cart_content}
            <div class="cart-wheel" style="background-color: #fff"></div>
        </div> {order_amount}&nbsp;&nbsp;&nbsp;
        {msg_confirm}
            """.format(
            cart_content=cart_content,
            order_amount=order_amount,
            msg_confirm=msg_confirm
        )

    option_dict = {'id': "#my_basket", 'html': msg_html}
    to_json.append(option_dict)
    msg_html = "{order_amount}&nbsp;&nbsp;&nbsp;{msg_confirm}".format(
            order_amount=order_amount,
            msg_confirm=msg_confirm
        )
    option_dict = {'id': "#prepared_amount_visible_xs", 'html': msg_html}
    to_json.append(option_dict)


def clean_offer_item(permanence, queryset, reset_add_2_stock=False):
    if permanence.status > PERMANENCE_SEND:
        # The purchases are already invoiced.
        # The offer item may not be modified any more
        raise ValueError("Not offer item may be created when permanece status > PERMANENCE_SEND")
    getcontext().rounding = ROUND_HALF_UP
    for offer_item in queryset.select_related("producer", "product"):
        product = offer_item.product
        producer = offer_item.producer

        offer_item.set_from(product)

        offer_item.producer_pre_opening = producer.producer_pre_opening
        offer_item.manage_production = producer.represent_this_buyinggroup
        # Those offer_items not subjects to price modifications
        offer_item.is_resale_price_fixed = producer.is_resale_price_fixed or product.is_box or product.order_unit >= PRODUCT_ORDER_UNIT_DEPOSIT
        offer_item.price_list_multiplier = DECIMAL_ONE if offer_item.is_resale_price_fixed else producer.price_list_multiplier

        offer_item.may_order = False
        offer_item.manage_replenishment = False
        if offer_item.contract is not None:
            offer_item.may_order = len(offer_item.permanences_dates) > 0
            # No stock limit if this is a contract (ie a pre-order)
            offer_item.limit_order_quantity_to_stock = False
            offer_item.manage_production = False
            offer_item.producer_pre_opening = False
        else:
            if offer_item.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                offer_item.may_order = product.is_into_offer
                offer_item.manage_replenishment = producer.manage_replenishment

        # The group must pay the VAT, so it's easier to allways have
        # offer_item with VAT included
        if producer.producer_price_are_wo_vat:
            offer_item.producer_unit_price += offer_item.producer_vat
        offer_item.producer_price_are_wo_vat = False

        if reset_add_2_stock:
            offer_item.add_2_stock = DECIMAL_ZERO

        offer_item.save()

    # Now got everything to calculate the sort order of the order display screen
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        translation.activate(language["code"])
        for offer_item in queryset.select_related("producer", "department_for_customer"):
            offer_item.long_name = offer_item.product.long_name
            offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.save_translations()

    translation.activate(cur_language)


def reorder_purchases(permanence_id):
    from repanier.models.purchase import Purchase

    # Order the purchases such that lower quantity are before larger quantity
    Purchase.objects.filter(
        permanence_id=permanence_id
    ).update(
        quantity_for_preparation_sort_order=DECIMAL_ZERO
    )
    Purchase.objects.filter(
        permanence_id=permanence_id,
        offer_item__wrapped=False,
        offer_item__order_unit__in=[PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]
    ).update(
        quantity_for_preparation_sort_order=F('quantity_invoiced')
    )


def reorder_offer_items(permanence_id):
    from repanier.models.offeritem import OfferItemWoReceiver
    # calculate the sort order of the order display screen
    cur_language = translation.get_language()
    offer_item_qs = OfferItemWoReceiver.objects.filter(permanence_id=permanence_id).order_by('?')
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)

        i = 0
        reorder_queryset = offer_item_qs.filter(
            is_box=False,
            translations__language_code=language_code
        ).order_by(
            "department_for_customer",
            "translations__long_name",
            "order_average_weight",
            "producer__short_profile_name",
            "permanences_dates_order"
        )
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = offer_item.order_sort_order = offer_item.preparation_sort_order = i
            offer_item.save_translations()
            if i < 9999:
                i += 1
        # producer lists sort order : sort by reference if needed, otherwise sort by order_sort_order
        i = 9999
        reorder_queryset = offer_item_qs.filter(
            is_box=False,
            producer__sort_products_by_reference=True,
            translations__language_code=language_code
        ).order_by(
            "department_for_customer",
            "reference"
        )
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = i
            offer_item.save_translations()
            if i < 19999:
                i += 1
        # preparation lists sort order
        i = -9999
        reorder_queryset = offer_item_qs.filter(
            is_box=True,
            translations__language_code=language_code
        ).order_by(
            "customer_unit_price",
            # "department_for_customer__lft",
            "unit_deposit",
            "translations__long_name"
        )
        # 'TranslatableQuerySet' object has no attribute 'desc'
        for offer_item in reorder_queryset:
            # display box on top
            offer_item.producer_sort_order = offer_item.order_sort_order = offer_item.preparation_sort_order = i
            offer_item.save_translations()
            if i < -1:
                i += 1
    translation.activate(cur_language)


def update_offer_item(product_id=None, producer_id=None):
    from repanier.models.permanence import Permanence
    from repanier.models.offeritem import OfferItem

    # The user can modify the price of a product PERMANENCE_SEND via "rule_of_3_per_product"
    for permanence in Permanence.objects.filter(
            status__in=[PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED]
    ):
        if producer_id is None:
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=permanence.id,
                product_id=product_id,
            ).order_by('?')
        else:
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=permanence.id,
                producer_id=producer_id,
            ).order_by('?')
        clean_offer_item(permanence, offer_item_qs)
        permanence.recalculate_order_amount(offer_item_qs=offer_item_qs)
    cache.clear()


def producer_web_services_activated(reference_site=None):
    web_services_activated = False
    web_service_version = None
    if reference_site:
        try:
            web_services = urlopen(
                "{}{}".format(reference_site, urlresolvers.reverse('version_rest')),
                timeout=0.5
            )
            version_rest = json.load(web_services)
            if version_rest['version'] == '1':
                web_services_activated = True
                web_service_version = 1
        except:
            pass
    return web_services_activated, "Repanier", web_service_version


def add_months(sourcedate, months):
    # months must be an integer
    months = int(months)
    month = sourcedate.month - 1 + months
    year = int(sourcedate.year + month / 12)
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def calc_basket_message(customer, permanence, status):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
    if status == PERMANENCE_OPENED:
        if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
            if permanence.with_delivery_point:
                you_can_change = "<br>{}".format(
                    _("You can increase the order quantities as long as the orders are open for your delivery point.")
                )
            else:
                you_can_change = "<br>{}".format(
                    _("You can increase the order quantities as long as the orders are open.")
                )
        else:
            if permanence.with_delivery_point:
                you_can_change = "<br>{}".format(
                    _("You can change the order quantities as long as the orders are open for your delivery point.")
                )
            else:
                you_can_change = "<br>{}".format(
                    _("You can change the order quantities as long as the orders are open.")
                )
    else:
        if permanence.with_delivery_point:
            you_can_change = "<br>{}".format(
                _('The orders are closed for your delivery point.')
            )
        else:
            you_can_change = "<br>{}".format(
                _('The orders are closed.')
            )
    invoice_msg = EMPTY_STRING
    payment_msg = EMPTY_STRING
    customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
        customer, permanence)
    if apps.REPANIER_SETTINGS_INVOICE:
        if customer_last_balance:
            invoice_msg = "<br>{} {}".format(
                customer_last_balance,
                customer_on_hold_movement
            )
    if apps.REPANIER_SETTINGS_BANK_ACCOUNT is not None:
        payment_msg = "<br>{}".format(
            customer_payment_needed
        )
    basket_message = "{}{}{}{}".format(
        customer_order_amount,
        invoice_msg,
        payment_msg,
        you_can_change
    )
    return basket_message


def html_box_content(offer_item, user):
    from repanier.models.box import BoxContent
    from repanier.models.offeritem import OfferItemWoReceiver

    box_id = offer_item.product_id
    box_products = list(BoxContent.objects.filter(
        box_id=box_id
    ).values_list(
        'product_id', flat=True
    ).order_by('?'))
    if len(box_products) > 0:
        box_offer_items_qs = OfferItemWoReceiver.objects.filter(
            permanence_id=offer_item.permanence_id,
            product_id__in=box_products,
            translations__language_code=translation.get_language()
        ).order_by(
            "translations__order_sort_order"
        ).select_related("producer")
        box_products_description = []
        for box_offer_item in box_offer_items_qs:
            box_products_description.append(
                format_html(
                    '<li>{} * {}, {} <span class="btn_like{}" style="cursor: pointer;">{}</span></li>',
                    mark_safe(box_offer_item.get_display(
                        qty=BoxContent.objects.filter(box_id=box_id, product_id=box_offer_item.product_id).only(
                            "content_quantity").order_by('?').first().content_quantity,
                        order_unit=box_offer_item.order_unit,
                        without_price_display=True)),
                    box_offer_item.long_name,
                    box_offer_item.producer.short_profile_name,
                    box_offer_item.id,
                    mark_safe(box_offer_item.get_like(user))
                )
            )
        return format_html(
            '<ul>{}</ul>',
            mark_safe(EMPTY_STRING.join(box_products_description))
        )
    return EMPTY_STRING


def rule_of_3_reload_purchase(customer, offer_item, purchase_form, purchase_form_instance):
    from repanier.models.purchase import Purchase

    purchase_form.repanier_is_valid = True
    # Reload purchase, because it has maybe be deleted
    purchase = Purchase.objects.filter(
        customer_id=customer.id,
        offer_item_id=offer_item.id,
        is_box_content=False
    ).order_by('?').first()
    if purchase is None:
        # Doesn't exists ? Create one
        purchase = Purchase.objects.create(
            permanence=offer_item.permanence,
            permanence_date=offer_item.permanence.permanence_date,
            offer_item=offer_item,
            producer=offer_item.producer,
            customer=customer,
            quantity_ordered=DECIMAL_ZERO,
            quantity_invoiced=DECIMAL_ZERO,
            comment=purchase_form_instance.comment,
            is_box_content=False,
            status=PERMANENCE_SEND
        )
    # And set the form's values
    purchase.quantity_invoiced = purchase_form_instance.quantity_invoiced
    purchase.purchase_price = purchase_form_instance.purchase_price
    purchase.comment = purchase_form_instance.comment
    # Set it as new form instance
    purchase_form.instance = purchase
    return purchase


def check_if_is_coordinator(request):
    return request.user.is_superuser or request.user.groups.filter(name=COORDINATION_GROUP).exists()


def get_recurrence_dates(first_date, recurrences):
    dates = []
    d_start = first_date
    dt_start = new_datetime(d_start)
    dt_end = new_datetime(d_start + datetime.timedelta(days=ONE_YEAR))
    occurrences = recurrences.between(
        dt_start,
        dt_end,
        dtstart=dt_start,
        inc=True
    )
    for occurrence in occurrences:
        dates.append(occurrence.date())
    return dates