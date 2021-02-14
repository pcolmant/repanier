from os import sep as os_sep

from django import forms
from django.conf import settings
from django.contrib.admin import helpers
from django.core.checks import messages
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy, reverse, path
from django.utils import translation
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _, get_language_info
from easy_select2 import apply_select2
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from parler.forms import TranslatableModelForm

from repanier.admin.admin_filter import (
    ProductFilterByDepartmentForThisProducer,
    ProductFilterByProducer,
    ProductFilterByProductionMode,
    ProductFilterByPlacement,
    ProductFilterByVatLevel,
)
from repanier.admin.admin_model import RepanierAdminTranslatableImportExport
from repanier.admin.tools import check_cancel_in_post, check_product
from repanier.const import (
    LUT_PRODUCT_ORDER_UNIT_REVERSE,
    LUT_ALL_VAT,
    LUT_ALL_VAT_REVERSE,
    REPANIER_MONEY_ZERO,
    DECIMAL_ZERO,
    PRODUCT_ORDER_UNIT_DEPOSIT,
    PRODUCT_ORDER_UNIT_PC,
    PRODUCT_ORDER_UNIT_PC_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    EMPTY_STRING,
    PRODUCT_ORDER_UNIT_PC_PRICE_LT,
    LUT_VAT,
    LUT_PRODUCT_ORDER_UNIT,
    PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
)
from repanier.middleware import add_filter, get_query_filters, get_query_params
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
    TwoMoneysWidget,
    HTMLWidget,
)


class ProductResource(resources.ModelResource):
    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    producer_name = fields.Field(
        attribute="producer",
        widget=ForeignKeyWidget(Producer, field="short_name"),
    )
    long_name = fields.Field(attribute="long_name")
    offer_description = fields.Field(attribute="offer_description", widget=HTMLWidget())
    department = fields.Field(
        attribute="department",
        widget=TranslatedForeignKeyWidget(
            LUT_DepartmentForCustomer, field="short_name"
        ),
    )
    order_unit = fields.Field(
        attribute="order_unit",
        widget=ChoiceWidget(LUT_PRODUCT_ORDER_UNIT, LUT_PRODUCT_ORDER_UNIT_REVERSE),
    )
    order_average_weight = fields.Field(
        attribute="order_average_weight", widget=ThreeDecimalsWidget()
    )
    at_producer_tariff = fields.Field(
        attribute="at_producer_tariff", widget=TwoMoneysWidget()
    )
    at_customer_tariff = fields.Field(
        attribute="at_customer_tariff", widget=TwoMoneysWidget()
    )
    deposit = fields.Field(attribute="deposit", widget=TwoMoneysWidget())
    tax_level = fields.Field(
        attribute="tax_level", widget=ChoiceWidget(LUT_ALL_VAT, LUT_ALL_VAT_REVERSE)
    )
    customer_minimum_order_quantity = fields.Field(
        attribute="customer_minimum_order_quantity", widget=ThreeDecimalsWidget()
    )
    customer_increment_order_quantity = fields.Field(
        attribute="customer_increment_order_quantity", widget=ThreeDecimalsWidget()
    )
    wrapped = fields.Field(attribute="wrapped", widget=DecimalBooleanWidget())
    is_into_offer = fields.Field(
        attribute="is_into_offer", widget=DecimalBooleanWidget(), readonly=True
    )
    qty_on_sale = fields.Field(attribute="qty_on_sale", widget=ThreeDecimalsWidget())
    label = fields.Field(
        attribute="production_mode",
        widget=TranslatedManyToManyWidget(
            LUT_ProductionMode, separator="; ", field="short_name"
        ),
    )
    picture = fields.Field(attribute="picture2", readonly=True)
    is_active = fields.Field(
        attribute="is_active", widget=DecimalBooleanWidget(), readonly=True
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        if instance.wrapped is None:
            instance.wrapped = False
        if instance.at_producer_tariff is None:
            instance.at_producer_tariff = REPANIER_MONEY_ZERO
        if instance.at_customer_tariff is None:
            instance.at_customer_tariff = REPANIER_MONEY_ZERO
        if instance.deposit is None:
            instance.deposit = REPANIER_MONEY_ZERO
        if instance.customer_minimum_order_quantity is None:
            instance.customer_minimum_order_quantity = DECIMAL_ZERO
        if instance.customer_increment_order_quantity is None:
            instance.customer_increment_order_quantity = DECIMAL_ZERO
        if instance.qty_on_sale is None:
            instance.qty_on_sale = DECIMAL_ZERO
        if instance.order_unit is None:
            raise ValueError(_("The order unit must be set."))
        if instance.order_unit != PRODUCT_ORDER_UNIT_DEPOSIT:
            if instance.at_producer_tariff < DECIMAL_ZERO:
                raise ValueError(_("The price must be greater than or equal to zero."))
            if instance.at_customer_tariff < DECIMAL_ZERO:
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
                if instance.qty_on_sale != instance.qty_on_sale // 1:
                    raise ValueError(_("The qty_on_sale must be an integer."))

        if instance.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            if instance.customer_minimum_order_quantity <= DECIMAL_ZERO:
                raise ValueError(
                    _("The minimum order quantity must be greater than zero.")
                )

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
            "department",
            "long_name",
            "order_unit",
            "wrapped",
            "order_average_weight",
            "at_producer_tariff",
            "at_customer_tariff",
            "deposit",
            "tax_level",
            "customer_minimum_order_quantity",
            "customer_increment_order_quantity",
            "is_into_offer",
            "qty_on_sale",
            "label",
            "picture",
            "is_active",
            "offer_description",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


class ProductDataForm(TranslatableModelForm):
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

        producer = self.cleaned_data["producer"]
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
                    reference=reference, producer_id=producer
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
            at_producer_tariff = self.cleaned_data["at_producer_tariff"]
            if at_producer_tariff < DECIMAL_ZERO:
                self.add_error(
                    "at_producer_tariff",
                    _("The price must be greater than or equal to zero."),
                )

            at_customer_tariff = self.cleaned_data.get(
                "at_customer_tariff", DECIMAL_ZERO
            )
            if at_customer_tariff < DECIMAL_ZERO:
                self.add_error(
                    "at_customer_tariff",
                    _("The price must be greater than or equal to zero."),
                )

        if order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            customer_minimum_order_quantity = self.cleaned_data.get(
                "customer_minimum_order_quantity", DECIMAL_ZERO
            )
            customer_increment_order_quantity = self.cleaned_data.get(
                "customer_increment_order_quantity", DECIMAL_ZERO
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
            if customer_minimum_order_quantity <= DECIMAL_ZERO:
                self.add_error(
                    "customer_minimum_order_quantity",
                    _("The minimum order quantity must be greater than zero."),
                )

    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
            "long_name": forms.TextInput(attrs={"style": "width:100% !important"}),
            "order_unit": SelectAdminOrderUnitWidget(
                attrs={"style": "width:100% !important"}
            ),
            "department": apply_select2(forms.Select),
        }


class ProductAdmin(RepanierAdminTranslatableImportExport):
    change_list_template = None  # get default admin selection to use customized product change_list template
    form = ProductDataForm
    change_list_url = reverse_lazy("admin:repanier_product_changelist")
    resource_class = ProductResource
    list_display = ("get_long_name_with_producer",)
    list_display_links = ("get_long_name_with_producer",)
    readonly_fields = ("is_updated_on",)
    list_select_related = ("producer", "department")
    list_per_page = 16
    list_max_show_all = 16
    filter_horizontal = ("production_mode",)
    ordering = [
        "producer",
        "translations__long_name",
    ]
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
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "action": "duplicate_product",
                "product": product,
                "producers": Producer.objects.filter(is_active=True),
            },
        )

    duplicate_product.short_description = _("Duplicate")

    def get_list_display(self, request):
        list_display = ["get_long_name_with_producer", "get_row_actions"]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += ["language_column"]
        list_display += ["at_producer_tariff", "qty_on_sale"]
        self.list_editable = ["at_producer_tariff", "qty_on_sale"]
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
            ProductFilterByProductionMode,
        ]
        return list_filter

    def get_fieldsets(self, request, product=None):
        fields_basic = [
            "producer",
            "department",
            "long_name",
            "picture2",
            "order_unit",
            ("at_producer_tariff", "deposit", "order_average_weight"),
            (
                "customer_minimum_order_quantity",
                "customer_increment_order_quantity",
            ),
            "wrapped",
            "is_into_offer",
            "qty_on_sale",
        ]
        fields_advanced_descriptions = [
            "placement",
            "offer_description",
            "production_mode",
        ]

        fields_advanced_options = ["reference", "tax_level", "is_active"]

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

    def get_form(self, request, product=None, **kwargs):
        department_id = None
        is_active_value = None
        is_into_offer_value = None

        if product is not None:
            producer_queryset = Producer.objects.filter(id=product.producer_id)
        else:
            producer_queryset = Producer.objects.none()
            query_params = get_query_params()
            if "producer" in query_params:
                producer_id = query_params["producer"]
                if producer_id:
                    producer_queryset = Producer.objects.filter(id=producer_id)
            if "department" in query_params:
                department_id = query_params["department"]
            if "is_active__exact" in query_params:
                is_active_value = query_params["is_active__exact"]
            if "is_into_offer__exact" in query_params:
                is_into_offer_value = query_params["is_into_offer__exact"]

        producer = producer_queryset.first()
        form = super().get_form(request, product, **kwargs)

        producer_field = form.base_fields["producer"]
        producer_field.widget.can_delete_related = False
        department_field = form.base_fields["department"]
        picture_field = form.base_fields["picture2"]
        order_unit_field = form.base_fields["order_unit"]
        tax_level_field = form.base_fields["tax_level"]
        production_mode_field = form.base_fields["production_mode"]

        # TODO : Make it dependent of the producer country
        tax_level_field.widget.choices = LUT_VAT

        department_field.widget.can_delete_related = False
        if producer is not None:
            producer_field.widget.attrs["readonly"] = True
            producer_field.initial = producer.id
            # One folder by producer for clarity
            if hasattr(picture_field.widget, "upload_to"):
                picture_field.widget.upload_to = "{}{}{}".format(
                    "product", os_sep, producer.id
                )
        order_unit_field.choices = LUT_PRODUCT_ORDER_UNIT

        if product is not None:
            department_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                rght=F("lft") + 1,
                is_active=True,
                translations__language_code=translation.get_language(),
            ).order_by("translations__short_name")
        else:
            if department_id is not None:
                department_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    id=department_id
                )
            else:
                department_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    rght=F("lft") + 1,
                    is_active=True,
                    translations__language_code=translation.get_language(),
                ).order_by("translations__short_name")
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
        production_mode_field.empty_label = None
        production_mode_field.queryset = LUT_ProductionMode.objects.filter(
            rght=F("lft") + 1,
            is_active=True,
            translations__language_code=translation.get_language(),
        ).order_by("translations__short_name")
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                r"<int:product_id>/duplicate-product/",
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
        super().save_model(request, product, form, change)
        update_offer_item(product_id=product.id)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(
            is_box=False,
            # Important to also display untranslated products : translations__language_code=settings.LANGUAGE_CODE
            translations__language_code=settings.LANGUAGE_CODE,
        ).exclude(order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE)
        return qs

    class Media:
        js = ("admin/js/jquery.init.js", get_repanier_static_name("js/confirm_exit.js"))
