# -*- coding: utf-8
from __future__ import unicode_literals
from django.core.urlresolvers import reverse
from django.template import Template, Context as djangoContext
from django.utils.safestring import mark_safe
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
from django.conf import settings
# from repanier.const import *


def send(permanence_id):
    permanence = Permanence.objects.get(id=permanence_id)
    sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_invoice_email=True)

    if repanier_settings['SEND_INVOICE_MAIL_TO_PRODUCER']:
        # To the producer we speak of "payment".
        # This is the detail of the paiment to the producer, i.e. received products
        filename = ("%s - %s.xlsx" % (_("Payment"), permanence)).encode('ascii', errors='replace').replace('?', '_')
        producer_set = Producer.objects.filter(
            permanence=permanence_id).order_by()
        for producer in producer_set:
            if producer.email.upper().find("NO-SPAM.WS") < 0:
                long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
                wb = xslx_invoice.export(permanence=permanence, producer=producer, sheet_name=long_profile_name)
                if wb is not None:
                    invoice_producer_mail = repanier_settings['CONFIG'].invoice_producer_mail
                    template = Template(invoice_producer_mail)
                    context = djangoContext({
                        'long_profile_name' : long_profile_name,
                        'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('producer_invoice_uuid_view', args=(0, producer.uuid)), permanence)),
                        'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier_settings['GROUP_NAME']))
                    })
                    html_content = template.render(context)
                    email = EmailMultiAlternatives(
                        "%s - %s - %s - %s" % (_('Payment'), permanence, repanier_settings['GROUP_NAME'], long_profile_name),
                        strip_tags(html_content),
                        sender_email,
                        [producer.email],
                        bcc=[sender_email]
                    )
                    email.attach(filename,
                                 save_virtual_workbook(wb),
                                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    email.attach_alternative(html_content, "text/html")
                    send_email(email=email)

    if repanier_settings['SEND_INVOICE_MAIL_TO_CUSTOMER']:
        # To the customer we speak of "invoice".
        # This is the detail of the invoice, i.e. sold products
        filename = ("%s - %s.xlsx" % (_("Invoice"), permanence)).encode('ascii', errors='replace').replace('?', '_')
        try:
            invoice_description = permanence.invoice_description
        except TranslationDoesNotExist:
             invoice_description = ""
        customer_set = Customer.objects.filter(
            purchase__permanence=permanence_id, represent_this_buyinggroup=False).order_by().distinct()
        for customer in customer_set:
            long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
            wb = xslx_invoice.export(permanence=permanence, customer=customer, sheet_name=long_basket_name)
            if wb is not None:
                email_customer = [customer.user.email,]
                if customer.email2 is not None and len(customer.email2) > 0:
                    email_customer.append(customer.email2)
                invoice_customer_mail = repanier_settings['CONFIG'].invoice_customer_mail
                template = Template(invoice_customer_mail)
                context = djangoContext({
                    'long_basket_name' : long_basket_name,
                    'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('producer_invoice_uuid_view', args=(0, producer.uuid)), permanence)),
                    'invoice_description' : invoice_description,
                    'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier_settings['GROUP_NAME']))
                })
                html_content = template.render(context)
                email = EmailMultiAlternatives(
                    "%s - %s - %s - %s" % (_('Invoice'), permanence, repanier_settings['GROUP_NAME'], long_basket_name),
                    strip_tags(html_content),
                    sender_email,
                    email_customer,
                    bcc=[sender_email]
                )
                email.attach(filename,
                             save_virtual_workbook(wb),
                             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                email.attach_alternative(html_content, "text/html")
                send_email(email=email)

    # Report to the staff
    # wb = xslx_invoice.export(permanence=permanence, sheet_name=repanier_settings['GROUP_NAME'])
    # if wb is not None:
    #     html_content = '%s,<br/><br/>%s %s %s.<br/>%s<br/><br/>%s<br/>%s<br/>%s' \
    #         % (_('Dear staff member'),
    #            _('The invoices of'), permanence, _("are now available in attachment"),
    #            invoice_description,
    #            signature,
    #            sender_function,
    #            repanier_settings['GROUP_NAME']
    #     )
    #     email = EmailMultiAlternatives(
    #         "%s - %s - %s" % (_('Invoice'), permanence, repanier_settings['GROUP_NAME']),
    #         strip_tags(html_content),
    #         sender_email,
    #         cc_email_staff
    #     )
    #     email.attach(filename,
    #                  save_virtual_workbook(wb),
    #                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    #     email.attach_alternative(html_content, "text/html")
    #     send_email(email=email)