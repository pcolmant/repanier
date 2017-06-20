# -*- coding: utf-8
from __future__ import unicode_literals

import calendar
import datetime
import json
import time

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen

from smtplib import SMTPRecipientsRefused, SMTPAuthenticationError

from django.conf import settings
from django.core import mail
from django.core import urlresolvers
from django.core.cache import cache
from django.core.mail import EmailMessage, mail_admins
from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.http import Http404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from six import string_types

from repanier import models
from repanier.const import *
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
        return


def emails_of_testers():
    tester_qs = models.Staff.objects.filter(is_tester=True, is_active=True).order_by("id")
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
        subject = "%s" % _("Test from Repanier")
        body = "%s" % _("The mail is correctly configured on your Repanier website")
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=host_user,
            to=to
        )
        return send_email(
            email,
            test=True,
            host=host,
            port=port,
            host_user=host_user,
            host_password=host_password,
            use_tls=use_tls)
    else:
        return False


def send_email(
        email=None, from_name=EMPTY_STRING, track_customer_on_error=False,
        test=False, host=None, port=None, host_user=None, host_password=None, use_tls=None):
    email_send = False
    from_email, host, host_password, host_user, port, use_tls = send_email_get_connection_param(
        test, host, host_password, host_user, port, use_tls)
    if settings.DJANGO_SETTINGS_DEMO:
        email.to = [DEMO_EMAIL]
        email.cc = []
        email.bcc = []
        email_send = send_email_with_error_log(email, from_name, from_email=from_email, host=host,
            port=port,
            host_user=host_user,
            host_password=host_password,
            use_tls=use_tls)
    else:
        from repanier.apps import REPANIER_SETTINGS_TEST_MODE
        if REPANIER_SETTINGS_TEST_MODE:
            email.to = emails_of_testers()
            if len(email.to) > 0:
                # Send the mail only if there is at least one tester
                email.cc = []
                email.bcc = []
                email_send = send_email_with_error_log(email, from_name, from_email=from_email, host=host,
                    port=port,
                    host_user=host_user,
                    host_password=host_password,
                    use_tls=use_tls)
            else:
                print('############################ test mode, without tester...')
        else:
            if settings.DEBUG:
                print("to : %s" % email.to)
                print("cc : %s" % email.cc)
                print("bcc : %s" % email.bcc)
                print("subject : %s" % slugify(email.subject))
                email_send = True
            else:
                # chunks = [email.to[x:x+100] for x in xrange(0, len(email.to), 100)]
                # for chunk in chunks:
                # Remove duplicates
                send_email_to = list(set(email.to + email.cc + email.bcc))
                email.cc = []
                email.bcc = []
                email_send = True
                if len(send_email_to) >= 1:
                    customer = None
                    for email_to in send_email_to:
                        email.to = [email_to]
                        email_send &= send_email_with_error_log(
                            email,
                            from_name,
                            track_customer_on_error,
                            from_email=from_email,
                            host=host,
                            port=port,
                            host_user=host_user,
                            host_password=host_password,
                            use_tls=use_tls)
                        time.sleep(1)
    return email_send


def send_email_with_error_log(
        email, from_name=None, track_customer_on_error=False,
        from_email=None, host=None, port=None, host_user=None, host_password=None, use_tls=None):
    email_send = False
    email_to = email.to[0]
    customer, send_mail = send_email_get_customer(email_to, track_customer_on_error)
    if send_mail:
        try:
            with mail.get_connection(host=host, port=port, username=host_user, password=host_password, use_tls=use_tls, use_ssl=not use_tls) as connection:
                email.connection = connection
                message = EMPTY_STRING
                if not email.from_email.endswith(settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION):
                    email.reply_to = [email.from_email]
                    email.from_email = "%s <%s>" % (from_name or apps.REPANIER_SETTINGS_GROUP_NAME, from_email)
                else:
                    email.from_email = "%s <%s>" % (from_name or apps.REPANIER_SETTINGS_GROUP_NAME, email.from_email)
                try:
                    print("################################## send_email")
                    reply_to = "reply_to : %s" % email.reply_to
                    to = "to : %s" % email.to
                    cc = "cc : %s" % email.cc
                    bcc = "bcc : %s" % email.bcc
                    subject = "subject : %s" % slugify(email.subject)
                    print(reply_to)
                    print(to)
                    print(cc)
                    print(bcc)
                    print(subject)
                    message = "%s\n%s\n%s\n%s" % (to, cc, bcc, subject)
                    email.send()
                    email_send = True
                except SMTPRecipientsRefused as error_str:
                    print("################################## send_email SMTPRecipientsRefused")
                    print(error_str)
                    time.sleep(1)
                    connection = mail.get_connection()
                    connection.open()
                    mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
                    connection.close()
                except Exception as error_str:
                    print("################################## send_email error")
                    print(error_str)
                    time.sleep(1)
                    connection = mail.get_connection()
                    connection.open()
                    mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
                    connection.close()
                print("##################################")
                if customer is not None:
                    # customer.valid_email = valid_email
                    # customer.save(update_fields=['valid_email'])
                    # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
                    models.Customer.objects.filter(id=customer.id).order_by('?').update(valid_email=email_send)
        except SMTPAuthenticationError as error_str:
            print("################################## send_email SMTPAuthenticationError")
            # https://support.google.com/accounts/answer/185833
            # https://support.google.com/accounts/answer/6010255
            # https://security.google.com/settings/security/apppasswords
            print(error_str)
    return email_send


def send_email_get_connection_param(test, host, host_password, host_user, port, use_tls):
    from repanier.apps import REPANIER_SETTINGS_CONFIG
    config = REPANIER_SETTINGS_CONFIG
    if config.email_is_custom and not test and not settings.DJANGO_SETTINGS_DEMO:
        host = config.email_host
        port = config.email_port
        from_email = host_user = config.email_host_user
        host_password = config.email_host_password
        use_tls = config.email_use_tls
    if test and not settings.DJANGO_SETTINGS_DEMO:
        from_email = host_user
    else:
        host = settings.EMAIL_HOST
        port = settings.EMAIL_PORT
        host_user = settings.EMAIL_HOST_USER
        from_email = settings.DEFAULT_FROM_EMAIL
        host_password = settings.EMAIL_HOST_PASSWORD
        use_tls = settings.EMAIL_USE_TLS
    return from_email, host, host_password, host_user, port, use_tls


def send_email_get_customer(email_to, track_customer_on_error):
    if track_customer_on_error:
        # select the customer based on user__email or customer__email2
        customer = models.Customer.objects.filter(user__email=email_to, subscribe_to_email=True).exclude(
            valid_email=False).only('id').order_by('?').first()
        if customer is None:
            customer = models.Customer.objects.filter(email2=email_to, subscribe_to_email=True).exclude(
                valid_email=False).only('id').order_by('?').first()
        send_mail = customer is not None
    else:
        send_mail = True
        customer = None
    return customer, send_mail


def send_email_to_who(is_email_send, board=False):
    if not is_email_send:
        if board:
            if apps.REPANIER_SETTINGS_TEST_MODE:
                return True, _("This email will be sent to %s.") % ', '.join(emails_of_testers())
            else:
                if settings.DEBUG:
                    return False, _("No email will be sent.")
                else:
                    return True, _("This email will be sent to the staff.")
        else:
            return False, _("No email will be sent.")
    else:
        if apps.REPANIER_SETTINGS_TEST_MODE:
            return True, _("This email will be sent to %s.") % ', '.join(emails_of_testers())
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
            sender_function = staff.safe_translation_getter(
                'long_name', any_language=True, default=EMPTY_STRING
            )
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
        unit = _("%s or kg :") % (apps.REPANIER_SETTINGS_CURRENCY_DISPLAY.decode('utf-8'),)
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


def payment_message(customer, permanence):
    from repanier.apps import REPANIER_SETTINGS_INVOICE

    customer_invoice = models.CustomerInvoice.objects.filter(
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

    if customer_invoice.customer_id != customer_invoice.customer_charged_id:
        customer_on_hold_movement = EMPTY_STRING
        customer_payment_needed = '<font color="#51a351">%s</font>' % (
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
                    customer_payment_needed = '<br/><font color="#51a351">%s.</font>' % (_('Your account balance is sufficient'))
                else:
                    customer_payment_needed = EMPTY_STRING
        else:
            customer_payment_needed = EMPTY_STRING

    return customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount


def display_selected_value(offer_item, quantity_ordered, is_open=True):
    option_dict = {
        'id': "#offer_item%d" % offer_item.id,
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
            option_dict["html"] = '<option value="0" selected>%s</option>' % label

        else:
            unit_price_amount = offer_item.customer_unit_price.amount + offer_item.unit_deposit.amount
            display = get_display(
                qty=quantity_ordered,
                order_average_weight=offer_item.order_average_weight,
                order_unit=offer_item.order_unit,
                unit_price_amount=unit_price_amount,
                for_order_select=True
            )
            option_dict["html"] = '<option value="%d" selected>%s</option>' % (quantity_ordered, display)
    else:
        option_dict["html"] = EMPTY_STRING
    return option_dict


def display_selected_box_value(offer_item, box_purchase):
    option_dict = {
        'id': "#box_offer_item%d" % offer_item.id,
    }
    if box_purchase.is_box_content:
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
                option_dict[
                    "html"] = '<select id="box_offer_item%d" name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ %s %s</option></select>' % \
                                      (offer_item.id, offer_item.id, qty_display, box_name)
            else:
                option_dict[
                    "html"] = '<select id="box_offer_item%d" name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ --- %s</option></select>' % \
                              (offer_item.id, offer_item.id, box_name)
        else:
            option_dict[
                "html"] = '<select id="box_offer_item%d" name="box_offer_item%d" disabled class="form-control"><option value="0" selected>☑ --- %s</option></select>' % \
                          (offer_item.id, offer_item.id, box_name)
    else:
        option_dict["html"] = EMPTY_STRING
    return option_dict


def create_or_update_one_purchase(
        customer_id, offer_item,
        permanence_date=None, status=PERMANENCE_OPENED, q_order=None,
        batch_job=False, is_box_content=False, comment=EMPTY_STRING):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
    # The batch_job flag is used because we need to forbid
    # customers to add purchases during the close_orders_async or other batch_job process
    # when the status is PERMANENCE_WAIT_FOR_SEND
    purchase = models.Purchase.objects.filter(
        customer_id=customer_id,
        offer_item_id=offer_item.id,
        is_box_content=is_box_content
    ).order_by('?').first()
    if batch_job:
        if purchase is None:
            permanence_date = permanence_date or models.Permanence.objects.filter(
                id=offer_item.permanence_id).only("permanence_date").order_by('?').first().permanence_date
            purchase = models.Purchase.objects.create(
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
        permanence_is_opened = models.CustomerInvoice.objects.filter(
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
                    non_box_purchase = models.Purchase.objects.filter(
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
                permanence = models.Permanence.objects.filter(id=offer_item.permanence_id) \
                    .only("permanence_date") \
                    .order_by('?').first()
                purchase = models.Purchase.objects.create(
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
    # from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
    to_json = []
    offer_item = models.OfferItem.objects.select_for_update(nowait=False) \
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
            purchase = models.Purchase.objects.filter(
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
                for content in models.BoxContent.objects.filter(
                    box=offer_item.product_id
                ).only(
                    "product_id", "content_quantity"
                ).order_by('?'):
                    box_offer_item = models.OfferItem.objects.filter(
                        product_id=content.product_id,
                        permanence_id=offer_item.permanence_id
                    ).order_by('?').select_related("producer").first()
                    if box_offer_item is not None:
                        # Select one purchase
                        purchase = models.Purchase.objects.filter(
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
            purchase = models.Purchase.objects.filter(
                customer_id=customer.id,
                offer_item_id=offer_item.id,
                is_box_content=False
            ).order_by('?').first()
            return purchase, False

        # if not batch_job:
        #     if purchase is None:
        #         if offer_item.is_box:
        #             sold_out = _("Sold out")
        #             option_dict = {
        #                 'id'  : "#offer_item%d" % offer_item.id,
        #                 'html': '<option value="0" selected>%s</option>' % sold_out
        #             }
        #         else:
        #             option_dict = display_selected_value(offer_item, DECIMAL_ZERO)
        #         to_json.append(option_dict)
        #     else:
        #         offer_item = models.OfferItem.objects.filter(id=offer_item_id).order_by('?').first()
        #         if offer_item is not None:
        #             option_dict = display_selected_value(offer_item, purchase.quantity_ordered)
        #             to_json.append(option_dict)
        #
        #     if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
        #         producer_invoice = models.ProducerInvoice.objects.filter(
        #             producer_id=offer_item.producer_id, permanence_id=offer_item.permanence_id
        #         ).only("total_price_with_tax").order_by('?').first()
        #         producer_invoice.get_order_json(to_json)
        #
        #     customer_invoice = models.CustomerInvoice.objects.filter(
        #         permanence_id=permanence_id,
        #         customer_id=customer.id
        #     ).order_by('?').first()
        #     permanence = models.Permanence.objects.filter(
        #         id=permanence_id
        #     ).only(
        #         "id", "with_delivery_point", "status"
        #     ).order_by('?').first()
        #     if customer_invoice is not None and permanence is not None:
        #         status_changed = customer_invoice.cancel_confirm_order()
        #         if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS and status_changed:
        #             html = render_to_string(
        #                 'repanier/communication_confirm_order.html')
        #             option_dict = {'id': "#communication", 'html': html}
        #             to_json.append(option_dict)
        #         customer_invoice.save()
        #         my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(),
        #                   to_json)
        #         if is_basket:
        #             basket_message = calc_basket_message(customer, permanence, PERMANENCE_OPENED)
        #         else:
        #             basket_message = EMPTY_STRING
        #         my_order_confirmation(
        #             permanence=permanence,
        #             customer_invoice=customer_invoice,
        #             is_basket=is_basket,
        #             basket_message=basket_message,
        #             to_json=to_json
        #         )
    # return json.dumps(to_json, cls=DjangoJSONEncoder)


def my_basket(is_order_confirm_send, order_amount, to_json):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS

    if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS and not is_order_confirm_send:
        if order_amount.amount <= DECIMAL_ZERO:
            msg_confirm = EMPTY_STRING
        else:
            msg_confirm = '<span class="glyphicon glyphicon-exclamation-sign"></span>&nbsp;<span class="glyphicon glyphicon-floppy-remove"></span>'
        msg_html = """
        {order_amount}&nbsp;&nbsp;&nbsp;
        {msg_confirm}
            """.format(
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
    msg_html = """
    {order_amount}&nbsp;&nbsp;&nbsp;
    {msg_confirm}
        """.format(
            order_amount=order_amount,
            msg_confirm=msg_confirm
        )
    option_dict = {'id': "#prepared_amount_visible_xs", 'html': msg_html}
    to_json.append(option_dict)


def my_order_confirmation(permanence, customer_invoice, is_basket=False,
                          basket_message=EMPTY_STRING, to_json=None):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS

    if permanence.with_delivery_point:
        if customer_invoice.delivery is not None:
            label = customer_invoice.delivery.get_delivery_customer_display()
            delivery_id = customer_invoice.delivery_id
        else:
            delivery_id = 0
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
        if customer_invoice.customer_id != customer_invoice.customer_charged_id:
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

        msg_delivery = '%s<b><i><select name="delivery" id="delivery" onmouseover="show_select_delivery_list_ajax(%d)" onchange="delivery_ajax(%d)" class="form-control"><option value="%d" selected>%s</option></select></i></b><br/>%s%s' % (
            _("Delivery point"),
            delivery_id,
            delivery_id,
            delivery_id,
            label,
            msg_transport,
            msg_price
        )
    else:
        msg_delivery = EMPTY_STRING
    msg_confirmation1 = EMPTY_STRING
    if not is_basket and not REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        # or customer_invoice.total_price_with_tax.amount != DECIMAL_ZERO:
        # If apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS is True,
        # then permanence.with_delivery_point is also True
        msg_html = EMPTY_STRING
    else:
        if customer_invoice.is_order_confirm_send:
            msg_confirmation2 = my_order_confirmation_email_send_to(customer_invoice.customer)
            msg_html = """
            <div class="row">
            <div class="panel panel-default">
            <div class="panel-heading">
            %s
            <p><font color="#51a351">%s</font><p/>
            %s
            </div>
            </div>
            </div>
             """ % (msg_delivery, msg_confirmation2, basket_message)
        else:
            msg_html = None
            btn_disabled = EMPTY_STRING if permanence.status == PERMANENCE_OPENED else "disabled"
            msg_confirmation2 = EMPTY_STRING
            if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                if is_basket:
                    if customer_invoice.status == PERMANENCE_OPENED:
                        if (permanence.with_delivery_point and customer_invoice.delivery is None) \
                                or customer_invoice.total_price_with_tax == DECIMAL_ZERO:
                            btn_disabled = "disabled"
                        msg_confirmation1 = '<font color="red">%s</font><br/>' % _("An unconfirmed order will be canceled.")
                        msg_confirmation2 = '<span class="glyphicon glyphicon-floppy-disk"></span>&nbsp;&nbsp;%s' % _("Confirm this order and receive an email containing its summary.")
                else:
                    href = urlresolvers.reverse(
                        'order_view', args=(permanence.id,)
                    )
                    if customer_invoice.status == PERMANENCE_OPENED:
                        msg_confirmation1 = '<font color="red">%s</font><br/>' % _("An unconfirmed order will be canceled.")
                        msg_confirmation2 = _("Verify my order content before validating it.")
                        msg_html = """
                            <div class="row">
                            <div class="panel panel-default">
                            <div class="panel-heading">
                            %s
                            %s
                            <a href="%s?is_basket=yes" class="btn btn-info" %s>%s</a>
                            </div>
                            </div>
                            </div>
                             """ % (msg_delivery, msg_confirmation1, href, btn_disabled, msg_confirmation2)
            else:
                if is_basket:
                    msg_confirmation2 = _("Receive an email containing this order summary.")
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
                if msg_confirmation2 == EMPTY_STRING:
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
                    %s
                    <button id="btn_confirm_order" class="btn btn-info" %s onclick="btn_receive_order_email();">%s</button>
                    <div class="clearfix"></div>
                    %s
                    </div>
                    </div>
                    </div>
                     """ % (msg_delivery, msg_confirmation1, btn_disabled, msg_confirmation2, basket_message)
    if to_json is not None:
        option_dict = {'id': "#span_btn_confirm_order", 'html': msg_html}
        to_json.append(option_dict)


def my_order_confirmation_email_send_to(customer):
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS

    if customer is not None and customer.email2:
        to_email = (customer.user.email, customer.email2)
    else:
        to_email = (customer.user.email,)
    sent_to = ", ".join(to_email) if to_email is not None else EMPTY_STRING
    if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
        msg_confirmation = _(
            "Your order is confirmed. An email containing this order summary has been sent to %s.") % sent_to
    else:
        msg_confirmation = _("An email containing this order summary has been sent to %s.") % sent_to
    return msg_confirmation


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
        offer_item.manage_production = producer.manage_production
        # Those offer_items not subjects to price modifications
        offer_item.is_resale_price_fixed = producer.is_resale_price_fixed or product.is_box or product.order_unit >= PRODUCT_ORDER_UNIT_DEPOSIT
        offer_item.price_list_multiplier = DECIMAL_ONE if offer_item.is_resale_price_fixed else producer.price_list_multiplier

        offer_item.may_order = False
        offer_item.manage_replenishment = False
        if offer_item.is_active:
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
    # Order the purchases such that lower quantity are before larger quantity
    models.Purchase.objects.filter(
        permanence_id=permanence_id
    ).update(
        quantity_for_preparation_sort_order=DECIMAL_ZERO
    )
    models.Purchase.objects.filter(
        permanence_id=permanence_id,
        offer_item__wrapped=False,
        offer_item__order_unit__in=[PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]
    ).update(
        quantity_for_preparation_sort_order=F('quantity_invoiced')
    )


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
            "department_for_customer",
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
            "department_for_customer",
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
            "department_for_customer",
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
    # The user can modify the price of a product PERMANENCE_SEND via "rule_of_3_per_product"
    for permanence in models.Permanence.objects.filter(
            status__in=[PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED]
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
        permanence.recalculate_order_amount(offer_item_qs=offer_item_qs)
    cache.clear()


@transaction.atomic()
def get_or_create_offer_item(permanence, product):
    offer_item_qs = models.OfferItem.objects.filter(
        permanence_id=permanence.id,
        product_id=product.id,
    ).order_by('?')
    if not offer_item_qs.exists():
        models.OfferItem.objects.create(
            permanence=permanence,
            product=product,
            producer=product.producer,
        )
        clean_offer_item(permanence, offer_item_qs)
    offer_item = offer_item_qs.first()
    return offer_item


def producer_web_services_activated(reference_site=None):
    web_services_activated = False
    web_service_version = None
    if reference_site:
        try:
            web_services = urlopen(
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
    from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
    if status == PERMANENCE_OPENED:
        if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
            if permanence.with_delivery_point:
                you_can_change = "<br/>%s" % (
                    _("You can increase the order quantities as long as the orders are open for your delivery point."),
                )
            else:
                you_can_change = "<br/>%s" % (
                    _("You can increase the order quantities as long as the orders are open."),
                )
        else:
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


def html_box_content(offer_item, user, previous_result=EMPTY_STRING):
    if offer_item.is_box:
        box_id = offer_item.product_id
        box_products = list(models.BoxContent.objects.filter(
            box_id=box_id
        ).values_list(
            'product_id', flat=True
        ).order_by('?'))
        if len(box_products) > 0:
            box_offer_items_qs = models.OfferItemWoReceiver.objects.filter(
                permanence_id=offer_item.permanence_id,
                product_id__in=box_products,
                translations__language_code=translation.get_language()
            ).order_by(
                "translations__order_sort_order"
            ).select_related("producer")
            box_products_description = []
            for box_offer_item in box_offer_items_qs:
                box_products_description.append(
                    '<li>%s * %s, %s <span class="btn_like%s" style="cursor: pointer;">%s</span></li>' % (
                        get_display(
                            qty=models.BoxContent.objects.filter(box_id=box_id, product_id=box_offer_item.product_id).only(
                                "content_quantity").order_by('?').first().content_quantity,
                            order_average_weight=box_offer_item.order_average_weight,
                            order_unit=box_offer_item.order_unit,
                            without_price_display=True),
                        box_offer_item.long_name,
                        box_offer_item.producer.short_profile_name,
                        box_offer_item.id,
                        box_offer_item.get_like(user)
                    )
                )
            return '%s%s<ul>%s</ul>' % (
                previous_result,
                "<hr/>" if previous_result else EMPTY_STRING,
                "".join(box_products_description)
            )
    return previous_result


def rule_of_3_reload_purchase(customer, offer_item, purchase_form, purchase_form_instance):
        purchase_form.repanier_is_valid = True
        # Reload purchase, because it has maybe be deleted
        purchase = models.Purchase.objects.filter(
            customer_id=customer.id,
            offer_item_id=offer_item.id,
            is_box_content=False
        ).order_by('?').first()
        if purchase is None:
            # Doesn't exists ? Create one
            purchase = models.Purchase.objects.create(
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
