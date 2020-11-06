from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group
from django.db.models import F, Q
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.const import DECIMAL_ZERO, DECIMAL_ONE, DECIMAL_THREE, WEBMASTER_GROUP
from repanier.models import Customer, Staff, Configuration

UserModel = get_user_model()


class RepanierAuthBackend(ModelBackend):
    user = None

    def __init__(self, *args, **kwargs):
        super().__init__()

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_username = (
            UserModel.objects.filter(
                Q(last_name__iexact=username[:150]) | Q(email__iexact=username)
            )
            .order_by("?")
            .first()
        )
        is_superuser = False
        # staff = customer = None
        customer = None
        login_attempt_counter = DECIMAL_THREE
        if user_username is not None:
            username = user_username.username
            customer = (
                Customer.objects.filter(user_id=user_username.id).order_by("?").first()
            )
            if customer is None:
                # staff = Staff.objects.filter(
                #     user_id=user_username.id
                # ).order_by('?').first()
                # if staff is None:
                is_superuser = True
                login_attempt_counter = (
                    Configuration.objects.filter(id=DECIMAL_ONE)
                    .only("login_attempt_counter")
                    .first()
                    .login_attempt_counter
                )
                # else:
                #     login_attempt_counter = staff.login_attempt_counter
            else:
                login_attempt_counter = customer.login_attempt_counter

        user = super().authenticate(
            request, username=username, password=password
        )
        if user is None:
            # Failed to log in
            if login_attempt_counter < 20:
                # Do not increment indefinitely
                if customer is not None:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=F("login_attempt_counter") + DECIMAL_ONE
                    )
                # elif staff is not None:
                #     Staff.objects.filter(id=staff.id).update(
                #         login_attempt_counter=F('login_attempt_counter') +
                #                               DECIMAL_ONE
                #     )
                elif is_superuser:
                    Configuration.objects.filter(id=DECIMAL_ONE).update(
                        login_attempt_counter=F("login_attempt_counter") + DECIMAL_ONE
                    )
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "You must now first reset your password because you tried to log in too many time without success."
                    ),
                    code="attempt",
                )
        else:
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "You must now first reset your password because you tried to log in too many time without success."
                    ),
                    code="attempt",
                )
            else:
                # Reset login_attempt_counter
                # and if it's a customer, update/save the customer's language
                if customer is not None:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Customer.objects.filter(id=customer.id).update(
                            login_attempt_counter=DECIMAL_ZERO,
                            language=translation.get_language(),
                        )
                    else:
                        Customer.objects.filter(id=customer.id).update(
                            language=translation.get_language()
                        )
                # elif staff is not None:
                #     if login_attempt_counter > DECIMAL_ZERO:
                #         Staff.objects.filter(id=staff.id).update(
                #             login_attempt_counter=DECIMAL_ZERO
                #         )
                elif is_superuser:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Configuration.objects.filter(id=DECIMAL_ONE).update(
                            login_attempt_counter=DECIMAL_ZERO
                        )

                self.user = self.get_user(user.id)
                return self.user

    @classmethod
    def set_staff_right(cls, request, user=None, as_staff=None):
        auth_logout(request)
        Customer.objects.filter(user_id=user.id).order_by("?").update(as_staff=as_staff)
        user.is_staff = True
        user.groups.clear()
        if as_staff.is_webmaster:
            group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
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
                Customer.objects.filter(user_id=user.id).order_by("?").update(
                    as_staff=None
                )
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
            .order_by("?")
            .first()
        )
        if user_or_none is not None:
            if not user_or_none.is_superuser:
                customer = (
                    Customer.objects.filter(user_id=user_or_none.id)
                    .only("id", "is_active", "as_staff")
                    .order_by("?")
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
                            .order_by("?")
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
