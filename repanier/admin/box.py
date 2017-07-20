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

import repanier.apps
from repanier.models import Producer
from repanier.admin.fkey_choice_cache_mixin import ForeignKeyCacheMixin
from repanier.const import DECIMAL_ZERO, ORDER_GROUP, INVOICE_GROUP, \
    COORDINATION_GROUP, PERMANENCE_PLANNED, PERMANENCE_CLOSED, DECIMAL_MAX_STOCK
from repanier.models.box import BoxContent, Box
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.product import Product
from repanier.task import task_box
from repanier.tools import update_offer_item

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl


class BoxContentInlineFormSet(BaseInlineFormSet):
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



class BoxContentInlineForm(ModelForm):
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
        super(BoxContentInlineForm, self).__init__(*args, **kwargs)
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


class BoxContentInline(ForeignKeyCacheMixin, TabularInline):
    form = BoxContentInlineForm
    formset = BoxContentInlineFormSet
    model = BoxContent
    ordering = ("product",)
    if settings.DJANGO_SETTINGS_IS_MINIMALIST:
        fields = ['product', 'is_into_offer', 'content_quantity',
                  'get_calculated_customer_content_price']
    else:
        fields = ['product', 'is_into_offer', 'content_quantity', 'stock', 'limit_order_quantity_to_stock',
                  'get_calculated_customer_content_price']
    extra = 0
    fk_name = 'box'
    # The stock and limit_order_quantity_to_stock are read only to have only one place to update it : the product.
    readonly_fields = [
        'get_calculated_customer_content_price'
    ]
    has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self.has_add_or_delete_permission is None:
            try:
                parent_object = Box.objects.filter(
                    id=request.resolver_match.args[0]
                ).only(
                    "id").order_by('?').first()
                if parent_object is not None and OfferItemWoReceiver.objects.filter(
                    product=parent_object.id,
                    permanence__status__gt=PERMANENCE_PLANNED
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
            kwargs["queryset"] = Product.objects.filter(
                is_active=True,
                # A box may not include another box
                is_box=False,
                # We can't make any composition with producer preparing baskets on basis of our order.
                producer__invoice_by_basket=False,
                translations__language_code=translation.get_language()
            ).order_by(
                "producer__short_profile_name",
                "translations__long_name",
                "order_average_weight",
            )
        return super(BoxContentInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class BoxForm(TranslatableModelForm):
    calculated_customer_box_price = forms.DecimalField(
        label=_("calculated customer box price"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)
    calculated_box_deposit = forms.DecimalField(
        label=_("calculated box deposit"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)
    if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
        calculated_stock = forms.DecimalField(
            label=_("Calculated current stock"), max_digits=9, decimal_places=3, required=False, initial=DECIMAL_ZERO)

    def __init__(self, *args, **kwargs):
        super(BoxForm, self).__init__(*args, **kwargs)
        box = self.instance
        if box.id is not None:
            box_price, box_deposit = box.get_calculated_price()
            self.fields["calculated_customer_box_price"].initial = box_price
            self.fields["calculated_box_deposit"].initial = box_deposit
            if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
                self.fields["calculated_stock"].initial = box.get_calculated_stock()

        self.fields["calculated_customer_box_price"].disabled = True
        self.fields["calculated_box_deposit"].disabled = True
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            self.fields["calculated_stock"].disabled = True


class BoxAdmin(TranslatableAdmin):
    form = BoxForm
    model = Box

    list_display = (
        'is_into_offer', 'get_long_name', 'language_column',
    )
    list_display_links = ('get_long_name',)
    list_per_page = 16
    list_max_show_all = 16
    inlines = (BoxContentInline,)
    ordering = (
        'customer_unit_price',
        'unit_deposit',
        'translations__long_name',
    )
    search_fields = (
        'translations__long_name',
    )
    list_filter = (
       'is_into_offer',
       'is_active'
    )
    actions = [
        'flip_flop_select_for_offer_status',
        'duplicate_box'
    ]

    def has_delete_permission(self, request, box=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, box=None):
        return self.has_delete_permission(request, box)

    def get_list_display(self, request):
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            if settings.DJANGO_SETTINGS_IS_MINIMALIST:
                return ('get_is_into_offer', 'get_long_name', 'language_column')
            else:
                self.list_editable = ('stock',)
                return ('get_is_into_offer', 'get_long_name', 'language_column', 'stock')
        else:
            if settings.DJANGO_SETTINGS_IS_MINIMALIST:
                return ('get_is_into_offer', 'get_long_name')
            else:
                self.list_editable = ('stock',)
                return ('get_is_into_offer', 'get_long_name', 'stock')

    def flip_flop_select_for_offer_status(self, request, queryset):
        task_box.flip_flop_is_into_offer(queryset)

    flip_flop_select_for_offer_status.short_description = _(
        'flip_flop_select_for_offer_status for offer')

    def duplicate_box(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        box = queryset.first()
        if box is None:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            user_message, user_message_level = task_box.admin_duplicate(queryset)
            self.message_user(request, user_message, user_message_level)
            return
        return render(
            request,
            'repanier/confirm_admin_duplicate_box.html', {
                'sub_title'           : _("Please, confirm the action : duplicate box"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action'              : 'duplicate_box',
                'product'             : box,
            })

    duplicate_box.short_description = _('duplicate box')

    def get_fieldsets(self, request, box=None):
        if settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields_basic = [
                ('producer', 'long_name', 'picture2'),
                ('customer_unit_price', 'unit_deposit'),
                ('calculated_customer_box_price', 'calculated_box_deposit'),
            ]
        else:
            fields_basic = [
                ('producer', 'long_name', 'picture2'),
                ('stock', 'customer_unit_price', 'unit_deposit'),
                ('calculated_stock', 'calculated_customer_box_price', 'calculated_box_deposit'),
            ]
        fields_advanced_descriptions = [
            'placement',
            'offer_description',
        ]
        fields_advanced_options = [
            'vat_level',
            'is_into_offer',
            'is_active'
        ]
        fieldsets = (
            (None, {'fields': fields_basic}),
            (_('Advanced descriptions'), {'classes': ('collapse',), 'fields': fields_advanced_descriptions}),
            (_('Advanced options'), {'classes': ('collapse',), 'fields': fields_advanced_options})
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        return ['is_updated_on']

    def get_form(self, request, box=None, **kwargs):
        producer_queryset = Producer.objects.filter(id=repanier.apps.REPANIER_SETTINGS_GROUP_PRODUCER_ID)
        form = super(BoxAdmin, self).get_form(request, box, **kwargs)
        producer_field = form.base_fields["producer"]
        picture_field = form.base_fields["picture2"]
        # if hasattr(picture_field.widget, 'upload_to'):
        #     picture_field.widget.upload_to = "%s%s%s" % ("product", os_sep, "box")
        # return form
        vat_level_field = form.base_fields["vat_level"]
        producer_field.widget.can_add_related = False
        producer_field.widget.can_delete_related = False
        producer_field.widget.attrs['readonly'] = True
        # TODO : Make it dependent of the producer country
        vat_level_field.widget.choices = settings.LUT_VAT

        # One folder by producer for clarity
        if hasattr(picture_field.widget, 'upload_to'):
            picture_field.widget.upload_to = "box"

        producer_field.empty_label = None
        producer_field.queryset = producer_queryset

        if box is None:
            preserved_filters = request.GET.get('_changelist_filters', None)
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if 'is_active__exact' in param:
                    is_active_value = param['is_active__exact']
                    is_active_field = form.base_fields["is_active"]
                    if is_active_value == '0':
                        is_active_field.initial = False
                    else:
                        is_active_field.initial = True
                if 'is_into_offer__exact' in param:
                    is_into_offer_value = param['is_into_offer__exact']
                    is_into_offer_field = form.base_fields["is_into_offer"]
                    if is_into_offer_value == '0':
                        is_into_offer_field.initial = False
                    else:
                        is_into_offer_field.initial = True
        return form

    def get_queryset(self, request):
        qs = super(BoxAdmin, self).get_queryset(request)
        qs = qs.filter(
            is_box=True,
            translations__language_code=translation.get_language()
        )
        return qs

    def save_model(self, request, box, form, change):
        if box.is_into_offer and box.stock <= 0:
            box.stock = DECIMAL_MAX_STOCK
        super(BoxAdmin, self).save_model(request, box, form, change)
        update_offer_item(box)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, 'new_objects'): formset.new_objects = []
            if not hasattr(formset, 'changed_objects'): formset.changed_objects = []
            if not hasattr(formset, 'deleted_objects'): formset.deleted_objects = []
        box = form.instance
        try:
            formset = formsets[0]
            for box_content_form in formset:
                box_content = box_content_form.instance
                previous_product = box_content_form.fields['previous_product'].initial
                if previous_product is not None and previous_product != box_content.product:
                    # Delete the box_content because the product has changed
                    box_content_form.instance.delete()
                if box_content.product is not None:
                    if box_content.id is None:
                        box_content.box_id = box.id
                    if box_content_form.cleaned_data.get(DELETION_FIELD_NAME, False):
                        box_content_form.instance.delete()
                    elif box_content_form.has_changed():
                        box_content_form.instance.save()
        except IndexError:
            # No formset present in list admin, but well in detail admin
            pass
