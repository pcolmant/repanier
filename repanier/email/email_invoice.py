# -*- coding: utf-8

from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext
from django.utils.safestring import mark_safe

from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.purchase import Purchase
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
                    permanence_id=permanence.id,
                    language=language_code
            ).order_by('?'):
                long_profile_name = producer.long_profile_name \
                    if producer.long_profile_name is not None else producer.short_profile_name
                if Purchase.objects.filter(
                    permanence_id=permanence.id, producer_id=producer.id
                ).order_by('?').exists():
                    invoice_producer_mail = config.safe_translation_getter(
                        'invoice_producer_mail', any_language=True, default=EMPTY_STRING
                    )
                    invoice_producer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

                    template = Template(invoice_producer_mail)
                    context = TemplateContext({
                        'name'             : long_profile_name,
                        'long_profile_name': long_profile_name,
                        'permanence_link'  : mark_safe(
                            "<a href=\"https://{}{}\">{}</a>".format(settings.ALLOWED_HOSTS[0],
                                                              reverse('producer_invoice_uuid_view',
                                                                      args=(0, producer.uuid)),
                                                              permanence)),
                        'signature'        : mark_safe(
                            "{}<br>{}<br>{}".format(
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
                    email = RepanierEmail(
                        subject=invoice_producer_mail_subject,
                        html_content=html_content,
                        from_email=sender_email,
                        to=to_email_producer
                    )
                    email.send_email()

        if REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER:
            # To the customer we speak of "invoice".
            # This is the detail of the invoice, i.e. sold products
            invoice_description = permanence.safe_translation_getter(
                'invoice_description', any_language=True, default=EMPTY_STRING
            )
            for customer in Customer.objects.filter(
                customerinvoice__permanence_id=permanence.id,
                customerinvoice__customer_charged_id=F('customer_id'),
                represent_this_buyinggroup=False,
                language=language_code
            ).order_by('?'):
                long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
                if Purchase.objects.filter(
                    permanence_id=permanence.id,
                    customer_invoice__customer_charged_id=customer.id
                ).order_by('?').exists():
                    to_email_customer = [customer.user.email]
                    if customer.email2 is not None and len(customer.email2.strip()) > 0:
                        to_email_customer.append(customer.email2)

                    invoice_customer_mail = config.safe_translation_getter(
                        'invoice_customer_mail', any_language=True, default=EMPTY_STRING
                    )
                    invoice_customer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)
                    customer_last_balance, _, customer_payment_needed, customer_order_amount = payment_message(
                        customer, permanence)
                    template = Template(invoice_customer_mail)
                    context = TemplateContext({
                        'name'               : long_basket_name,
                        'long_basket_name'   : long_basket_name,
                        'basket_name'        : customer.short_basket_name,
                        'short_basket_name'  : customer.short_basket_name,
                        'permanence_link'    : mark_safe(
                            "<a href=\"https://{}{}\">{}</a>".format(settings.ALLOWED_HOSTS[0],
                                                              reverse('order_view', args=(permanence.id,)),
                                                              permanence)),
                        'last_balance_link'  : mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                            settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)),
                            customer_last_balance)),
                        'last_balance'       : mark_safe(customer_last_balance),
                        'order_amount'       : mark_safe(customer_order_amount),
                        'payment_needed'     : mark_safe(customer_payment_needed),
                        'invoice_description': mark_safe(invoice_description),
                        'signature'          : mark_safe(
                            "{}<br>{}<br>{}".format(
                                signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                    })
                    html_content = template.render(context)
                    email = RepanierEmail(
                        subject=invoice_customer_mail_subject,
                        html_content=html_content,
                        from_email=sender_email,
                        to=to_email_customer
                    )
                    email.send_email()
    translation.activate(cur_language)
