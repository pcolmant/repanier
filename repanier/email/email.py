# -*- coding: utf-8
from __future__ import unicode_literals

from smtplib import SMTPRecipientsRefused, SMTPAuthenticationError

import time
import datetime
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils import timezone

from repanier.const import DEMO_EMAIL, EMPTY_STRING


class RepanierEmail(EmailMultiAlternatives):

    def __init__(self, *args, **kwargs):
        self.html_content = kwargs.pop('html_content', None)
        self.unsubscribe = kwargs.pop('unsubscribe', True)
        self.test_connection = kwargs.pop('test_connection', None)
        super(RepanierEmail, self).__init__(*args, **kwargs)
        self._set_connection_param()

    def _set_connection_param(self):
        from repanier.apps import REPANIER_SETTINGS_CONFIG
        config = REPANIER_SETTINGS_CONFIG
        if config.email_is_custom and not settings.DJANGO_SETTINGS_DEMO:
            self.host = config.email_host
            self.port = config.email_port
            self.from_email = self.host_user = config.email_host_user
            self.host_password = config.email_host_password
            self.use_tls = config.email_use_tls
        else:
            self.host = settings.EMAIL_HOST
            self.port = settings.EMAIL_PORT
            self.host_user = settings.EMAIL_HOST_USER
            if not hasattr(self, 'from_email') or settings.DJANGO_SETTINGS_DEMO:
                self.from_email = settings.DEFAULT_FROM_EMAIL
            self.host_password = settings.EMAIL_HOST_PASSWORD
            self.use_tls = settings.EMAIL_USE_TLS

    def send_email(self, from_name=EMPTY_STRING):
        from repanier.apps import REPANIER_SETTINGS_GROUP_NAME

        email_send = False
        if not self.from_email.endswith(settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION):
            self.reply_to = [self.from_email]
            self.from_email = "%s <%s>" % (from_name or REPANIER_SETTINGS_GROUP_NAME, self.from_email)
        else:
            self.from_email = "%s <%s>" % (from_name or REPANIER_SETTINGS_GROUP_NAME, self.from_email)
        self.body = strip_tags(self.html_content)

        if settings.DJANGO_SETTINGS_DEMO:
            self.to = [DEMO_EMAIL]
            self.cc = []
            self.bcc = []
            email_send = self._send_email_with_error_log(from_name=from_name)
        else:
            from repanier.apps import REPANIER_SETTINGS_TEST_MODE
            if REPANIER_SETTINGS_TEST_MODE:
                from repanier.tools import emails_of_testers
                self.to = emails_of_testers()
                if len(self.to) > 0:
                    # Send the mail only if there is at least one tester
                    self.cc = []
                    self.bcc = []
                    email_send = self._send_email_with_error_log(from_name=from_name)
                else:
                    print('############################ test mode, without tester...')
            else:
                if settings.DEBUG:
                    print("to : %s" % self.to)
                    print("cc : %s" % self.cc)
                    print("bcc : %s" % self.bcc)
                    print("subject : %s" % slugify(self.subject))
                    email_send = True
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
                            email_send &= self._send_email_with_error_log(from_name=from_name)
                            time.sleep(1)
        return email_send

    def _send_email_with_error_log(self, from_name=EMPTY_STRING):
        email_to = self.to[0]
        if not self.test_connection:
            customer = self._get_customer(email_to)
            if customer is not None:
                if customer.user.last_login is None:
                    # Do not spam someone who has never logged in
                    return False
                else:
                    max_2_years_in_the_past = timezone.now() - datetime.timedelta(days=426)
                    if customer.user.last_login < max_2_years_in_the_past:
                        # Do not spam someone who has never logged in since more than 1 year and 2 months
                        return False
        else:
            customer = None

        self.alternatives = []
        if self.unsubscribe and customer is not None:
            self.attach_alternative(
                "%s%s" % (self.html_content, customer.get_unsubscribe_mail_footer()),
                "text/html"
            )
        else:
            self.attach_alternative(
                self.html_content,
                "text/html"
            )
        email_send = False
        # Email subject *must not* contain newlines
        self.subject = ''.join(self.subject.splitlines())
        try:
            with mail.get_connection(
                    host=self.host,
                    port=self.port,
                    username=self.host_user,
                    password=self.host_password,
                    use_tls=self.use_tls,
                    use_ssl=not self.use_tls) as connection:
                self.connection = connection
                message = EMPTY_STRING
                try:
                    print("################################## send_email")
                    # from_email : GasAth Ptidej <GasAth Ptidej <ptidej-cde@repanier.be>>
                    from_email = "from_email : %s" % self.from_email
                    reply_to = "reply_to : %s" % self.reply_to
                    to = "to : %s" % self.to
                    cc = "cc : %s" % self.cc
                    bcc = "bcc : %s" % self.bcc
                    subject = "subject : %s" % slugify(self.subject)
                    print(from_email)
                    print(reply_to)
                    print(to)
                    print(cc)
                    print(bcc)
                    print(subject)
                    message = "%s\n%s\n%s\n%s\n%s\n%s" % (from_email, reply_to, to, cc, bcc, subject)
                    self.send()
                    email_send = True
                except SMTPRecipientsRefused as error_str:
                    print("################################## send_email SMTPRecipientsRefused")
                    print(error_str)
                    time.sleep(1)
                    connection = mail.get_connection()
                    connection.open()
                    mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
                    connection.close()
                except Exception as error_str:
                    print("################################## send_email error")
                    print(error_str)
                    time.sleep(1)
                    connection = mail.get_connection()
                    connection.open()
                    mail_admins("ERROR", "%s\n%s" % (message, error_str), connection=connection)
                    connection.close()
                print("##################################")
                if email_send and customer is not None:
                    from repanier.models.customer import Customer

                    # customer.valid_email = valid_email
                    # customer.save(update_fields=['valid_email'])
                    # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
                    Customer.objects.filter(id=customer.id).order_by('?').update(valid_email=email_send)
        except SMTPAuthenticationError as error_str:
            print("################################## send_email SMTPAuthenticationError")
            # https://support.google.com/accounts/answer/185833
            # https://support.google.com/accounts/answer/6010255
            # https://security.google.com/settings/security/apppasswords
            print(error_str)
        return email_send

    def _get_customer(self, email_address):
        from repanier.models.customer import Customer

        # try to find a customer based on user__email or customer__email2
        customer = Customer.objects.filter(
            user__email=email_address,
            subscribe_to_email=True,
        ).exclude(
            valid_email=False,
        ).order_by('?').first()
        if customer is None:
            customer = Customer.objects.filter(
                email2=email_address,
                subscribe_to_email=True,
            ).exclude(
                valid_email=False
            ).order_by('?').first()
        return customer
