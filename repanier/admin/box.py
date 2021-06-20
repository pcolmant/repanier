from urllib.parse import parse_qsl

from django import forms
from django.contrib import messages, admin
from django.contrib.admin import TabularInline
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.forms import ModelForm, BaseInlineFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from easy_select2 import Select2
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import (
    PERMANENCE_PLANNED,
    PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
    LUT_VAT,
    REPANIER_MONEY_ZERO,
)
from repanier.fields.RepanierMoneyField import FormRepanierMoneyField
from repanier.middleware import get_request_params
from repanier.models.box import BoxContent, Box
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.product import Product
from repanier.task import task_box
from repanier.tools import update_offer_item, get_repanier_template_name


class BoxContentInlineFormSet(BaseInlineFormSet):
    def clean(self):
        products = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                # This is not an empty form or a "to be deleted" form
                product = form.cleaned_data.get("product", None)
                if product is not None:
                    if product in products:
                        raise forms.ValidationError(
                            _("The same product can not be selected twice.")
                        )
                    else:
                        products.add(product)


class BoxContentInlineForm(ModelForm):
    previous_product = forms.ModelChoiceField(Product.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].widget.can_add_related = False
        self.fields["product"].widget.can_delete_related = False
        if self.instance.id is not None:
            self.fields["previous_product"].initial = self.instance.product

    class Meta:
        widgets = {"product": Select2(select2attrs={"width": "450px"})}


class BoxContentInline(InlineForeignKeyCacheMixin, TabularInline):
    form = BoxContentInlineForm
    formset = BoxContentInlineFormSet
    model = BoxContent
    ordering = ("product",)
    fields = [
        "product",
        "content_quantity",
        "get_calculated_customer_content_price",
    ]
    extra = 0
    fk_name = "box"
    readonly_fields = ["get_calculated_customer_content_price"]
    _has_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self._has_delete_permission is None:
            object_id = request.resolver_match.kwargs.get("object_id", None)
            if object_id:
                # Update
                parent_object = Box.objects.filter(id=object_id).only("id").first()
                if (
                    parent_object is not None
                    and OfferItemReadOnly.objects.filter(
                        product=parent_object.id,
                        permanence__status__gt=PERMANENCE_PLANNED,
                    ).exists()
                ):
                    self._has_delete_permission = False
                else:
                    self._has_delete_permission = True
            else:
                # Create
                self._has_delete_permission = True
        return self._has_delete_permission

    def has_add_permission(self, request, obj):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = (
                Product.objects.filter(
                    # Box products may be only bought via a box (is_into_offer = False but is_active=True)
                    is_active=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
                    # A box may not include another box
                    is_box=False,
                    # We can't make any composition with producer preparing baskets on basis of our order.
                    producer__invoice_by_basket=False,
                )
                .select_related("producer")
                .order_by(
                    "producer__short_profile_name",
                    "long_name_v2",
                    "order_average_weight",
                )
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class BoxForm(forms.ModelForm):
    calculated_customer_box_price = FormRepanierMoneyField(
        label=_("Customer rate per unit calculated"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    calculated_box_deposit = FormRepanierMoneyField(
        label=_("Calculated deposit per unit"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        box = self.instance
        if box.id is not None:
            box_price, box_deposit = box.get_calculated_price()
            self.fields["calculated_customer_box_price"].initial = box_price
            self.fields["calculated_box_deposit"].initial = box_deposit

        self.fields["calculated_customer_box_price"].disabled = True
        self.fields["calculated_box_deposit"].disabled = True

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        # if self.instance.id is None:
        #     if self.language_code != settings.LANGUAGE_CODE:
        #         # Important to also prohibit untranslated instance in settings.LANGUAGE_CODE
        #         self.add_error(
        #             "long_name_v2",
        #             _("Please define first a long_name in %(language)s")
        #             % {
        #                 "language": get_language_info(settings.LANGUAGE_CODE)[
        #                     "name_local"
        #                 ]
        #             },
        #         )


class BoxAdmin(admin.ModelAdmin):
    form = BoxForm
    model = Box

    list_display = (
        "get_html_is_into_offer",
        "__str__",
    )
    list_display_links = ("__str__",)
    list_per_page = 16
    list_max_show_all = 16
    inlines = (BoxContentInline,)
    ordering = (
        "customer_unit_price",
        "unit_deposit",
        "long_name_v2",
    )
    search_fields = ("long_name_v2",)
    list_filter = ("is_into_offer",)
    actions = [
        "duplicate_box",
    ]

    def has_delete_permission(self, request, box=None):
        user = request.user
        if user.is_order_manager or user.is_invoice_manager:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, box=None):
        return self.has_delete_permission(request, box)

    def duplicate_box(self, request, queryset):
        if "cancel" in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        box = queryset.first()
        if "apply" in request.POST:
            user_message, user_message_level = task_box.admin_duplicate(queryset)
            self.message_user(request, user_message, user_message_level)
            return
        template_name = get_repanier_template_name("admin/confirm_duplicate_box.html")
        return render(
            request,
            template_name,
            {
                "sub_title": _("Please, confirm the action : duplicate box."),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action": "duplicate_box",
                "product": box,
            },
        )

    duplicate_box.short_description = _("Duplicate")

    def get_fieldsets(self, request, box=None):
        fields_basic = [
            ("long_name_v2", "picture2"),
            (
                "customer_unit_price",
                "unit_deposit",
            ),
            (
                "calculated_customer_box_price",
                "calculated_box_deposit",
            ),
        ]
        fields_advanced_descriptions = [
            "offer_description_v2",
        ]
        fields_advanced_options = ["vat_level", "is_into_offer", "is_active"]
        fieldsets = (
            (None, {"fields": fields_basic}),
            (
                _("Advanced descriptions"),
                {"classes": ("collapse",), "fields": fields_advanced_descriptions},
            ),
            (
                _("Advanced options"),
                {"classes": ("collapse",), "fields": fields_advanced_options},
            ),
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        return ["is_updated_on"]

    def get_form(self, request, box=None, **kwargs):

        form = super().get_form(request, box, **kwargs)

        picture_field = form.base_fields["picture2"]
        vat_level_field = form.base_fields["vat_level"]
        # TODO : Make it dependent of the producer country
        vat_level_field.widget.choices = LUT_VAT

        if hasattr(picture_field.widget, "upload_to"):
            picture_field.widget.upload_to = "box"

        if box is None:
            query_params = get_request_params()
            is_active_value = query_params.get("is_active__exact", "0")
            is_active_field = form.base_fields["is_active"]
            if is_active_value == "0":
                is_active_field.initial = False
            else:
                is_active_field.initial = True
            is_into_offer_value = query_params.get("is_into_offer__exact", "0")
            is_into_offer_field = form.base_fields["is_into_offer"]
            if is_into_offer_value == "0":
                is_into_offer_field.initial = False
            else:
                is_into_offer_field.initial = True
        return form

    def get_html_is_into_offer(self, product):
        return product.get_html_admin_is_into_offer()

    get_html_is_into_offer.short_description = _("In offer")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(
            is_box=True,
        )
        return qs

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        if not actions:
            try:
                self.list_display.remove("action_checkbox")
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def save_model(self, request, box, form, change):
        super().save_model(request, box, form, change)
        update_offer_item(box)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, "new_objects"):
                formset.new_objects = []
            if not hasattr(formset, "changed_objects"):
                formset.changed_objects = []
            if not hasattr(formset, "deleted_objects"):
                formset.deleted_objects = []
        box = form.instance
        try:
            formset = formsets[0]
            for box_content_form in formset:
                box_content = box_content_form.instance
                previous_product = box_content_form.fields["previous_product"].initial
                if (
                    previous_product is not None
                    and previous_product != box_content.product
                ):
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
