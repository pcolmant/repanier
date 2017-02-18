# -*- coding: utf-8
from __future__ import unicode_literals

import re
from django import forms
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.db.models import F, Q
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from const import DECIMAL_ZERO, DECIMAL_ONE, DECIMAL_THREE
from models import Customer, Staff, Configuration

ACTION_RE = re.compile(r"(?<=\.)(.*?)(?=\_)")


class RepanierCustomBackend(ModelBackend):
    user = None

    def __init__(self, *args, **kwargs):
        super(RepanierCustomBackend, self).__init__()

    def authenticate(self, username=None, password=None, confirm=None, **kwargs):
        self.user = None
        user_username = User.objects.filter(Q(username=username[:30]) | Q(email=username)).order_by('?').first()
        admin = staff = customer = None
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
                    login_attempt_counter = Configuration.objects.filter(
                        id=DECIMAL_ONE
                    ).only(
                        'login_attempt_counter'
                    ).first().login_attempt_counter
                else:
                    admin = True
                    login_attempt_counter = staff.login_attempt_counter
            else:
                login_attempt_counter = customer.login_attempt_counter

        user_or_none = super(RepanierCustomBackend, self).authenticate(username, password)

        if user_or_none is None:
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
                elif admin is not None:
                    Configuration.objects.filter(id=DECIMAL_ONE).update(
                        login_attempt_counter=F('login_attempt_counter') +
                                              DECIMAL_ONE
                    )
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "Because you tried to log in too many time without success, you must now first reset your password."),
                    code='attempt',
                )
        else:
            if login_attempt_counter > DECIMAL_THREE:
                raise forms.ValidationError(
                    _(
                        "Because you tried to log in too many time without success, you must now first reset your password."),
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
                elif admin is not None:
                    if login_attempt_counter > DECIMAL_ZERO:
                        Configuration.objects.filter(id=DECIMAL_ONE).update(
                            login_attempt_counter=DECIMAL_ZERO
                        )

        self.user = user_or_none
        return user_or_none

    def get_user(self, user_id):
        if self.user is not None and self.user.id == user_id:
            return self.user
        user_or_none = User.objects.filter(pk=user_id).only("id", "is_superuser").order_by('?').first()
        if user_or_none is not None and not user_or_none.is_superuser:
            a = Customer.objects.filter(user_id=user_or_none.id) \
                .only("is_active").order_by('?').first()
            if a is not None:
                if not a.is_active:
                    user_or_none = None
            else:
                a = Staff.objects.filter(user_id=user_or_none.id) \
                    .only("is_active").order_by('?').first()
                if a is not None:
                    if not a.is_active:
                        user_or_none = None
                else:
                    user_or_none = None
        self.user = user_or_none
        return user_or_none

    # def has_perm(self, user_obj, perm, obj=None):
    #     # if perm.startswith('dummy_cmsplugin_cascade'):
    #     if perm.startswith('cascade_dummy'):
    #         codename = perm.split('.', 1)[1]
    #         if not Permission.objects.filter(codename=codename).exists():
    #             perm_splitted = codename.split('_', 1)
    #             # codename = '%s_bootstrapcontainerpluginmodel' % perm_splitted[0]
    #             codename = '%s_cascadeelement' % perm_splitted[0]
    #         perm = 'cmsplugin_cascade.%s' % codename
    #     return super(RepanierCustomBackend, self).has_perm(user_obj, perm, obj)

