# -*- coding: utf-8
from __future__ import unicode_literals
from django.core.urlresolvers import reverse
from django.template import Template, Context as djangoContext
# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!
from django.utils.safestring import mark_safe
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist
import repanier.apps
from repanier.models import Permanence, Producer, OfferItem
from repanier.models import Customer
from repanier.tools import *


def send_pre_open_order(permanence_id):
    translation.activate(settings.LANGUAGE_CODE)
    offer_producer_mail = repanier.apps.REPANIER_SETTINGS_CONFIG.offer_producer_mail
    permanence = Permanence.objects.get(id=permanence_id)
    sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
    try:
        offer_description = permanence.offer_description
    except TranslationDoesNotExist:
        offer_description = ""
    template = Template(offer_producer_mail)
    producer_set = Producer.objects.filter(
        permanence=permanence_id, producer_pre_opening=True).order_by()
    for producer in producer_set:
        if producer.email.upper().find("NO-SPAM.WS") < 0:
            translation.activate(producer.language)
            long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
            context = djangoContext({
                'name': long_profile_name,
                'long_profile_name': long_profile_name,
                'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('pre_order_uuid_view', args=(producer.offer_uuid,)), _("offer"))),
                'offer_description': mark_safe(offer_description),
                'offer': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('pre_order_uuid_view', args=( producer.offer_uuid,)), _("offer"))),
                'signature': mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME))
            })
            html_content = template.render(context)
            email = EmailMultiAlternatives(
                "%s - %s - %s" % (_("Pre-opening of orders"), permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
                strip_tags(html_content),
                sender_email,
                [producer.email],
                cc=cc_email_staff
            )
            email.attach_alternative(html_content, "text/html")
            send_email(email=email)


def send_open_order(permanence_id):
    if repanier.apps.REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER:
        translation.activate(settings.LANGUAGE_CODE)
        permanence = Permanence.objects.get(id=permanence_id)
        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
        for customer in Customer.objects.filter(is_active=True, represent_this_buyinggroup=False,
                                                may_order=True).order_by():
            cc_email_staff.append(customer.user.email)
            if customer.email2 is not None and len(customer.email2) > 0:
                cc_email_staff.append(customer.email2)
        try:
            offer_description = permanence.offer_description
        except TranslationDoesNotExist:
            offer_description = ""
        offer_customer_mail = repanier.apps.REPANIER_SETTINGS_CONFIG.offer_customer_mail
        offer_producer = ', '.join([p.short_profile_name for p in permanence.producers.all()])
        offer_detail = ("<br>\r\n".join(
            strip_tags(o.cache_part_a.replace(' <br/>', ', ').replace('<br/>', ', ')) +
            strip_tags(o.cache_part_b.replace(' <br/>', ', ').replace('<br/>', ', '))
            for o in OfferItem.objects.filter(
                permanence_id=permanence_id, is_active=True,
                order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT, # Don't display technical products.
                translations__language_code=translation.get_language()
            ).order_by(
                "translations__order_sort_order"
            )
        )).replace(' ,', ',')
        template = Template(offer_customer_mail)
        context = djangoContext({
            'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
            'offer_description': mark_safe(offer_description),
            'offer_detail': mark_safe(offer_detail),
            'offer_producer': offer_producer,
            'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME))
        })
        html_content = template.render(context)
        # import sys
        # import codecs
        # sys.stdout = codecs.getwriter('utf8')(sys.stdout)
        # print("------------------------")
        # print "%s" % html_content
        # i = 1 / 0
        email = EmailMultiAlternatives(
            "%s - %s - %s" % (_("Opening of orders"), permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
            strip_tags(html_content),
            sender_email,
            bcc=cc_email_staff
        )
        email.attach_alternative(html_content, "text/html")
        send_email(email=email)
