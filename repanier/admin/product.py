# -*- coding: utf-8
from os import sep as os_sep
from urllib.parse import parse_qsl

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.core.checks import messages
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.utils import translation
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _, get_language_info
from easy_select2 import apply_select2
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX, XLS
from import_export.widgets import ForeignKeyWidget
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.admin.admin_filter import (
    ProductFilterByDepartmentForThisProducer,
    ProductFilterByProducer,
    ProductFilterByProductionMode,
    ProductFilterByPlacement,
    ProductFilterByVatLevel,
)
from repanier.admin.tools import check_cancel_in_post, check_product, add_filter
from repanier.admin.tools import get_query_filters
from repanier.const import (
    LUT_ALL_VAT,
    LUT_ALL_VAT_REVERSE,
    REPANIER_MONEY_ZERO,
    DECIMAL_ONE,
    DECIMAL_ZERO,
    PRODUCT_ORDER_UNIT_DEPOSIT,
    PRODUCT_ORDER_UNIT_PC,
    PRODUCT_ORDER_UNIT_PC_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    EMPTY_STRING,
    LIMIT_ORDER_QTY_ITEM,
    PRODUCT_ORDER_UNIT_PC_PRICE_LT,
    LUT_VAT,
    LUT_PRODUCT_ORDER_UNIT_WO_SHIPPING_COST,
    LUT_PRODUCT_ORDER_UNIT,
    LUT_PRODUCT_ORDER_UNIT_REVERSE_ALL, LUT_PRODUCT_ORDER_UNIT_ALL,
)
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
    TranslatedForeignKeyWidget,
    DecimalBooleanWidget,
    ChoiceWidget,
    ThreeDecimalsWidget,
    TranslatedManyToManyWidget,
    TwoMoneysWidget, HTMLWidget,
)


class ProductResource(resources.ModelResource):
    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    producer_name = fields.Field(
        attribute="producer",
        widget=ForeignKeyWidget(Producer, field="short_profile_name"),
    )
    long_name = fields.Field(attribute="long_name")
    offer_description = fields.Field(attribute="offer_description", widget=HTMLWidget())
    department_for_customer = fields.Field(
        attribute="department_for_customer",
        widget=TranslatedForeignKeyWidget(
            LUT_DepartmentForCustomer, field="short_name"
        ),
    )
    order_unit = fields.Field(
        attribute="order_unit",
        widget=ChoiceWidget(LUT_PRODUCT_ORDER_UNIT_ALL, LUT_PRODUCT_ORDER_UNIT_REVERSE_ALL),
    )
    order_average_weight = fields.Field(
        attribute="order_average_weight", widget=ThreeDecimalsWidget()
    )
    producer_unit_price = fields.Field(
        attribute="producer_unit_price", widget=TwoMoneysWidget()
    )
    customer_unit_price = fields.Field(
        attribute="customer_unit_price", widget=TwoMoneysWidget()
    )
    unit_deposit = fields.Field(attribute="unit_deposit", widget=TwoMoneysWidget())
    vat_level = fields.Field(
        attribute="vat_level", widget=ChoiceWidget(LUT_ALL_VAT, LUT_ALL_VAT_REVERSE)
    )
    customer_minimum_order_quantity = fields.Field(
        attribute="customer_minimum_order_quantity", widget=ThreeDecimalsWidget()
    )
    customer_increment_order_quantity = fields.Field(
        attribute="customer_increment_order_quantity", widget=ThreeDecimalsWidget()
    )
    customer_alert_order_quantity = fields.Field(
        attribute="customer_alert_order_quantity", widget=ThreeDecimalsWidget()
    )
    wrapped = fields.Field(attribute="wrapped", widget=DecimalBooleanWidget())
    stock = fields.Field(attribute="stock", widget=ThreeDecimalsWidget())
    limit_order_quantity_to_stock = fields.Field(
        attribute="limit_order_quantity_to_stock",
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    producer_order_by_quantity = fields.Field(
        attribute="producer_order_by_quantity", widget=ThreeDecimalsWidget()
    )
    label = fields.Field(
        attribute="production_mode",
        widget=TranslatedManyToManyWidget(
            LUT_ProductionMode, separator="; ", field="short_name"
        ),
    )
    picture = fields.Field(attribute="picture2", readonly=True)
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
        if instance.customer_alert_order_quantity is None:
            instance.customer_alert_order_quantity = DECIMAL_ZERO
        if instance.stock is None:
            instance.stock = DECIMAL_ZERO
        if instance.producer_order_by_quantity is None:
            instance.producer_order_by_quantity = DECIMAL_ZERO
        if instance.order_unit is None:
            raise ValueError(_("The order unit must be set."))
        if instance.order_unit != PRODUCT_ORDER_UNIT_DEPOSIT:
            if instance.producer_unit_price < DECIMAL_ZERO:
                raise ValueError(_("The price must be greater than or equal to zero."))
            if instance.customer_unit_price < DECIMAL_ZERO:
                raise ValueError(_("The price must be greater than or equal to zero."))
            if instance.order_unit in [
                PRODUCT_ORDER_UNIT_PC,
                PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                PRODUCT_ORDER_UNIT_PC_PRICE_PC,
                PRODUCT_ORDER_UNIT_PC_KG,
            ]:
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
                if (
                    instance.customer_alert_order_quantity
                    != instance.customer_alert_order_quantity // 1
                ):
                    raise ValueError(_("The alert quantity must be an integer."))

        if instance.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            if instance.customer_minimum_order_quantity <= DECIMAL_ZERO:
                raise ValueError(
                    _("The minimum order quantity must be greater than zero.")
                )

            if (
                instance.customer_minimum_order_quantity
                != instance.customer_alert_order_quantity
                and instance.customer_increment_order_quantity <= DECIMAL_ZERO
            ):
                raise ValueError(_("The increment must be greater than zero."))

        qs = Product.objects.filter(
            reference=instance.reference, producer=instance.producer
        ).order_by("?")
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
            "producer_name",
            "reference",
            "department_for_customer",
            "long_name",
            "order_unit",
            "wrapped",
            "order_average_weight",
            "producer_unit_price",
            "customer_unit_price",
            "unit_deposit",
            "vat_level",
            "customer_minimum_order_quantity",
            "customer_increment_order_quantity",
            "customer_alert_order_quantity",
            "stock",
            "limit_order_quantity_to_stock",
            "producer_order_by_quantity",
            "label",
            "picture",
            "is_into_offer",
            "is_active",
            "offer_description",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


class ProductDataForm(TranslatableModelForm):
    def __init__(self, *args, **kwargs):
        super(ProductDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        if self.instance.id is None:
            if self.language_code != settings.LANGUAGE_CODE:
                # Important to also prohibit untranslated instance in settings.LANGUAGE_CODE
                self.add_error(
                    "long_name",
                    _("Please define first a long_name in %(language)s")
                    % {
                        "language": get_language_info(settings.LANGUAGE_CODE)[
                            "name_local"
                        ]
                    },
                )

        producer = self.cleaned_data.get("producer", None)
        if producer is None:
            self.add_error(
                "producer",
                _("Please select first a producer in the filter of previous screen..."),
            )
        else:
            reference = self.cleaned_data.get("reference", EMPTY_STRING)
            if reference:
                qs = Product.objects.filter(
                    reference=reference, producer_id=producer.id
                ).order_by("?")
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if qs.exists():
                    self.add_error(
                        "reference",
                        _("The reference is already used by %(product)s")
                        % {"product": qs.first()},
                    )

        order_unit = self.cleaned_data.get("order_unit", PRODUCT_ORDER_UNIT_PC)
        if order_unit != PRODUCT_ORDER_UNIT_DEPOSIT:
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

        if order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            customer_minimum_order_quantity = self.cleaned_data.get(
                "customer_minimum_order_quantity", DECIMAL_ZERO
            )
            customer_increment_order_quantity = self.cleaned_data.get(
                "customer_increment_order_quantity", DECIMAL_ZERO
            )
            field_customer_alert_order_quantity_is_present = (
                "customer_alert_order_quantity" in self.cleaned_data
            )
            customer_alert_order_quantity = self.cleaned_data.get(
                "customer_alert_order_quantity", LIMIT_ORDER_QTY_ITEM
            )
            if not settings.REPANIER_SETTINGS_STOCK:
                limit_order_quantity_to_stock = False
            else:
                # Important, default for limit_order_quantity_to_stock is True, because this field is not displayed
                # if the pre-opening of offer is activated fro this producer.
                limit_order_quantity_to_stock = self.cleaned_data.get(
                    "limit_order_quantity_to_stock", False
                )
                if not limit_order_quantity_to_stock and producer is not None:
                    if producer.represent_this_buyinggroup:
                        self.add_error(
                            "limit_order_quantity_to_stock",
                            _(
                                "You must limit the order quantity to the stock because the producer represent this buyinggroup."
                            ),
                        )

            if order_unit in [
                PRODUCT_ORDER_UNIT_PC,
                PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                PRODUCT_ORDER_UNIT_PC_PRICE_PC,
                PRODUCT_ORDER_UNIT_PC_KG,
            ]:
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
                if limit_order_quantity_to_stock:
                    stock = self.cleaned_data.get("stock", DECIMAL_ZERO)
                    if stock != stock // 1:
                        self.add_error("stock", _("The stock must be an integer."))
                elif (
                    customer_alert_order_quantity != customer_alert_order_quantity // 1
                ):
                    self.add_error(
                        "customer_alert_order_quantity",
                        _("The alert quantity must be an integer."),
                    )
            if customer_minimum_order_quantity <= DECIMAL_ZERO:
                self.add_error(
                    "customer_minimum_order_quantity",
                    _("The minimum order quantity must be greater than zero."),
                )

            if (
                customer_minimum_order_quantity != customer_alert_order_quantity
                and customer_increment_order_quantity <= DECIMAL_ZERO
            ):
                self.add_error(
                    "customer_increment_order_quantity",
                    _("The increment must be greater than zero."),
                )
            elif not limit_order_quantity_to_stock:
                if customer_increment_order_quantity <= customer_minimum_order_quantity:
                    if customer_minimum_order_quantity != customer_alert_order_quantity:
                        order_qty_item = (
                            customer_alert_order_quantity
                            - customer_minimum_order_quantity
                        ) / customer_increment_order_quantity
                        q_max = (
                            customer_minimum_order_quantity
                            + int(order_qty_item) * customer_increment_order_quantity
                        )
                        if order_qty_item > (LIMIT_ORDER_QTY_ITEM - 1):
                            q_max = (
                                customer_minimum_order_quantity
                                + LIMIT_ORDER_QTY_ITEM
                                * customer_increment_order_quantity
                            )
                    else:
                        order_qty_item = DECIMAL_ONE
                        q_max = customer_alert_order_quantity
                else:
                    order_qty_item = (
                        customer_alert_order_quantity
                        / customer_increment_order_quantity
                    )
                    q_max = int(order_qty_item) * customer_increment_order_quantity
                    if order_qty_item > LIMIT_ORDER_QTY_ITEM:
                        q_max = (
                            customer_minimum_order_quantity
                            + LIMIT_ORDER_QTY_ITEM * customer_increment_order_quantity
                        )
                if field_customer_alert_order_quantity_is_present:
                    if order_qty_item > LIMIT_ORDER_QTY_ITEM:
                        self.add_error(
                            "customer_alert_order_quantity",
                            _(
                                "This alert quantity will generate more than %(qty_item)d choices for the customer into the order form."
                            )
                            % {"qty_item": LIMIT_ORDER_QTY_ITEM},
                        )
                    elif (
                        customer_alert_order_quantity < customer_minimum_order_quantity
                    ):
                        self.add_error(
                            "customer_alert_order_quantity",
                            _(
                                "The alert quantity must be greater than or equal to the minimum order quantity."
                            ),
                        )
                    if (
                        q_max != customer_alert_order_quantity
                        and q_max > customer_minimum_order_quantity
                    ):
                        self.add_error(
                            "customer_alert_order_quantity",
                            _(
                                "This alert quantity is not reachable. %(q_max)s is the best lower choice."
                            )
                            % {"q_max": number_format(q_max, 3)},
                        )

    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
            "long_name": forms.TextInput(attrs={"style": "width:450px !important"}),
            "order_unit": SelectAdminOrderUnitWidget(
                attrs={"style": "width:100% !important"}
            ),
            "department_for_customer": apply_select2(forms.Select),
        }


class ProductAdmin(ImportExportMixin, TranslatableAdmin):
    change_list_template = (
        None
    )  # get default admin selection to use customized product change_list template
    form = ProductDataForm
    change_list_url = reverse_lazy("admin:repanier_product_changelist")
    resource_class = ProductResource
    list_display = ("get_long_name_with_producer",)
    list_display_links = ("get_long_name_with_producer",)
    readonly_fields = ("is_updated_on",)
    list_select_related = ("producer", "department_for_customer")
    list_per_page = 16
    list_max_show_all = 16
    filter_horizontal = ("production_mode",)
    ordering = ("producer", "translations__long_name")
    search_fields = ("translations__long_name",)
    # actions = ["deselect_is_into_offer"]

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request)

    def get_redirect_to_change_list_url(self):
        return "{}{}".format(self.change_list_url, get_query_filters())

    # def deselect_is_into_offer(self, request, queryset):
    #     task_product.deselect_is_into_offer(queryset)
    #
    # deselect_is_into_offer.short_description = _(
    #     "Remove selected products from the offer"
    # )

    @check_cancel_in_post
    @check_product
    def duplicate_product(self, request, product_id, product):
        if "apply" in request.POST:
            if "producers" in request.POST:
                producers = request.POST.getlist("producers", [])
                if len(producers) == 1:
                    producer = (
                        Producer.objects.filter(id=producers[0]).order_by("?").first()
                    )
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
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
                "action": "duplicate_product",
                "product": product,
                "producers": Producer.objects.filter(is_active=True),
            },
        )

    duplicate_product.short_description = _("Duplicate")

    def get_list_display(self, request):
        list_display = ["get_long_name_with_producer", "get_row_actions"]
        list_editable = ["producer_unit_price"]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += ["language_column"]
        list_display += ["producer_unit_price"]
        if settings.REPANIER_SETTINGS_STOCK:
            list_display += ["stock"]
            list_editable += ["stock"]
        else:
            if not settings.REPANIER_SETTINGS_IS_MINIMALIST:
                list_display += ["get_customer_alert_order_quantity"]
        self.list_editable = list_editable
        return list_display

    def get_list_filter(self, request):
        list_filter = [
            ProductFilterByProducer,
            ProductFilterByDepartmentForThisProducer,
            "is_into_offer",
            "wrapped",
            ProductFilterByPlacement,
            ProductFilterByVatLevel,
            "is_active",
        ]
        if settings.REPANIER_SETTINGS_PRODUCT_LABEL:
            list_filter += [ProductFilterByProductionMode]
        if settings.REPANIER_SETTINGS_STOCK:
            list_filter += ["limit_order_quantity_to_stock"]
        return list_filter

    def get_form(self, request, product=None, **kwargs):
        department_for_customer_id = None
        is_active_value = None
        is_into_offer_value = None
        producer_queryset = Producer.objects.none()
        if product is not None:
            producer_queryset = Producer.objects.filter(
                id=product.producer_id
            ).order_by("?")
        else:
            preserved_filters = request.GET.get("_changelist_filters", None)
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if "producer" in param:
                    producer_id = param["producer"]
                    if producer_id:
                        producer_queryset = Producer.objects.filter(
                            id=producer_id
                        ).order_by("?")
                if "department_for_customer" in param:
                    department_for_customer_id = param["department_for_customer"]
                if "is_active__exact" in param:
                    is_active_value = param["is_active__exact"]
                if "is_into_offer__exact" in param:
                    is_into_offer_value = param["is_into_offer__exact"]
        producer = producer_queryset.first()
        fields_basic = [
            ("producer", "long_name", "picture2"),
            "order_unit",
            "wrapped",
            ("producer_unit_price", "unit_deposit", "order_average_weight"),
        ]
        if settings.REPANIER_SETTINGS_STOCK:
            fields_basic += [
                (
                    "customer_minimum_order_quantity",
                    "customer_increment_order_quantity",
                ),
                "limit_order_quantity_to_stock",
                "stock",
            ]
        else:
            if settings.REPANIER_SETTINGS_IS_MINIMALIST:
                # Important : do not use ( ) for minimalist. The UI will be more logical.
                fields_basic += [
                    "customer_minimum_order_quantity",
                    "customer_increment_order_quantity",
                ]
            else:
                fields_basic += [
                    (
                        "customer_minimum_order_quantity",
                        "customer_increment_order_quantity",
                        "customer_alert_order_quantity",
                    )
                ]
        fields_advanced_descriptions = [
            ("department_for_customer", "placement"),
            "offer_description",
        ]

        fields_advanced_options = []

        if settings.REPANIER_SETTINGS_PRODUCT_LABEL:
            fields_advanced_descriptions += ["production_mode"]
        if settings.REPANIER_SETTINGS_STOCK:
            fields_advanced_options += ["producer_order_by_quantity"]
        fields_advanced_options += ["reference"]
        fields_advanced_options += ["vat_level"]
        fields_advanced_options += [("is_into_offer", "is_active")]

        self.fieldsets = (
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

        form = super(ProductAdmin, self).get_form(request, product, **kwargs)

        producer_field = form.base_fields["producer"]
        department_for_customer_field = form.base_fields["department_for_customer"]

        picture_field = form.base_fields["picture2"]
        order_unit_field = form.base_fields["order_unit"]
        vat_level_field = form.base_fields["vat_level"]
        # TODO : Make it dependent of the producer country
        vat_level_field.widget.choices = LUT_VAT
        producer_field.widget.can_add_related = False
        producer_field.widget.can_delete_related = False
        producer_field.widget.attrs["readonly"] = True
        department_for_customer_field.widget.can_delete_related = False

        production_mode_field = form.base_fields.get("production_mode")

        order_unit_choices = LUT_PRODUCT_ORDER_UNIT
        if producer is not None:
            # One folder by producer for clarity
            if hasattr(picture_field.widget, "upload_to"):
                picture_field.widget.upload_to = "{}{}{}".format(
                    "product", os_sep, producer.id
                )
            if producer.represent_this_buyinggroup:
                order_unit_choices = LUT_PRODUCT_ORDER_UNIT_WO_SHIPPING_COST
        order_unit_field.choices = order_unit_choices

        if product is not None:
            producer_field.empty_label = None
            producer_field.queryset = producer_queryset
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                rght=F("lft") + 1,
                is_active=True,
                translations__language_code=translation.get_language(),
            ).order_by(
                "translations__short_name"
            )
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
            if department_for_customer_id is not None:
                department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    id=department_for_customer_id
                )
            else:
                department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    rght=F("lft") + 1,
                    is_active=True,
                    translations__language_code=translation.get_language(),
                ).order_by(
                    "translations__short_name"
                )
            if is_active_value:
                is_active_field = form.base_fields["is_active"]
                if is_active_value == "0":
                    is_active_field.initial = False
                else:
                    is_active_field.initial = True
            if is_into_offer_value:
                is_into_offer_field = form.base_fields["is_into_offer"]
                if is_into_offer_value == "0":
                    is_into_offer_field.initial = False
                else:
                    is_into_offer_field.initial = True
        if production_mode_field is not None:
            production_mode_field.queryset = LUT_ProductionMode.objects.filter(
                rght=F("lft") + 1,
                is_active=True,
                translations__language_code=translation.get_language(),
            ).order_by("translations__short_name")
        return form

    def get_urls(self):
        urls = super(ProductAdmin, self).get_urls()
        custom_urls = [
            url(
                r"^(?P<product_id>.+)/duplicate-product/$",
                self.admin_site.admin_view(self.duplicate_product),
                name="duplicate-product",
            )
        ]
        return custom_urls + urls

    def get_row_actions(self, product):
        return format_html(
            '<div class="repanier-button-row">'
            '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-retweet"></i></a></span>'
            "{}"
            "</div>",
            add_filter(reverse("admin:duplicate-product", args=[product.pk])),
            _("Duplicate"),
            product.get_html_admin_is_into_offer(),
            _("In offer"),
        )

    get_row_actions.short_description = EMPTY_STRING

    def save_model(self, request, product, form, change):
        super(ProductAdmin, self).save_model(request, product, form, change)
        update_offer_item(product_id=product.id)

    def get_queryset(self, request):
        qs = super(ProductAdmin, self).get_queryset(request)
        qs = qs.filter(
            is_box=False,
            producer__is_active=True,
            # Important to also display untranslated products : translations__language_code=settings.LANGUAGE_CODE
            translations__language_code=settings.LANGUAGE_CODE)
        # ).exclude(order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE)
        return qs

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, XLS, CSV) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, CSV) if f().can_export()]

    class Media:
        js = ("admin/js/jquery.init.js", get_repanier_static_name("js/confirm_exit.js"))
