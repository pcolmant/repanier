# -*- coding: utf-8
from __future__ import unicode_literals
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import F
from const import DECIMAL_ZERO, DECIMAL_ONE, DECIMAL_TWO
from email.email_alert import send_error
from models import Customer, Staff, Configuration
from django.utils.translation import ugettext_lazy as _
from tools import sint


class RepanierCustomBackend(ModelBackend):

    user = None

    def __init__(self, *args, **kwargs):
        super(RepanierCustomBackend, self).__init__(*args, **kwargs)

    def authenticate(self, username=None, password=None, confirm=None, **kwargs):
        self.user = None
        # try:
        user_username = User.objects.filter(username=username[:30]).order_by().first()
        if user_username is None:
            user_username = User.objects.filter(email=username).order_by().first()
            if user_username is not None:
                username = user_username.username
        if user_username is not None:
            staff = Staff.objects.filter(
                user=user_username, is_active=True
            ).order_by().first()
        else:
            staff = None
        if staff is not None:
            customer = staff.customer_responsible
        else:
            customer = Customer.objects.filter(
                user=user_username, is_active=True
            ).order_by().first()
        user_or_none = super(RepanierCustomBackend, self).authenticate(username, password)
        if user_or_none is not None:
            if user_or_none.is_superuser and customer is not None:
                # a customer or a staff member may not be superuser
                user_or_none = None
        if customer is not None:
            # This is a customer or staff member
            login_attempt_counter = customer.login_attempt_counter
            if login_attempt_counter > DECIMAL_ONE:
                if confirm is None:
                    confirm = ""
                else:
                    confirm = str(sint(confirm))
                phone_digits = ""
                i = 0
                phone1 = customer.phone1
                while i < len(phone1):
                    if '0' <= phone1[i] <= '9':
                        phone_digits += phone1[i]
                    i += 1
                if confirm is not None and len(confirm) >= 4 and phone_digits.endswith(confirm):
                    pass
                else:
                    # Sorry you may no log in because the four last digits of your phone are not given
                    user_or_none = None
            if user_or_none is None:
                if login_attempt_counter < 50:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=F('login_attempt_counter') +
                        DECIMAL_ONE
                    )
                if login_attempt_counter > DECIMAL_ONE:
                    raise forms.ValidationError(
                        _("Too many attempt."),
                        code='attempt',
                    )
            else:
                if login_attempt_counter < 10:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=DECIMAL_ZERO
                    )
                else:
                    Customer.objects.filter(id=customer.id).update(
                        may_order=False
                    )
                    Staff.objects.filter(customer_responsible_id=customer.id).update(
                        is_active=False
                    )
        elif user_username is not None and user_username.is_superuser:
            # This is the superuser. One and only one superuser should be defined.
            login_attempt_counter = Configuration.objects.filter(
                id=DECIMAL_ONE
            ).only(
                'login_attempt_counter'
            ).first().login_attempt_counter
            if user_or_none is None:
                # Failed to log in
                if login_attempt_counter < 50:
                    Configuration.objects.filter(id=DECIMAL_ONE).update(
                        login_attempt_counter=F('login_attempt_counter') +
                        DECIMAL_ONE
                    )
                if login_attempt_counter > DECIMAL_ONE:
                    send_error("Login attempt failed : %s" % username)
            else:
                # Log in successful
                if login_attempt_counter > 6:
                    # Sorry you may no log in because of too many failed log in attempt
                    user_or_none = None
                else:
                    Configuration.objects.filter(id=DECIMAL_ONE).update(
                        login_attempt_counter=DECIMAL_ZERO
                    )
                    if login_attempt_counter > DECIMAL_TWO:
                        send_error("Login attempt success : %s" % username)
        # except:
        #     user_or_none = None
        self.user = user_or_none
        # if user_or_none :
        # print ('Authenticate user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
        # else:
        # print ('Authenticate user : not defined')
        return user_or_none

    def get_user(self, user_id):
        if self.user is not None and self.user.id == user_id:
            return self.user
        user_or_none = User.objects.filter(pk=user_id).only("id", "is_superuser", "is_staff").order_by().first()
        if user_or_none is not None and not user_or_none.is_superuser:
            a = Customer.objects.filter(user_id=user_or_none.id)\
                .only("is_active").order_by().first()
            if a is not None:
                if not a.is_active:
                    user_or_none = None
            else:
                a = Staff.objects.filter(user_id=user_or_none.id)\
                    .only("is_active").order_by().first()
                if a is not None:
                    if not a.is_active:
                        user_or_none = None
                else:
                    user_or_none = None
        self.user = user_or_none
        # if user_or_none :
        # print ('Get user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
        # else:
        # print ('Get user : not defined')
        return user_or_none