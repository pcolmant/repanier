from admin_auto_filters.filters import AutocompleteFilter
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from repanier.const import (
    DECIMAL_ZERO,
    BankMovement,
    SaleStatus,
)


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
        return [(1, _("Only recorded"))]

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
            (1, _("Not booked")),
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
                return queryset.filter(
                    operation_status__in=[BankMovement.PROFIT, BankMovement.TAX]
                )

        else:
            return queryset


class AdminFilterPermanenceInPreparationStatus(SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            (SaleStatus.PLANNED.value, SaleStatus.PLANNED.label),
            (SaleStatus.OPENED.value, SaleStatus.OPENED.label),
            (SaleStatus.SEND.value, SaleStatus.SEND.label),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == SaleStatus.PLANNED.value:
                return queryset.filter(status__lt=SaleStatus.OPENED)
            elif value == SaleStatus.OPENED.value:
                return queryset.filter(
                    status=SaleStatus.OPENED,
                )
            else:
                return queryset.filter(
                    status__gt=SaleStatus.OPENED,
                )
        else:
            return queryset


class AdminFilterPermanenceDoneStatus(SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            (SaleStatus.SEND.value, SaleStatus.SEND.label),
            (SaleStatus.INVOICED.value, SaleStatus.INVOICED.label),
            (SaleStatus.CANCELLED.value, SaleStatus.CANCELLED.label),
            (SaleStatus.ARCHIVED.value, SaleStatus.ARCHIVED.label),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == SaleStatus.SEND.value:
                return queryset.filter(status__lt=SaleStatus.INVOICED.value)
            elif value == SaleStatus.INVOICED.value:
                return queryset.filter(
                    status=SaleStatus.INVOICED,
                )
            elif value == SaleStatus.CANCELLED.value:
                return queryset.filter(
                    status=SaleStatus.CANCELLED,
                )
            else:
                return queryset.filter(
                    status=SaleStatus.RCHIVED,
                )
        else:
            return queryset
