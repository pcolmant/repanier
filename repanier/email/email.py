import datetime
import logging
import time
from random import random
from smtplib import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPNotSupportedError,
    SMTPServerDisconnected,
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPDataError,
    SMTPConnectError,
    SMTPHeloError,
)

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from repanier.const import EMPTY_STRING

logger = logging.getLogger(__name__)


class RepanierEmail(EmailMultiAlternatives):
    def __init__(self, *args, **kwargs):
        self.html_body = kwargs.pop("html_body", None)
        self.show_customer_may_unsubscribe = kwargs.pop(
            "show_customer_may_unsubscribe", True
        )
        self.send_even_if_unsubscribed = kwargs.pop("send_even_if_unsubscribed", False)
        super().__init__(*args, **kwargs)

    def send_email(self):
        self.body = strip_tags(self.html_body)

        # chunks = [email.to[x:x+100] for x in xrange(0, len(email.to), 100)]
        # for chunk in chunks:
        # Remove duplicates
        send_email_to = list(set(self.to + self.cc + self.bcc))
        for email_to in send_email_to:
            self._send_email_with_unsubscribe(email_to=email_to.strip())

    # @debug_parameters
    def _send_email_with_unsubscribe(self, email_to=None):
        from repanier.models.customer import Customer

        self.to = [email_to]
        self.cc = []
        self.bcc = []
        self.reply_to = [settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO]

        customer = Customer.get_customer_from_valid_email(email_to)
        if customer is not None:
            if not self.send_even_if_unsubscribed:
                if not customer.subscribe_to_email:
                    return False
                elif customer.user.last_login is not None:
                    max_2_years_in_the_past = timezone.now() - datetime.timedelta(
                        days=426
                    )
                    if customer.user.last_login < max_2_years_in_the_past:
                        # Do not spam someone who has never logged in since more than 1 year and 2 months
                        return False

        self.alternatives = []
        if customer is not None and self.show_customer_may_unsubscribe:
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
        email_send = False
        # Email subject *must not* contain newlines
        self.subject = "".join(self.subject.splitlines())

        logger.debug(
            "################################## send_email to : {}".format(email_to)
        )
        attempt_counter = 1
        while not email_send and attempt_counter < 3:
            attempt_counter += 1
            try:
                if settings.DEBUG:
                    if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                        self.to = [settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO]
                        self.send()
                        logger.debug(
                            "email send only to REPANIER_SETTINGS_BCC_ALL_EMAIL_TO (DEBUG)"
                        )
                    else:
                        logger.debug(
                            "email not send (DEBUG and no REPANIER_SETTINGS_BCC_ALL_EMAIL_TO)"
                        )
                else:
                    if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                        self.bcc = [settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO]
                    self.send()
                email_send = True
            except SMTPRecipientsRefused as error_str:
                logger.error(
                    "################################## send_email SMTPRecipientsRefused"
                )
                logger.error(error_str)
                # reset connection : EmailMessage.get_connection() will get/open a new connection
                # before next self.send()
                self.connection = None
            except Exception as error_str:
                logger.error("################################## send_email error")
                logger.error(error_str)
                self._send_error("send_email error", error_str)
                # reset connection : EmailMessage.get_connection() will get/open a new connection
                # before next self.send()
                self.connection = None
            if customer is not None:
                # customer.valid_email = valid_email
                # customer.save(update_fields=['valid_email'])
                # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
                Customer.objects.filter(id=customer.id).update(valid_email=email_send)
            time.sleep(min(1, 1 + int(random())))

        return email_send

    @classmethod
    def send_test_email(cls, to_email, subject=EMPTY_STRING, body=EMPTY_STRING):
        try:
            # Avoid : string payload expected: <class 'django.utils.functional.__proxy__'>
            subject = subject or "{}".format(
                _("Test mail server configuration from Repanier")
            )
            body = body or "{}".format(
                _(
                    "The mail server configuration is working on your website {}."
                ).format(settings.REPANIER_SETTINGS_GROUP_NAME)
            )
            # to_email = list({to_email, host_user})
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email, settings.ADMIN_EMAIL],
                reply_to=[settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO],
            )
            email.send()
            return _(
                "An email has been send from {} to {}.".format(
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
        except:
            return "socket.gaierror"

    @classmethod
    def send_startup_email(cls, argv_0):
        if argv_0 == "uwsgi":  # Maybe better != manage.py',
            subject = "Start of instance {}".format(settings.ALLOWED_HOSTS[0])
            body = """
                        [{REPANIER_SETTINGS_GROUP_NAME} : {ALLOWED_HOSTS}]
                        DJANGO_SETTINGS_LANGUAGE : {DJANGO_SETTINGS_LANGUAGE}
                        DJANGO_SETTINGS_LOGGING : {DJANGO_SETTINGS_LOGGING}
                        REPANIER_SETTINGS_BCC_ALL_EMAIL_TO : {REPANIER_SETTINGS_BCC_ALL_EMAIL_TO}
                        REPANIER_SETTINGS_BOOTSTRAP_CSS : {REPANIER_SETTINGS_BOOTSTRAP_CSS}
                        REPANIER_SETTINGS_COUNTRY: {REPANIER_SETTINGS_COUNTRY}
                        REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER: {REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER}
                        REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE : {REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE}
                        REPANIER_SETTINGS_DELIVERY_POINT : {REPANIER_SETTINGS_DELIVERY_POINT}
                        REPANIER_SETTINGS_MANAGE_ACCOUNTING : {REPANIER_SETTINGS_MANAGE_ACCOUNTING}
                        REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO : {REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO}
                        REPANIER_SETTINGS_ROUND_INVOICES : {REPANIER_SETTINGS_ROUND_INVOICES}
                        REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM : {REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM}
                        REPANIER_SETTINGS_SMS_GATEWAY_MAIL : {REPANIER_SETTINGS_SMS_GATEWAY_MAIL}
                        REPANIER_SETTINGS_TEMPLATE : {REPANIER_SETTINGS_TEMPLATE}
                        """ "".format(
                REPANIER_SETTINGS_GROUP_NAME=settings.REPANIER_SETTINGS_GROUP_NAME,
                ALLOWED_HOSTS=settings.ALLOWED_HOSTS[0],
                DJANGO_SETTINGS_LANGUAGE=settings.DJANGO_SETTINGS_LANGUAGE,
                DJANGO_SETTINGS_LOGGING=settings.DJANGO_SETTINGS_LOGGING,
                REPANIER_SETTINGS_BCC_ALL_EMAIL_TO=settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO,
                REPANIER_SETTINGS_BOOTSTRAP_CSS=settings.REPANIER_SETTINGS_BOOTSTRAP_CSS,
                REPANIER_SETTINGS_COUNTRY=settings.REPANIER_SETTINGS_COUNTRY,
                REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER=settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER,
                REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE=settings.REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE,
                REPANIER_SETTINGS_DELIVERY_POINT=settings.REPANIER_SETTINGS_DELIVERY_POINT,
                REPANIER_SETTINGS_MANAGE_ACCOUNTING=settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING,
                REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO=settings.REPANIER_SETTINGS_REPLY_ALL_EMAIL_TO,
                REPANIER_SETTINGS_ROUND_INVOICES=settings.REPANIER_SETTINGS_ROUND_INVOICES,
                REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM=settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM,
                REPANIER_SETTINGS_SMS_GATEWAY_MAIL=settings.REPANIER_SETTINGS_SMS_GATEWAY_MAIL,
                REPANIER_SETTINGS_TEMPLATE=settings.REPANIER_SETTINGS_TEMPLATE,
            )
            RepanierEmail.send_test_email(
                settings.ADMIN_EMAIL, subject=subject, body=body
            )

    @classmethod
    def send_email_to_who(cls, is_email_send=True, board=False):
        if is_email_send or board:
            if settings.DEBUG:
                if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
                    return (
                        True,
                        _(
                            "Debug mode with REPANIER_SETTINGS_BCC_ALL_EMAIL_TO. This email will be send to : {}"
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
        else:
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
        except:
            pass
