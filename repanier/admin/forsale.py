from django import forms
from django.contrib import admin
from django.utils import translation
from django.utils.html import strip_tags

from repanier.admin.admin_filter import (
    PurchaseFilterByProducerForThisPermanence,
    ProductFilterByDepartmentForThisProducer,
    OfferItemFilter,
)
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import sint, update_offer_item


class ForSaleClosedDataForm(forms.ModelForm):
    stock_reserved = forms.CharField(required=False, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        offer_item = self.instance
        self.fields["stock_reserved"].initial = strip_tags(offer_item.qty_sold)
        self.fields["stock_reserved"].widget.attrs["readonly"] = True
        self.fields["stock_reserved"].disabled = True

    def get_readonly_fields(self, request, obj=None):
        return [
            "stock_reserved",
        ]


class ForSaleClosedAdmin(admin.ModelAdmin):
    form = ForSaleClosedDataForm
    search_fields = ("translations__long_name",)
    list_display = [
        "get_long_name_with_producer",
    ]
    list_display_links = ("get_long_name_with_producer",)
    list_filter = (
        PurchaseFilterByProducerForThisPermanence,
        OfferItemFilter,
        ProductFilterByDepartmentForThisProducer,
    )
    list_select_related = ("producer", "department")
    list_per_page = 13
    list_max_show_all = 13
    ordering = [
        "translations__long_name",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(
            translations__language_code=translation.get_language()
        ).distinct()

    def get_list_display(self, request):
        producer_id = sint(request.GET.get("producer", 0))
        if producer_id != 0:
            producer_queryset = Producer.objects.filter(id=producer_id).order_by("?")
            producer = producer_queryset.first()
        else:
            producer = None
        # permanence_id = sint(request.GET.get('permanence', 0))
        # permanence_open = False
        # permanence = Permanence.objects.filter(id=permanence_id, status=SALE_OPENED).order_by('?')
        # if permanence.exists():
        #     permanence_open = True
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

    def get_fieldsets(self, request, offer_item=None):
        fields_basic = [
            ("permanence", "department", "product"),
            ("stock_reserved",),
        ]

        fieldsets = ((None, {"fields": fields_basic}),)
        return fieldsets

    def get_form(self, request, offer_item=None, **kwargs):
        form = super().get_form(request, offer_item, **kwargs)
        permanence_field = form.base_fields["permanence"]
        department_field = form.base_fields["department"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.empty_label = None
        department_field.empty_label = None
        product_field.empty_label = None

        permanence_field.queryset = Permanence.objects.filter(
            id=offer_item.permanence_id
        )
        department_field.queryset = LUT_DepartmentForCustomer.objects.filter(
            id=offer_item.department_id
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
