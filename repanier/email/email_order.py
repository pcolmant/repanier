# -*- coding: utf-8 -*-
from django.conf import settings
from repanier.const import *
from django.utils import translation
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from openpyxl.writer.excel import save_virtual_workbook
from repanier.models import Customer
from repanier.models import Permanence
from repanier.models import PermanenceBoard
from repanier.models import Producer
from repanier.models import Staff
from repanier.tools import *
from repanier.xslx import xslx_order
from repanier.settings import *

def send(permanence_id, current_site_name):
    translation.activate(settings.LANGUAGE_CODE)
    permanence = Permanence.objects.get(id=permanence_id)
    filename = (unicode(_("Order")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('ascii',
                                                                                           errors='replace').replace(
        '?', '_')
    sender_email = settings.DEFAULT_FROM_EMAIL
    sender_function = ""
    signature = ""
    cc_email_staff = []

    for staff in Staff.objects.filter(is_active=True):
        cc_email_staff.append(staff.user.email)
        if staff.is_reply_to_order_email:
            # sender_email = staff.user.username + '@repanier.be'
            sender_email = staff.user.email
            sender_function = staff.long_name
            r = staff.customer_responsible
            if r:
                if r.long_basket_name:
                    signature = r.long_basket_name + " - " + r.phone1
                else:
                    signature = r.short_basket_name + " - " + r.phone1
                if r.phone2:
                    signature += " / " + r.phone2

    board_composition = ""
    board_message = ""
    first_board = True
    for permanenceboard in PermanenceBoard.objects.filter(
            permanence=permanence_id).order_by(
            "permanence_role__tree_id",
            "permanence_role__lft"
    ):
        r_part = ''
        m_part = ''
        r = permanenceboard.permanence_role
        if r:
            r_part = r.short_name + ', '
            m_part = '</br>' + r.description
        c_part = ''
        c = permanenceboard.customer
        if c:
            if c.phone2:
                c_part = c.long_basket_name + ', <b>' + c.phone1 + '</b>, <b>' + c.phone2 + '</b>'
            else:
                c_part = c.long_basket_name + ', <b>' + c.phone1 + '</b>'
            if first_board:
                board_composition += '<br/>'
            board_composition += c_part + '<br/>'
        board_message += r_part + c_part + '<br/>' + m_part
        first_board = False
    # Order adressed to our producers,
    producer_set = Producer.objects.filter(
        permanence=permanence_id).order_by()
    for producer in producer_set:
        if producer.email.upper().find("NO-SPAM.WS") < 0:
            translation.activate(producer.language)
            wb = xslx_order.export_producer(permanence=permanence, producer=producer, wb=None)
            if wb is not None:
                long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
                html_content = unicode(_('Dear')) + " " + long_profile_name + ",<br/><br/>" + unicode(
                    _('In attachment, you will find the detail of our order for the')) + \
                               " " + unicode(permanence) + ".<br/><br/>" + \
                    unicode(_('WARNING: The command is present in duplicate in two separate tabs.<br/>')) + \
                    unicode(_('Once in the order of the products to be prepared and second once in the order of families to prepare.<br/>')) + \
                    unicode(_('Use only one of both.<br/>')) + \
                    "<br/>" + \
                    unicode(_('In case of impediment for delivering the order, please advertise me :')) + \
                               "<br/><br/>" + signature + \
                               "<br/>" + sender_function + \
                               "<br/>" + current_site_name
                email = EmailMultiAlternatives(
                    unicode(_("Order")) + " - " + unicode(
                        permanence) + " - " + current_site_name + " - " + long_profile_name,
                    strip_tags(html_content),
                    sender_email,
                    [producer.email],
                    cc=cc_email_staff
                )
                email.attach(filename,
                             save_virtual_workbook(wb),
                             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                email.attach_alternative(html_content, "text/html")
                if not settings.DEBUG:
                    email.send()
                else:
                    email.to = [v for k, v in settings.ADMINS]
                    email.cc = []
                    email.bcc = []
                    email.send()

    customer_set = Customer.objects.filter(
        purchase__permanence=permanence_id, represent_this_buyinggroup=False).order_by().distinct()
    for customer in customer_set:
        order_amount, wb = xslx_order.export_customer(permanence=permanence, customer=customer, wb=None)
        if wb is not None:
            translation.activate(customer.language)
            if (order_amount - customer.balance) > 0:
                please_pay = unicode(_('Please pay ')) + number_format(order_amount - customer.balance, 2) + ' &euro; ' + \
                    unicode(_('to the bank account number ')) + REPANIER_BANK_ACCOUNT + \
                    unicode(_(' with communication ')) + customer.short_basket_name + ", " + unicode(permanence)
            else:
                please_pay = unicode(_('Your account balance is sufficient.'))
            long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
            html_content = unicode(_('Dear')) + " " + long_basket_name + ",<br/><br/>" + unicode(
                _('In attachment, you will find the detail of your order for the')) + \
                " " + unicode(permanence) + ".<br/><br/>" + \
                unicode(_('The balance of your account as of ')) + customer.date_balance.strftime('%d-%m-%Y') + \
                unicode(_(' is ')) + number_format(customer.balance, 2) + ' &euro;.<br/>' + \
                unicode(_('The amount of your order is ')) + number_format(order_amount, 2) + ' &euro;.<br/>' + \
                please_pay + \
                ".<br/><br/>" + unicode(
                _('In case of impediment for keeping your basket, please advertise me :')) + \
               "<br/><br/>" + signature + \
               "<br/>" + sender_function + \
               "<br/>" + current_site_name
            email = EmailMultiAlternatives(
                unicode(_("Order")) + " - " + unicode(
                    permanence) + " - " + current_site_name + " - " + long_basket_name,
                strip_tags(html_content),
                sender_email,
                [customer.user.email]
            )
            email.attach(filename,
                         save_virtual_workbook(wb),
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            email.attach_alternative(html_content, "text/html")
            if not settings.DEBUG:
                email.send()
            else:
                email.to = [v for k, v in settings.ADMINS]
                email.cc = []
                email.bcc = []
                email.send()

    wb = xslx_order.export(permanence=permanence, wb=None)
    if wb is not None:
        translation.activate(settings.LANGUAGE_CODE)
        to_email_board = []
        for permanenceboard in PermanenceBoard.objects.filter(
                permanence=permanence_id).order_by():
            if permanenceboard.customer:
                to_email_board.append(permanenceboard.customer.user.email)
        html_content = unicode(_('Dear preparation team member')) + ",<br/><br/>" + \
            unicode(_('In attachment, you will find the preparation lists for the')) + \
            " " + unicode(permanence) + ".<br/><br/>" + \
            unicode(_('In case of impediment, please advertise me :')) + \
           "<br/><br/>" + board_message + \
           "<br/><br/>" + signature + \
           "<br/>" + sender_function + \
           "<br/>" + current_site_name

        # unicode(_('Or, at default a member of the staff team :')) + \
        # "<br/>" + staff_composition + \

        email = EmailMultiAlternatives(
            unicode(_('Permanence preparation list')) + " - " + unicode(permanence) + " - " + current_site_name,
            strip_tags(html_content),
            sender_email,
            to_email_board,
            cc=cc_email_staff
        )
        email.attach(filename,
                     save_virtual_workbook(wb),
                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        email.attach_alternative(html_content, "text/html")
        if not settings.DEBUG:
            email.send()
        else:
            email.to = [v for k, v in settings.ADMINS]
            email.cc = []
            email.bcc = []
            email.send()
