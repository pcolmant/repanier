# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.admin.admin_filter import ContractFilterByProducer
from repanier.const import ORDER_GROUP, INVOICE_GROUP, \
    COORDINATION_GROUP
from repanier.models import Contract
from repanier.models import Customer
from repanier.models import Producer

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl


class ContractDataForm(TranslatableModelForm):
    producers = forms.ModelMultipleChoiceField(
        Producer.objects.filter(is_active=True),
        label=_('Producers'),
        widget=admin.widgets.FilteredSelectMultiple(_('Producers'), False),
        required=True
    )


class ContractAdmin(TranslatableAdmin):
    form = ContractDataForm
    model = Contract

    list_display = ('get_contract_admin_display',)
    list_display_links = ('get_contract_admin_display',)
    list_filter = [
        'is_active',
        ContractFilterByProducer
    ]
    date_hierarchy = 'first_permanence_date'
    list_per_page = 16
    list_max_show_all = 16
    ordering = (
        'first_permanence_date',
    )
    search_fields = ('translations__long_name',)
    _has_delete_permission = None

    def has_delete_permission(self, request, contract=None):
        if self._has_delete_permission is None:
            if request.user.groups.filter(
                    name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
                self._has_delete_permission = settings.DJANGO_SETTINGS_CONTRACT
            else:
                self._has_delete_permission = False
        return self._has_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, contract=None):
        return self.has_delete_permission(request, contract)

    def get_list_display(self, request):
        list_display = [
            'get_contract_admin_display', 'get_producers'
        ]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += [
                'language_column',
            ]
        return list_display

    def get_fieldsets(self, request, contract=None):
        fields_basic = [
            ('long_name', 'picture2'),
            'first_permanence_date',
            'recurrences'
        ]
        if contract is not None:
            fields_basic += [
                'get_dates'
            ]
        fields_basic += [
            'producers',
            'customers',
            'is_active'
        ]
        fieldsets = (
            (None, {'fields': fields_basic}),
        )
        return fieldsets

    def get_readonly_fields(self, request, contract=None):
        if contract is not None:
            return ['get_dates', 'customers']
        else:
            return ['customers']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "customers":
            kwargs["queryset"] = Customer.objects.filter(may_order=True, represent_this_buyinggroup=False)

    def get_queryset(self, request):
        qs = super(ContractAdmin, self).get_queryset(request)
        qs = qs.filter(
            translations__language_code=translation.get_language()
        )
        return qs