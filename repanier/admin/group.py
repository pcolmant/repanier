# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.admin import CustomerWithUserDataAdmin


class GroupWithUserDataAdmin(CustomerWithUserDataAdmin):

    def get_list_display(self, request):
        if repanier.apps.REPANIER_SETTINGS_INVOICE:
            return ('short_basket_name', 'get_balance', 'long_basket_name', 'phone1', 'get_email',
                    'valid_email')
        else:
            return ('short_basket_name', 'long_basket_name', 'phone1', 'get_email',
                    'valid_email')

    def get_fieldsets(self, request, customer=None):
        fields_basic = [
            ('short_basket_name', 'long_basket_name', 'language'),
            ('email', 'email2',),
            ('phone1', 'phone2',),
        ]
        if customer is not None:
            fields_basic += [
                ('address', 'city', 'picture'),
                'memo',
            ]
        else:
            # Do not accept the picture because there is no customer.id for the "upload_to"
            fields_basic += [
                ('address', 'city'),
                'memo',
            ]
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields_basic += [
                'price_list_multiplier',
            ]
        if customer is not None:
            fields_basic += [
                'is_active',
                ('get_admin_balance', 'get_admin_date_balance'),
            ]
            fields_advanced = [
                'bank_account1',
                'bank_account2',
                'get_purchase'
            ]
        else:
            fields_basic += [
                'is_active',
            ]
            fields_advanced = [
                'bank_account1',
                'bank_account2',
            ]
        fieldsets = (
            (None, {'fields': fields_basic}),
            (_('Advanced options'), {'classes': ('collapse',), 'fields': fields_advanced})
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        if customer is not None:
            readonly_fields = [
                'get_admin_date_balance', 'get_admin_balance',
                'get_purchase',
            ]
            return readonly_fields
        return []

    def get_queryset(self, request):
        qs = super(CustomerWithUserDataAdmin, self).get_queryset(request)
        qs = qs.filter(
            is_group=True,
        )
        return qs