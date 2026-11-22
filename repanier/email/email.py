import logging
import time
from email.mime.image import MIMEImage
from random import random
from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPDataError,
    SMTPHeloError,
    SMTPNotSupportedError,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.utils import translation
from django.utils import timezone
from django.utils.html import format_html, strip_tags
from django.utils.translation import gettext_lazy as _

from repanier.const import EMPTY_STRING, EmailDeliveryStatus, EmailNature
from repanier.models.emaillog import EmailLog

logger = logging.getLogger(__name__)


def in_customer_language(function):
    """Speak the language of the customer during the whole build and
    send of his mail: the subject, the body and every lazy label of
    the attachments resolve against Customer.language, whatever the
    language of the site or of the sending process.

    @in_customer_language
    def email_one_customer(customer, ...):
        ...

    The first argument of the decorated function must be the
    customer. Restore the previous language on the way out, whatever
    happens inside."""
    from functools import wraps

    @wraps(function)
    def wrapper(customer, *args, **kwargs):
        with translation.override(customer.language):
            return function(customer, *args, **kwargs)

    return wrapper


class RepanierEmail(EmailMultiAlternatives):
    def __init__(self, *args, **kwargs):
        self.html_body = kwargs.pop("html_body", None)
        self.show_customer_may_unsubscribe = kwargs.pop(
            "show_customer_may_unsubscribe", True
        )
        self.send_even_if_unsubscribed = kwargs.pop("send_even_if_unsubscribed", False)
        self.email_nature = kwargs.pop("email_nature", EmailNature.OTHER)
        self.permanence = kwargs.pop("permanence", None)
        super().__init__(*args, **kwargs)

    def send_email(self):
        self.body = strip_tags(self.html_body)

        recipients = dict.fromkeys(
            address.strip() for address in self.to + self.cc + self.bcc if address.strip()
        )
        if settings.DEBUG and not settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
            logger.debug(
                "email not send (DEBUG and no REPANIER_SETTINGS_BCC_ALL_EMAIL_TO)"
            )
            return set()

        sent = set()
        for address in recipients:
            result = self._send_email_with_unsubscribe(email_to=address)
            if result:
                sent.add(address)
            if settings.DEBUG and result is not None:
                break
        return sent

    def _ensure_email_log(self, customer, email_to):
        email_log = EmailLog.objects.create(
            customer=customer,
            recipient_email=email_to,
            permanence=self.permanence,
            nature=self.email_nature,
            status=EmailDeliveryStatus.SENT,
        )
        domain = email_to.split("@")[-1] if "@" in email_to else "repanier.local"
        rfc_message_id = f"<{email_log.uuid}@{domain}>"
        self.extra_headers["Message-ID"] = rfc_message_id
        EmailLog.objects.filter(id=email_log.id).update(
            message_id=rfc_message_id,
            updated_at=timezone.now(),
        )
        return email_log

    # @debug_parameters
    def _send_email_with_unsubscribe(self, email_to=None):
        from repanier.models.customer import Customer

        self.to = [email_to]
        self.cc = []
        self.bcc = []
        self.reply_to = [settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO]
        self.alternatives = []

        customer = Customer.get_customer_from_valid_email(email_to)
        if customer is not None:
            if self.send_even_if_unsubscribed or customer.subscribe_to_email:
                if self.show_customer_may_unsubscribe:
                    self.attach_alternative(
                        "{}{}".format(
                            self.html_body, customer.get_html_unsubscribe_mail_footer()
                        ),
                        "text/html",
                    )
                    self.extra_headers[
                        "List-Unsubscribe"
                    ] = customer.get_html_list_unsubscribe()
                else:
                    self.attach_alternative(self.html_body, "text/html")
            else:
                return
        else:
            self.attach_alternative(self.html_body, "text/html")

        email_send = False
        # Email subject *must not* contain newlines
        self.subject = "".join(self.subject.splitlines())

        logger.debug(
            "################################## send_email to : {}".format(email_to)
        )
        email_log = None
        last_error = EMPTY_STRING
        attempt_counter = 1
        while not email_send and attempt_counter < 3:
            if attempt_counter > 1:
                time.sleep(1 + int(random() * 3))
            attempt_counter += 1
            try:
                if settings.DEBUG:
                    if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                        self.to = [settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO]
                        subject_save = self.subject
                        self.subject = "<{}>, subject : <{}>".format(
                            email_to, self.subject
                        )
                        if email_log is None:
                            email_log = self._ensure_email_log(customer, email_to)
                        email_send = bool(self.send())
                        self.subject = subject_save
                        logger.debug(
                            "email send only to REPANIER_SETTINGS_BCC_ALL_EMAIL_TO (DEBUG)"
                        )
                    else:
                        pass
                else:
                    if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                        self.bcc = [settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO]
                    if email_log is None:
                        email_log = self._ensure_email_log(customer, email_to)
                    email_send = bool(self.send())
            except Exception as error_str:
                last_error = error_str
                logger.error("################################## send_email error")
                logger.error(error_str)
                self._send_error("send_email error", error_str)
                # reset connection : EmailMessage.get_connection() will get/open a new connection
                # before next self.send()
                self.connection = None

        if email_log is not None:
            if email_send:
                EmailLog.objects.filter(
                    id=email_log.id, status=EmailDeliveryStatus.SENT
                ).update(
                    status=EmailDeliveryStatus.SENT,
                    reason=EMPTY_STRING,
                    updated_at=timezone.now(),
                )
            else:
                EmailLog.objects.filter(
                    id=email_log.id, status=EmailDeliveryStatus.SENT
                ).update(
                    status=EmailDeliveryStatus.SEND_ERROR,
                    reason=str(last_error)[:255],
                    updated_at=timezone.now(),
                )

        return email_send

    @classmethod
    def send_test_email(cls, to_email, subject=EMPTY_STRING, html_body=EMPTY_STRING):
        try:
            # Avoid : string payload expected: <class 'django.utils.functional.__proxy__'>
            subject = subject or "{}".format(
                _("Test mail server configuration from Repanier")
            )
            html_body = html_body or format_html(
                _("The mail server configuration is working on your website {}."),
                settings.REPANIER_SETTINGS_GROUP_NAME,
            )
            body = strip_tags(html_body)

            # to_email = list({to_email, host_user})
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email, settings.ADMIN_EMAIL],
                reply_to=[settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO],
            )

            with open(settings.MEDIA_ROOT / "android-chrome-192x192.png", "rb") as fp:
                msgImage = MIMEImage(fp.read(), name="repanier.jpg")
            # Define the image's ID in header
            msgImage.add_header("Content-ID", "<id1>")
            # attach it to root
            email.attach(msgImage)
            html_body = format_html(
                """
                <hr/>
                <img
                  alt="{label}" title="{label}"
                  style="float: left; margin: 5px;"
                  src="cid:id1"/>
                <hr/>
                {body}
                """,
                label="label",
                body=html_body,
            )

            email.attach_alternative(
                html_body,
                "text/html",
            )

            email.send()
            return _(
                "An email has been sent from {} to {}.".format(
                    settings.DEFAULT_FROM_EMAIL, to_email
                )
            )
        except SMTPNotSupportedError:
            return "SMTPNotSupportedError"
        except SMTPServerDisconnected:
            return "SMTPServerDisconnected"
        except SMTPAuthenticationError:
            return "SMTPAuthenticationError : user {}, password {}".format(
                settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD
            )
        except SMTPSenderRefused:
            return "SMTPSenderRefused : sender {}".format(settings.DEFAULT_FROM_EMAIL)
        except SMTPRecipientsRefused:
            return "SMTPRecipientsRefused : recipient {}".format(to_email)
        except SMTPConnectError:
            return "SMTPConnectError : host {}, port {}".format(
                settings.EMAIL_HOST, settings.EMAIL_HOST_PORT
            )
        except SMTPHeloError:
            return "SMTPHeloError"
        except SMTPDataError:
            return "SMTPDataError"
        except SMTPResponseException:
            return "SMTPResponseException"
        except Exception:
            return "socket.gaierror"

    @classmethod
    def send_startup_email(cls, argv_0):
        if argv_0 == "uwsgi":  # Maybe better != manage.py',
            subject = "Start of instance {}".format(settings.ALLOWED_HOSTS[0])
            body = "\n".join([
                f"[{settings.REPANIER_SETTINGS_GROUP_NAME} : {settings.ALLOWED_HOSTS[0]}]",
                f"DJANGO_SETTINGS_LANGUAGE : {settings.DJANGO_SETTINGS_LANGUAGE}",
                f"DJANGO_SETTINGS_LOGGING : {settings.DJANGO_SETTINGS_LOGGING}",
                f"REPANIER_SETTINGS_BCC_ALL_EMAIL_TO : {settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO}",
                f"REPANIER_SETTINGS_BOOTSTRAP_CSS : {settings.REPANIER_SETTINGS_BOOTSTRAP_CSS}",
                f"REPANIER_SETTINGS_COUNTRY : {settings.REPANIER_SETTINGS_COUNTRY}",
                f"REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER : {settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER}",
                f"REPANIER_SETTINGS_MANAGE_ACCOUNTING : {settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING}",
                f"REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO : {settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO}",
                f"REPANIER_SETTINGS_ROUND_INVOICES : {settings.REPANIER_SETTINGS_ROUND_INVOICES}",
                f"REPANIER_SETTINGS_SMS_GATEWAY_MAIL : {settings.REPANIER_SETTINGS_SMS_GATEWAY_MAIL}",
            ])
            RepanierEmail.send_test_email(
                settings.ADMIN_EMAIL, subject=subject, html_body=body
            )

    @classmethod
    def send_email_to_who(cls, is_email_send=True, board=False):
        if is_email_send or board:
            if settings.DEBUG:
                if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                    return (
                        True,
                        _(
                            "Debug mode with REPANIER_SETTINGS_BCC_ALL_EMAIL_TO. This email will be sent to: {}"
                        ).format(settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO),
                    )
                else:
                    return (
                        False,
                        _(
                            "Debug mode without REPANIER_SETTINGS_BCC_ALL_EMAIL_TO : No email will be sent."
                        ),
                    )
            else:
                if is_email_send:
                    if board:
                        return (
                            True,
                            _(
                                "This email will be sent to the preparation team and the staff."
                            ),
                        )
                    else:
                        return (
                            True,
                            _(
                                "This email will be sent to customers or producers depending of the case."
                            ),
                        )
                else:
                    if board:
                        return True, _("This email will be sent to the staff.")
        return False, _("No email will be sent.")

    def _send_error(self, subject, error_str):
        from_email = "from_email : {}".format(self.from_email)
        reply_to = "reply_to : {}".format(self.reply_to)
        to_email = "to : {}".format(self.to)
        cc_email = "cc : {}".format(self.cc)
        bcc_email = "bcc : {}".format(self.bcc)
        subject_email = "subject : {}".format(self.subject)
        message = "{}\n{}\n{}\n{}\n{}\n{}".format(
            from_email, reply_to, to_email, cc_email, bcc_email, subject_email
        )
        time.sleep(5)
        try:
            connection = mail.get_connection()
            connection.open()
            mail_admins(
                subject, "{}\n{}".format(message, error_str), connection=connection
            )
            connection.close()
        except Exception:
            pass
