from django import forms
from django.contrib import admin
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _

from repanier.admin.admin_filter import (
    AdminFilterProducerOfPermanence,
    AdminFilterQuantityInvoiced,
    AdminFilterDepartment,
)
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.tools import update_offer_item


class OfferItemClosedDataForm(forms.ModelForm):
    producer_qty_stock_invoiced = forms.CharField(
        label=_("Quantity invoiced by the producer"), required=False, initial=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        offer_item = self.instance
        self.fields["producer_qty_stock_invoiced"].initial = strip_tags(
            offer_item.get_html_producer_qty_stock_invoiced()
        )
        self.fields["producer_qty_stock_invoiced"].widget.attrs["readonly"] = True
        self.fields["producer_qty_stock_invoiced"].disabled = True

    def get_readonly_fields(self, request, obj=None):
        return [
            "qty_invoiced",
        ]


class OfferItemClosedAdmin(admin.ModelAdmin):
    form = OfferItemClosedDataForm
    search_fields = ("long_name_v2",)
    list_display = (
        "producer",
        "department_for_customer",
        "get_long_name_with_producer_price",
        "stock",
        "get_html_producer_qty_stock_invoiced",
    )
    list_display_links = ("get_long_name_with_producer_price",)
    list_editable = ("stock",)
    list_filter = (
        AdminFilterProducerOfPermanence,
        AdminFilterQuantityInvoiced,
        AdminFilterDepartment,
    )
    list_select_related = ("producer", "department_for_customer")
    list_per_page = 13
    list_max_show_all = 13
    ordering = (
        "department_for_customer",
        "long_name_v2",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs

    def get_fieldsets(self, request, offer_item=None):
        fields_basic = [
            "permanence",
            "department_for_customer",
            "product",
            "producer_qty_stock_invoiced",
        ]

        fieldsets = ((None, {"fields": fields_basic}),)
        return fieldsets

    def get_form(self, request, offer_item=None, **kwargs):

        form = super().get_form(request, offer_item, **kwargs)

        permanence_field = form.base_fields["permanence"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.empty_label = None
        department_for_customer_field.empty_label = None
        product_field.empty_label = None

        permanence_field.queryset = Permanence.objects.filter(
            id=offer_item.permanence_id
        )
        department_for_customer_field.queryset = (
            LUT_DepartmentForCustomer.objects.filter(
                id=offer_item.department_for_customer_id
            )
        )
        product_field.queryset = Product.objects.filter(id=offer_item.product_id)
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_repanier_staff

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

    def save_model(self, request, offer_item, form, change):
        super().save_model(request, offer_item, form, change)
        if offer_item.product_id is not None:
            offer_item.product.stock = offer_item.stock
            offer_item.product.save(update_fields=["stock"])
            update_offer_item(product_id=offer_item.product_id)
