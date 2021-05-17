# Filters in the right sidebar of the change list page of the admin
from admin_auto_filters.filters import AutocompleteFilter
from admin_auto_filters.views import AutocompleteJsonView
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.middleware import get_request_params
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.lut import LUT_ProductionMode
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.tools import sint, get_admin_template_name


class AdminFilterProducer(AutocompleteFilter):
    title = _("Producers")  # display title
    field_name = "producer"  # name of the foreign key field
    parameter_name = "producer"


class AdminFilterDepartment(AutocompleteFilter):
    title = _("Departments")  # display title
    field_name = "department_for_customer"  # name of the foreign key field
    parameter_name = "department_for_customer"


class AdminFilterProductionMode(SimpleListFilter):
    title = _("Productions modes")
    parameter_name = "production_mode"
    template = get_admin_template_name("production_mode_filter.html")

    def lookups(self, request, model_admin):
        return [
            (p.id, p.short_name_v2)
            for p in LUT_ProductionMode.objects.filter(is_active=True)
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(production_mode=self.value())
        else:
            return queryset


class AdminFilterPlacement(SimpleListFilter):
    title = _("Products placements")
    parameter_name = "placement"
    template = get_admin_template_name("placement_filter.html")

    def lookups(self, request, model_admin):
        return [(p[0], p[1]) for p in LUT_PRODUCT_PLACEMENT]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(placement=self.value())
        else:
            return queryset


class AdminFilterTaxLevel(SimpleListFilter):
    title = _("TAX")
    parameter_name = "tax_level"
    template = get_admin_template_name("tax_level_filter.html")

    def lookups(self, request, model_admin):
        return [(p[0], p[1]) for p in LUT_ALL_VAT]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(vat_level=self.value())
        else:
            return queryset


class AdminFilterCustomerOfPermanence(SimpleListFilter):
    title = _("Customers")
    parameter_name = "customer"
    template = get_admin_template_name("customer_filter.html")

    def lookups(self, request, model_admin):
        param = get_request_params()
        permanence_id = param.get("permanence", None)
        list_filter = []
        for c in Customer.objects.filter(may_order=True):
            ci = (
                CustomerInvoice.objects.filter(
                    permanence_id=permanence_id, customer_id=c.id
                )
                .order_by("?")
                .first()
            )
            if ci is not None:
                if ci.is_order_confirm_send:
                    list_filter.append(
                        (
                            c.id,
                            "{} {} ({})".format(
                                settings.LOCK_UNICODE,
                                c.short_basket_name,
                                ci.get_total_price_with_tax(),
                            ),
                        )
                    )
                else:
                    list_filter.append(
                        (
                            c.id,
                            "{} ({})".format(
                                c.short_basket_name, ci.total_price_with_tax
                            ),
                        )
                    )
            else:
                list_filter.append((c.id, c.short_basket_name))
        return list_filter

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(customer_id=self.value())
        else:
            return queryset


class AdminFilterProducerOfPermanence(SimpleListFilter):
    title = _("Producers")
    parameter_name = "producer"
    template = get_admin_template_name("producer_filter.html")

    def lookups(self, request, model_admin):
        param = get_request_params()
        permanence_id = param.get("permanence", None)
        if permanence_id is None:
            list_filter = [(0, _("No permanence selected"))]
        else:
            list_filter = [(None, _("All"))]
            for p in Producer.objects.filter(permanence=permanence_id):
                pi = ProducerInvoice.objects.filter(
                    permanence_id=permanence_id, producer_id=p.id
                ).first()
                if pi is not None:
                    list_filter.append(
                        (
                            p.id,
                            "{} ({})".format(
                                p.short_profile_name, pi.total_price_with_tax
                            ),
                        )
                    )
                else:
                    list_filter.append((p.id, p.short_profile_name))
        return list_filter

    def queryset(self, request, queryset):
        param = get_request_params()
        permanence_id = param.get("permanence", None)
        if permanence_id is None:
            # return a queryset which returns nothing if not permanence is selected
            return queryset.filter(producer_id=0)
        elif self.value():
            return queryset.filter(producer_id=self.value())
        else:
            return queryset

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


class AdminFilterPermanenceSendSearchView(AutocompleteJsonView):
    model_admin = None

    def get_queryset(self):
        queryset = Permanence.objects.filter(status=PERMANENCE_SEND).order_by(
            "permanence_date",
            "id",
        )
        return queryset


class AdminFilterPermanenceSend(AutocompleteFilter):
    title = _("Permanences")
    field_name = "permanence"  # name of the foreign key field
    parameter_name = "permanence"

    def get_autocomplete_url(self, request, model_admin):
        return reverse("admin:afcs_offer_item_send_permanence")


class AdminFilterQuantityInvoiced(SimpleListFilter):
    title = _("Invoiced")
    parameter_name = "is_filled_exact"

    def lookups(self, request, model_admin):
        return [(1, _("Only invoiced"))]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.exclude(quantity_invoiced=DECIMAL_ZERO)
        else:
            return queryset


class AdminFilterBankAccountStatus(SimpleListFilter):
    title = _("Status")
    parameter_name = "is_filled_exact"

    def lookups(self, request, model_admin):
        return [
            (1, _("Not invoiced")),
            (2, _("Balance")),
            (3, _("Loses and profits")),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == "1":
                return queryset.filter(
                    Q(permanence_id__isnull=True, customer_id__isnull=False)
                    | Q(permanence_id__isnull=True, producer_id__isnull=False)
                )
            elif value == "2":
                return queryset.filter(
                    permanence_id__isnull=False,
                    customer_id__isnull=True,
                    producer_id__isnull=True,
                )
            else:
                return queryset.filter(operation_status__in=[BANK_PROFIT, BANK_TAX])

        else:
            return queryset


class AdminFilterPermanenceInPreparationStatus(SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            (PERMANENCE_PLANNED, PERMANENCE_PLANNED_STR),
            (PERMANENCE_OPENED, PERMANENCE_OPENED_STR),
            (PERMANENCE_SEND, PERMANENCE_SEND_STR),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == PERMANENCE_PLANNED:
                return queryset.filter(status__lt=PERMANENCE_OPENED)
            elif value == PERMANENCE_OPENED:
                return queryset.filter(
                    status=PERMANENCE_OPENED,
                )
            else:
                return queryset.filter(
                    status__gt=PERMANENCE_OPENED,
                )
        else:
            return queryset


class AdminFilterPermanenceDoneStatus(SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            (PERMANENCE_SEND, PERMANENCE_SEND_STR),
            (PERMANENCE_INVOICED, PERMANENCE_INVOICED_STR),
            (PERMANENCE_CANCELLED, PERMANENCE_CANCELLED_STR),
            (PERMANENCE_ARCHIVED, PERMANENCE_ARCHIVED_STR),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == PERMANENCE_SEND:
                return queryset.filter(status__lt=PERMANENCE_INVOICED)
            elif value == PERMANENCE_INVOICED:
                return queryset.filter(
                    status=PERMANENCE_INVOICED,
                )
            elif value == PERMANENCE_CANCELLED:
                return queryset.filter(
                    status=PERMANENCE_CANCELLED,
                )
            else:
                return queryset.filter(
                    status=PERMANENCE_ARCHIVED,
                )
        else:
            return queryset
