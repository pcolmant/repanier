# -*- coding: utf-8 -*-
from repanier.const import *
from django.conf import settings
from django.core import urlresolvers
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist
from openpyxl.writer.excel import save_virtual_workbook
from repanier.models import Customer
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import Staff
from repanier.tools import *
from repanier.xslx import xslx_invoice


def send(permanence_id, current_site_name):
    permanence = Permanence.objects.get(id=permanence_id)
    sender_email = settings.DEFAULT_FROM_EMAIL
    sender_function = ""
    signature = ""
    cc_email_staff = []
    for staff in Staff.objects.filter(is_active=True, is_external_group=False):
        cc_email_staff.append(staff.user.email)
        if staff.is_reply_to_invoice_email:
            sender_email = staff.user.username + '@repanier.be'
            sender_function = staff.long_name
            r = staff.customer_responsible
            if r:
                if r.long_basket_name:
                    signature = r.long_basket_name + " - " + r.phone1
                else:
                    signature = r.short_basket_name + " - " + r.phone1
                if r.phone2:
                    signature += " / " + r.phone2

    # To the producer we speak of "payment".
    # This is the detail of the paiment to the producer, i.e. received products
    filename = (unicode(_("Payment")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('ascii',
                                                                                             errors='replace').replace(
        '?', '_')
    producer_set = Producer.objects.filter(
        permanence=permanence_id).order_by()
    for producer in producer_set:
        if producer.email.upper().find("NO-SPAM.WS") < 0:
            long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
            wb = xslx_invoice.export(permanence=permanence, producer=producer, wb=None, sheet_name=long_profile_name)
            if wb is not None:
                invoices_url = 'http://' + settings.ALLOWED_HOSTS[0] + urlresolvers.reverse(
                    'invoicep_uuid_view',
                    args=(0, producer.uuid )
                )
                html_content = unicode(_('Dear')) + " " + long_profile_name + ",<br/><br/>" + unicode(
                    _('In attachment, you will find the detail of our payment for the')) + \
                               ' <a href="' + invoices_url + '">' + unicode(permanence) + \
                               "</a>.<br/><br/>" + unicode(
                    _('In case of discordance, please advertise the staff team :')) + \
                               "<br/><br/>" + signature + \
                               "<br/>" + sender_function + \
                               "<br/>" + current_site_name
                email = EmailMultiAlternatives(
                    unicode(_('Payment')) + " - " + unicode(
                        permanence) + " - " + current_site_name + " - " + long_profile_name,
                    strip_tags(html_content),
                    sender_email,
                    [producer.email],
                    cc=[sender_email]
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

    # To the customer we speak of "invoice".
    # This is the detail of the invoice, i.e. sold products
    filename = (unicode(_("Invoice")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('ascii',
                                                                                             errors='replace').replace(
        '?', '_')
    try:
        invoice_description = permanence.invoice_description
    except TranslationDoesNotExist:
         invoice_description = ""
    customer_set = Customer.objects.filter(
        purchase__permanence=permanence_id, represent_this_buyinggroup=False).order_by().distinct()
    for customer in customer_set:
        long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
        wb = xslx_invoice.export(permanence=permanence, customer=customer, wb=None, sheet_name=long_basket_name)
        if wb is not None:
            html_content = unicode(_('Dear')) + " " + long_basket_name + ",<br/><br/>" + unicode(_('Your invoice of')) + \
                           " " + unicode(permanence) + " " + unicode(
                _("is now available in attachment")) + ".<br/>" + invoice_description + \
                           "<br/><br/>" + signature + \
                           "<br/>" + sender_function + \
                           "<br/>" + current_site_name
            email = EmailMultiAlternatives(
                unicode(_('Invoice')) + " - " + unicode(
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

    # Report to the staff
    wb = xslx_invoice.export(permanence=permanence, wb=None, sheet_name=current_site_name)
    if wb is not None:
        html_content = unicode(_('Dear staff member')) + ",<br/><br/>" + unicode(_('The invoices of')) + \
                       " " + unicode(permanence) + " " + unicode(
            _("are now available in attachment")) + ".<br/>" + invoice_description + \
                       "<br/><br/>" + signature + \
                       "<br/>" + sender_function + \
                       "<br/>" + current_site_name
        email = EmailMultiAlternatives(
            unicode(_('Invoice')) + " - " + unicode(permanence) + " - " + current_site_name,
            strip_tags(html_content),
            sender_email,
            cc_email_staff
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
