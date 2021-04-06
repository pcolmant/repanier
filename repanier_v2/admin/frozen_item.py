from django import forms
from django.contrib import admin
from django.utils.html import strip_tags

from repanier_v2.admin.admin_filter import (
    PurchaseFilterByProducerForThisPermanence,
    ProductFilterByDepartmentForThisProducer,
    FrozenItemFilter,
)
from repanier_v2.models.lut import LUT_DepartmentForCustomer
from repanier_v2.models.order import Order
from repanier_v2.models.producer import Producer
from repanier_v2.models.product import Product
from repanier_v2.tools import sint, update_offer_item


class FrozenItemClosedDataForm(forms.ModelForm):
    stock_reserved = forms.CharField(required=False, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        frozen_item = self.instance
        self.fields["stock_reserved"].initial = strip_tags(frozen_item.qty_sold)
        self.fields["stock_reserved"].widget.attrs["readonly"] = True
        self.fields["stock_reserved"].disabled = True

    def get_readonly_fields(self, request, obj=None):
        return [
            "stock_reserved",
        ]


class FrozenItemClosedAdmin(admin.ModelAdmin):
    form = FrozenItemClosedDataForm
    search_fields = ("name",)
    list_display = [
        "name",
    ]
    list_display_links = ("name",)
    list_filter = (
        PurchaseFilterByProducerForThisPermanence,
        FrozenItemFilter,
        ProductFilterByDepartmentForThisProducer,
    )
    list_select_related = ("producer", "department")
    list_per_page = 13
    list_max_show_all = 13
    ordering = [
        "name",
    ]

    def get_list_display(self, request):
        producer_id = sint(request.GET.get("producer", 0))
        if producer_id != 0:
            producer_queryset = Producer.objects.filter(id=producer_id).order_by("?")
            producer = producer_queryset.first()
        else:
            producer = None
        # order_id = sint(request.GET.get('order', 0))
        # order_open = False
        # order = Permanence.objects.filter(id=order_id, status=ORDER_OPENED).order_by('?')
        # if order.exists():
        #     order_open = True
        if producer is not None:
            self.list_editable = ("stock",)
            return (
                "department",
                "get_long_name_with_producer",
                "stock",
                "qty",
            )
        else:
            return (
                "department",
                "get_long_name_with_producer",
                "qty",
            )

    def get_fieldsets(self, request, frozen_item=None):
        fields_basic = [
            ("order", "department", "product"),
            ("stock_reserved",),
        ]

        fieldsets = ((None, {"fields": fields_basic}),)
        return fieldsets

    def get_form(self, request, frozen_item=None, **kwargs):
        form = super().get_form(request, frozen_item, **kwargs)
        order_field = form.base_fields["order"]
        department_field = form.base_fields["department"]
        product_field = form.base_fields["product"]

        order_field.widget.can_add_related = False
        department_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        order_field.empty_label = None
        department_field.empty_label = None
        product_field.empty_label = None

        order_field.queryset = Order.objects.filter(id=frozen_item.order_id)
        department_field.queryset = LUT_DepartmentForCustomer.objects.filter(
            id=frozen_item.department_id
        )
        product_field.queryset = Product.objects.filter(id=frozen_item.product_id)
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

    def save_model(self, request, frozen_item, form, change):
        super().save_model(request, frozen_item, form, change)
        if frozen_item.product_id is not None:
            frozen_item.product.stock = frozen_item.stock
            frozen_item.product.save(update_fields=["stock"])
            update_offer_item(product_id=frozen_item.product_id)
