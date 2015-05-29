# -*- coding: utf-8
from __future__ import unicode_literals
# from django.conf import settings
# from django.contrib.sites.models import Site
import uuid
from django.core.urlresolvers import reverse
from django.template import Template, Context as djangoContext
# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!
from django.utils.safestring import mark_safe
# from repanier.const import *
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
# from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist
from repanier.models import Permanence, Producer
from repanier.models import Staff
from repanier.models import Customer
from repanier.tools import *


def send_pre_opening(permanence_id):
    if repanier_settings['SEND_OPENING_MAIL_TO_CUSTOMER']:
        translation.activate(settings.LANGUAGE_CODE)
        offer_producer_mail = repanier_settings['CONFIG'].offer_producer_mail
        permanence = Permanence.objects.get(id=permanence_id)
        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
        try:
            offer_description = permanence.offer_description
        except TranslationDoesNotExist:
            offer_description = ""
        template = Template(offer_producer_mail)
        producer_set = Producer.objects.filter(
            permanence=permanence_id).order_by()
        for producer in producer_set:
            if producer.email.upper().find("NO-SPAM.WS") < 0:
                producer.offer_uuid = uuid.uuid4()
                producer.save(update_fields=['offer_uuid',])
                translation.activate(producer.language)
                long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
                context = djangoContext({
                    'long_profile_name': long_profile_name,
                    'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('pre_order_uuid_view', args=(0, producer.offer_uuid)), _("offer"))),
                    'offer_description': mark_safe(offer_description),
                    'offer': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('pre_order_uuid_view', args=(0, producer.offer_uuid)), _("offer"))),
                    'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier_settings['GROUP_NAME']))
                })
                html_content = template.render(context)
                email = EmailMultiAlternatives(
                    "%s - %s - %s" % (_("Pre-opening of orders"), permanence, repanier_settings['GROUP_NAME']),
                    strip_tags(html_content),
                    sender_email,
                    [producer.email],
                    cc=cc_email_staff
                )
                email.attach_alternative(html_content, "text/html")
                send_email(email=email)


def send(permanence_id):
    if repanier_settings['SEND_OPENING_MAIL_TO_CUSTOMER']:
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
        offer_customer_mail = repanier_settings['CONFIG'].offer_customer_mail
        template = Template(offer_customer_mail)
        context = djangoContext({
            'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
            'offer_description': mark_safe(offer_description),
            'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier_settings['GROUP_NAME']))
        })
        html_content = template.render(context)
        # import sys
        # import codecs
        # sys.stdout = codecs.getwriter('utf8')(sys.stdout)
        # print("------------------------")
        # print "%s" % html_content
        # i = 1 / 0
        email = EmailMultiAlternatives(
            "%s - %s - %s" % (_("Opening of orders"), permanence, repanier_settings['GROUP_NAME']),
            strip_tags(html_content),
            sender_email,
            bcc=cc_email_staff
        )
        email.attach_alternative(html_content, "text/html")
        send_email(email=email)
