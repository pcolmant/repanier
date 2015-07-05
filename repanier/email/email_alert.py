# -*- coding: utf-8
from __future__ import unicode_literals
from repanier.apps import RepanierSettings
from repanier.const import *
from django.conf import settings
from django.core.mail import send_mail
# from django.contrib.sites.models import get_current_site


def send(permanence):
    try:
        send_mail("Alert - %s - %s" % (permanence, RepanierSettings.group_name), permanence.get_status_display(),
                  "%s@repanier.be" % (settings.ALLOWED_HOSTS[0]), [v for k, v in settings.ADMINS])
    except:
        pass


def send_error(error_str):
    try:
        send_mail("Alert - %s" % RepanierSettings.group_name, error_str,
                  "%s@repanier.be" % (settings.ALLOWED_HOSTS[0]), [v for k, v in settings.ADMINS])
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

