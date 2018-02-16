# -*- coding: utf-8

from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext
# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!
from django.utils.translation import ugettext_lazy as _

from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.staff import Staff
from repanier.tools import *


def send_pre_open_order(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_CONFIG
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = REPANIER_SETTINGS_CONFIG

        offer_producer_mail = config.safe_translation_getter(
            'offer_producer_mail', any_language=True, default=EMPTY_STRING
        )

        staff = Staff.get_or_create_order_responsible()

        offer_description = permanence.safe_translation_getter(
            'offer_description', any_language=True, default=EMPTY_STRING
        )
        offer_producer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

        template = Template(offer_producer_mail)
        producer_set = Producer.objects.filter(
            permanence=permanence_id, producer_pre_opening=True,
            language=language_code
        ).order_by('?')
        for producer in producer_set:
            long_profile_name = producer.long_profile_name \
                if producer.long_profile_name is not None else producer.short_profile_name
            context = TemplateContext({
                'name': long_profile_name,
                'long_profile_name': long_profile_name,
                'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                    settings.ALLOWED_HOSTS[0],
                    reverse('pre_order_uuid_view', args=(producer.offer_uuid,)), _("Offers"))
                ),
                'offer_description': mark_safe(offer_description),
                'offer_link': mark_safe(
                    "<a href=\"https://{}{}\">{}</a>".format(
                        settings.ALLOWED_HOSTS[0],
                        reverse('pre_order_uuid_view', args=(producer.offer_uuid,)), _("Offers"))
                ),
                'signature': staff.get_html_signature
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
                subject=offer_producer_mail_subject,
                html_content=html_content,
                from_email=staff.get_from_email,
                reply_to=staff.get_reply_to_email,
                to=to_email_producer,
                cc=staff.get_to_email
            )
            email.send_email()
            send_sms(
                sms_nr=producer.phone1,
                sms_msg="{} : {} - {}".format(REPANIER_SETTINGS_GROUP_NAME,
                                              permanence, _("Pre-opening of orders")))
    translation.activate(cur_language)


def send_open_order(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_CONFIG
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = REPANIER_SETTINGS_CONFIG

        staff = Staff.get_or_create_order_responsible()

        to_email_customer = []
        for customer in Customer.objects.filter(
                represent_this_buyinggroup=False,
                may_order=True,
                language=language_code
        ).order_by('?'):
            to_email_customer.append(customer.user.email)
            if customer.email2 is not None and len(customer.email2.strip()) > 0:
                to_email_customer.append(customer.email2)
        offer_description = permanence.safe_translation_getter(
            'offer_description', any_language=True, default=EMPTY_STRING
        )
        offer_customer_mail = config.safe_translation_getter(
            'offer_customer_mail', any_language=True, default=EMPTY_STRING
        )
        offer_customer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)
        offer_producer = ', '.join([p.short_profile_name for p in permanence.producers.all()])
        qs = OfferItemWoReceiver.objects.filter(
            permanence_id=permanence_id, is_active=True,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
            translations__language_code=language_code
        ).order_by(
            "translations__order_sort_order"
        )
        offer_detail = "<ul>{}</ul>".format("".join("<li>{}, {}, {}</li>".format(
            o.get_long_name(),
            o.producer.short_profile_name,
            o.email_offer_price_with_vat,
        )
                                                    for o in qs
                                                    ), )
        template = Template(offer_customer_mail)
        context = TemplateContext({
            'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
            'offer_description': mark_safe(offer_description),
            'offer_detail': mark_safe(offer_detail),
            'offer_recent_detail': mark_safe(permanence.get_new_products),
            'offer_producer': offer_producer,
            'signature': staff.get_html_signature
        })
        html_content = template.render(context)
        email = RepanierEmail(
            subject=offer_customer_mail_subject,
            html_content=html_content,
            from_email=staff.get_from_email,
            reply_to=staff.get_reply_to_email,
            bcc=list(set(staff.get_to_email) | set(to_email_customer)),
            show_customer_may_unsubscribe=True
        )
        email.send_email()
    translation.activate(cur_language)
