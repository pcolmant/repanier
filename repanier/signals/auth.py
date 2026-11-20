"""The admin sign in notification.

Every time an account without a customer profile - in practice a
superuser - opens a session, whatever the door (the sign in form of
the site, /admin/, the private username door), a short mail reaches
the ADMIN_EMAIL of the ini: the moment, the visible address of the
machine, the account. A connection of the admin is a rare and
sensitive event: a mail received at an odd hour is an alarm the
admin can act on - a sign in at three in the morning he did not
make means somebody else holds his password.

The notification never blocks the sign in: a mail problem is
logged for the operator, the session opens anyway.
"""
import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from repanier.const import EMPTY_STRING

logger = logging.getLogger(__name__)


def notify_admin_sign_in(sender, request, user, **kwargs):
    if not user.is_superuser or settings.DEBUG:
        return
    try:
        from repanier.const import EmailNature
        from repanier.email.email import RepanierEmail

        # Behind the nginx proxy the visible address of the client
        # arrives in X-Forwarded-For.
        client_address = request.META.get("HTTP_X_FORWARDED_FOR", None) or (
            request.META.get("REMOTE_ADDR", EMPTY_STRING)
        )
        html_body = format_html(
            "<p>{} : {}</p>"
            "<p>{} : {}</p>"
            "<p>{} : {}</p>",
            _("Context"),
            settings.REPANIER_SETTINGS_GROUP_NAME,
            _("Ref"),
            f"{user.username} ({client_address})",
            _("Date"),
            timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),
        )
        email = RepanierEmail(
            email_nature=EmailNature.ADMIN,
            subject="{} - {}".format(
                settings.REPANIER_SETTINGS_GROUP_NAME,
                _("Session notice"),
            ),
            html_body=html_body,
            to=[settings.ADMIN_EMAIL],
            show_customer_may_unsubscribe=False,
        )
        email.send_email()
    except Exception as error:
        logger.error("notify_admin_sign_in error : {}".format(error))


user_logged_in.connect(notify_admin_sign_in, dispatch_uid="repanier_notify_admin_sign_in")
