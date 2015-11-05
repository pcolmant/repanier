# -*- coding: utf-8
from __future__ import unicode_literals
import repanier.apps
from repanier.const import *
from django.conf import settings
from django.core.mail import send_mail, EmailMessage


# from django.contrib.sites.models import get_current_site


def send(permanence):
    try:
        send_mail("Alert - %s - %s" % (permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME), permanence.get_status_display(),
                  "%s@repanier.be" % (settings.ALLOWED_HOSTS[0]), [v for k, v in settings.ADMINS])
    except:
        pass


def send_error(error_str):
    try:
        send_mail("Alert - %s" % repanier.apps.REPANIER_SETTINGS_GROUP_NAME, error_str,
                  "%s@repanier.be" % (settings.ALLOWED_HOSTS[0]), [v for k, v in settings.ADMINS])
    except:
        pass


def send_sms(sms_nr=None, sms_msg=None):
    try:
        if sms_nr is not None and sms_msg is not None:
            valid_nr = "0"
            i = 0
            while i < len(sms_nr) and not sms_nr[i] == '4':
                i += 1
            while i < len(sms_nr):
                if '0' <= sms_nr[i] <= '9':
                    valid_nr += sms_nr[i]
                i += 1
            if len(valid_nr) == 10:
                # Send SMS with free gateway : Sms Gateway - Android.
                email = EmailMessage(valid_nr, sms_msg, "no-reply@repanier.be",
                          [settings.ANDROID_SMS_GATEWAY_MAIL,])
                email.send()
    except:
        pass



# subject, from_email, to = 'Order Confirmation', 'admin@yourdomain.com', 'someone@somewhere.com'

# html_content = render_to_string('the_template.html', {'varname':'value'}) # ...
# <div style="display: none"><a onclick="javascript:pageTracker._trackPageview('/outgoing/wikiexback.com/');" href="http://wikiexback.com/" title="how to get your ex back">how to get your ex back</a></div>

# text_content = strip_tags(html_content) # this strips the html, so people will have the text as well.

# # create the email, and attach the HTML version as well.
# msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
# msg.attach_alternative(html_content, "text/html")
# msg.send()

