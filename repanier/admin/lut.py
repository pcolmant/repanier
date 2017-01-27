# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.contrib import admin
from django.contrib.admin import TabularInline
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django_mptt_admin.admin import DjangoMpttAdmin
from easy_select2 import apply_select2
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.admin.fkey_choice_cache_mixin import ForeignKeyCacheMixin
from repanier.const import PERMANENCE_CLOSED, ORDER_GROUP, INVOICE_GROUP, \
    COORDINATION_GROUP, DECIMAL_ONE
from repanier.models import PermanenceBoard, Customer, Permanence, LUT_DeliveryPoint


class LUTAdmin(TranslatableAdmin, DjangoMpttAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    mptt_level_indent = 20
    mptt_indent_field = "short_name"

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_add_permission(self, request):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False


class LUTProductionModeAdmin(LUTAdmin):
    exclude = ('picture', 'description')


class LUTDeliveryPointDataForm(TranslatableModelForm):
    customers = forms.ModelMultipleChoiceField(
        Customer.objects.filter(
            may_order=True, delivery_point__isnull=True,
            represent_this_buyinggroup=False
        ),
        widget=admin.widgets.FilteredSelectMultiple(_('Members'), False),
        required=False
    )
    customer_responsible = forms.ModelChoiceField(
        Customer.objects.filter(
            may_order=False, is_active=True, delivery_point__isnull=True,
            represent_this_buyinggroup=False
        ),
        label=_("customer_responsible"),
        help_text=_("Invoices are sent to this consumer who is responsible for collecting the payments."),
        required=False)

    def __init__(self, *args, **kwargs):
        super(LUTDeliveryPointDataForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['customers'].initial = self.instance.customer_set.all()
            self.fields['customers'].queryset = Customer.objects.filter(
                Q(may_order=True, delivery_point__isnull=True) | Q(delivery_point=self.instance.id)
            ).distinct()

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        customer_responsible = self.cleaned_data.get("customer_responsible", None)
        if customer_responsible is not None:
            for delivery_point in LUT_DeliveryPoint.objects.filter(
                    customer_responsible=customer_responsible
            ).order_by('?'):
                if delivery_point.id != self.instance.id:
                    self.add_error(
                        "customer_responsible",
                        _(
                            'This customer is already responsible of another delivery point (%(delivery_point)s). A customer may be responsible of maximum one delivery point.') % {
                            'delivery_point': delivery_point,})


    def save(self, *args, **kwargs):
        instance = super(LUTDeliveryPointDataForm, self).save(*args, **kwargs)
        if instance.id is not None:
            instance.closed_group = len(self.cleaned_data['customers']) > 0
            instance.customer_set = self.cleaned_data['customers']
            self.instance.save()
            if instance.closed_group and instance.customer_responsible is not None:
                # If this is a closed group with a customer_responsible, the customer.price_list_multiplier must be set to ONE
                # Invoices are sent to the consumer responsible of the group who is
                # also responsible for collecting the payments.
                # The LUT_DeliveryPoint.price_list_multiplier will be used when invoicing the consumer responsible
                # The link between the customer invoice and this customer responsible is made with
                # CustomerInvoice.customer_who_pays
                Customer.objects.filter(delivery_point=self.instance.id).update(price_list_multiplier=DECIMAL_ONE)

        return instance

    class Meta:
        model = LUT_DeliveryPoint
        fields = "__all__"
        exclude = ('description',)
        widgets = {
            'customer_responsible': apply_select2(forms.Select),
        }


class LUTDeliveryPointAdmin(LUTAdmin):
    form = LUTDeliveryPointDataForm

    def get_fields(self, request, obj=None):
        if obj is None:
            return [('parent',), 'is_active', 'short_name', 'customer_responsible', 'price_list_multiplier', 'transport', 'min_transport']
        return [('parent',), 'is_active', 'short_name', 'customer_responsible', 'price_list_multiplier', 'transport', 'min_transport', 'customers']


class LUTDepartmentForCustomerAdmin(LUTAdmin):
    exclude = ('description',)


class PermanenceBoardInlineForm(forms.ModelForm):
    class Meta:
        widgets = {
            'permanence': apply_select2(forms.Select),
            'customer'  : apply_select2(forms.Select),
        }


class PermanenceBoardInline(ForeignKeyCacheMixin, TabularInline):
    form = PermanenceBoardInlineForm

    model = PermanenceBoard
    fields = ['permanence', 'customer']
    extra = 1

    def get_queryset(self, request):
        return super(PermanenceBoardInline, self).get_queryset(request).filter(
            permanence__status__lte=PERMANENCE_CLOSED)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence":
            kwargs["queryset"] = Permanence.objects.filter(status__lte=PERMANENCE_CLOSED).order_by("permanence_date")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class LUTPermanenceRoleAdmin(LUTAdmin):
    inlines = [PermanenceBoardInline]

    def get_fields(self, request, obj=None):
        return [
            ('parent',),
            ('is_active', 'customers_may_register', 'is_counted_as_participation'),
            ('short_name',),
            ('description',)
        ]
