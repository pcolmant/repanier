from django import forms
from django.contrib import admin
from django.db import transaction
from django.forms import BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _
from easy_select2 import Select2

from repanier.admin.admin_filter import (
    PurchaseFilterByProducerForThisPermanence,
    ProductFilterByDepartmentForThisProducer,
    OfferItemFilter,
    OfferItemSendFilterByPermanence,
)
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import *
from repanier.fields.RepanierMoneyField import FormMoneyField
from repanier.models import LUT_DepartmentForCustomer
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.tools import rule_of_3_reload_purchase


class OfferItemPurchaseSendInlineFormSet(BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        qty_invoiced = DECIMAL_ZERO
        values = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                # This is not an empty form or a "to be deleted" form
                value = form.cleaned_data.get("customer", None)
                if value is not None:
                    if value in values:
                        raise forms.ValidationError(
                            _("The same customer can not be selected twice.")
                        )
                    else:
                        values.add(value)
                    qty_invoiced += form.cleaned_data.get(
                        "quantity_invoiced", DECIMAL_ZERO
                    ).quantize(THREE_DECIMALS)


class OfferItemPurchaseSendInlineForm(forms.ModelForm):
    previous_purchase_price = FormMoneyField(
        label=_("Purchase price"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    previous_customer = forms.ModelChoiceField(Customer.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super(OfferItemPurchaseSendInlineForm, self).__init__(*args, **kwargs)
        if self.instance.id is not None:
            self.fields[
                "previous_purchase_price"
            ].initial = self.instance.purchase_price
            self.fields["previous_customer"].initial = self.instance.customer
            self.fields["customer"].widget.can_add_related = False
            self.fields["customer"].widget.can_delete_related = False
            if self.instance.offer_item.order_unit not in [
                PRODUCT_ORDER_UNIT_KG,
                PRODUCT_ORDER_UNIT_PC_KG,
            ]:
                self.fields["purchase_price"].widget.attrs["readonly"] = True

    class Meta:
        widgets = {"customer": Select2(select2attrs={"width": "450px"})}


class OfferItemPurchaseSendInline(InlineForeignKeyCacheMixin, admin.TabularInline):
    form = OfferItemPurchaseSendInlineForm
    formset = OfferItemPurchaseSendInlineFormSet
    model = Purchase
    fields = ["customer", "quantity_invoiced", "purchase_price", "comment"]
    extra = 0
    fk_name = "offer_item"

    def has_delete_permission(self, request, obj=None):
        # To delete the purchase, set the quantity to zero
        return False

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        return super(OfferItemPurchaseSendInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def get_queryset(self, request):
        qs = super(OfferItemPurchaseSendInline, self).get_queryset(request)
        return qs.filter(is_box_content=False)


class OfferItemSendDataForm(forms.ModelForm):
    offer_purchase_price = FormMoneyField(
        label=_("Producer amount invoiced"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    rule_of_3 = forms.BooleanField(
        label=_("Apply the rule of 3"), required=False, initial=False
    )
    qty_delivered = forms.DecimalField(
        min_value=DECIMAL_ZERO,
        label=_("Stock delivered"),
        max_digits=9,
        decimal_places=4,
        required=False,
        initial=0,
    )
    qty_prepared = forms.DecimalField(
        label=_("Qty prepared"),
        max_digits=9,
        decimal_places=4,
        required=False,
        initial=0,
    )
    previous_producer_unit_price = FormMoneyField(
        max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO
    )
    previous_customer_unit_price = FormMoneyField(
        max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO
    )
    previous_unit_deposit = FormMoneyField(
        max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO
    )

    def __init__(self, *args, **kwargs):
        super(OfferItemSendDataForm, self).__init__(*args, **kwargs)
        offer_item = self.instance
        self.fields[
            "previous_producer_unit_price"
        ].initial = offer_item.producer_unit_price
        self.fields[
            "previous_customer_unit_price"
        ].initial = offer_item.customer_unit_price
        self.fields["previous_unit_deposit"].initial = offer_item.unit_deposit
        self.fields["offer_purchase_price"].initial = offer_item.total_purchase_with_tax
        if offer_item.wrapped or offer_item.order_unit not in [
            PRODUCT_ORDER_UNIT_KG,
            PRODUCT_ORDER_UNIT_PC_KG,
        ]:
            self.fields["offer_purchase_price"].widget.attrs["readonly"] = True
            self.fields["offer_purchase_price"].disabled = True
        if offer_item.producer_price_are_wo_vat:
            self.fields["offer_purchase_price"].label = _(
                "Producer amount invoiced wo VAT"
            )

    def get_readonly_fields(self, request, obj=None):
        if obj.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            return ["product"]
        else:
            return ["offer_purchase_price", "product"]

    def save(self, *args, **kwargs):
        offer_item = super(OfferItemSendDataForm, self).save(*args, **kwargs)
        if offer_item.id is not None:
            previous_producer_unit_price = self.cleaned_data[
                "previous_producer_unit_price"
            ]
            previous_customer_unit_price = self.cleaned_data.get(
                "previous_customer_unit_price", DECIMAL_ZERO
            )
            previous_unit_deposit = self.cleaned_data["previous_unit_deposit"]
            producer_unit_price = self.cleaned_data["producer_unit_price"]
            customer_unit_price = self.cleaned_data.get(
                "customer_unit_price", offer_item.customer_unit_price
            )
            unit_deposit = self.cleaned_data["unit_deposit"]

            if (
                previous_producer_unit_price != producer_unit_price
                or previous_customer_unit_price != customer_unit_price
                or previous_unit_deposit != unit_deposit
            ):
                offer_item.producer_unit_price = producer_unit_price
                offer_item.customer_unit_price = customer_unit_price
                offer_item.unit_deposit = unit_deposit
                # The previous save is called with "commit=False" or we need to update the producer
                # to recalculate the offer item prices. So a call to self.instance.save() is required
                offer_item.save()
                # Important : linked with vvvv
        return offer_item


class OfferItemSendAdmin(admin.ModelAdmin):
    form = OfferItemSendDataForm
    inlines = [OfferItemPurchaseSendInline]
    search_fields = ("long_name_v2",)
    list_display = [
        "department_for_customer",
        "producer",
        "get_long_name_with_producer_price",
        "get_html_producer_qty_stock_invoiced",
        "get_html_producer_price_purchased",
    ]
    list_display_links = ("get_long_name_with_producer_price",)
    list_filter = (
        OfferItemSendFilterByPermanence,
        PurchaseFilterByProducerForThisPermanence,
        OfferItemFilter,
        ProductFilterByDepartmentForThisProducer,
    )
    list_select_related = ("producer", "department_for_customer")
    list_per_page = 16
    list_max_show_all = 16
    # Important : Do not order by 'translations__order_sort_order'
    # because in this case, when searching on the long_name, records may be duplicated in the admin result list.
    ordering = ("long_name_v2",)
    readonly_fields = ("get_html_producer_qty_stock_invoiced", "get_vat_level")

    def get_queryset(self, request):
        qs = super(OfferItemSendAdmin, self).get_queryset(request)
        return qs

    def get_form(self, request, obj=None, **kwargs):
        prices = ("producer_unit_price", "unit_deposit")

        if not obj.wrapped and obj.order_unit in [
            PRODUCT_ORDER_UNIT_KG,
            PRODUCT_ORDER_UNIT_PC_KG,
        ]:
            self.fields = (
                (
                    "permanence",
                    "department_for_customer",
                    "product",
                    "get_vat_level",
                ),
                prices,
                (
                    "offer_purchase_price",
                    "rule_of_3",
                ),
            )
        else:
            self.fields = (
                (
                    "permanence",
                    "department_for_customer",
                    "product",
                    "get_vat_level",
                ),
                prices,
                ("offer_purchase_price",),
            )

        form = super(OfferItemSendAdmin, self).get_form(request, obj, **kwargs)
        permanence_field = form.base_fields["permanence"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.widget.can_delete_related = False
        department_for_customer_field.widget.can_delete_related = False
        product_field.widget.can_delete_related = False
        permanence_field.empty_label = None
        department_for_customer_field.empty_label = None
        product_field.empty_label = None

        if obj is not None:
            permanence_field.queryset = Permanence.objects.filter(id=obj.permanence_id)
            department_for_customer_field.queryset = (
                LUT_DepartmentForCustomer.objects.filter(
                    id=obj.department_for_customer_id
                )
            )
            product_field.queryset = Product.objects.filter(id=obj.product_id)
        else:
            permanence_field.queryset = Permanence.objects.none()
            department_for_customer_field.queryset = (
                LUT_DepartmentForCustomer.objects.none()
            )
            product_field.queryset = Product.objects.none()
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def get_actions(self, request):
        actions = super(OfferItemSendAdmin, self).get_actions(request)
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

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, "new_objects"):
                formset.new_objects = []
            if not hasattr(formset, "changed_objects"):
                formset.changed_objects = []
            if not hasattr(formset, "deleted_objects"):
                formset.deleted_objects = []
        offer_item = OfferItem.objects.filter(id=form.instance.id).order_by("?").first()
        formset = formsets[0]
        for purchase_form in formset:
            purchase = purchase_form.instance
            previous_customer = purchase_form.fields["previous_customer"].initial
            if previous_customer is not None and previous_customer != purchase.customer:
                # Delete the purchase because the customer has changed
                purchase = (
                    Purchase.objects.filter(
                        customer_id=previous_customer.id,
                        offer_item_id=offer_item.id,
                        is_box_content=False,
                    )
                    .order_by("?")
                    .first()
                )
                if purchase is not None:
                    purchase.quantity_invoiced = DECIMAL_ZERO
                    purchase.save()
                    purchase.save_box()
        for purchase_form in formset:
            purchase_form_instance = purchase_form.instance
            try:
                customer = purchase_form_instance.customer
            except Customer.DoesNotExist:  # RelatedObjectDoesNotExist
                customer = None
            if customer is None:
                purchase_form.repanier_is_valid = False
            else:
                purchase = rule_of_3_reload_purchase(
                    customer, offer_item, purchase_form, purchase_form_instance
                )
                if offer_item.order_unit in [
                    PRODUCT_ORDER_UNIT_KG,
                    PRODUCT_ORDER_UNIT_PC_KG,
                    PRODUCT_ORDER_UNIT_LT,
                ]:
                    purchase_price = purchase.purchase_price
                    previous_purchase_price = purchase_form.fields[
                        "previous_purchase_price"
                    ].initial
                else:
                    purchase_price = previous_purchase_price = REPANIER_MONEY_ZERO
                if purchase_price != previous_purchase_price:
                    purchase.purchase_price = purchase_price
                    if offer_item.producer_unit_price.amount != DECIMAL_ZERO:
                        purchase.quantity_invoiced = (
                            purchase_price.amount
                            / offer_item.producer_unit_price.amount
                        ).quantize(FOUR_DECIMALS)
                    else:
                        purchase.quantity_invoiced = DECIMAL_ZERO
                else:
                    purchase.purchase_price.amount = (
                        purchase.quantity_invoiced
                        * offer_item.producer_unit_price.amount
                    ).quantize(TWO_DECIMALS)

        if not offer_item.wrapped and offer_item.order_unit in [
            PRODUCT_ORDER_UNIT_KG,
            PRODUCT_ORDER_UNIT_PC_KG,
        ]:
            rule_of_3 = form.cleaned_data["rule_of_3"]
            if rule_of_3:
                rule_of_3_target = form.cleaned_data[
                    "offer_purchase_price"
                ].amount.quantize(TWO_DECIMALS)
                rule_of_3_source = DECIMAL_ZERO
                max_purchase_counter = 0
                for purchase_form in formset:
                    if purchase_form.repanier_is_valid:
                        rule_of_3_source += purchase_form.instance.purchase_price.amount
                        max_purchase_counter += 1
                if (
                    rule_of_3_target is not None
                    and rule_of_3_target != rule_of_3_source
                ):
                    if rule_of_3_source != DECIMAL_ZERO:
                        ratio = rule_of_3_target / rule_of_3_source
                    else:
                        if rule_of_3_target == DECIMAL_ZERO:
                            ratio = DECIMAL_ZERO
                        else:
                            ratio = DECIMAL_ONE
                    # Rule of 3
                    if ratio != DECIMAL_ONE:
                        adjusted_invoice = DECIMAL_ZERO
                        i = 0
                        for purchase_form in formset:
                            if purchase_form.repanier_is_valid:
                                i += 1
                                purchase = purchase_form.instance
                                if i == max_purchase_counter:
                                    delta = rule_of_3_target - adjusted_invoice
                                    if (
                                        offer_item.producer_unit_price.amount
                                        != DECIMAL_ZERO
                                    ):
                                        purchase.quantity_invoiced = (
                                            delta
                                            / offer_item.producer_unit_price.amount
                                        ).quantize(FOUR_DECIMALS)
                                    else:
                                        purchase.quantity_invoiced = DECIMAL_ZERO
                                else:
                                    purchase.quantity_invoiced = (
                                        purchase.quantity_invoiced * ratio
                                    ).quantize(FOUR_DECIMALS)
                                    adjusted_invoice += (
                                        purchase.quantity_invoiced
                                        * offer_item.producer_unit_price.amount
                                    ).quantize(TWO_DECIMALS)
                                purchase.save()
                                purchase.save_box()

        for purchase_form in formset:
            if purchase_form.has_changed() and purchase_form.repanier_is_valid:
                purchase_form.instance.save()
                purchase_form.instance.save_box()

        # Important : linked with ^^^^^
        offer_item.permanence.recalculate_order_amount(
            offer_item_qs=OfferItem.objects.filter(id=offer_item.id).order_by("?")
        )
