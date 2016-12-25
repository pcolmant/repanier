# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.models import Purchase
from repanier.models import Configuration
from repanier.models import Customer
from repanier.models import Permanence
from repanier.models import Producer
from repanier.tools import *


def send_invoice(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER, \
        REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = Configuration.objects.get(id=DECIMAL_ONE)
        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_invoice_email=True)
        if REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER:
            # To the producer we speak of "payment".
            # This is the detail of the payment to the producer, i.e. received products
            for producer in Producer.objects.filter(
                    permanence=permanence.id,
                    language=language_code
            ).order_by('?'):
                long_profile_name = producer.long_profile_name \
                    if producer.long_profile_name is not None else producer.short_profile_name
                if Purchase.objects.filter(
                    permanence_id=permanence.id, producer_id=producer.id
                ).order_by('?').exists():
                    try:
                        invoice_producer_mail = config.invoice_producer_mail
                    except TranslationDoesNotExist:
                        invoice_producer_mail = EMPTY_STRING
                    # invoice_producer_mail_subject = "%s - %s - %s - %s" % (
                    #         _('Payment'), permanence, REPANIER_SETTINGS_GROUP_NAME, long_profile_name)
                    invoice_producer_mail_subject = "%s - %s" % (REPANIER_SETTINGS_GROUP_NAME, permanence)

                    template = Template(invoice_producer_mail)
                    context = TemplateContext({
                        'name'             : long_profile_name,
                        'long_profile_name': long_profile_name,
                        'permanence_link'  : mark_safe(
                            '<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0],
                                                              reverse('producer_invoice_uuid_view',
                                                                      args=(0, producer.uuid)),
                                                              permanence)),
                        'signature'        : mark_safe(
                            '%s<br/>%s<br/>%s' % (
                                signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                    })
                    html_content = template.render(context)
                    to_email_producer = []
                    if producer.email:
                        to_email_producer.append(producer.email)
                    if producer.email2:
                        to_email_producer.append(producer.email2)
                    if producer.email3:
                        to_email_producer.append(producer.email3)
                    email = EmailMultiAlternatives(
                        invoice_producer_mail_subject,
                        strip_tags(html_content),
                        from_email=sender_email,
                        to=to_email_producer
                    )
                    email.attach_alternative(html_content, "text/html")
                    send_email(email=email)

        if REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER:
            # To the customer we speak of "invoice".
            # This is the detail of the invoice, i.e. sold products
            try:
                invoice_description = permanence.invoice_description
            except TranslationDoesNotExist:
                invoice_description = EMPTY_STRING

            for customer in Customer.objects.filter(
                customerinvoice__permanence=permanence.id,
                customerinvoice__customer_who_pays_id=F('customer_id'),
                represent_this_buyinggroup=False,
                language=language_code
            ).order_by('?'):
                long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
                if Purchase.objects.filter(
                    permanence_id=permanence.id, customer_who_pays_id=customer.id
                ).order_by('?').exists():
                    to_email_customer = [customer.user.email]
                    if customer.email2 is not None and len(customer.email2.strip()) > 0:
                        to_email_customer.append(customer.email2)
                    try:
                        invoice_customer_mail = config.invoice_customer_mail
                    except TranslationDoesNotExist:
                        invoice_customer_mail = EMPTY_STRING
                    # invoice_customer_mail_subject = "%s - %s - %s - %s" % (_('Invoice'), permanence, REPANIER_SETTINGS_GROUP_NAME,
                    #                            long_basket_name)
                    invoice_customer_mail_subject = "%s - %s" % (REPANIER_SETTINGS_GROUP_NAME, permanence)
                    customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
                        customer, permanence)
                    template = Template(invoice_customer_mail)
                    context = TemplateContext({
                        'name'               : long_basket_name,
                        'long_basket_name'   : long_basket_name,
                        'basket_name'        : customer.short_basket_name,
                        'short_basket_name'  : customer.short_basket_name,
                        'permanence_link'    : mark_safe(
                            '<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0],
                                                              reverse('order_view', args=(permanence.id,)),
                                                              permanence)),
                        'last_balance_link'  : mark_safe('<a href="http://%s%s">%s</a>' % (
                            settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)),
                            customer_last_balance)),
                        'last_balance'       : mark_safe(customer_last_balance),
                        'order_amount'       : mark_safe(customer_order_amount),
                        'payment_needed'     : mark_safe(customer_payment_needed),
                        'invoice_description': mark_safe(invoice_description),
                        'signature'          : mark_safe(
                            '%s<br/>%s<br/>%s' % (
                                signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                    })
                    html_content = template.render(context)
                    email = EmailMultiAlternatives(
                        invoice_customer_mail_subject,
                        strip_tags(html_content),
                        from_email=sender_email,
                        to=to_email_customer
                    )
                    email.attach_alternative(html_content, "text/html")
                    send_email(email=email)
    translation.activate(cur_language)
