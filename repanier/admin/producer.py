from collections import OrderedDict

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.forms import Textarea
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX, XLS
from import_export.widgets import CharWidget

import repanier.apps
from repanier.admin.forms import ImportStockForm
from repanier.admin.tools import check_cancel_in_post, get_query_filters
from repanier.const import PERMANENCE_PLANNED, DECIMAL_ONE, DECIMAL_ZERO, EMPTY_STRING
from repanier.models.box import BoxContent
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.tools import web_services_activated, get_repanier_static_name
from repanier.xlsx.views import import_xslx_view
from repanier.xlsx.widget import (
    IdWidget,
    TwoDecimalsWidget,
    DecimalBooleanWidget,
    TwoMoneysWidget,
    DateWidgetExcel,
)
from repanier.xlsx.xlsx_invoice import export_invoice
from repanier.xlsx.xlsx_product import export_customer_prices
from repanier.xlsx.xlsx_stock import handle_uploaded_stock, export_producer_stock


class ProducerResource(resources.ModelResource):

    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    phone1 = fields.Field(attribute="phone1", widget=CharWidget(), readonly=False)
    phone2 = fields.Field(attribute="phone2", widget=CharWidget(), readonly=False)

    price_list_multiplier = fields.Field(
        attribute="price_list_multiplier",
        default=DECIMAL_ONE,
        widget=TwoDecimalsWidget(),
        readonly=False,
    )
    date_balance = fields.Field(
        attribute="get_admin_date_balance", widget=DateWidgetExcel(), readonly=True
    )
    balance = fields.Field(
        attribute="get_admin_balance", widget=TwoMoneysWidget(), readonly=True
    )
    invoice_by_basket = fields.Field(
        attribute="invoice_by_basket",
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
    represent_this_buyinggroup = fields.Field(
        attribute="represent_this_buyinggroup",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=True,
    )
    is_active = fields.Field(
        attribute="is_active", widget=DecimalBooleanWidget(), readonly=True
    )
    reference_site = fields.Field(attribute="reference_site", readonly=True)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        producer_qs = Producer.objects.filter(
            short_profile_name=instance.short_profile_name
        ).order_by("?")
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
            "short_profile_name",
            "long_profile_name",
            "email",
            "email2",
            "email3",
            "language",
            "phone1",
            "phone2",
            "fax",
            "address",
            "invoice_by_basket",
            "sort_products_by_reference",
            "producer_price_are_wo_vat",
            "price_list_multiplier",
            "reference_site",
            "bank_account",
            "date_balance",
            "balance",
            "represent_this_buyinggroup",
            "is_active",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


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
    from repanier.apps import REPANIER_SETTINGS_PERMANENCES_NAME

    permanences = forms.ModelMultipleChoiceField(
        Permanence.objects.filter(status=PERMANENCE_PLANNED),
        label="{}".format(REPANIER_SETTINGS_PERMANENCES_NAME),
        widget=FilteredSelectMultiple(
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME, False
        ),
        required=False,
    )
    reference_site = forms.URLField(
        label=_("Reference site"),
        widget=forms.URLInput(attrs={"style": "width:100% !important"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ProducerDataForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields["permanences"].initial = self.instance.permanence_set.all()

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
        invoice_by_basket = self.cleaned_data.get("invoice_by_basket", False)
        price_list_multiplier = self.cleaned_data.get(
            "price_list_multiplier", DECIMAL_ONE
        )

        if invoice_by_basket and self.instance.id is not None:
            if BoxContent.objects.filter(
                product__producer_id=self.instance.id
            ).exists():
                self.add_error(
                    "invoice_by_basket",
                    _(
                        "Some products of this producer are in a box. This implies that this producer cannot invoice by basket."
                    ),
                )
        short_profile_name = self.cleaned_data["short_profile_name"]
        qs = Producer.objects.filter(short_profile_name=short_profile_name).order_by(
            "?"
        )
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            self.add_error(
                "short_profile_name",
                _("The given short_profile_name is used by another producer."),
            )

    def save(self, *args, **kwargs):
        instance = super(ProducerDataForm, self).save(*args, **kwargs)
        if instance.id is not None:
            updated_permanences = (
                Permanence.objects.filter(producers=instance.pk)
                .exclude(status=PERMANENCE_PLANNED)
                .order_by("?")
            )
            instance.permanence_set.set(updated_permanences)
            instance.permanence_set.add(*self.cleaned_data["permanences"])
            # The previous save is called with "commit=False"
            # But we need to update the producer
            # to recalculate the products prices. So a call to self.instance.save() is required
            # self.instance.save()
            # for product in Product.objects.filter(producer_id=instance.id).order_by('?'):
            #     product.save()
            # update_offer_item(producer_id=instance.id)

        return instance

    class Meta:
        widgets = {
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 30em;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 60em;"}
            ),
        }
        model = Producer
        fields = "__all__"


class ProducerAdmin(ImportExportMixin, admin.ModelAdmin):
    form = ProducerDataForm
    resource_class = ProducerResource
    change_list_url = reverse_lazy("admin:repanier_producer_changelist")

    search_fields = ("short_profile_name", "email")
    list_per_page = 16
    list_max_show_all = 16
    list_filter = ("is_active", "invoice_by_basket")
    actions = ["export_customer_prices"]

    # change_list_template = 'admin/producer_change_list.html'

    def has_delete_permission(self, request, producer=None):
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

    def get_urls(self):
        urls = super(ProducerAdmin, self).get_urls()
        custom_urls = [
            url(
                r"^export-stock/$",
                self.admin_site.admin_view(self.export_stock),
                name="producer-export-stock",
            ),
            url(
                r"^import-stock/$",
                self.admin_site.admin_view(self.import_stock),
                name="producer-import-stock",
            ),
        ]
        return custom_urls + urls

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

    def export_stock(self, request):
        wb = export_producer_stock(
            producers=Producer.objects.all().order_by("short_profile_name"),
            wb=None,
        )
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = "attachment; filename={0}.xlsx".format(
                _("Inventory")
            )
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    @check_cancel_in_post
    def import_stock(self, request):
        return import_xslx_view(
            self,
            admin,
            request,
            None,
            _("Import the stock"),
            handle_uploaded_stock,
            action="import_stock",
            form_klass=ImportStockForm,
        )

    def get_actions(self, request):
        actions = super(ProducerAdmin, self).get_actions(request)
        this_year = timezone.now().year
        actions.update(
            OrderedDict(
                create__producer_action(y)
                for y in [this_year, this_year - 1, this_year - 2]
            )
        )
        return actions

    def get_list_display(self, request):
        list_display = ["__str__", "get_products"]
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            list_display += ["get_balance"]
        list_display += ["phone1", "email"]
        return list_display

    def get_fieldsets(self, request, producer=None):
        fields_basic = [
            ("short_profile_name", "long_profile_name", "language"),
            ("email", "email2", "email3"),
            ("phone1", "phone2", "fax"),
        ]
        if producer is not None:
            fields_basic += [
                ("address", "city", "picture"),
                "memo",
                "is_active",
                "producer_price_are_wo_vat",
                "permanences",
                "get_admin_balance",
                "get_admin_date_balance",
            ]
        else:
            # Do not accept the picture because there is no producer.id for the "upload_to"
            fields_basic += [
                ("address", "city"),
                "memo",
                "producer_price_are_wo_vat",
                "is_active",
            ]
        if producer is not None and producer.represent_this_buyinggroup:
            fields_advanced = ["represent_this_buyinggroup"]
        else:
            fields_advanced = []
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            fields_advanced += ["bank_account", "vat_id"]
        fields_advanced += [
            "sort_products_by_reference",
            "invoice_by_basket",
            "minimum_order_value",
            "price_list_multiplier",
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

    def save_model(self, request, producer, form, change):
        producer.web_services_activated, _, _ = web_services_activated(
            producer.reference_site
        )
        super(ProducerAdmin, self).save_model(request, producer, form, change)

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

    # class Media:
    #     if settings.REPANIER_SETTINGS_STOCK:
    #         js = (
    #             "admin/js/jquery.init.js",
    #             get_repanier_static_name("js/export_import_stock.js"),
    #         )
