from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.forms import Textarea
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy, path
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.admin.admin_model import RepanierAdminImportExport
from repanier.admin.forms import ImportStockForm
from repanier.admin.tools import check_cancel_in_post
from repanier.const import SALE_PLANNED, DECIMAL_ONE, DECIMAL_ZERO, EMPTY_STRING
from repanier.impexport.producer import ProducerResource
from repanier.middleware import get_query_filters
from repanier.models.box import BoxContent
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.tools import web_services_activated
from repanier.xlsx.views import import_xslx_view
from repanier.xlsx.xlsx_invoice import export_invoice
from repanier.xlsx.xlsx_product import export_customer_prices
from repanier.xlsx.xlsx_stock import handle_uploaded_stock, export_producer_stock


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
    permanences = forms.ModelMultipleChoiceField(
        Permanence.objects.filter(status=SALE_PLANNED),
        label="{}".format(_("Sale")),
        widget=FilteredSelectMultiple(
            repanier.globals.REPANIER_SETTINGS_SALE_ON_NAME, False
        ),
        required=False,
    )
    reference_site = forms.URLField(
        label=_("Reference site"),
        widget=forms.URLInput(attrs={"style": "width:100% !important"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            self.fields["permanences"].initial = self.instance.permanence_set.all()

    def clean_customer_tariff_margin(self):
        customer_tariff_margin = self.cleaned_data["customer_tariff_margin"]
        if customer_tariff_margin is None:
            customer_tariff_margin = DECIMAL_ONE
        elif customer_tariff_margin < DECIMAL_ZERO:
            self.add_error(
                "customer_tariff_margin",
                _("The customer tariff margin must be greater than or equal to zero."),
            )
        return customer_tariff_margin

    def clean_purchase_tariff_margin(self):
        purchase_tariff_margin = self.cleaned_data["purchase_tariff_margin"]
        if purchase_tariff_margin is None:
            purchase_tariff_margin = DECIMAL_ONE
        elif purchase_tariff_margin < DECIMAL_ZERO:
            self.add_error(
                "purchase_tariff_margin",
                _("The customer tariff margin must be greater than or equal to zero."),
            )
        return purchase_tariff_margin

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
        short_name = self.cleaned_data["short_name"]
        qs = Producer.objects.filter(short_name=short_name).order_by("?")
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            self.add_error(
                "short_name",
                _("The given short_name is used by another producer."),
            )

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.id is not None:
            updated_permanences = (
                Permanence.objects.filter(producers=instance.pk)
                .exclude(status=SALE_PLANNED)
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


class ProducerAdmin(RepanierAdminImportExport):
    form = ProducerDataForm
    resource_class = ProducerResource
    change_list_url = reverse_lazy("admin:repanier_producer_changelist")

    search_fields = ("short_name", "email")
    list_per_page = 16
    list_max_show_all = 16
    list_filter = ("is_active", "invoice_by_basket")
    ordering = ["-is_default", "short_name"]
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
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-stock/",
                self.admin_site.admin_view(self.export_stock),
                name="producer-export-stock",
            ),
            path(
                "import-stock/",
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
                _("Consumer tariff")
            )
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    export_customer_prices.short_description = _("Export the customer tariff")

    def export_stock(self, request):
        wb = export_producer_stock(
            producers=Producer.objects.all().order_by("short_name"),
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
        actions = super().get_actions(request)
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
            ("short_name", "long_name", "language"),
            ("email", "email2", "email3"),
            ("phone1", "phone2", "fax"),
            ("address", "city"),
            "memo",
            "invoice_by_basket",
        ]
        if producer is not None:
            if not producer.is_default:
                fields_basic += [
                    "producer_tariff_is_wo_tax",
                    "is_active",
                    "minimum_order_value",
                    "purchase_tariff_margin",
                    "customer_tariff_margin",
                    "bank_account",
                    "vat_id",
                ]
            fields_basic += [
                "permanences",
                "get_admin_balance",
                "get_admin_date_balance",
            ]
        else:
            fields_basic += [
                "producer_tariff_is_wo_tax",
                "is_active",
                "minimum_order_value",
                "purchase_tariff_margin",
                "customer_tariff_margin",
                "bank_account",
                "vat_id",
            ]
        fields_advanced = [
            "sort_products_by_reference",
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
            if producer.is_default:
                return [
                    "web_services_activated",
                    "is_default",
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
        super().save_model(request, producer, form, change)

    # class Media:
    #     if settings.REPANIER_SETTINGS_STOCK:
    #         js = (
    #             "admin/js/jquery.init.js",
    #             get_repanier_static_name("js/export_import_stock.js"),
    #         )
