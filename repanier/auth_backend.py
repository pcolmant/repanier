# -*- coding: utf-8
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import F, Q
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.const import DECIMAL_ZERO, DECIMAL_ONE, DECIMAL_THREE
from repanier.models import Customer, Staff, Configuration

UserModel = get_user_model()


class RepanierCustomBackend(ModelBackend):
    user = None

    def __init__(self, *args, **kwargs):
        super(RepanierCustomBackend, self).__init__()

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_username = UserModel.objects.filter(
            Q(
                username__iexact=username[:150]
            ) | Q(
                email__iexact=username
            )
        ).order_by('?').first()
        is_admin = False
        staff = customer = None
        login_attempt_counter = DECIMAL_THREE
        if user_username is not None:
            username = user_username.username
            customer = Customer.objects.filter(
                user=user_username, is_active=True
            ).order_by('?').first()
            if customer is None:
                staff = Staff.objects.filter(
                    user=user_username, is_active=True
                ).order_by('?').first()
                if staff is None:
                    is_admin = True
                    login_attempt_counter = Configuration.objects.filter(
                        id=DECIMAL_ONE
                    ).only(
                        'login_attempt_counter'
                    ).first().login_attempt_counter
                else:
                    login_attempt_counter = staff.login_attempt_counter
            else:
                login_attempt_counter = customer.login_attempt_counter

        user = super(RepanierCustomBackend, self).authenticate(request, username=username, password=password)
        if user is None:
            # Failed to log in
            if login_attempt_counter < 20:
                # Do not increment indefinitely
                if customer is not None:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=F('login_attempt_counter') +
                                              DECIMAL_ONE
                    )
                elif staff is not None:
                    Staff.objects.filter(id=staff.id).update(
                        login_attempt_counter=F('login_attempt_counter') +
                                              DECIMAL_ONE
                    )
                elif is_admin:
                    Configuration.objects.filter(id=DECIMAL_ONE).update(
                        login_attempt_counter=F('login_attempt_counter') +
                                              DECIMAL_ONE
                    )
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "You must now first reset your password because you tried to log in too many time without success."),
                    code='attempt',
                )
        else:
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "You must now first reset your password because you tried to log in too many time without success."),
                    code='attempt',
                )
            else:
                # Reset login_attempt_counter
                # and if it's a customer, update/save the customer's language
                if customer is not None:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Customer.objects.filter(id=customer.id).update(
                            login_attempt_counter=DECIMAL_ZERO,
                            language=translation.get_language()
                        )
                    else:
                        Customer.objects.filter(id=customer.id).update(
                            language=translation.get_language()
                        )
                elif staff is not None:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Staff.objects.filter(id=staff.id).update(
                            login_attempt_counter=DECIMAL_ZERO
                        )
                elif is_admin:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Configuration.objects.filter(id=DECIMAL_ONE).update(
                            login_attempt_counter=DECIMAL_ZERO
                        )

                self.user = self.get_user(user.id)
                return self.user

    def get_user(self, user_id):
        if self.user is not None and self.user.id == user_id:
            return self.user
        user_or_none = UserModel.objects.filter(pk=user_id).only("id", "password", "is_staff", "is_superuser").order_by(
            '?').first()
        if user_or_none is not None:
            if not user_or_none.is_superuser:
                customer = Customer.objects.filter(user_id=user_or_none.id).only(
                    "id",
                    "is_active", "as_staff", "subscribe_to_email"
                ).order_by('?').first()
                if customer is not None:
                    if not customer.is_active:
                        user_or_none = None
                    elif customer.as_staff is not None:
                        staff = Staff.objects.filter(id=customer.as_staff_id).only(
                            "id",
                            "is_active", "is_reply_to_order_email", "is_reply_to_invoice_email",
                            "is_contributor", "is_coordinator"
                        ).order_by('?').first()
                        if staff is not None:
                            if not staff.is_active:
                                user_or_none = None
                            else:
                                user_or_none.is_order = staff.is_reply_to_order_email
                                user_or_none.is_invoice = staff.is_reply_to_invoice_email
                                user_or_none.is_contributor = staff.is_contributor
                                user_or_none.is_coordinator = staff.is_coordinator
                                user_or_none.is_customer = True
                                user_or_none.customer_id = customer.id
                                user_or_none.staff_id = staff.id
                                user_or_none.subscribe_to_email = True
                    else:
                        user_or_none.is_order = False
                        user_or_none.is_invoice = False
                        user_or_none.is_contributor = False
                        user_or_none.is_coordinator = False
                        user_or_none.is_customer = True
                        user_or_none.customer_id = customer.id
                        user_or_none.staff_id = None
                        user_or_none.subscribe_to_email = customer.subscribe_to_email

                else:
                    staff = Staff.objects.filter(user_id=user_or_none.id).only(
                        "id", "customer_responsible_id",
                        "is_active", "is_reply_to_order_email", "is_reply_to_invoice_email",
                        "is_contributor", "is_coordinator"
                    ).order_by('?').first()
                    if staff is not None:
                        if not staff.is_active:
                            user_or_none = None
                        else:
                            user_or_none.is_order = staff.is_reply_to_order_email
                            user_or_none.is_invoice = staff.is_reply_to_invoice_email
                            user_or_none.is_contributor = staff.is_contributor
                            user_or_none.is_coordinator = staff.is_coordinator
                            user_or_none.is_customer = False
                            user_or_none.customer_id = staff.customer_responsible_id
                            user_or_none.staff_id = staff.id
                            user_or_none.subscribe_to_email = True
                    else:
                        user_or_none = None
            else:
                user_or_none.is_order = True
                user_or_none.is_invoice = True
                user_or_none.is_contributor = True
                user_or_none.is_coordinator = True
                user_or_none.is_customer = False
                user_or_none.customer_id = None
                user_or_none.staff_id = None
                user_or_none.subscribe_to_email = True
        self.user = user_or_none
        return user_or_none
