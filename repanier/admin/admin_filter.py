from admin_auto_filters.filters import AutocompleteFilter
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from repanier.const import *


class AdminFilterProducer(AutocompleteFilter):
    title = _("Producers")  # display title
    field_name = "producer"  # name of the foreign key field
    parameter_name = "producer"


class AdminFilterDepartment(AutocompleteFilter):
    title = _("Departments")  # display title
    field_name = "department_for_customer"  # name of the foreign key field
    parameter_name = "department_for_customer"


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
