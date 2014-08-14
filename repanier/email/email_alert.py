# -*- coding: utf-8 -*-
from repanier.const import *
from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import ugettext_lazy as _


def send(permanence, current_site_name):
    try:
        send_mail('Alert - ' + " - " + unicode(permanence) + " - " + current_site_name, permanence.get_status_display(),
                  settings.ALLOWED_HOSTS[0] + '@repanier.be', [v for k, v in settings.ADMINS])
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

