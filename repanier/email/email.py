# -*- coding: utf-8

import datetime
import logging
import time
from random import randint
from smtplib import SMTPRecipientsRefused, SMTPAuthenticationError

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.utils import timezone
from django.utils.html import strip_tags

from repanier.const import DEMO_EMAIL, EMPTY_STRING
from repanier.tools import debug_parameters

logger = logging.getLogger(__name__)


class RepanierEmail(EmailMultiAlternatives):
    def __init__(self, *args, **kwargs):
        self.html_body = kwargs.pop('html_body', None)
        self.show_customer_may_unsubscribe = kwargs.pop('show_customer_may_unsubscribe', True)
        self.send_even_if_unsubscribed = kwargs.pop('send_even_if_unsubscribed', False)
        self.test_connection = kwargs.pop('test_connection', False)
        super(RepanierEmail, self).__init__(*args, **kwargs)
        self._set_connection_param()

    def _set_connection_param(self):
        from repanier.apps import REPANIER_SETTINGS_CONFIG
        config = REPANIER_SETTINGS_CONFIG
        if config.email_is_custom and not settings.REPANIER_SETTINGS_DEMO:
            self.host = config.email_host
            self.port = config.email_port
            self.from_email = self.host_user = config.email_host_user
            self.host_password = config.email_host_password
            self.use_tls = config.email_use_tls
        else:
            self.host = settings.EMAIL_HOST
            self.port = settings.EMAIL_PORT
            self.host_user = settings.EMAIL_HOST_USER
            if not hasattr(self, 'from_email') or settings.REPANIER_SETTINGS_DEMO:
                self.from_email = settings.DEFAULT_FROM_EMAIL
            self.host_password = settings.EMAIL_HOST_PASSWORD
            self.use_tls = settings.EMAIL_USE_TLS

    def send_email(self, from_name=EMPTY_STRING):
        from repanier.apps import REPANIER_SETTINGS_GROUP_NAME

        self.from_email = "{} <{}>".format(from_name or REPANIER_SETTINGS_GROUP_NAME, self.from_email)
        self.body = strip_tags(self.html_body)

        if settings.REPANIER_SETTINGS_DEMO:
            self.to = [DEMO_EMAIL]
            self.cc = []
            self.bcc = []
            email_send = self._send_email_with_error_log()
        else:
            # chunks = [email.to[x:x+100] for x in xrange(0, len(email.to), 100)]
            # for chunk in chunks:
            # Remove duplicates
            send_email_to = list(set(self.to + self.cc + self.bcc))
            self.cc = []
            self.bcc = []
            email_send = True
            if len(send_email_to) >= 1:
                for email_to in send_email_to:
                    self.to = [email_to]
                    email_send &= self._send_email_with_error_log()
                    time.sleep(1)
        return email_send

    @debug_parameters
    def _send_email_with_error_log(self):
        email_to = self.to[0]
        if not self.test_connection:
            from repanier.models.customer import Customer

            customer = Customer.get_customer_from_valid_email(email_to)
            if customer is not None:
                if not self.send_even_if_unsubscribed and not customer.subscribe_to_email:
                    return False
                elif customer.user.last_login is not None:
                    max_2_years_in_the_past = timezone.now() - datetime.timedelta(days=426)
                    if customer.user.last_login < max_2_years_in_the_past:
                        # Do not spam someone who has never logged in since more than 1 year and 2 months
                        return False
        else:
            customer = None

        self.alternatives = []
        if customer is not None and self.show_customer_may_unsubscribe:
            self.attach_alternative(
                "{}{}".format(self.html_body, customer.get_html_unsubscribe_mail_footer()),
                "text/html"
            )
            self.extra_headers['List-Unsubscribe'] = customer.get_html_list_unsubscribe()
        else:
            self.attach_alternative(
                self.html_body,
                "text/html"
            )
        email_send = False
        try_to_send = True
        # Email subject *must not* contain newlines
        self.subject = ''.join(self.subject.splitlines())
        if settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO:
            self.bcc = [settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO, ]

        logger.info("################################## send_email")
        attempt_counter = 1
        while not email_send and try_to_send:
            attempt_counter += 1
            try_to_send = False
            try:
                with mail.get_connection(
                        host=self.host,
                        port=self.port,
                        username=self.host_user,
                        password=self.host_password,
                        use_tls=self.use_tls,
                        use_ssl=not self.use_tls) as connection:
                    self.connection = connection
                    try:
                        if not settings.DEBUG:
                            # Do not send mail in debug mode
                            # self.to = ['ask.it@to.me']
                            self.send()
                        email_send = True
                    except SMTPRecipientsRefused as error_str:
                        logger.error("################################## send_email SMTPRecipientsRefused")
                        logger.error(error_str)
                        self._send_error("ERROR", error_str)
                    except Exception as error_str:
                        logger.error("################################## send_email error")
                        logger.error(error_str)
                        self._send_error("ERROR", error_str)
                    logger.info("##################################")
                    if email_send and customer is not None:
                        from repanier.models.customer import Customer

                        # customer.valid_email = valid_email
                        # customer.save(update_fields=['valid_email'])
                        # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
                        Customer.objects.filter(id=customer.id).order_by('?').update(valid_email=email_send)
            except SMTPAuthenticationError as error_str:
                logger.fatal("################################## send_email SMTPAuthenticationError")
                # https://support.google.com/accounts/answer/185833
                # https://support.google.com/accounts/answer/6010255
                # https://security.google.com/settings/security/apppasswords
                logger.fatal(error_str)
                self._send_error("FATAL", error_str)
            except Exception as error_str:
                if attempt_counter <= 5:
                    logger.info("################################## send_email error, retry")
                    logger.info(error_str)
                    # retry max 5 more times
                    attempt_counter += 1
                    try_to_send = True
                    time.sleep(min(5 * attempt_counter, randint(10, 20)))
                else:
                    logger.fatal("################################## send_email error, abort")
                    logger.fatal(error_str)
                    self._send_error("FATAL", error_str)

        return email_send

    def _send_error(self, subject, error_str, connection=None):
        from_email = "from_email : {}".format(self.from_email)
        reply_to = "reply_to : {}".format(self.reply_to)
        to_email = "to : {}".format(self.to)
        cc_email = "cc : {}".format(self.cc)
        bcc_email = "bcc : {}".format(self.bcc)
        subject_email = "subject : {}".format(self.subject)
        message = "{}\n{}\n{}\n{}\n{}\n{}".format(from_email, reply_to, to_email, cc_email, bcc_email,
                                                  subject_email)
        time.sleep(5)
        try:
            connection = mail.get_connection()
            connection.open()
            mail_admins(subject, "{}\n{}".format(message, error_str), connection=connection)
            connection.close()
        except:
            pass
