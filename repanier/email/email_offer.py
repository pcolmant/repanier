# -*- coding: utf-8 -*-
from django.conf import settings
from repanier.const import *
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist
from repanier.models import Permanence
from repanier.models import Staff
from repanier.tools import *


def send(permanence_id, current_site_name):
    translation.activate(settings.LANGUAGES[0][0])
    permanence = Permanence.objects.get(id=permanence_id)
    sender_email = settings.DEFAULT_FROM_EMAIL
    sender_function = ""
    signature = ""
    cc_email_staff = []
    for staff in Staff.objects.filter(is_active=True).order_by():
        cc_email_staff.append(staff.user.email)
        if staff.is_reply_to_order_email:
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

    for customer in Customer.objects.filter(is_active=True, represent_this_buyinggroup=False,
                                            may_order=True).order_by():
        cc_email_staff.append(customer.user.email)
    try:
        offer_description = permanence.offer_description
    except TranslationDoesNotExist:
         offer_description = ""
    html_content = unicode(_('Hello')) + ",<br/><br/>" + unicode(_('The order of')) + \
                   " " + unicode(permanence) + " " + unicode(
        _("are now opened.")) + "<br/>" + offer_description  + \
                   "<br/><br/>" + signature + \
                   "<br/>" + sender_function + \
                   "<br/>" + current_site_name
    email = EmailMultiAlternatives(
        unicode(_("Opening of orders")) + " - " + unicode(permanence) + " - " + current_site_name,
        strip_tags(html_content),
        sender_email,  # [sender_email],
        bcc=cc_email_staff
    )
    email.attach_alternative(html_content, "text/html")
    if not settings.DEBUG:
        email.send()
    else:
        email.to = [v for k, v in settings.ADMINS]
        email.cc = []
        email.bcc = []
        email.send()

