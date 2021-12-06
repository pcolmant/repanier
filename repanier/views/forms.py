import logging

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template import loader
from django.utils import timezone
from repanier.const import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    EMPTY_STRING,
)
from repanier.email.email import RepanierEmail
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.tools import get_repanier_template_name

logger = logging.getLogger(__name__)


class AuthRepanierPasswordResetForm(PasswordResetForm):
    def send_mail(
            self,
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name=None,
    ):
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(html_email_template_name, context)

        email = RepanierEmail(
            subject,
            html_body=body,
            to=[to_email],
            show_customer_may_unsubscribe=False,
            send_even_if_unsubscribed=True,
        )
        email.send_email()

    # From Django 1.8, this let the user enter name or email to recover
    def get_users(self, email):
        """Given an email, return matching user(s) who should receive a reset."""
        if email:
            return User.objects.filter(
                Q(username__iexact=email[:150], is_active=True)
                | Q(email__iexact=email, is_active=True)
            )
        else:
            return User.objects.none()


class AuthRepanierSetPasswordForm(SetPasswordForm):
    def send_mail(
            self,
            subject_template_name,
            email_template_name,
            context,
            to_email,
            html_email_template_name=None,
    ):
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = EMPTY_STRING.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(
            subject,
            body,
            [
                to_email,
            ],
        )
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        email_message.send()

    def save(self, commit=True, use_https=False, request=None):
        super().save(commit)
        if commit:
            now = timezone.now()
            if self.user.is_superuser:
                Configuration.objects.filter(id=DECIMAL_ONE).update(
                    login_attempt_counter=DECIMAL_ZERO, password_reset_on=now
                )
            else:
                customer = (
                    Customer.objects.filter(user=self.user, is_active=True)
                        .first()
                )
                if customer is not None:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=DECIMAL_ZERO, password_reset_on=now
                    )
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
            context = {
                "email": self.user.email,
                "domain": domain,
                "site_name": site_name,
                "user": self.user,
                "protocol": "https" if use_https else "http",
            }
            self.send_mail(
                get_repanier_template_name(
                    "registration/password_reset_done_subject.txt"
                ),
                get_repanier_template_name(
                    "registration/password_reset_done_email.html"
                ),
                context,
                self.user.email,
                html_email_template_name=None,
            )
        return self.user
