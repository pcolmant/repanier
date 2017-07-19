# -*- coding: utf-8
from __future__ import unicode_literals

from os import sep as os_sep

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin import TabularInline
from django.forms import ModelForm, BaseInlineFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.shortcuts import render
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from easy_select2 import Select2
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.admin.admin_filter import ProductFilterByProducer, ProductFilterByVatLevel
from repanier.admin.fkey_choice_cache_mixin import ForeignKeyCacheMixin
from repanier.const import DECIMAL_ZERO, ORDER_GROUP, INVOICE_GROUP, \
    COORDINATION_GROUP, PERMANENCE_PLANNED, PERMANENCE_CLOSED, EMPTY_STRING
from repanier.models import BoxContent
from repanier.models import Contract
from repanier.models import Customer
from repanier.models import OfferItemWoReceiver
from repanier.models import Producer
from repanier.models import Product
from repanier.task import task_contract
from repanier.tools import update_offer_item

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl


class ContractContentInlineFormSet(BaseInlineFormSet):
    def clean(self):
        products = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                # This is not an empty form or a "to be deleted" form
                product = form.cleaned_data.get('product', None)
                if product is not None:
                    if product in products:
                        raise forms.ValidationError(_('Duplicate product are not allowed.'))
                    else:
                        products.add(product)

    def get_queryset(self):
        return self.queryset.filter(
            product__translations__language_code=translation.get_language()
        ).order_by(
            "product__producer__short_profile_name",
            "product__translations__long_name",
            "product__order_average_weight",
        )


class ContractContentInlineForm(ModelForm):
    is_into_offer = forms.BooleanField(
        label=_("is_into_offer"), required=False, initial=True)
    previous_product = forms.ModelChoiceField(
        Product.objects.none(), required=False)
    if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
        stock = forms.DecimalField(
            label=_("Current stock"), max_digits=9, decimal_places=3, required=False, initial=DECIMAL_ZERO)
        limit_order_quantity_to_stock = forms.BooleanField(
            label=_("limit maximum order qty of the group to stock qty"), required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super(ContractContentInlineForm, self).__init__(*args, **kwargs)
        # TODO : Allow to add related products -> to solve : need to send the producer to the product form
        self.fields["product"].widget.can_add_related = False
        self.fields["product"].widget.can_delete_related = False
        if self.instance.id is not None:
            self.fields["is_into_offer"].initial = self.instance.product.is_into_offer
            self.fields["previous_product"].initial = self.instance.product
            if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
                self.fields["stock"].initial = self.instance.product.stock
                self.fields["limit_order_quantity_to_stock"].initial = self.instance.product.limit_order_quantity_to_stock

        self.fields["is_into_offer"].disabled = True
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            self.fields["stock"].disabled = True
            self.fields["limit_order_quantity_to_stock"].disabled = True

    class Meta:
        widgets = {
            'product': Select2(select2attrs={'width': '450px'})
        }


class ContractContentInline(ForeignKeyCacheMixin, TabularInline):
    form = ContractContentInlineForm
    formset = ContractContentInlineFormSet
    model = BoxContent
    ordering = ("product",)
    if settings.DJANGO_SETTINGS_IS_MINIMALIST:
        fields = ['product', 'is_into_offer', 'content_quantity',
                  'get_calculated_customer_content_price']
    else:
        fields = ['product', 'is_into_offer', 'content_quantity', 'stock', 'limit_order_quantity_to_stock',
                  'get_calculated_customer_content_price']
    extra = 0
    fk_name = 'contract'
    # The stock and limit_order_quantity_to_stock are read only to have only one place to update it : the product.
    readonly_fields = [
        'get_calculated_customer_content_price'
    ]
    has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self.has_add_or_delete_permission is None:
            try:
                parent_object = Contract.objects.filter(
                    id=request.resolver_match.args[0]
                ).only(
                    "id").order_by('?').first()
                if parent_object is not None and OfferItemWoReceiver.objects.filter(
                    product=parent_object.id,
                    permanence__status__gt=PERMANENCE_PLANNED,
                    permanence__status__lt=PERMANENCE_CLOSED
                ).order_by('?').exists():
                    self.has_add_or_delete_permission = False
                else:
                    self.has_add_or_delete_permission = True
            except:
                self.has_add_or_delete_permission = True
        return self.has_add_or_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            preserved_filters = request.GET.get('_changelist_filters', None)
            producer_id = None
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if 'producer' in param:
                    producer_id = param['producer']
            if producer_id is not None:
                kwargs["queryset"] = Product.objects.filter(
                    producer_id=producer_id,
                    is_active=True,
                    # A contract may not include another contract
                    is_box=False,
                    translations__language_code=translation.get_language()
                ).order_by(
                    "producer__short_profile_name",
                    "translations__long_name",
                    "order_average_weight",
                )
            else:
                kwargs["queryset"] = Product.objects.none()
        return super(ContractContentInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class ContractDataForm(TranslatableModelForm):
    calculated_customer_contract_price = forms.DecimalField(
        label=_("calculated customer contract price"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)
    calculated_contract_deposit = forms.DecimalField(
        label=_("calculated contract deposit"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)
    if settings.DJANGO_SETTINGS_IS_AMAP:
        customers = forms.ModelMultipleChoiceField(
            Customer.objects.filter(is_active=True),
            widget=admin.widgets.FilteredSelectMultiple(_('Customers'), False),
            required=False
        )
    if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
        calculated_stock = forms.DecimalField(
            label=_("Calculated current stock"), max_digits=9, decimal_places=3, required=False, initial=DECIMAL_ZERO)

    def __init__(self, *args, **kwargs):
        super(ContractDataForm, self).__init__(*args, **kwargs)
        contract = self.instance
        if contract.id is not None:
            contract_price, contract_deposit = contract.get_calculated_price()
            self.fields["calculated_customer_contract_price"].initial = contract_price
            self.fields["calculated_contract_deposit"].initial = contract_deposit
            if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
                self.fields["calculated_stock"].initial = contract.get_calculated_stock()

        self.fields["calculated_customer_contract_price"].disabled = True
        self.fields["calculated_contract_deposit"].disabled = True
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            self.fields["calculated_stock"].disabled = True

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        producer = self.cleaned_data.get("producer", None)
        if producer is None:
            self.add_error(
                'producer',
                _('Please select first a producer in the filter of previous screen'))
        else:
            reference = self.cleaned_data.get("reference", EMPTY_STRING)
            if reference:
                qs = Product.objects.filter(reference=reference, producer_id=producer.id).order_by('?')
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if qs.exists():
                    self.add_error(
                        "reference",
                        _('The reference is already used by %(product)s') % {'product': qs.first()})

    def save(self, *args, **kwargs):
        instance = super(ContractDataForm, self).save(*args, **kwargs)
        if settings.DJANGO_SETTINGS_IS_AMAP:
            if instance.id is not None:
                instance.customers.clear()
                instance.customers.add(*self.cleaned_data['customers'])
        return instance

class ContractAdmin(TranslatableAdmin):
    form = ContractDataForm
    model = Contract

    list_display = (
        'is_into_offer', 'get_long_name', 'language_column',
    )
    list_display_links = ('get_long_name',)
    list_per_page = 16
    list_max_show_all = 16
    inlines = (ContractContentInline,)
    ordering = (
        'customer_unit_price',
        'unit_deposit',
        'translations__long_name'
    )
    search_fields = ('translations__long_name',)
    list_filter = (
        'is_active',
        'is_into_offer',
        ProductFilterByProducer,
        ProductFilterByVatLevel
   )
    actions = [
        'flip_flop_select_for_offer_status',
        'duplicate_contract'
    ]

    def has_delete_permission(self, request, contract=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, contract=None):
        return self.has_delete_permission(request, contract)

    def get_list_display(self, request):
        # producer_id = sint(request.GET.get('producer', 0))
        # if producer_id != 0:
        #     producer_queryset = Producer.objects.filter(id=producer_id).order_by('?')
        #     producer = producer_queryset.first()
        # else:
        #     producer = None

        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
                self.list_editable = ('stock',)
                return ('producer', 'get_is_into_offer', 'get_long_name', 'language_column', 'stock')
            else:
                return ('producer', 'get_is_into_offer', 'get_long_name', 'language_column')
        else:
            if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
                self.list_editable = ('stock',)
                return ('producer', 'get_is_into_offer', 'get_long_name', 'stock')
            else:
                return ('producer', 'get_is_into_offer', 'get_long_name')

    def flip_flop_select_for_offer_status(self, request, queryset):
        task_contract.flip_flop_is_into_offer(queryset)

    flip_flop_select_for_offer_status.short_description = _(
        'flip_flop_select_for_offer_status for offer')

    def duplicate_contract(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        contract = queryset.first()
        if contract is None:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            user_message, user_message_level = task_contract.admin_duplicate(queryset)
            self.message_user(request, user_message, user_message_level)
            return
        return render(
            request,
            'repanier/confirm_admin_duplicate_contract.html', {
                'sub_title'           : _("Please, confirm the action : duplicate contract"),
                'action_checkcontract_name': admin.ACTION_CHECKBOX_NAME,
                'action'              : 'duplicate_contract',
                'product'             : contract,
            })

    duplicate_contract.short_description = _('duplicate contract')

    def get_fieldsets(self, request, contract=None):
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields_basic = [
                ('producer', 'long_name', 'picture2'),
                ('calculated_stock', 'calculated_customer_contract_price', 'calculated_contract_deposit'),
                ('stock', 'customer_unit_price', 'unit_deposit'),
            ]
        else:
            fields_basic = [
                ('producer', 'long_name', 'picture2'),
                ('calculated_customer_contract_price', 'calculated_contract_deposit'),
                ('customer_unit_price', 'unit_deposit'),
            ]
        if settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields_advanced_descriptions = [
                'placement',
                'offer_description',
            ]
            fields_advanced_options = [
                'vat_level',
                ('is_into_offer', 'is_active')
            ]
        else:
            fields_advanced_descriptions = [
                'placement',
                'offer_description',
            ]
            fields_advanced_options = [
                ('reference', 'vat_level'),
                ('is_into_offer', 'is_active')
            ]
        fieldsets = (
            (None, {'fields': fields_basic}),
            (_('Advanced descriptions'), {'classes': ('collapse',), 'fields': fields_advanced_descriptions}),
            (_('Advanced options'), {'classes': ('collapse',), 'fields': fields_advanced_options})
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        return ['is_updated_on']

    def get_form(self, request, contract=None, **kwargs):
        is_active_value = None
        is_into_offer_value = None
        producer_queryset = Producer.objects.none()
        if contract is not None:
            producer_queryset = Producer.objects.filter(id=contract.producer_id).order_by('?')
        else:
            preserved_filters = request.GET.get('_changelist_filters', None)
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if 'producer' in param:
                    producer_id = param['producer']
                    if producer_id:
                        producer_queryset = Producer.objects.filter(id=producer_id).order_by('?')
                if 'is_active__exact' in param:
                    is_active_value = param['is_active__exact']
                if 'is_into_offer__exact' in param:
                    is_into_offer_value = param['is_into_offer__exact']
        producer = producer_queryset.first()

        form = super(ContractAdmin, self).get_form(request, contract, **kwargs)

        producer_field = form.base_fields["producer"]
        picture_field = form.base_fields["picture2"]
        vat_level_field = form.base_fields["vat_level"]
        producer_field.widget.can_add_related = False
        producer_field.widget.can_delete_related = False
        producer_field.widget.attrs['readonly'] = True
        # TODO : Make it dependent of the producer country
        vat_level_field.widget.choices = settings.LUT_VAT

        if producer is not None:
            # One folder by producer for clarity
            if hasattr(picture_field.widget, 'upload_to'):
                picture_field.widget.upload_to = "%s%s%d" % ("contract", os_sep, producer.id)

        if contract is not None:
            producer_field.empty_label = None
            producer_field.queryset = producer_queryset
        else:
            if producer is None:
                producer_field.choices = [('-1', _("Please select first a producer in the filter of previous screen"))]
                producer_field.disabled = True
            else:
                producer_field.empty_label = None
                producer_field.queryset = producer_queryset
            if is_active_value:
                is_active_field = form.base_fields["is_active"]
                if is_active_value == '0':
                    is_active_field.initial = False
                else:
                    is_active_field.initial = True
            if is_into_offer_value:
                is_into_offer_field = form.base_fields["is_into_offer"]
                if is_into_offer_value == '0':
                    is_into_offer_field.initial = False
                else:
                    is_into_offer_field.initial = True
        return form

    def get_queryset(self, request):
        qs = super(ContractAdmin, self).get_queryset(request)
        qs = qs.filter(
            is_box=True,
            translations__language_code=translation.get_language()
        )
        return qs

    def save_model(self, request, contract, form, change):
        super(ContractAdmin, self).save_model(request, contract, form, change)
        update_offer_item(contract)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, 'new_objects'): formset.new_objects = []
            if not hasattr(formset, 'changed_objects'): formset.changed_objects = []
            if not hasattr(formset, 'deleted_objects'): formset.deleted_objects = []
        contract = form.instance
        try:
            formset = formsets[0]
            for contract_content_form in formset:
                contract_content = contract_content_form.instance
                previous_product = contract_content_form.fields['previous_product'].initial
                if previous_product is not None and previous_product != contract_content.product:
                    # Delete the contract_content because the product has changed
                    contract_content_form.instance.delete()
                if contract_content.product is not None:
                    if contract_content.id is None:
                        contract_content.contract_id = contract.id
                    if contract_content_form.cleaned_data.get(DELETION_FIELD_NAME, False):
                        contract_content_form.instance.delete()
                    elif contract_content_form.has_changed():
                        contract_content_form.instance.save()
        except IndexError:
            # No formset present in list admin, but well in detail admin
            pass
