# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext

# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from repanier.models import Permanence, Producer, OfferItem
from repanier.models import Customer, Configuration
from repanier.tools import *


def send_pre_open_order(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = Configuration.objects.get(id=DECIMAL_ONE)

        try:
            offer_producer_mail = config.offer_producer_mail
        except TranslationDoesNotExist:
            offer_producer_mail = EMPTY_STRING

        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
        try:
            offer_description = permanence.offer_description
        except TranslationDoesNotExist:
            offer_description = EMPTY_STRING
        offer_producer_mail_subject = "%s - %s - %s" % (_("Pre-opening of orders"), permanence, REPANIER_SETTINGS_GROUP_NAME)
        try:
            if config.offer_producer_mail_subject:
                offer_producer_mail_subject = config.offer_producer_mail_subject
        except TranslationDoesNotExist:
            pass
        template = Template(offer_producer_mail)
        producer_set = Producer.objects.filter(
            permanence=permanence_id, producer_pre_opening=True,
            language=language_code
        ).order_by('?')
        for producer in producer_set:
            long_profile_name = producer.long_profile_name \
                if producer.long_profile_name is not None else producer.short_profile_name
            context = TemplateContext({
                'name'             : long_profile_name,
                'long_profile_name': long_profile_name,
                'permanence_link'  : mark_safe('<a href="http://%s%s">%s</a>' % (
                    settings.ALLOWED_HOSTS[0],
                    reverse('pre_order_uuid_view', args=(producer.offer_uuid,)), _("offer"))
                                               ),
                'offer_description': mark_safe(offer_description),
                'offer_link'       : mark_safe(
                    '<a href="http://%s%s">%s</a>' % (
                        settings.ALLOWED_HOSTS[0],
                        reverse('pre_order_uuid_view', args=(producer.offer_uuid,)), _("offer"))
                ),
                'signature'        : mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, REPANIER_SETTINGS_GROUP_NAME)
                )
            })
            html_content = template.render(context)
            if producer.email2:
                to_email_producer = [producer.email, producer.email2]
            else:
                to_email_producer = [producer.email]
            email = EmailMultiAlternatives(
                offer_producer_mail_subject,
                strip_tags(html_content),
                from_email=sender_email,
                to=to_email_producer,
                cc=cc_email_staff
            )
            email.attach_alternative(html_content, "text/html")
            send_email(email=email)
            send_sms(
                sms_nr=producer.phone1,
                sms_msg="%s : %s - %s" % (REPANIER_SETTINGS_GROUP_NAME,
                                          permanence, _("Pre-opening of orders")))
    translation.activate(cur_language)


def send_open_order(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER, \
        REPANIER_SETTINGS_GROUP_NAME
    if REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER:
        cur_language = translation.get_language()
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            translation.activate(language_code)
            permanence = Permanence.objects.get(id=permanence_id)
            config = Configuration.objects.get(id=DECIMAL_ONE)
            sender_email, sender_function, signature, to_email_staff = get_signature(is_reply_to_order_email=True)
            to_email_customer = []
            for customer in Customer.objects.filter(
                    is_active=True,
                    represent_this_buyinggroup=False,
                    may_order=True,
                    language=language_code
            ).order_by('?'):
                to_email_customer.append(customer.user.email)
                if customer.email2 is not None and len(customer.email2.strip()) > 0:
                    to_email_customer.append(customer.email2)
            try:
                offer_description = permanence.offer_description
            except TranslationDoesNotExist:
                offer_description = EMPTY_STRING
            try:
                offer_customer_mail = config.offer_customer_mail
            except TranslationDoesNotExist:
                offer_customer_mail = EMPTY_STRING
            offer_customer_mail_subject = "%s - %s - %s" % (_("Opening of orders"), permanence, REPANIER_SETTINGS_GROUP_NAME)
            try:
                if config.offer_customer_mail_subject:
                    offer_customer_mail_subject = config.offer_customer_mail_subject
            except TranslationDoesNotExist:
                pass
            offer_producer = ', '.join([p.short_profile_name for p in permanence.producers.all()])
            qs = OfferItem.objects.filter(
                permanence_id=permanence_id, is_active=True,
                order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                translations__language_code=language_code
            ).order_by(
                "translations__order_sort_order"
            )
            offer_detail = '<ul>%s</ul>' % ("".join('<li>%s, %s, %s</li>' % (
                o.get_long_name(box_unicode=EMPTY_STRING),
                o.producer.short_profile_name,
                o.email_offer_price_with_vat,
            )
                                                    for o in qs
                                                    ),)
            template = Template(offer_customer_mail)
            context = TemplateContext({
                'permanence_link'  : mark_safe('<a href="http://%s%s">%s</a>' % (
                    settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                'offer_description': mark_safe(offer_description),
                'offer_detail'     : mark_safe(offer_detail),
                'offer_producer'   : offer_producer,
                'signature'        : mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
            })
            html_content = template.render(context)
            email = EmailMultiAlternatives(
                offer_customer_mail_subject,
                strip_tags(html_content),
                from_email=sender_email,
                bcc=list(set(to_email_staff) | set(to_email_customer))
            )
            email.attach_alternative(html_content, "text/html")
            send_email(email=email, track_customer_on_error=True)
        translation.activate(cur_language)
