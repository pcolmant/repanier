# -*- coding: utf-8
from __future__ import unicode_literals

import calendar
import datetime
import json
import time
import urllib2
from smtplib import SMTPRecipientsRefused

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core import urlresolvers
from django.core.cache import cache
from django.core.mail import EmailMessage, mail_admins
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F
from django.db.models import Q, Sum
from django.http import Http404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist

import models
from const import *
from repanier import apps
from repanier.fields.RepanierMoneyField import RepanierMoney


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


def next_row(query_iterator):
    try:
        return next(query_iterator)
    except StopIteration:
        # No rows were found, so do nothing.
        return None


def send_email(email=None, track_customer_on_error=False):
    if settings.DJANGO_SETTINGS_DEMO:
        email.to = [DEMO_EMAIL]
        email.cc = []
        email.bcc = []
        send_email_with_error_log(email)
    elif settings.DEBUG:
        print('############################ debug, send_email')
        if apps.REPANIER_SETTINGS_TEST_MODE:
            email.to = [v for k, v in settings.ADMINS]
            email.cc = []
            email.bcc = []
            print('the mail is send to : %s' % email.to)
            send_email_with_error_log(email)
        else:
            print("to : %s" % email.to)
            print("cc : %s" % email.cc)
            print("bcc : %s" % email.bcc)
            print("subject : %s" % slugify(email.subject))
    elif apps.REPANIER_SETTINGS_TEST_MODE:
        coordinator = models.Staff.objects.filter(is_coordinator=True, is_active=True).order_by("id").first()
        if coordinator is not None:
            email.to = [coordinator.user.email]
        else:
            email.to = [v for k, v in settings.ADMINS]
        email.cc = []
        email.bcc = []
        send_email_with_error_log(email)
    else:
        # chunks = [email.to[x:x+100] for x in xrange(0, len(email.to), 100)]
        # for chunk in chunks:
        if len(email.bcc) > 1:
            # Remove duplicate
            email_bcc = list(set(email.bcc))
            customer = None
            for bcc in email_bcc:
                email.bcc = [bcc]
                if track_customer_on_error:
                    # If the email is conained both in user__email and customer__email2
                    # select the customer based on user__email
                    customer = models.Customer.objects.filter(user__email=bcc).order_by('?').first()
                    if customer is None:
                        customer = models.Customer.objects.filter(email2=bcc).order_by('?').first()
                time.sleep(2)
                send_email_with_error_log(email, customer)
        else:
            send_email_with_error_log(email)


def send_email_with_error_log(email, customer=None):
    with mail.get_connection() as connection:
        email.connection = connection
        message = EMPTY_STRING
        try:
            print("################################## send_email")
            to = "to : %s" % email.to
            cc = "cc : %s" % email.cc
            bcc = "bcc : %s" % email.bcc
            subject = "subject : %s" % slugify(email.subject)
            print(to)
            print(cc)
            print(bcc)
            print(subject)
            message = "%s\n%s\n%s\n%s" % (to, cc, bcc, subject)
            email.send()
            valid_email = True
        except SMTPRecipientsRefused as error_str:
            valid_email = False
            print("################################## send_email error")
            print(error_str)
            time.sleep(2)
            connection = mail.get_connection()
            connection.open()
            mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
            connection.close()
        except Exception as error_str:
            valid_email = None
            print("################################## send_email error")
            print(error_str)
            time.sleep(2)
            connection = mail.get_connection()
            connection.open()
            mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
            connection.close()
        if customer is not None:
            customer.valid_email = valid_email
            customer.save(update_fields=['valid_email'])
        print("##################################")


def send_email_to_who(is_email_send, board=False):
    if not is_email_send:
        if board:
            if settings.DEBUG:
                if apps.REPANIER_SETTINGS_TEST_MODE:
                    return True, _("This email will be sent to %s.") % ' ,'.join(v for k, v in settings.ADMINS)
                else:
                    return False, _("No email will be sent.")
            elif apps.REPANIER_SETTINGS_TEST_MODE:
                coordinator = models.Staff.objects.filter(is_coordinator=True, is_active=True).order_by('?').first()
                if coordinator is not None:
                    return True, _("This email will be sent to %s.") % coordinator.user.email
                else:
                    return True, _("This email will be sent to %s.") % ' ,'.join(v for k, v in settings.ADMINS)
            else:
                return True, _("This email will be sent to the staff.")
        else:
            return False, _("No email will be sent.")
    else:
        if settings.DEBUG:
            if apps.REPANIER_SETTINGS_TEST_MODE:
                return True, _("This email will be sent to %s.") % ' ,'.join(v for k, v in settings.ADMINS)
            else:
                return False, _("No email will be sent.")
        elif apps.REPANIER_SETTINGS_TEST_MODE:
            coordinator = models.Staff.objects.filter(is_coordinator=True, is_active=True).order_by('?').first()
            if coordinator is not None:
                return True, _("This email will be sent to %s.") % coordinator.user.email
            else:
                return True, _("This email will be sent to %s.") % ' ,'.join(v for k, v in settings.ADMINS)
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
                email = EmailMessage(valid_nr, sms_msg, "no-reply@repanier.be",
                                     [apps.REPANIER_SETTINGS_SMS_GATEWAY_MAIL, ])
                send_email(email=email)
    except:
        pass


def get_signature(is_reply_to_order_email=False, is_reply_to_invoice_email=False):
    sender_email = None
    sender_function = EMPTY_STRING
    signature = EMPTY_STRING
    cc_email_staff = []
    for staff in models.Staff.objects.filter(is_active=True).order_by('?'):
        if (is_reply_to_order_email and staff.is_reply_to_order_email) \
                or (is_reply_to_invoice_email and staff.is_reply_to_invoice_email):
            cc_email_staff.append(staff.user.email)
            sender_email = staff.user.email
            try:
                sender_function = staff.long_name
            except TranslationDoesNotExist:
                sender_function = EMPTY_STRING
            r = staff.customer_responsible
            if r:
                if r.long_basket_name:
                    signature = "%s - %s" % (r.long_basket_name, r.phone1)
                else:
                    signature = "%s - %s" % (r.short_basket_name, r.phone1)
                if r.phone2 and len(r.phone2.strip()) > 0:
                    signature += " / %s" % (r.phone2,)
        elif staff.is_coordinator:
            cc_email_staff.append(staff.user.email)

    if sender_email is None:
        sender_email = settings.DEFAULT_FROM_EMAIL
    return sender_email, sender_function, signature, cc_email_staff


def get_board_composition(permanence_id):
    board_composition = EMPTY_STRING
    board_composition_and_description = EMPTY_STRING
    for permanenceboard in models.PermanenceBoard.objects.filter(
            permanence=permanence_id).order_by(
        "permanence_role__tree_id",
        "permanence_role__lft"
    ):
        r = permanenceboard.permanence_role
        c = permanenceboard.customer
        if c is not None:
            if c.phone2 is not None:
                c_part = "%s, <b>%s</b>, <b>%s</b>" % (c.long_basket_name, c.phone1, c.phone2)
            else:
                c_part = "%s, <b>%s</b>" % (c.long_basket_name, c.phone1)
            member = "<b>%s</b> : %s, %s<br/>" % (r.short_name, c_part, c.user.email)
            board_composition += member
            board_composition_and_description += "%s%s<br/>" % (member, r.description)

    return board_composition, board_composition_and_description


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
    utf8_bytes = unicode_text.encode("utf8")
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
        unit = _("%s or kg :") % (apps.REPANIER_SETTINGS_CURRENCY_DISPLAY.decode('utf-8'),)
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        unit = _("L :")
    else:
        unit = _("Kg :")
    return unit


def get_base_unit(qty=0, order_unit=PRODUCT_ORDER_UNIT_PC, status=None):
    if order_unit == PRODUCT_ORDER_UNIT_KG or (status >= PERMANENCE_SEND and order_unit == PRODUCT_ORDER_UNIT_PC_KG):
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


def get_display(qty=0, order_average_weight=0, order_unit=PRODUCT_ORDER_UNIT_PC, unit_price_amount=None,
                for_customer=True, for_order_select=False, without_price_display=False):
    magnitude = None
    display_qty = True
    if order_unit == PRODUCT_ORDER_UNIT_KG:
        if qty == DECIMAL_ZERO:
            unit = EMPTY_STRING
        elif for_customer and qty < 1:
            unit = "%s" % (_('gr'))
            magnitude = 1000
        else:
            unit = "%s" % (_('kg'))
    elif order_unit == PRODUCT_ORDER_UNIT_LT:
        if qty == DECIMAL_ZERO:
            unit = EMPTY_STRING
        elif for_customer and qty < 1:
            unit = "%s" % (_('cl'))
            magnitude = 100
        else:
            unit = "%s" % (_('l'))
    elif order_unit in [PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG]:
        # display_qty = not (order_average_weight == 1 and order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_KG)
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
        if order_unit == PRODUCT_ORDER_UNIT_PC_KG and unit_price_amount is not None:
            unit_price_amount *= order_average_weight
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
        tilde = EMPTY_STRING
        if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            tilde = '~'
        if for_customer:
            if qty == DECIMAL_ZERO:
                unit = EMPTY_STRING
            else:
                if order_average_weight == 1 and order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
                    unit = "%s%s %s" % (tilde, number_format(average_weight, decimal), average_weight_unit)
                else:
                    unit = "%s%s%s" % (tilde, number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                unit = EMPTY_STRING
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
                unit = EMPTY_STRING
            else:
                if display_qty:
                    unit = "%s%s" % (number_format(average_weight, decimal), average_weight_unit)
                else:
                    unit = "%s %s" % (number_format(average_weight, decimal), average_weight_unit)
        else:
            if qty == DECIMAL_ZERO:
                unit = EMPTY_STRING
            else:
                unit = "%s%s" % (number_format(average_weight, decimal), average_weight_unit)
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
        display_qty = order_average_weight != 1
        average_weight = order_average_weight
        if for_customer:
            average_weight *= qty
            if qty == DECIMAL_ZERO:
                unit = EMPTY_STRING
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
                unit = EMPTY_STRING
            elif average_weight < 2:
                unit = '%s %s' % (number_format(average_weight, 0), _('pc'))
            else:
                unit = '%s %s' % (number_format(average_weight, 0), _('pcs'))
    else:
        if for_order_select:
            if qty == DECIMAL_ZERO:
                unit = EMPTY_STRING
            elif qty < 2:
                unit = "%s" % (_('unit'))
            else:
                unit = "%s" % (_('units'))
        else:
            unit = EMPTY_STRING
    if unit_price_amount is not None:
        price_display = " = %s" % RepanierMoney(unit_price_amount * qty)
    else:
        price_display = EMPTY_STRING
    if magnitude is not None:
        qty *= magnitude
    decimal = 3
    if qty == int(qty):
        decimal = 0
    elif qty * 10 == int(qty * 10):
        decimal = 1
    elif qty * 100 == int(qty * 100):
        decimal = 2
    if for_customer or for_order_select:
        if unit:
            if display_qty:
                qty_display = "%s (%s)" % (number_format(qty, decimal), unit)
            else:
                qty_display = "%s" % unit
        else:
            qty_display = "%s" % number_format(qty, decimal)
    else:
        if unit:
            qty_display = "(%s)" % unit
        else:
            qty_display = EMPTY_STRING
    if without_price_display:
        return qty_display
    else:
        display = "%s%s" % (qty_display, price_display)
        return display


def on_hold_movement_message(customer, bank_not_invoiced=None, order_not_invoiced=None, total_price_with_tax=REPANIER_MONEY_ZERO):
    # If permanence_id is None, only "customer_on_hold_movement" is calculated
    if customer is None:
        customer_on_hold_movement = EMPTY_STRING
    else:
        if apps.REPANIER_SETTINGS_INVOICE:
            bank_not_invoiced = bank_not_invoiced if bank_not_invoiced is not None else customer.get_bank_not_invoiced()
            order_not_invoiced = order_not_invoiced if order_not_invoiced is not None else customer.get_order_not_invoiced()
            other_order_not_invoiced = order_not_invoiced - total_price_with_tax
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO
            other_order_not_invoiced = REPANIER_MONEY_ZERO

        if other_order_not_invoiced.amount != DECIMAL_ZERO or bank_not_invoiced.amount != DECIMAL_ZERO:
            if other_order_not_invoiced.amount != DECIMAL_ZERO:
                if bank_not_invoiced.amount == DECIMAL_ZERO:
                    customer_on_hold_movement = \
                        _('This balance does not take account of any unbilled sales %(other_order)s.') % {
                            'other_order': other_order_not_invoiced
                        }
                else:
                    customer_on_hold_movement = \
                        _(
                            'This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s.') \
                        % {
                            'bank'       : bank_not_invoiced,
                            'other_order': other_order_not_invoiced
                        }
            else:
                customer_on_hold_movement = \
                    _(
                        'This balance does not take account of any unrecognized payments %(bank)s.') % {
                        'bank': bank_not_invoiced
                    }
        else:
            customer_on_hold_movement = EMPTY_STRING

    return customer_on_hold_movement


def payment_message(customer, permanence):
    # If permanence_id is None, only "customer_on_hold_movement" is calculated
    customer_last_balance = EMPTY_STRING
    if customer is None or permanence is None:
        customer_order_amount = EMPTY_STRING
        customer_payment_needed = EMPTY_STRING
        customer_on_hold_movement = EMPTY_STRING
    else:
        customer_invoice = models.CustomerInvoice.objects.filter(
            customer_id=customer.id,
            permanence_id=permanence.id
        ).order_by('?').first()
        if customer_invoice is None:
            total_price_with_tax = REPANIER_MONEY_ZERO
        else:
            total_price_with_tax = customer_invoice.get_total_price_with_tax()
        customer_order_amount = \
            _('The amount of your order is %(amount)s.') % {
                'amount': total_price_with_tax
            }
        if apps.REPANIER_SETTINGS_INVOICE:
            bank_not_invoiced = customer.get_bank_not_invoiced()
            order_not_invoiced = customer.get_order_not_invoiced()
            payment_needed = - (customer.balance - order_not_invoiced + bank_not_invoiced)
            # other_order_not_invoiced = order_not_invoiced - total_price_with_tax
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO
            order_not_invoiced = DECIMAL_ZERO
            payment_needed = total_price_with_tax
            # other_order_not_invoiced = REPANIER_MONEY_ZERO

        if customer_invoice.customer_id != customer_invoice.customer_who_pays_id:
            invoices_sent_to = '<font color="green">%s</font>' % (
                _('Invoices for this delivery point are sent to %(name)s who is responsible for collecting the payments.') % {
                    'name': customer_invoice.customer_who_pays.long_basket_name
                }
            )
        else:
            invoices_sent_to = EMPTY_STRING
        customer_on_hold_movement = on_hold_movement_message(customer, bank_not_invoiced, order_not_invoiced, total_price_with_tax)
        if apps.REPANIER_SETTINGS_INVOICE:
            if customer.balance.amount != DECIMAL_ZERO:
                if customer.balance.amount < DECIMAL_ZERO:
                    balance = '<font color="#bd0926">%s</font>' % customer.balance
                else:
                    balance = '%s' % customer.balance
                customer_last_balance = \
                    _('The balance of your account as of %(date)s is %(balance)s.') % {
                        'date'   : customer.date_balance.strftime(settings.DJANGO_SETTINGS_DATE),
                        'balance': balance
                    }
            else:
                customer_last_balance = EMPTY_STRING

        bank_account_number = apps.REPANIER_SETTINGS_BANK_ACCOUNT
        if bank_account_number is not None:
            if payment_needed.amount > DECIMAL_ZERO:
                if permanence.short_name:
                    communication = "%s (%s)" % (customer.short_basket_name, permanence.short_name)
                else:
                    communication = customer.short_basket_name
                group_name = apps.REPANIER_SETTINGS_GROUP_NAME
                customer_payment_needed = '<br/><font color="#bd0926">%s</font>' % (
                    _('Please pay %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s.') % {
                        'payment': payment_needed,
                        'name': group_name,
                        'number': bank_account_number,
                        'communication': communication
                    }
                )

            else:
                if customer.balance.amount != DECIMAL_ZERO:
                    customer_payment_needed = '<br/><font color="green">%s.</font>' % (_('Your account balance is sufficient'))
                else:
                    customer_payment_needed = EMPTY_STRING
            if invoices_sent_to:
                customer_payment_needed = invoices_sent_to + customer_payment_needed
        else:
            customer_payment_needed = invoices_sent_to

    return customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount


def recalculate_order_amount(permanence_id,
                             customer_id=None,
                             offer_item_queryset=None,
                             all_producers=True,
                             producers_id=None,
                             send_to_producer=False,
                             re_init=False):
    if send_to_producer or re_init:
        if all_producers:
            models.ProducerInvoice.objects.filter(
                permanence_id=permanence_id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
                total_profit_with_tax=DECIMAL_ZERO,
                total_profit_vat=DECIMAL_ZERO
            )
            models.CustomerInvoice.objects.filter(
                permanence_id=permanence_id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO
            )
            models.CustomerProducerInvoice.objects.filter(
                permanence_id=permanence_id
            ).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            models.OfferItem.objects.filter(
                permanence_id=permanence_id
            ).update(
                quantity_invoiced=DECIMAL_ZERO,
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            for offer_item in models.OfferItem.objects.filter(
                    permanence_id=permanence_id,
                    is_active=True,
                    manage_replenishment=True
            ).exclude(add_2_stock=DECIMAL_ZERO).order_by('?'):
                # Recalculate the total_price_with_tax of ProducerInvoice and
                # the total_purchase_with_tax of OfferItem
                # taking into account "add_2_stock"
                offer_item.previous_add_2_stock = DECIMAL_ZERO
                offer_item.save()
        else:
            models.ProducerInvoice.objects.filter(
                permanence_id=permanence_id, producer_id__in=producers_id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO
            )
            for ci in models.CustomerInvoice.objects.filter(
                    permanence_id=permanence_id):
                result_set = models.CustomerProducerInvoice.objects.filter(
                    permanence_id=permanence_id,
                    customer_id=ci.customer_id,
                    producer_id__in=producers_id
                ).order_by('?').aggregate(
                    Sum('total_selling_with_tax'),
                )
                if result_set["total_selling_with_tax__sum"] is not None:
                    sum_total_selling_with_tax = result_set["total_selling_with_tax__sum"]
                else:
                    sum_total_selling_with_tax = DECIMAL_ZERO
                models.CustomerInvoice.objects.filter(
                    permanence_id=permanence_id
                ).update(
                    total_price_with_tax=F('total_price_with_tax') - sum_total_selling_with_tax
                )
            models.CustomerProducerInvoice.objects.filter(
                permanence_id=permanence_id,
                producer_id__in=producers_id
            ).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            models.OfferItem.objects.filter(
                permanence_id=permanence_id,
                producer_id__in=producers_id
            ).update(
                quantity_invoiced=DECIMAL_ZERO,
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            for offer_item in models.OfferItem.objects.filter(
                    permanence_id=permanence_id,
                    producer_id__in=producers_id,
                    is_active=True,
                    manage_replenishment=True
            ).exclude(add_2_stock=DECIMAL_ZERO).order_by('?'):
                # Recalculate the total_price_with_tax of ProducerInvoice and
                # the total_purchase_with_tax of OfferItem
                # taking into account "add_2_stock"
                offer_item.previous_add_2_stock = DECIMAL_ZERO
                offer_item.save()

    if customer_id is None:
        if offer_item_queryset is not None:
            purchase_set = models.Purchase.objects \
                .filter(permanence_id=permanence_id, offer_item__in=offer_item_queryset) \
                .order_by('?')
        else:
            purchase_set = models.Purchase.objects \
                .filter(permanence_id=permanence_id) \
                .order_by('?')
            if not all_producers:
                purchase_set = purchase_set.filter(producer_id__in=producers_id)
    else:
        purchase_set = models.Purchase.objects \
            .filter(permanence_id=permanence_id, customer_id=customer_id) \
            .order_by('?')
        if not all_producers:
            purchase_set = purchase_set.filter(producer_id__in=producers_id)

    for purchase in purchase_set.select_related("offer_item"):
        # Recalcuate the total_price_with_tax of ProducerInvoice,
        # the total_price_with_tax of CustomerInvoice,
        # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
        # and quantity_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
        offer_item = purchase.offer_item
        if send_to_producer or re_init:
            # purchase.admin_update = True
            purchase.previous_quantity = DECIMAL_ZERO
            purchase.previous_purchase_price = DECIMAL_ZERO
            purchase.previous_selling_price = DECIMAL_ZERO
            purchase.previous_producer_vat = DECIMAL_ZERO
            purchase.previous_customer_vat = DECIMAL_ZERO
            purchase.previous_deposit = DECIMAL_ZERO
            if send_to_producer:
                if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                    purchase.quantity_invoiced = (purchase.quantity_ordered * offer_item.order_average_weight) \
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
        purchase.save()


def display_selected_value(offer_item, quantity_ordered):
    if offer_item.may_order:
        if quantity_ordered <= DECIMAL_ZERO:
            q_min = offer_item.customer_minimum_order_quantity
            if offer_item.limit_order_quantity_to_stock:
                q_alert = offer_item.stock - offer_item.quantity_invoiced
                if q_alert < DECIMAL_ZERO:
                    q_alert = DECIMAL_ZERO
            else:
                q_alert = offer_item.customer_alert_order_quantity
            if q_min <= q_alert:
                qs = models.ProducerInvoice.objects.filter(
                    permanence__offeritem=offer_item.id,
                    producer__offeritem=offer_item.id,
                    status=PERMANENCE_OPENED
                ).order_by('?')
                if qs.exists():
                    option_dict = {
                        'id'  : "#offer_item%d" % offer_item.id,
                        'html': '<option value="0" selected>---</option>'
                    }
                else:
                    closed = _("Closed")
                    option_dict = {
                        'id'  : "#offer_item%d" % offer_item.id,
                        'html': '<option value="0" selected>%s</option>' % closed
                    }
            else:
                sold_out = _("Sold out")
                option_dict = {
                    'id'  : "#offer_item%d" % offer_item.id,
                    'html': '<option value="0" selected>%s</option>' % sold_out
                }

        else:
            unit_price_amount = offer_item.customer_unit_price.amount + offer_item.unit_deposit.amount
            display = get_display(
                qty=quantity_ordered,
                order_average_weight=offer_item.order_average_weight,
                order_unit=offer_item.order_unit,
                unit_price_amount=unit_price_amount,
                for_order_select=True
            )
            option_dict = {
                'id'  : "#offer_item%d" % offer_item.id,
                'html': '<option value="%d" selected>%s</option>' % (quantity_ordered, display,)
            }
    else:
        option_dict = {
            'id'  : "#box_offer_item%d" % offer_item.id,
            'html': ''
        }
    return option_dict


def display_selected_box_value(customer, offer_item, box_purchase):
    if offer_item.is_box_content:
        # box_name = _not_lazy("Composition")
        box_name = BOX_UNICODE
        # Select one purchase
        if box_purchase is not None:
            if box_purchase.quantity_ordered > DECIMAL_ZERO:
                qty_display = get_display(
                    qty=box_purchase.quantity_ordered,
                    order_average_weight=offer_item.order_average_weight,
                    order_unit=offer_item.order_unit,
                    for_order_select=True,
                    without_price_display=True
                )
                option_dict = {
                    'id'  : "#box_offer_item%d" % offer_item.id,
                    'html': '<select name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ %s %s</option></select>'
                            % (offer_item.id, qty_display, box_name)
                }
            else:
                option_dict = {
                    'id'  : "#box_offer_item%d" % offer_item.id,
                    'html': '<select name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ --- %s</option></select>'
                            % (offer_item.id, box_name)
                }
        else:
            option_dict = {
                'id'  : "#box_offer_item%d" % offer_item.id,
                'html': '<select name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ --- %s</option></select>'
                        % (offer_item.id, box_name)
            }
    else:
        option_dict = {
            'id'  : "#box_offer_item%d" % offer_item.id,
            'html': ''
        }
    return option_dict


@transaction.atomic
def update_or_create_purchase(customer=None, offer_item_id=None, value_id=None, basket=False, batch_job=False):
    to_json = []
    if offer_item_id is not None and value_id is not None and customer is not None:
        offer_item = models.OfferItem.objects.select_for_update(nowait=False) \
            .filter(id=offer_item_id, is_active=True) \
            .order_by('?').select_related("product", "producer").first()
        if offer_item is not None and offer_item.may_order:
            purchase = None
            permanence_id = offer_item.permanence_id
            updated = True
            if offer_item.is_box:
                # Select one purchase
                purchase = models.Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item.id,
                    is_box_content=False
                ).order_by('?').first()
                if purchase is not None:
                    delta_value_id = value_id - purchase.quantity_ordered
                else:
                    delta_value_id = value_id
                with transaction.atomic():
                    sid = transaction.savepoint()
                    # This code executes inside a transaction.
                    for content in models.BoxContent.objects.filter(
                            box=offer_item.product_id
                    ).only(
                        "product_id","content_quantity"
                    ).order_by('?'):
                        # box_offer_item = models.OfferItem.objects.select_for_update(nowait=False)\
                        box_offer_item = models.OfferItem.objects \
                            .filter(product_id=content.product_id, permanence_id=offer_item.permanence_id) \
                            .order_by('?').select_related("producer").first()
                        if box_offer_item is not None:
                            # Select one purchase
                            purchase = models.Purchase.objects.filter(
                                customer_id=customer.id,
                                offer_item_id=box_offer_item.id,
                                is_box_content=True
                            ).order_by('?').first()
                            if purchase is not None:
                                quantity_ordered = purchase.quantity_ordered + delta_value_id * content.content_quantity
                            else:
                                quantity_ordered = delta_value_id * content.content_quantity
                            if quantity_ordered < DECIMAL_ZERO:
                                quantity_ordered = DECIMAL_ZERO
                            purchase, updated = create_or_update_one_purchase(
                                customer, box_offer_item, None, quantity_ordered, close_orders=batch_job, is_box_content=True
                            )
                        else:
                            updated = False
                        if not updated:
                            break
                    if updated:
                        for content in models.BoxContent.objects.filter(box=offer_item.product_id).only(
                                "product_id").order_by('?'):
                            box_offer_item = models.OfferItem.objects.filter(
                                product_id=content.product_id,
                                permanence_id=offer_item.permanence_id
                            ).order_by('?').first()
                            if box_offer_item is not None:
                                # Select one purchase
                                purchase = models.Purchase.objects.filter(
                                    customer_id=customer.id,
                                    offer_item_id=box_offer_item.id,
                                    is_box_content=False
                                ).order_by('?').first()
                                option_dict = display_selected_value(
                                    box_offer_item,
                                    purchase.quantity_ordered if purchase is not None else DECIMAL_ZERO
                                )
                                to_json.append(option_dict)
                                box_purchase = models.Purchase.objects.filter(
                                    customer_id=customer.id,
                                    offer_item_id=box_offer_item.id,
                                    is_box_content=True
                                ).order_by('?').first()
                                option_dict = display_selected_box_value(customer, box_offer_item, box_purchase)
                                to_json.append(option_dict)
                        transaction.savepoint_commit(sid)
                    else:
                        transaction.savepoint_rollback(sid)
            if not offer_item.is_box or updated:
                purchase, updated = create_or_update_one_purchase(customer, offer_item, value_id, None, close_orders=batch_job,
                                                                  is_box_content=False)
                if not batch_job and apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
                    producer_invoice = models.ProducerInvoice.objects.filter(
                        producer_id=offer_item.producer_id, permanence_id=offer_item.permanence_id
                    ).only("total_price_with_tax").order_by('?').first()
                    if producer_invoice is None:
                        ratio = 0
                    else:
                        if offer_item.producer.minimum_order_value.amount == DECIMAL_ZERO:
                            ratio = 100
                        else:
                            ratio = producer_invoice.total_price_with_tax.amount / offer_item.producer.minimum_order_value.amount
                        if ratio >= DECIMAL_ONE:
                            ratio = 100
                        else:
                            ratio *= 100
                    option_dict = {'id'  : "#order_procent" + str(offer_item.producer_id),
                                   'html': "%s%%" % number_format(ratio, 0)}
                    to_json.append(option_dict)
            elif not batch_job:
                # Select one purchase
                purchase = models.Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item.id,
                    is_box_content=False
                ).order_by('?').first()

            if not batch_job:
                if purchase is None:
                    if offer_item.is_box:
                        sold_out = _("Sold out")
                        option_dict = {
                            'id'  : "#offer_item%d" % offer_item.id,
                            'html': '<option value="0" selected>%s</option>' % sold_out
                        }
                    else:
                        option_dict = display_selected_value(offer_item, DECIMAL_ZERO)
                    to_json.append(option_dict)
                else:
                    offer_item = models.OfferItem.objects.filter(id=offer_item_id).order_by('?').first()
                    if offer_item is not None:
                        option_dict = display_selected_value(offer_item, purchase.quantity_ordered)
                        to_json.append(option_dict)

                customer_invoice = models.CustomerInvoice.objects.filter(
                    permanence_id=permanence_id,
                    customer_id=customer.id
                ).order_by('?').first()
                permanence = models.Permanence.objects.filter(
                    id=permanence_id
                ).only("id", "with_delivery_point", "status").order_by('?').first()
                if customer_invoice is not None and permanence is not None:
                    order_amount = customer_invoice.get_total_price_with_tax()
                    customer_invoice.cancel_confirm_order()
                    customer_invoice.save()
                    my_basket(customer_invoice.is_order_confirm_send, order_amount, to_json)
                    if basket:
                        basket_message = calc_basket_message(customer, permanence, customer_invoice.status)
                    else:
                        basket_message = EMPTY_STRING
                    my_order_confirmation(
                        permanence=permanence,
                        customer_invoice=customer_invoice,
                        is_basket=basket,
                        basket_message=basket_message,
                        to_json=to_json
                    )
    return json.dumps(to_json, cls=DjangoJSONEncoder)


def my_basket(is_order_confirm_send, order_amount, to_json):
    if not is_order_confirm_send and apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        msg_html = '<span class="glyphicon glyphicon-shopping-cart"></span> %s&nbsp;&nbsp;&nbsp;<span class="glyphicon glyphicon-exclamation-sign"></span>&nbsp;<span class="glyphicon glyphicon-floppy-remove"></span></a>' % (
        order_amount,)
    else:
        msg_html = '<span class="glyphicon glyphicon-shopping-cart"></span> %s&nbsp;&nbsp;&nbsp;<span class="glyphicon glyphicon-floppy-saved"></span></a>' % (
        order_amount,)
    option_dict = {'id': "#my_basket", 'html': msg_html}
    to_json.append(option_dict)
    option_dict = {'id': "#prepared_amount_visible_xs", 'html': msg_html}
    to_json.append(option_dict)


def my_order_confirmation(permanence, customer_invoice, is_basket=False,
                          basket_message=EMPTY_STRING, to_json=None):
    if permanence.with_delivery_point:
        if customer_invoice.delivery is not None:
            label = customer_invoice.delivery.get_delivery_customer_display()
            delivery_id = customer_invoice.delivery_id
        else:
            delivery_id = -1
            if customer_invoice.customer.delivery_point is not None:
                qs = models.DeliveryBoard.objects.filter(
                    Q(
                        permanence_id=permanence.id,
                        delivery_point_id=customer_invoice.customer.delivery_point_id,
                        status=PERMANENCE_OPENED
                    ) | Q(
                        permanence_id=permanence.id,
                        delivery_point__closed_group=False,
                        status=PERMANENCE_OPENED
                    )
                ).order_by('?')
            else:
                qs = models.DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    delivery_point__closed_group=False,
                    status=PERMANENCE_OPENED
                ).order_by('?')
            if qs.exists():
                label = "%s" % _('Please, select a delivery point')
                models.CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    customer_id=customer_invoice.customer_id).order_by('?').update(
                    status=PERMANENCE_OPENED)
            else:
                label = "%s" % _('No delivery point is open for you. You can not place order.')
                # IMPORTANT :
                # 1 / This prohibit to place an order into the customer UI
                # 2 / task_order.close_send_order will delete any CLOSED orders without any delivery point
                models.CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    customer_id=customer_invoice.customer_id
                ).order_by('?').update(
                    status=PERMANENCE_CLOSED)
        if customer_invoice.customer_id != customer_invoice.customer_who_pays_id:
            msg_price = msg_transport = EMPTY_STRING
        else:
            if customer_invoice.transport.amount <= DECIMAL_ZERO:
                transport = False
                msg_transport = EMPTY_STRING
            else:
                transport = True
                if customer_invoice.min_transport.amount > DECIMAL_ZERO:
                    msg_transport = "%s<br/>" % \
                                    _(
                                        'The shipping costs for this delivery point amount to %(transport)s for orders of less than %(min_transport)s.') % {
                                        'transport'    : customer_invoice.transport,
                                        'min_transport': customer_invoice.min_transport
                                    }
                else:
                    msg_transport = "%s<br/>" % \
                                    _(
                                        'The shipping costs for this delivery point amount to %(transport)s.') % {
                                        'transport': customer_invoice.transport,
                                    }
            if customer_invoice.price_list_multiplier == DECIMAL_ONE:
                msg_price = EMPTY_STRING
            else:
                if transport:
                    if customer_invoice.price_list_multiplier > DECIMAL_ONE:
                        msg_price = "%s<br/>" % \
                                        _(
                                            'A price increase of %(increase)s %% of the total invoiced is due for this delivery point. This does not apply to the cost of transport which is fixed.') % {
                                            'increase'    : number_format((customer_invoice.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                                        }
                    else:
                        msg_price = "%s<br/>" % \
                                        _(
                                            'A price decrease of %(decrease)s %% of the total invoiced is given for this delivery point. This does not apply to the cost of transport which is fixed.') % {
                                            'decrease': number_format((DECIMAL_ONE - customer_invoice.price_list_multiplier) * 100, 2)
                                        }
                else:
                    if customer_invoice.price_list_multiplier > DECIMAL_ONE:
                        msg_price = "%s<br/>" % \
                                        _(
                                            'A price increase of %(increase)s %% of the total invoiced is due for this delivery point.') % {
                                            'increase'    : number_format((customer_invoice.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                                        }
                    else:
                        msg_price = "%s<br/>" % \
                                        _(
                                            'A price decrease of %(decrease)s %% of the total invoiced is given for this delivery point.') % {
                                            'decrease': number_format((DECIMAL_ONE - customer_invoice.price_list_multiplier) * 100, 2)
                                        }

        msg_delivery = '%s<b><i><select name="delivery" id="delivery" onmouseover="delivery_select_ajax()" onchange="delivery_ajax()" class="form-control"><option value="%d" selected>%s</option></select></i></b><br/>%s%s' % (
            _("Delivery point"),
            delivery_id,
            label,
            msg_transport,
            msg_price
        )
    else:
        msg_delivery = EMPTY_STRING
    if not is_basket and not apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        # or customer_invoice.total_price_with_tax.amount != DECIMAL_ZERO:
        # If apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS is True,
        # then permanence.with_delivery_point is also True
        msg_confirmation = msg_html = EMPTY_STRING
    else:
        if customer_invoice.is_order_confirm_send:
            msg_confirmation = my_order_confirmation_email_send_to(customer_invoice.customer)
            msg_html = """
            <div class="row">
            <div class="panel panel-default">
            <div class="panel-heading">
            %s
            <button id="btn_confirm_order" class="btn" disabled>%s</button>
            <div class="clearfix"></div>
            %s
            </div>
            </div>
            </div>
             """ % (msg_delivery, msg_confirmation, basket_message)
        else:
            msg_html = None
            btn_disabled = EMPTY_STRING
            msg_confirmation = EMPTY_STRING
            if apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                if is_basket:
                    if customer_invoice.status == PERMANENCE_OPENED:
                        if permanence.with_delivery_point and customer_invoice.delivery is None:
                            btn_disabled = "disabled"
                        msg_confirmation = '<span class="glyphicon glyphicon-floppy-disk"></span>&nbsp;&nbsp;%s' % _("Confirm this order and receive an email containing its summary.")
                else:
                    href = urlresolvers.reverse(
                        'basket_view', args=(permanence.id,)
                    )
                    msg_confirmation = _("Verify my order content before validating it.")
                    msg_html = """
                        <div class="row">
                        <div class="panel panel-default">
                        <div class="panel-heading">
                        %s
                        <a href="%s" class="btn btn-info" %s>%s</a>
                        </div>
                        </div>
                        </div>
                         """ % (msg_delivery, href, btn_disabled, msg_confirmation)
            else:
                if is_basket:
                    msg_confirmation = _("Receive an email containing this order summary.")
                elif permanence.with_delivery_point:
                    msg_html = """
                        <div class="row">
                        <div class="panel panel-default">
                        <div class="panel-heading">
                        %s
                        </div>
                        </div>
                        </div>
                         """ % msg_delivery
                else:
                    msg_html = EMPTY_STRING
            if msg_html is None:
                if msg_confirmation == EMPTY_STRING:
                    msg_html = """
                    <div class="row">
                    <div class="panel panel-default">
                    <div class="panel-heading">
                    %s
                    <div class="clearfix"></div>
                    %s
                    </div>
                    </div>
                    </div>
                     """ % (msg_delivery, basket_message)
                else:
                    msg_html = """
                    <div class="row">
                    <div class="panel panel-default">
                    <div class="panel-heading">
                    %s
                    <button id="btn_confirm_order" class="btn btn-info" %s onclick="btn_receive_order_email();">%s</button>
                    <div class="clearfix"></div>
                    %s
                    </div>
                    </div>
                    </div>
                     """ % (msg_delivery, btn_disabled, msg_confirmation, basket_message)
    if to_json is not None:
        option_dict = {'id': "#span_btn_confirm_order", 'html': msg_html}
        to_json.append(option_dict)
    return msg_confirmation


def my_order_confirmation_email_send_to(customer):
    if customer is not None and customer.email2:
        to_email = (customer.user.email, customer.email2)
    else:
        to_email = (customer.user.email,)
    sent_to = ", ".join(to_email) if to_email is not None else EMPTY_STRING
    if apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        msg_confirmation = _(
            "Your order is confirmed. An email containing this order summary has been sent to %s.") % sent_to
    else:
        msg_confirmation = _("An email containing this order summary has been sent to %s.") % sent_to
    return msg_confirmation


def create_or_update_one_purchase(customer, offer_item, value_id, value, close_orders, is_box_content):
    status = models.CustomerInvoice.objects.filter(
        permanence_id=offer_item.permanence_id, customer_id=customer.id) \
        .only("status") \
        .order_by('?').first().status
    # The close_orders flag is used because we need to forbid
    # customers to add purchases during the close_orders_async process
    # when the status is PERMANENCE_WAIT_FOR_SEND
    if (status == PERMANENCE_OPENED) or close_orders:
        # The offer_item belong to an open permanence
        # Select one purchase
        purchase = models.Purchase.objects.filter(
            customer_id=customer.id,
            offer_item_id=offer_item.id,
            is_box_content=is_box_content
        ).order_by('?').first()
        if purchase is not None:
            q_previous_order = purchase.quantity_ordered
        else:
            q_previous_order = DECIMAL_ZERO
        if value is not None:
            q_order = value if value > 0 else DECIMAL_ZERO
        else:
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
        if status == PERMANENCE_OPENED and offer_item.limit_order_quantity_to_stock:
            q_alert = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
            if is_box_content and q_alert < q_order:
                # Select one purchase
                non_box_purchase = models.Purchase.objects.filter(
                    customer_id=customer.id,
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
        if q_order <= q_alert:
            if purchase is not None:
                if close_orders and value_id == DECIMAL_ZERO:
                    purchase.comment = _("Cancelled qty : %s") % number_format(purchase.quantity_ordered, 4)
                purchase.quantity_ordered = q_order
                purchase.save()
            else:
                permanence = models.Permanence.objects.filter(id=offer_item.permanence_id) \
                    .only("permanence_date") \
                    .order_by('?').first()
                purchase = models.Purchase.objects.create(
                    permanence_id=offer_item.permanence_id,
                    permanence_date=permanence.permanence_date,
                    offer_item_id=offer_item.id,
                    producer_id=offer_item.producer_id,
                    customer_id=customer.id,
                    quantity_ordered=q_order,
                    quantity_invoiced=DECIMAL_ZERO,
                    is_box_content=is_box_content,
                    status=status
                )
            return purchase, True
        else:
            return purchase, False


def clean_offer_item(permanence, queryset, reset_add_2_stock=False):
    if permanence.status > PERMANENCE_SEND:
        # The purchases are already invoiced.
        # The offer item may not be modified any more
        return
    getcontext().rounding = ROUND_HALF_UP
    for offer_item in queryset.select_related("product", "producer"):
        product = offer_item.product
        producer = offer_item.producer
        if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            offer_item.is_active = product.is_into_offer
        offer_item.picture2 = product.picture2
        offer_item.reference = product.reference
        offer_item.department_for_customer_id = product.department_for_customer_id
        offer_item.producer_id = product.producer_id
        offer_item.order_unit = product.order_unit
        offer_item.wrapped = product.wrapped
        offer_item.order_average_weight = product.order_average_weight
        offer_item.placement = product.placement
        offer_item.producer_vat = product.producer_vat
        offer_item.customer_vat = product.customer_vat
        # Important : the group must pay the VAT, so it's easier to allways have
        # offer_item with VAT included
        if producer.producer_price_are_wo_vat:
            offer_item.producer_unit_price = product.producer_unit_price + offer_item.producer_vat
            offer_item.producer_price_are_wo_vat = False
        else:
            offer_item.producer_unit_price = product.producer_unit_price
            offer_item.producer_price_are_wo_vat = producer.producer_price_are_wo_vat
        offer_item.customer_unit_price = product.customer_unit_price
        # Important : for purchasing : the price is * by order_average_weight
        # Thus, the unit deposit must be Zero.
        offer_item.unit_deposit = DECIMAL_ZERO if product.order_unit == PRODUCT_ORDER_UNIT_PC_KG else product.unit_deposit
        offer_item.vat_level = product.vat_level
        offer_item.limit_order_quantity_to_stock = product.limit_order_quantity_to_stock
        offer_item.producer_pre_opening = producer.producer_pre_opening
        if offer_item.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            offer_item.manage_replenishment = producer.manage_replenishment
        else:
            offer_item.manage_replenishment = False
        offer_item.manage_production = producer.manage_production
        # Important : or product.is_box -> impact into Purchase.get_customer_unit_price
        # The boxes prices are not subjects to price modifications
        offer_item.is_resale_price_fixed = producer.is_resale_price_fixed or product.is_box
        offer_item.price_list_multiplier = DECIMAL_ONE if offer_item.is_resale_price_fixed else producer.price_list_multiplier
        offer_item.stock = product.stock
        if reset_add_2_stock:
            offer_item.add_2_stock = DECIMAL_ZERO
        offer_item.customer_minimum_order_quantity = product.customer_minimum_order_quantity
        offer_item.customer_increment_order_quantity = product.customer_increment_order_quantity
        offer_item.customer_alert_order_quantity = product.customer_alert_order_quantity
        offer_item.producer_order_by_quantity = product.producer_order_by_quantity
        offer_item.is_box = product.is_box
        offer_item.is_membership_fee = product.is_membership_fee
        offer_item.save()

    # Now got everything to calculate the sort order of the order display screen
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        translation.activate(language["code"])
        for offer_item in queryset.select_related("product", "producer", "department_for_customer"):
            offer_item.long_name = offer_item.product.long_name
            offer_item.cache_part_a = render_to_string('repanier/cache_part_a.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_b = render_to_string('repanier/cache_part_b.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.cache_part_e = render_to_string('repanier/cache_part_e.html',
                                                       {'offer': offer_item, 'MEDIA_URL': settings.MEDIA_URL})
            offer_item.save_translations()

        departementforcustomer_set = models.LUT_DepartmentForCustomer.objects.filter(
            offeritem__permanence_id=permanence.id,
            offeritem__order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT) \
            .order_by("tree_id", "lft") \
            .distinct("id", "tree_id", "lft")
        if departementforcustomer_set:
            pass
        if apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
            producer_set = models.Producer.objects.filter(permanence=permanence.id).only("id", "short_profile_name")
        else:
            producer_set = None
        permanence.cache_part_d = render_to_string('repanier/cache_part_d.html',
                                                   {'producer_set'              : producer_set,
                                                    'departementforcustomer_set': departementforcustomer_set})
        permanence.save_translations()
    translation.activate(cur_language)


def reorder_offer_items(permanence_id):
    # calculate the sort order of the order display screen
    cur_language = translation.get_language()
    offer_item_qs = models.OfferItem.objects.filter(permanence_id=permanence_id).order_by('?')
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        # customer order lists sort order
        i = 0
        reorder_queryset = offer_item_qs.filter(
            is_box=False,
            translations__language_code=language_code
        ).order_by(
            "department_for_customer__tree_id",
            "department_for_customer__lft",
            "translations__long_name",
            "order_average_weight",
            "producer__short_profile_name"
        )
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = offer_item.order_sort_order = i
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
            "department_for_customer__tree_id",
            "department_for_customer__lft",
            "reference"
        )
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = i
            offer_item.save_translations()
            if i < 19999:
                i += 1
        # preparation lists sort order
        i = 0
        reorder_queryset = offer_item_qs.filter(
            is_box=False,
            translations__language_code=language_code
        ).order_by(
            "department_for_customer__tree_id",
            # "department_for_customer__lft",
            "translations__long_name",
            "order_average_weight",
            "producer__short_profile_name"
        )
        for offer_item in reorder_queryset:
            offer_item.preparation_sort_order = i
            offer_item.save_translations()
            if i < 9999:
                i += 1
        i = -9999
        reorder_queryset = offer_item_qs.filter(
            is_box=True,
            translations__language_code=language_code
        ).order_by(
            "customer_unit_price",
            "department_for_customer__lft",
            "unit_deposit",
            "translations__long_name"
        )
        # 'TranslatableQuerySet' object has no attribute 'desc'
        for offer_item in reorder_queryset:
            # display box on top
            offer_item.order_sort_order = i
            offer_item.producer_sort_order = i
            offer_item.preparation_sort_order = i
            offer_item.save_translations()
            if i < -1:
                i += 1
    translation.activate(cur_language)


def update_offer_item(product_id=None, producer_id=None):
    # Important : If the user want to modify the price of a product PERMANENCE_SEND
    # Then he can do it via "rule_of_3_per_product"
    for permanence in models.Permanence.objects.filter(
            status__in=[PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED]
    ):
        if producer_id is None:
            offer_item_qs = models.OfferItem.objects.filter(
                permanence_id=permanence.id,
                product_id=product_id,
            ).order_by('?')
        else:
            offer_item_qs = models.OfferItem.objects.filter(
                permanence_id=permanence.id,
                producer_id=producer_id,
            ).order_by('?')
        clean_offer_item(permanence, offer_item_qs)
        recalculate_order_amount(
            permanence_id=permanence.id,
            offer_item_queryset=offer_item_qs,
            all_producers=True,
            send_to_producer=False
        )
    cache.clear()


def get_or_create_offer_item(permanence, product_id, producer_id=None):
    offer_item_qs = models.OfferItem.objects.filter(
        permanence_id=permanence.id,
        product_id=product_id,
    ).order_by('?')
    if not offer_item_qs.exists():
        if producer_id is None:
            producer_id = models.Product.objects.filter(id=product_id).only("producer_id").order_by(
                '?').first().producer_id
        models.OfferItem.objects.create(
            permanence_id=permanence.id,
            product_id=product_id,
            producer_id=producer_id,
            is_active=False,
            may_order=False
        )
        clean_offer_item(permanence, offer_item_qs)
    offer_item = offer_item_qs.first()
    return offer_item


def producer_web_services_activated(reference_site=None):
    web_services_activated = False
    web_service_version = None
    if reference_site is not None and len(reference_site) > 0:
        try:
            web_services = urllib2.urlopen(
                '%s%s' % (reference_site, urlresolvers.reverse('version_rest')),
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
    if apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        customer_invoice = models.CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence_id=permanence.id
        ).only("is_order_confirm_send").order_by('?').first()
        if not customer_invoice.is_order_confirm_send:
            return EMPTY_STRING
        else:
            invoice_msg = EMPTY_STRING
            customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
                customer, permanence)
            if apps.REPANIER_SETTINGS_INVOICE:
                invoice_msg = "<br/>%s %s" % (
                    customer_last_balance,
                    customer_on_hold_movement,
                )
            basket_message = "%s%s%s" % (
                customer_order_amount,
                invoice_msg,
                customer_payment_needed
            )
            return basket_message
    else:
        if status == PERMANENCE_OPENED:
            if permanence.with_delivery_point:
                you_can_change = "<br/>%s" % (
                    _("You can change the order quantities as long as the orders are open for your delivery point."),
                )
            else:
                you_can_change = "<br/>%s" % (
                    _("You can change the order quantities as long as the orders are open."),
                )
        else:
            if permanence.with_delivery_point:
                you_can_change = "<br/>%s" % (
                    _('The orders are closed for your delivery point.'),
                )
            else:
                you_can_change = "<br/>%s" % (
                    _('The orders are closed.'),
                )
        invoice_msg = EMPTY_STRING
        payment_msg = EMPTY_STRING
        customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
            customer, permanence)
        if apps.REPANIER_SETTINGS_INVOICE:
            if customer_last_balance:
                invoice_msg = "<br/>%s %s" % (
                    customer_last_balance,
                    customer_on_hold_movement,
                )
        if apps.REPANIER_SETTINGS_BANK_ACCOUNT is not None:
            payment_msg = "<br/>%s" % (
                customer_payment_needed,
            )
        basket_message = "%s%s%s%s" % (
            customer_order_amount,
            invoice_msg,
            payment_msg,
            you_can_change
        )
        return basket_message


def recalculate_prices(product, producer_price_are_wo_vat, is_resale_price_fixed, price_list_multiplier):
    getcontext().rounding = ROUND_HALF_UP
    vat = DICT_VAT[product.vat_level]
    vat_rate = vat[DICT_VAT_RATE]
    if producer_price_are_wo_vat:
        product.producer_vat.amount = (product.producer_unit_price.amount * vat_rate).quantize(FOUR_DECIMALS)
        if not is_resale_price_fixed:
            if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                product.customer_unit_price.amount = (
                    product.producer_unit_price.amount * price_list_multiplier).quantize(
                    TWO_DECIMALS)
            else:
                product.customer_unit_price = product.producer_unit_price
        product.customer_vat.amount = (product.customer_unit_price.amount * vat_rate).quantize(FOUR_DECIMALS)
        if not is_resale_price_fixed:
            product.customer_unit_price += product.customer_vat
    else:
        product.producer_vat.amount = product.producer_unit_price.amount - (
            product.producer_unit_price.amount / (DECIMAL_ONE + vat_rate)).quantize(
            FOUR_DECIMALS)
        if not is_resale_price_fixed:
            if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                product.customer_unit_price.amount = (
                    product.producer_unit_price.amount * price_list_multiplier).quantize(
                    TWO_DECIMALS)
            else:
                product.customer_unit_price = product.producer_unit_price

        product.customer_vat.amount = product.customer_unit_price.amount - (
            product.customer_unit_price.amount / (DECIMAL_ONE + vat_rate)).quantize(
            FOUR_DECIMALS)


def html_box_content(offer_item, user, result=EMPTY_STRING):
    if offer_item.is_box:
        box_id = offer_item.product_id
        if result is not None and result != EMPTY_STRING:
            result += '<hr/>'
        product_ids = models.BoxContent.objects.filter(
            box_id=box_id
        ).only("product_id")
        qs = models.OfferItem.objects.filter(
            permanence_id=offer_item.permanence_id,  # is_active=True,
            product__box_content__in=product_ids,
            translations__language_code=translation.get_language()
        ).order_by(
            "translations__order_sort_order"
        )
        result += '<ul>' + ("".join('<li>%s * %s, %s <span class="btn_like%s" style="cursor: pointer;">%s</span></li>' % (
            get_display(
                qty=models.BoxContent.objects.filter(box_id=box_id, product_id=o.product_id).only(
                    "content_quantity").order_by('?').first().content_quantity,
                order_average_weight=o.order_average_weight,
                order_unit=o.order_unit,
                without_price_display=True),
            o.long_name,
            o.producer.short_profile_name,
            o.id,
            o.get_like(user)
        ) for o in qs)) + '</ul>'
    return result


def get_full_status_display(permanence):
    need_to_refresh_status = permanence.status in [
        PERMANENCE_WAIT_FOR_PRE_OPEN,
        PERMANENCE_WAIT_FOR_OPEN,
        PERMANENCE_WAIT_FOR_CLOSED,
        PERMANENCE_WAIT_FOR_SEND,
        PERMANENCE_WAIT_FOR_DONE
    ]
    if permanence.with_delivery_point:
        status_list = []
        status = None
        status_counter = 0
        for delivery in models.DeliveryBoard.objects.filter(permanence_id=permanence.id).order_by("status", "id"):
            if status != delivery.status:
                need_to_refresh_status |= delivery.status in [
                    PERMANENCE_WAIT_FOR_PRE_OPEN,
                    PERMANENCE_WAIT_FOR_OPEN,
                    PERMANENCE_WAIT_FOR_CLOSED,
                    PERMANENCE_WAIT_FOR_SEND,
                    PERMANENCE_WAIT_FOR_DONE
                ]
                status = delivery.status
                status_counter += 1
                status_list.append("<b>%s</b>" % delivery.get_status_display())
            status_list.append("- %s" % delivery)
        if status_counter > 1:
            return '<div class="wrap-text">%s</div>' % "<br/>".join(status_list)
    if need_to_refresh_status:
        url = urlresolvers.reverse(
                            'display_status',
                            args=(permanence.id,)
                        )
        msg_html = """
            <div class="wrap-text" id="id_get_status_%d">
            <script type="text/javascript">
                window.setTimeout(function(){
                    django.jQuery.ajax({
                        url: '%s',
                        cache: false,
                        async: false,
                        success: function (result) {
                            django.jQuery("#id_get_status_%d").html(result);
                        }
                    });
                }, 1000);
            </script>
            %s</div>
        """ % (
            permanence.id, url, permanence.id, permanence.get_status_display()
        )
        return mark_safe(msg_html)
    else:
        return mark_safe('<div class="wrap-text">%s</div>' % permanence.get_status_display())
