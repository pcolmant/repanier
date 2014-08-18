# -*- coding: utf-8 -*-
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class RepanierCustomBackend(ModelBackend):
    def authenticate(self, **credentials):
        user_or_none = None
        try:
            user_or_none = super(RepanierCustomBackend, self).authenticate(**credentials)
            if user_or_none and not user_or_none.is_superuser:
                try:
                    a = user_or_none.customer
                    if not a.is_active:
                        user_or_none = None
                except:
                    try:
                        a = user_or_none.staff
                        if not a.is_active:
                            user_or_none = None
                    except:
                        user_or_none = None
        except Exception as e:
            user_or_none = None
        # if user_or_none :
        # print ('Authenticate user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
        # else:
        # print ('Authenticate user : not defined')
        return user_or_none

    def get_user(self, user_id):
        user_or_none = None
        try:
            user_or_none = User.objects.get(pk=user_id)
            if user_or_none and not user_or_none.is_superuser:
                try:
                    a = user_or_none.customer
                    if not a.is_active:
                        user_or_none = None
                except:
                    try:
                        a = user_or_none.staff
                        if not a.is_active:
                            user_or_none = None
                    except:
                        user_or_none = None
        except:
            user_or_none = None
        # if user_or_none :
        # print ('Get user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
        # else:
        # print ('Get user : not defined')
        return user_or_none