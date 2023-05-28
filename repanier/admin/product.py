# -*- coding: utf-8
from os import sep as os_sep

from django import forms
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.checks import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy, reverse, path
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from repanier.admin.admin_filter import (
    AdminFilterProducer,
    AdminFilterDepartment,
)
from repanier.admin.tools import check_cancel_in_post, check_product
from repanier.const import (
    LUT_ALL_VAT,
    LUT_ALL_VAT_REVERSE,
    REPANIER_MONEY_ZERO,
    DECIMAL_ZERO,
    EMPTY_STRING,
    LUT_VAT,
    OrderUnit,
)
from repanier.middleware import get_request_params, get_query_filters, add_filter
from repanier.models.lut import LUT_DepartmentForCustomer, LUT_ProductionMode
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_product
from repanier.tools import (
    update_offer_item,
    get_repanier_template_name,
    get_repanier_static_name,
)
from repanier.widget.select_admin_order_unit import SelectAdminOrderUnitWidget
from repanier.xlsx.widget import (
    IdWidget,
    DecimalBooleanWidget,
    ThreeDecimalsWidget,
    TwoMoneysWidget,
    HTMLWidget,
    OrderUnitWidget,
    TaxLevelWidget,
)


class ProductResource(resources.ModelResource):
    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    producer = fields.Field(
        attribute="producer",
        widget=ForeignKeyWidget(Producer, field="short_profile_name"),
    )
    product = fields.Field(attribute="long_name_v2")
    description = fields.Field(attribute="offer_description_v2", widget=HTMLWidget())
    department = fields.Field(
        attribute="department_for_customer",
        widget=ForeignKeyWidget(LUT_DepartmentForCustomer, field="short_name_v2"),
    )
    unit = fields.Field(
        attribute="order_unit",
        widget=OrderUnitWidget(OrderUnit.choices, OrderUnit.PC),
    )
    average_weight = fields.Field(
        attribute="order_average_weight", widget=ThreeDecimalsWidget()
    )
    producer_unit_price = fields.Field(
        attribute="producer_unit_price", widget=TwoMoneysWidget()
    )
    customer_unit_price = fields.Field(
        attribute="customer_unit_price", widget=TwoMoneysWidget()
    )
    unit_deposit = fields.Field(attribute="unit_deposit", widget=TwoMoneysWidget())
    tax_level = fields.Field(
        attribute="vat_level", widget=TaxLevelWidget(LUT_ALL_VAT, LUT_ALL_VAT_REVERSE)
    )
    minimum_order_quantity = fields.Field(
        attribute="customer_minimum_order_quantity", widget=ThreeDecimalsWidget()
    )
    increment_order_quantity = fields.Field(
        attribute="customer_increment_order_quantity", widget=ThreeDecimalsWidget()
    )
    wrapped = fields.Field(attribute="wrapped", widget=DecimalBooleanWidget())
    stock = fields.Field(attribute="stock", widget=ThreeDecimalsWidget())
    label = fields.Field(
        attribute="production_mode",
        widget=ManyToManyWidget(
            LUT_ProductionMode, separator="; ", field="short_name_v2"
        ),
    )
    is_into_offer = fields.Field(
        attribute="is_into_offer", widget=DecimalBooleanWidget(), readonly=True
    )
    is_active = fields.Field(
        attribute="is_active", widget=DecimalBooleanWidget(), readonly=True
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        if instance.wrapped is None:
            instance.wrapped = False
        if instance.producer_unit_price is None:
            instance.producer_unit_price = REPANIER_MONEY_ZERO
        if instance.customer_unit_price is None:
            instance.customer_unit_price = REPANIER_MONEY_ZERO
        if instance.unit_deposit is None:
            instance.unit_deposit = REPANIER_MONEY_ZERO
        if instance.customer_minimum_order_quantity is None:
            instance.customer_minimum_order_quantity = DECIMAL_ZERO
        if instance.customer_increment_order_quantity is None:
            instance.customer_increment_order_quantity = DECIMAL_ZERO
        if instance.stock is None:
            instance.stock = DECIMAL_ZERO
        if instance.order_unit is None:
            raise ValueError(_("The order unit must be set."))
        if instance.order_unit != OrderUnit.DEPOSIT:
            if instance.producer_unit_price < DECIMAL_ZERO:
                raise ValueError(_("The price must be greater than or equal to zero."))
            if instance.customer_unit_price < DECIMAL_ZERO:
                raise ValueError(_("The price must be greater than or equal to zero."))
            if instance.order_unit in {
                OrderUnit.PC,
                OrderUnit.PC_PRICE_KG,
                OrderUnit.PC_PRICE_LT,
                OrderUnit.PC_PRICE_PC,
                OrderUnit.PC_KG,
            }:
                # Do not allow decimal value when the qty represents pieces.
                if (
                    instance.customer_minimum_order_quantity
                    != instance.customer_minimum_order_quantity // 1
                ):
                    raise ValueError(
                        _("The minimum order quantity must be an integer.")
                    )
                if (
                    instance.customer_increment_order_quantity
                    != instance.customer_increment_order_quantity // 1
                ):
                    raise ValueError(_("The increment must be an integer."))
                if instance.stock != instance.stock // 1:
                    raise ValueError(_("The stock must be an integer."))

        if instance.order_unit < OrderUnit.DEPOSIT:
            if instance.customer_minimum_order_quantity <= DECIMAL_ZERO:
                raise ValueError(
                    _("The minimum order quantity must be greater than zero.")
                )

            if instance.customer_increment_order_quantity <= DECIMAL_ZERO:
                raise ValueError(_("The increment must be greater than zero."))

        qs = Product.objects.filter(
            reference=instance.reference, producer=instance.producer
        )
        if instance.id is not None:
            qs = qs.exclude(id=instance.id)
        if qs.exists():
            raise ValueError(
                _("The reference %(reference)s is already used by %(product)s")
                % {"reference": instance.reference, "product": qs.first()}
            )

    class Meta:
        model = Product
        fields = (
            "id",
            "reference",
            "producer",
            "department",
            "product",
            "unit",
            "wrapped",
            "average_weight",
            "producer_unit_price",
            "customer_unit_price",
            "unit_deposit",
            "tax_level",
            "minimum_order_quantity",
            "increment_order_quantity",
            "stock",
            "label",
            "is_into_offer",
            "is_active",
            "description",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


class ProductDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        producer = self.cleaned_data.get("producer", None)
        if producer is None:
            self.add_error(
                "producer",
                _("Please select first a producer in the filter of previous screen..."),
            )
            return
        else:
            reference = self.cleaned_data.get("reference", EMPTY_STRING)
            if reference:
                qs = Product.objects.filter(
                    reference=reference, producer_id=producer.id
                )
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if qs.exists():
                    self.add_error(
                        "reference",
                        _("The reference is already used by %(product)s")
                        % {"product": qs.first()},
                    )

        order_unit = self.cleaned_data.get("order_unit", OrderUnit.PC)
        if order_unit != OrderUnit.DEPOSIT:
            producer_unit_price = self.cleaned_data["producer_unit_price"]
            if producer_unit_price < DECIMAL_ZERO:
                self.add_error(
                    "producer_unit_price",
                    _("The price must be greater than or equal to zero."),
                )

            customer_unit_price = self.cleaned_data.get(
                "customer_unit_price", DECIMAL_ZERO
            )
            if customer_unit_price < DECIMAL_ZERO:
                self.add_error(
                    "customer_unit_price",
                    _("The price must be greater than or equal to zero."),
                )

        if order_unit < OrderUnit.DEPOSIT:
            customer_minimum_order_quantity = self.cleaned_data.get(
                "customer_minimum_order_quantity", DECIMAL_ZERO
            )
            customer_increment_order_quantity = self.cleaned_data.get(
                "customer_increment_order_quantity", DECIMAL_ZERO
            )
            stock = self.cleaned_data.get("stock", DECIMAL_ZERO)

            if order_unit in {
                OrderUnit.PC,
                OrderUnit.PC_PRICE_KG,
                OrderUnit.PC_PRICE_LT,
                OrderUnit.PC_PRICE_PC,
                OrderUnit.PC_KG,
            }:
                # Do not allow decimal value when the qty represents pieces.
                if (
                    customer_minimum_order_quantity
                    != customer_minimum_order_quantity // 1
                ):
                    self.add_error(
                        "customer_minimum_order_quantity",
                        _("The minimum order quantity must be an integer."),
                    )
                if (
                    customer_increment_order_quantity
                    != customer_increment_order_quantity // 1
                ):
                    self.add_error(
                        "customer_increment_order_quantity",
                        _("The increment must be an integer."),
                    )
                if stock != stock // 1:
                    self.add_error("stock", _("The stock must be an integer."))
            if customer_minimum_order_quantity <= DECIMAL_ZERO:
                self.add_error(
                    "customer_minimum_order_quantity",
                    _("The minimum order quantity must be greater than zero."),
                )

            if customer_increment_order_quantity <= DECIMAL_ZERO:
                self.add_error(
                    "customer_increment_order_quantity",
                    _("The increment must be greater than zero."),
                )

    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
            "long_name_v2": forms.TextInput(attrs={"style": "width: 95%;"}),
            "order_unit": SelectAdminOrderUnitWidget(attrs={"style": "width: 95%;"}),
        }


class ProductAdmin(ImportExportMixin, admin.ModelAdmin):
    change_list_template = None  # get default admin selection to use customized product change_list template
    form = ProductDataForm
    change_list_url = reverse_lazy("admin:repanier_product_changelist")
    resource_class = ProductResource
    list_display = (
        "producer",
        "department_for_customer",
        "get_long_name_with_customer_price",
        "get_row_actions",
        "producer_unit_price",
        "stock",
    )
    list_display_links = ("get_long_name_with_customer_price",)
    list_editable = (
        "producer_unit_price",
        "stock",
    )
    readonly_fields = ("is_updated_on",)
    list_select_related = ("producer", "department_for_customer")
    list_per_page = 16
    list_max_show_all = 16
    filter_horizontal = ("production_mode",)
    ordering = ("department_for_customer", "long_name_v2")
    search_fields = ("long_name_v2",)
    list_filter = (
        AdminFilterProducer,
        AdminFilterDepartment,
        "is_into_offer",
        "wrapped",
        "is_active",
    )
    autocomplete_fields = ["department_for_customer", "production_mode"]

    def has_module_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, product=None):
        return self.has_delete_permission(request)

    def get_redirect_to_change_list_url(self):
        return "{}{}".format(self.change_list_url, get_query_filters())

    @check_cancel_in_post
    @check_product
    def duplicate_product(self, request, product_id, product):
        if "apply" in request.POST:
            if "producers" in request.POST:
                producers = request.POST.getlist("producers", [])
                if len(producers) == 1:
                    producer = Producer.objects.filter(id=producers[0]).first()
                    if producer is not None:
                        user_message, user_message_level = task_product.admin_duplicate(
                            product, producer
                        )
                        self.message_user(request, user_message, user_message_level)
                    return HttpResponseRedirect(self.get_redirect_to_change_list_url())
            user_message = _("You must select one and only one producer.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name(
            "admin/confirm_duplicate_product.html"
        )

        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action": "duplicate_product",
                "product": product,
                "producers": Producer.objects.filter(is_active=True),
            },
        )

    duplicate_product.short_description = _("Duplicate")

    def get_fields(self, request, product=None):
        return [
            "producer",
            "department_for_customer",
            "long_name_v2",
            "picture2",
            "order_unit",
            ("producer_unit_price", "unit_deposit", "order_average_weight"),
            (
                "customer_minimum_order_quantity",
                "customer_increment_order_quantity",
            ),
            "stock",
            "wrapped",
            "is_into_offer",
            "placement",
            "offer_description_v2",
            "production_mode",
            "reference",
            "vat_level",
            "is_active",
        ]

    def get_form(self, request, product=None, **kwargs):

        query_params = get_request_params()
        if product is not None:
            producer_queryset = Producer.objects.filter(id=product.producer_id)
        else:
            producer_id = query_params.get("producer", "0")
            producer_queryset = Producer.objects.filter(id=producer_id)

        producer = producer_queryset.first()

        form = super().get_form(request, product, **kwargs)

        producer_field = form.base_fields["producer"]

        picture_field = form.base_fields["picture2"]
        order_unit_field = form.base_fields["order_unit"]
        vat_level_field = form.base_fields["vat_level"]
        department_field = form.base_fields["department_for_customer"]

        # department_field is not required in the product model
        department_field.required = True
        # TODO : Make it dependent of the producer country
        vat_level_field.widget.choices = LUT_VAT
        producer_field.widget.can_add_related = False
        producer_field.widget.can_delete_related = False
        producer_field.widget.attrs["readonly"] = True

        production_mode_field = form.base_fields.get("production_mode")

        if producer is not None:
            # One folder by producer for clarity
            if hasattr(picture_field.widget, "upload_to"):
                picture_field.widget.upload_to = "{}{}{}".format(
                    "product", os_sep, producer.id
                )

        if product is not None:
            producer_field.empty_label = None
            producer_field.queryset = producer_queryset
            if production_mode_field is not None:
                production_mode_field.empty_label = None
        else:
            if producer is not None:
                producer_field.empty_label = None
                producer_field.queryset = producer_queryset
            else:
                producer_field.choices = [
                    (
                        "-1",
                        _(
                            "Please select first a producer in the filter of previous screen..."
                        ),
                    )
                ]
                producer_field.disabled = True
            is_active_value = query_params.get("is_active__exact", False)
            is_active_field = form.base_fields["is_active"]
            if is_active_value == "0":
                is_active_field.initial = False
            else:
                is_active_field.initial = True
            is_into_offer_value = query_params.get("is_into_offer__exact", False)
            is_into_offer_field = form.base_fields["is_into_offer"]
            if is_into_offer_value == "0":
                is_into_offer_field.initial = False
            else:
                is_into_offer_field.initial = True
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:product_id>/duplicate-product/",
                self.admin_site.admin_view(self.duplicate_product),
                name="duplicate-product",
            )
        ]
        return custom_urls + urls

    def get_row_actions(self, product):
        return format_html(
            '<div class="repanier-button-row">'
            '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-retweet"></i></a>'
            "{}"
            "</div>",
            add_filter(reverse("admin:duplicate-product", args=[product.pk])),
            _("Duplicate"),
            product.get_html_admin_is_into_offer(),
            _("In offer"),
        )

    get_row_actions.short_description = EMPTY_STRING

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

    def save_model(self, request, product, form, change):
        super().save_model(request, product, form, change)
        update_offer_item(product=product)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_box=False)
        return qs

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, CSV) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, CSV) if f().can_export()]

    class Media:
        js = (
            "admin/js/jquery.init.js",
            get_repanier_static_name("js/admin/confirm_exit.js"),
        )
