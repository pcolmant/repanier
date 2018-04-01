# -*- coding: utf-8

from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext

from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.purchase import Purchase
from repanier.models.staff import Staff
from repanier.tools import *


def send_invoice(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER, \
        REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER, \
        REPANIER_SETTINGS_CONFIG
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = REPANIER_SETTINGS_CONFIG

        invoice_responsible = Staff.get_or_create_invoice_responsible()

        if REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER:
            # To the producer we speak of "payment".
            # This is the detail of the payment to the producer, i.e. received products
            for producer in Producer.objects.filter(
                    permanence_id=permanence.id,
                    language=language_code
            ).order_by('?'):
                to_email = []
                if producer.email:
                    to_email.append(producer.email)
                if producer.email2:
                    to_email.append(producer.email2)
                if producer.email3:
                    to_email.append(producer.email3)
                if to_email:
                    to_email = list(
                        set(to_email) | set(invoice_responsible.get_to_email) | set(Staff.get_to_invoice_copy()))
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
                            'name': long_profile_name,
                            'long_profile_name': long_profile_name,
                            'permanence_link': mark_safe(
                                "<a href=\"https://{}{}\">{}</a>".format(settings.ALLOWED_HOSTS[0],
                                                                         reverse('producer_invoice_uuid_view',
                                                                                 args=(0, producer.uuid)),
                                                                         permanence)),
                            'signature': invoice_responsible.get_html_signature
                        })
                        html_body = template.render(context)
                        email = RepanierEmail(
                            subject=invoice_producer_mail_subject,
                            html_body=html_body,
                            from_email=invoice_responsible.get_from_email,
                            to=to_email,
                            reply_to=invoice_responsible.get_reply_to
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
                    to_email = [customer.user.email]
                    if customer.email2:
                        to_email.append(customer.email2)
                    to_email = list(
                        set(to_email) | set(invoice_responsible.get_to_email) | set(Staff.get_to_invoice_copy()))

                    invoice_customer_mail = config.safe_translation_getter(
                        'invoice_customer_mail', any_language=True, default=EMPTY_STRING
                    )
                    invoice_customer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)
                    customer_last_balance, _, customer_payment_needed, customer_order_amount = payment_message(
                        customer, permanence)
                    template = Template(invoice_customer_mail)
                    context = TemplateContext({
                        'name': long_basket_name,
                        'long_basket_name': long_basket_name,
                        'basket_name': customer.short_basket_name,
                        'short_basket_name': customer.short_basket_name,
                        'permanence_link': mark_safe(
                            "<a href=\"https://{}{}\">{}</a>".format(settings.ALLOWED_HOSTS[0],
                                                                     reverse('order_view', args=(permanence.id,)),
                                                                     permanence)),
                        'last_balance_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                            settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)),
                            customer_last_balance)),
                        'last_balance': mark_safe(customer_last_balance),
                        'order_amount': mark_safe(customer_order_amount),
                        'payment_needed': mark_safe(customer_payment_needed),
                        'invoice_description': mark_safe(invoice_description),
                        'signature': invoice_responsible.get_html_signature
                    })
                    html_body = template.render(context)
                    email = RepanierEmail(
                        subject=invoice_customer_mail_subject,
                        html_body=html_body,
                        from_email=invoice_responsible.get_from_email,
                        to=to_email,
                        show_customer_may_unsubscribe=True
                    )
                    email.send_email()
    translation.activate(cur_language)
