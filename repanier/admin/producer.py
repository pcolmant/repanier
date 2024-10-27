from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import admin
from django.forms import Textarea, TextInput, EmailInput
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX
from import_export.widgets import CharWidget
from repanier.const import DECIMAL_ONE, DECIMAL_ZERO, EMPTY_STRING
from repanier.middleware import get_query_filters
from repanier.models.producer import Producer
from repanier.tools import web_services_activated
from repanier.xlsx.widget import (
    IdWidget,
    TwoDecimalsWidget,
    DecimalBooleanWidget,
)
from repanier.xlsx.xlsx_invoice import export_invoice
from repanier.xlsx.xlsx_product import export_customer_prices


class ProducerResource(resources.ModelResource):

    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    short_name = fields.Field(attribute="short_profile_name")
    long_name = fields.Field(attribute="long_profile_name")
    phone1 = fields.Field(attribute="phone1", widget=CharWidget(), readonly=False)
    phone2 = fields.Field(attribute="phone2", widget=CharWidget(), readonly=False)

    price_list_multiplier = fields.Field(
        attribute="price_list_multiplier",
        default=DECIMAL_ONE,
        widget=TwoDecimalsWidget(),
        readonly=False,
    )
    invoice_by_basket = fields.Field(
        attribute="invoice_by_basket",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    producer_price_are_wo_vat = fields.Field(
        attribute="producer_price_are_wo_vat",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    sort_products_by_reference = fields.Field(
        attribute="sort_products_by_reference",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    reference_site = fields.Field(attribute="reference_site", readonly=True)

    def before_save_instance(self, instance, row, **kwargs):
        """
        Override to add additional logic.
        """
        producer_qs = Producer.objects.filter(
            short_profile_name=instance.short_profile_name
        )
        if instance.id is not None:
            producer_qs = producer_qs.exclude(id=instance.id)
        if producer_qs.exists():
            raise ValueError(
                _(
                    "The short_basket_name {} is already used by another producer."
                ).format(instance.short_profile_name)
            )

    class Meta:
        model = Producer
        fields = (
            "id",
            "short_name",
            "long_name",
            "email",
            "email2",
            "email3",
            "phone1",
            "phone2",
            "address",
            "invoice_by_basket",
            "sort_products_by_reference",
            "producer_price_are_wo_vat",
            "price_list_multiplier",
            "reference_site",
            "bank_account",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = True


def create__producer_action(year):
    def action(modeladmin, request, producer_qs):
        # To the producer we speak of "payment".
        # This is the detail of the payment to the producer, i.e. received products
        wb = None
        for producer in producer_qs:
            wb = export_invoice(
                year=year, producer=producer, wb=wb, sheet_name=producer
            )
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(
                "{} {}".format(_("Payment"), year),
                settings.REPANIER_SETTINGS_GROUP_NAME,
            )
            wb.save(response)
            return response
        return

    name = "export_producer_{}".format(year)
    return (
        name,
        (action, name, _("Export the list of products purchased in {}").format(year)),
    )


class ProducerDataForm(forms.ModelForm):
    reference_site = forms.URLField(
        label=_("Reference site"),
        widget=forms.URLInput(attrs={"style": "width: 70%;"}),
        required=False,
    )

    def clean_price_list_multiplier(self):
        price_list_multiplier = self.cleaned_data["price_list_multiplier"]
        if price_list_multiplier is None:
            price_list_multiplier = DECIMAL_ONE
        elif price_list_multiplier < DECIMAL_ZERO:
            self.add_error(
                "price_list_multiplier",
                _("The price must be greater than or equal to zero."),
            )
        return price_list_multiplier

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        reference_site = self.cleaned_data.get("reference_site", EMPTY_STRING)
        for allowed_host in settings.ALLOWED_HOSTS:
            if reference_site.endswith(allowed_host):
                self.add_error(
                    "reference_site", _("The reference site may not be your site.")
                )
                break

        short_profile_name = self.cleaned_data["short_profile_name"]
        qs = Producer.objects.filter(short_profile_name=short_profile_name)
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            self.add_error(
                "short_profile_name",
                _("The given short_profile_name is used by another producer."),
            )

    class Meta:
        widgets = {
            "long_profile_name": TextInput(attrs={"style": "width: 70%;"}),
            "email": EmailInput(attrs={"style": "width: 70%;"}),
            "email2": EmailInput(attrs={"style": "width: 70%;"}),
            "email3": EmailInput(attrs={"style": "width: 70%;"}),
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 70%;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 70%;"}
            ),
        }
        model = Producer
        fields = "__all__"


class ProducerAdmin(ImportExportMixin, admin.ModelAdmin):
    form = ProducerDataForm
    resource_class = ProducerResource
    change_list_url = reverse_lazy("admin:repanier_producer_changelist")

    search_fields = ("short_profile_name", "email")
    list_per_page = 20
    list_max_show_all = 20
    list_filter = ("invoice_by_basket",)
    actions = ["export_customer_prices"]

    def has_delete_permission(self, request, producer=None):
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, producer=None):
        return self.has_delete_permission(request)

    def get_redirect_to_change_list_url(self):
        return "{}{}".format(self.change_list_url, get_query_filters())

    def export_customer_prices(self, request, producer_qs):
        wb = export_customer_prices(
            producer_qs=producer_qs, wb=None, producer_prices=False
        )
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = "attachment; filename={0}.xlsx".format(
                _("Customer rate")
            )
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    export_customer_prices.short_description = _("Export the customer tariff")

    # def export_stock(self, request):
    #     wb = export_producer_stock(
    #         producers=Producer.objects.all().order_by("short_profile_name"),
    #         wb=None,
    #     )
    #     if wb is not None:
    #         response = HttpResponse(
    #             content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    #         )
    #         response["Content-Disposition"] = "attachment; filename={0}.xlsx".format(
    #             _("Maximum quantity")
    #         )
    #         wb.save(response)
    #         return response
    #     else:
    #         return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    # @check_cancel_in_post
    # def import_stock(self, request):
    #     return import_xslx_view(
    #         self,
    #         admin,
    #         request,
    #         None,
    #         _("Import the stock"),
    #         handle_uploaded_stock,
    #         action="import_stock",
    #         form_klass=ImportStockForm,
    #     )

    def get_list_display(self, request):
        list_display = ["__str__", "get_products"]
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            list_display += ["get_balance"]
        list_display += ["phone1", "email"]
        return list_display

    def get_fieldsets(self, request, producer=None):
        fields_basic = [
            "short_profile_name",
            "long_profile_name",
            "email",
            "email2",
            "email3",
            "phone1",
            "phone2",
            "fax",
        ]
        if producer is not None:
            fields_basic += [
                "address",
                "city",
                "picture",
                "memo",
                "producer_price_are_wo_vat",
                "invoice_by_basket",
                "sort_products_by_reference",
                "checking_stock",
                "minimum_order_value",
                "price_list_multiplier",
                "get_admin_balance",
                "get_admin_date_balance",
            ]
        else:
            # Do not accept the picture because there is no producer.id for the "upload_to"
            fields_basic += [
                "address",
                "city",
                "memo",
                "producer_price_are_wo_vat",
                "invoice_by_basket",
                "sort_products_by_reference",
                "checking_stock",
                "minimum_order_value",
                "price_list_multiplier",
            ]
        if producer is not None and producer.represent_this_buyinggroup:
            fields_advanced = ["represent_this_buyinggroup"]
        else:
            if producer is not None:
                fields_basic += [
                    "is_active",
                ]
            fields_advanced = [
                "bank_account",
                "vat_id",
                "reference_site",
                "web_services_activated",
            ]
        fieldsets = (
            (None, {"fields": fields_basic}),
            (
                _("Advanced options"),
                {"classes": ("collapse",), "fields": fields_advanced},
            ),
        )
        return fieldsets

    def get_readonly_fields(self, request, producer=None):
        if producer is not None:
            if producer.represent_this_buyinggroup:
                return [
                    "web_services_activated",
                    "represent_this_buyinggroup",
                    "get_admin_date_balance",
                    "get_admin_balance",
                ]
            else:
                return [
                    "web_services_activated",
                    "get_admin_date_balance",
                    "get_admin_balance",
                ]
        else:
            return ["web_services_activated"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_active=True)
        return qs

    def get_actions(self, request):
        actions = super().get_actions(request)
        this_year = timezone.now().year
        actions.update(
            OrderedDict(
                create__producer_action(y)
                for y in [this_year, this_year - 1, this_year - 2, this_year - 3]
            )
        )
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

    def save_model(self, request, producer, form, change):
        producer.web_services_activated, _, _ = web_services_activated(
            producer.reference_site
        )
        super().save_model(request, producer, form, change)

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
