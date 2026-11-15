import logging

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from repanier.const import (
    DECIMAL_ZERO,
    DECIMAL_ONE,
    DECIMAL_THREE,
    EMPTY_STRING,
    AuthGroup,
)
from repanier.email.email import RepanierEmail
from repanier.models import Customer, Staff, Configuration
from repanier.tools import get_repanier_template_name

UserModel = get_user_model()

logger = logging.getLogger(__name__)

UserModel = get_user_model()

# The temporary lock of the sign in: three failed attempts lock the
# account for a quarter of an hour, correct password included. A blind
# guesser slows down to a few passwords per hour, a locked out
# legitimate user always knows when the door reopens.
LOGIN_LOCK_ATTEMPTS = DECIMAL_THREE
LOGIN_LOCK_MINUTES = 15


class RepanierAuthBackend(ModelBackend):
    user = None

    def __init__(self, *args, **kwargs):
        super().__init__()

    def authenticate(self, request, username=None, password=None, **kwargs):
        # The sign in happens with the e-mail address only: the short
        # and long names display an identity, they never open a door.
        user_username = (
            UserModel.objects.filter(email__iexact=username).order_by("id").first()
        )
        if user_username is None:
            # The credential resolves no e-mail address. One private
            # door remains: the accounts without a customer profile -
            # in practice the superusers - may open their session with
            # their username, an identifier never displayed anywhere
            # and unknown to the public, unlike their e-mail address.
            # A member never enters through this door: his account
            # carries a customer profile, his key stays his e-mail
            # address - the imported short names stay closed.
            user_by_name = UserModel.objects.filter(username=username).first()
            if user_by_name is None or Customer.objects.filter(
                user_id=user_by_name.id
            ).exists():
                return None
            user_username = user_by_name
        is_superuser = False
        customer = None
        login_attempt_counter = DECIMAL_ZERO
        login_locked_on = None
        username = user_username.username
        customer = Customer.objects.filter(user_id=user_username.id).first()
        if customer is None:
            is_superuser = True
            configuration = (
                Configuration.objects.filter(id=DECIMAL_ONE)
                .only("login_attempt_counter", "login_locked_on")
                .first()
            )
            login_attempt_counter = configuration.login_attempt_counter
            login_locked_on = configuration.login_locked_on
        else:
            login_attempt_counter = customer.login_attempt_counter
            login_locked_on = customer.login_locked_on

        if login_locked_on is not None:
            locked_until = login_locked_on + timezone.timedelta(
                minutes=int(LOGIN_LOCK_MINUTES)
            )
            now = timezone.now()
            if now < locked_until:
                # The temporary lock: three failed attempts closed the
                # account for a quarter of an hour, correct password
                # included - the guesser waits, the legitimate user sees
                # when the door reopens.
                minutes_left = int((locked_until - now).total_seconds() // 60) + 1
                raise forms.ValidationError(
                    _(
                        "Your account is locked after too many failed attempts: "
                        "try again in %(minutes)d minutes, or ask for a new password "
                        "right now."
                    )
                    % {"minutes": minutes_left},
                    code="login_lock",
                )
            # The lock expired: clean slate, the failed attempts of a
            # quarter hour ago do not poison the new episode.
            self._reset_attempts(customer, is_superuser)
            login_locked_on = None
            login_attempt_counter = DECIMAL_ZERO

        user = super().authenticate(request, username=username, password=password)
        if user is None:
            # Failed to log in
            counter = login_attempt_counter + DECIMAL_ONE
            if customer is not None:
                # The lock engages on the third failed attempt - and
                # the warning mail leaves once per lock episode, not
                # once per attempt.
                Customer.objects.filter(id=customer.id).update(
                    login_attempt_counter=min(counter, 20),
                    **(
                        {"login_locked_on": timezone.now()}
                        if counter >= LOGIN_LOCK_ATTEMPTS and login_locked_on is None
                        else {}
                    ),
                )
            elif is_superuser:
                Configuration.objects.filter(id=DECIMAL_ONE).update(
                    login_attempt_counter=min(counter, 20),
                    **(
                        {"login_locked_on": timezone.now()}
                        if counter >= LOGIN_LOCK_ATTEMPTS and login_locked_on is None
                        else {}
                    ),
                )
            if counter >= LOGIN_LOCK_ATTEMPTS:
                if login_locked_on is None:
                    self._warn_account_owner(user_username)
                raise forms.ValidationError(
                    _(
                        "Your account is locked after too many failed attempts: "
                        "try again in %(minutes)d minutes, or ask for a new password "
                        "right now."
                    )
                    % {"minutes": int(LOGIN_LOCK_MINUTES)},
                    code="login_lock",
                )
        else:
            # The password is correct: an authentication that succeeds
            # proves the credentials, whatever the failures that came
            # before. The counter exists to slow down guessing on a
            # wrong password, and the reset flows are not the only
            # path that proves an identity - an administrator resetting
            # a password by hand is one too. Locking a correct password
            # out trapped the customers in a login loop, with no code
            # path left to lift the lock.
            self._reset_attempts(customer, is_superuser)
            self.user = self.get_user(user.id)
            return self.user

    def _reset_attempts(self, customer, is_superuser):
        if customer is not None and (
            customer.login_attempt_counter > DECIMAL_ZERO
            or customer.login_locked_on is not None
        ):
            Customer.objects.filter(id=customer.id).update(
                login_attempt_counter=DECIMAL_ZERO, login_locked_on=None
            )
        elif is_superuser:
            configuration = Configuration.objects.filter(id=DECIMAL_ONE).only(
                "login_attempt_counter", "login_locked_on"
            ).first()
            if configuration is not None and (
                configuration.login_attempt_counter > DECIMAL_ZERO
                or configuration.login_locked_on is not None
            ):
                Configuration.objects.filter(id=DECIMAL_ONE).update(
                    login_attempt_counter=DECIMAL_ZERO, login_locked_on=None
                )

    def _warn_account_owner(self, user):
        """One mail per lock episode: the account owner must know that
        something strange is happening - a forgotten password with caps
        lock on, or someone else trying the door. The site coordinator
        receives a copy, so a dormant account asking for help or a
        complaining member arrives with the context already in the
        mailbox."""
        email = None
        to_email = None
        try:
            if user is None:
                return
            to_email = user.email
            if not to_email:
                return
            html_body = render_to_string(
                get_repanier_template_name("registration/login_locked_email.html"),
                {
                    "group_name": settings.REPANIER_SETTINGS_GROUP_NAME,
                    "site_name": settings.REPANIER_SETTINGS_GROUP_NAME,
                    "customer_email": to_email,
                    "login_lock_minutes": int(LOGIN_LOCK_MINUTES),
                    "password_reset_url": "https://{}{}".format(
                        settings.ALLOWED_HOSTS[0],
                        reverse("repanier:password_reset"),
                    ),
                },
            )
            email = RepanierEmail(
                subject="{} - {}".format(
                    settings.REPANIER_SETTINGS_GROUP_NAME,
                    _("Your account is temporarily locked"),
                ),
                html_body=html_body,
                to=[to_email],
                cc=[settings.REPANIER_SETTINGS_COORDINATOR_EMAIL],
                show_customer_may_unsubscribe=False,
                send_even_if_unsubscribed=True,
            )
            email.send_email()
        except Exception as error:
            logger.error("send_login_locked_email error : {}".format(error))
            # A lock warning that reaches neither the member nor the
            # coordinator must at least reach the admins: the same
            # failure report as the other mails of Repanier.
            try:
                if email is None:
                    # The mail itself could not be built: an empty
                    # RepanierEmail still carries the failed attempt -
                    # recipient and coordinator copy - in its report.
                    email = RepanierEmail(
                        subject=_("Your account is temporarily locked"),
                        html_body=EMPTY_STRING,
                        to=[to_email or EMPTY_STRING],
                        cc=[settings.REPANIER_SETTINGS_COORDINATOR_EMAIL],
                    )
                email._send_error("send_login_locked_email error", error)
            except Exception as nested_error:
                logger.error(
                    "send_login_locked_email error report error : {}".format(
                        nested_error
                    )
                )

    @classmethod
    def set_staff_right(cls, request, user=None, as_staff=None):
        auth_logout(request)
        Customer.objects.filter(user_id=user.id).update(as_staff=as_staff)
        user.is_staff = True
        user.groups.clear()
        if as_staff.is_webmaster:
            group_id = Group.objects.filter(name=AuthGroup.WEBMASTER).first()
            user.groups.add(group_id)
        if (
            as_staff.is_order_manager
            or as_staff.is_invoice_manager
            or as_staff.is_repanier_admin
        ):
            group_id = Group.objects.filter(name=AuthGroup.REPANIER).first()
            user.groups.add(group_id)
        user.save()
        auth_login(request, user)

    @classmethod
    def remove_staff_right(cls, user=None):
        if user is not None:
            is_customer_as_staff = Customer.objects.filter(
                user_id=user.id, as_staff__isnull=False
            ).exists()
            if is_customer_as_staff:
                Customer.objects.filter(user_id=user.id).update(as_staff=None)
                user.is_staff = False
                user.groups.clear()
                user.save()
                RepanierAuthBackend.set_user_right(
                    user=user, is_superuser=False, staff=None, customer=user.customer
                )

    @classmethod
    def set_user_right(cls, user, is_superuser, customer, staff):
        if is_superuser:
            user.is_order_manager = True
            user.is_invoice_manager = True
            user.is_repanier_admin = True
            user.is_repanier_staff = True
            user.is_webmaster = True
            user.customer_id = None
            user.staff_id = None
            user.subscribe_to_email = True
        else:
            if staff is None:
                user.is_order_manager = False
                user.is_invoice_manager = False
                user.is_repanier_admin = False
                user.is_repanier_staff = False
                user.is_webmaster = False
                user.customer_id = customer.id
                user.staff_id = None
                user.subscribe_to_email = customer.subscribe_to_email
            else:
                user.is_order_manager = (
                    staff.is_order_manager or staff.is_repanier_admin
                )
                user.is_invoice_manager = (
                    staff.is_invoice_manager or staff.is_repanier_admin
                )
                user.is_repanier_admin = staff.is_repanier_admin
                user.is_repanier_staff = (
                    user.is_order_manager or user.is_invoice_manager
                )
                user.is_webmaster = staff.is_webmaster or staff.is_repanier_admin
                user.staff_id = staff.id
                user.subscribe_to_email = True
                if customer is None:
                    user.customer_id = staff.customer_responsible_id
                else:
                    user.customer_id = customer.id

    def get_user(self, user_id):
        if self.user is not None and self.user.id == user_id:
            # Test "hasattr(self.user, 'is_order_manager')" to detect user without new attributes
            return self.user
        user_or_none = (
            UserModel.objects.filter(pk=user_id)
            .only("id", "password", "is_staff", "is_superuser")
            .first()
        )
        if user_or_none is not None:
            if not user_or_none.is_superuser:
                customer = (
                    Customer.objects.filter(user_id=user_or_none.id)
                    .only("id", "is_active", "as_staff", "subscribe_to_email")
                    .first()
                )
                if customer is not None:
                    if not customer.is_active:
                        user_or_none = None
                    elif customer.as_staff is not None:
                        staff = (
                            Staff.objects.filter(id=customer.as_staff_id)
                            .only(
                                "id",
                                "is_active",
                                "is_order_manager",
                                "is_invoice_manager",
                                "is_repanier_admin",
                                "is_webmaster",
                            )
                            .first()
                        )
                        if staff is not None and staff.is_active:
                            RepanierAuthBackend.set_user_right(
                                user=user_or_none,
                                is_superuser=False,
                                staff=staff,
                                customer=customer,
                            )
                        else:
                            user_or_none = None
                    else:
                        RepanierAuthBackend.set_user_right(
                            user=user_or_none,
                            is_superuser=False,
                            staff=None,
                            customer=customer,
                        )
                else:
                    user_or_none = None
            else:
                RepanierAuthBackend.set_user_right(
                    user=user_or_none, is_superuser=True, staff=None, customer=None
                )
        self.user = user_or_none
        return user_or_none
