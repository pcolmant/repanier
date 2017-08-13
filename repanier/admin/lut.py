# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.conf import settings
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
    COORDINATION_GROUP, DECIMAL_ONE, ONE_LEVEL_DEPTH, TWO_LEVEL_DEPTH
from repanier.models.customer import Customer
from repanier.models.lut import LUT_DeliveryPoint
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard


class LUTDataForm(TranslatableModelForm):

    def __init__(self, *args, **kwargs):
        super(LUTDataForm, self).__init__(*args, **kwargs)

    # def clean(self):
    #     if any(self.errors):
    #         # Don't bother validating the formset unless each form is valid on its own
    #         return
    #
    #     parent = self.cleaned_data["parent"]
    #     if parent is not None:
    #         # Get model name
    #         # str(type(self.instance)) = "<class 'repanier.models.lut.LUT_DepartmentForCustomer'>"
    #         # .rsplit('.', 1)[1][:-2] --> "LUT_DepartmentForCustomer"
    #         admin_model_name = str(type(self.instance)).rsplit('.', 1)[1][:-2]
    #         admin_model = apps.get_model("repanier", admin_model_name)
    #         if admin_model.objects.filter(**{"translations__short_name": parent, "level__gt": 0}).order_by('?').exists():
    #             self.add_error(
    #                 'parent',
    #                 _('Only two levels are allowed.'))


class LUTAdmin(TranslatableAdmin, DjangoMpttAdmin):
    form = LUTDataForm
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    mptt_level_indent = 20
    mptt_indent_field = "short_name"
    mptt_level_limit = None
    _has_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self._has_delete_permission is None:
            if request.user.groups.filter(
                    name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
                self._has_delete_permission = True
            else:
                self._has_delete_permission = False
        return self._has_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Overrides parent class formfield_for_foreignkey method."""
        # If mptt_level_limit is set filter levels depending on the limit.
        if db_field.name == "parent" and self.mptt_level_limit is not None:
            kwargs["queryset"] = self.model.objects.filter(level__lt=self.mptt_level_limit)
        return super(LUTAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def do_move(self, instance, position, target_instance):
        """
        Overwritting parent do_move method to disallow users to exceed the self.mptt_level_limit value when drag and
        dropping items.
        """
        if self.mptt_level_limit is not None:
            if position == "inside":
                if target_instance.level >= self.mptt_level_limit:
                    raise Exception(_(u'The maximum level for this model is %d' % self.mptt_level_limit))
            else:
                if target_instance.level > self.mptt_level_limit:
                    raise Exception(_(u'The maximum level for this model is %d' % self.mptt_level_limit))
        super(LUTAdmin, self).do_move(instance, position, target_instance)


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
        Customer.objects.filter(is_group=True, is_active=True),
        label=_("customer_responsible"),
        help_text=_("Invoices are sent to this consumer who is responsible for collecting the payments."),
        required=False)

    def __init__(self, *args, **kwargs):
        super(LUTDeliveryPointDataForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['customers'].initial = self.instance.customer_set.all()
            self.fields['customers'].queryset = Customer.objects.filter(
                Q(may_order=True, delivery_point__isnull=True) | Q(delivery_point_id=self.instance.id)
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
                # CustomerInvoice.customer_charged
                Customer.objects.filter(delivery_point_id=self.instance.id).update(price_list_multiplier=DECIMAL_ONE)

        return instance

    class Meta:
        model = LUT_DeliveryPoint
        fields = "__all__"
        exclude = ('description',)
        widgets = {
            'customer_responsible': apply_select2(forms.Select),
        }


class LUTDeliveryPointAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH
    form = LUTDeliveryPointDataForm

    def get_fields(self, request, obj=None):
        fields = [
            'short_name',
            'is_active',
            'customer_responsible',
            'inform_customer_responsible',
            # 'price_list_multiplier',
            'transport',
            'min_transport'
        ]
        if obj is not None:
            fields += [
                'customers'
            ]
        return fields


class LUTDepartmentForCustomerAdmin(LUTAdmin):
    mptt_level_limit = TWO_LEVEL_DEPTH

    fields = [
        'parent',
        'short_name',
        'is_active',
    ]


class PermanenceBoardInlineForm(forms.ModelForm):
    class Meta:
        widgets = {
            'permanence': apply_select2(forms.Select),
            'customer'  : apply_select2(forms.Select),
        }


class PermanenceBoardInline(ForeignKeyCacheMixin, TabularInline):
    mptt_level_limit = ONE_LEVEL_DEPTH
    form = PermanenceBoardInlineForm

    model = PermanenceBoard
    fields = [
        'permanence',
        'customer'
    ]
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
    mptt_level_limit = TWO_LEVEL_DEPTH

    fields = [
        'short_name',
        'customers_may_register',
        'is_counted_as_participation',
        'description',
        'is_active',
    ]

    if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
        inlines = [PermanenceBoardInline]
