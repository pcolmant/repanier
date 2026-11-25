from io import BytesIO

from openpyxl import Workbook

from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import gettext as _

from repanier.accounting_policy import AccountingPolicy
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.producer import Producer
from repanier.models.purchase import Purchase
from repanier.xlsx.export_tools import (
    new_landscape_a4_sheet,
    worksheet_set_header,
)


class AccountingExportFilters:
    def __init__(self, params=None):
        params = params or {}
        self.date_from = params.get("date_from") or params.get("from")
        self.date_to = params.get("date_to") or params.get("to")
        self.permanence_id = params.get("permanence")
        self.offer_id = params.get("offer")
        self.producer_id = params.get("producer")
        self.group_id = params.get("group")
        self.customer_id = params.get("customer")
        self.status = params.get("status")
        self.validation_status = params.get("validation_status")
        self.operation_status = params.get("operation_status")

    def apply_permanence(self, queryset):
        if self.date_from:
            queryset = queryset.filter(permanence_date__gte=self.date_from)
        if self.date_to:
            queryset = queryset.filter(permanence_date__lte=self.date_to)
        if self.permanence_id:
            queryset = queryset.filter(pk=self.permanence_id)
        if self.status:
            queryset = queryset.filter(status=self.status)
        return queryset

    def apply_invoice(self, queryset):
        queryset = queryset.filter(permanence__is_demo=False)
        if self.date_from:
            queryset = queryset.filter(permanence__permanence_date__gte=self.date_from)
        if self.date_to:
            queryset = queryset.filter(permanence__permanence_date__lte=self.date_to)
        if self.permanence_id:
            queryset = queryset.filter(permanence_id=self.permanence_id)
        if self.status:
            queryset = queryset.filter(status=self.status)
        if self.validation_status:
            queryset = queryset.filter(status=self.validation_status)
        return queryset

    def producer_closures(self):
        queryset = ProducerInvoice.objects.all()
        queryset = self.apply_invoice(queryset)
        if self.producer_id:
            queryset = queryset.filter(producer_id=self.producer_id)
        return queryset.select_related("permanence", "producer").order_by(
            "-permanence__permanence_date",
            "producer__short_profile_name",
        )

    def member_accounts(self):
        if not AccountingPolicy.manage_member_balances():
            return Customer.objects.none()
        queryset = Customer.objects.filter(is_active=True, is_anonymized=False)
        if not AccountingPolicy.use_groups():
            queryset = queryset.filter(group__isnull=True)
        elif self.group_id:
            queryset = queryset.filter(group_id=self.group_id)
        if self.customer_id:
            queryset = queryset.filter(pk=self.customer_id)
        return queryset.select_related("user", "group").order_by(
            "short_basket_name"
        )

    def purchase_lines(self):
        """Offer filter applies only to detailed purchase-line exports."""
        queryset = Purchase.objects.filter(permanence__is_demo=False)
        if self.date_from:
            queryset = queryset.filter(permanence__permanence_date__gte=self.date_from)
        if self.date_to:
            queryset = queryset.filter(permanence__permanence_date__lte=self.date_to)
        if self.permanence_id:
            queryset = queryset.filter(permanence_id=self.permanence_id)
        if getattr(self, "offer_id", None):
            queryset = queryset.filter(offer_item_id=self.offer_id)
        if self.producer_id:
            queryset = queryset.filter(producer_id=self.producer_id)
        if self.customer_id:
            queryset = queryset.filter(customer_id=self.customer_id)
        if self.group_id and AccountingPolicy.use_groups():
            queryset = queryset.filter(customer__group_id=self.group_id)
        if self.status:
            queryset = queryset.filter(status=self.status)
        return queryset.select_related(
            "permanence",
            "producer",
            "customer",
            "offer_item",
        ).order_by(
            "-permanence__permanence_date",
            "producer__short_profile_name",
            "customer__short_basket_name",
        )

    def bank_movements(self):
        if not AccountingPolicy.manage_bank_account():
            return BankAccount.objects.none()
        queryset = BankAccount.objects.filter(permanence__is_demo=False)
        if self.date_from:
            queryset = queryset.filter(operation_date__gte=self.date_from)
        if self.date_to:
            queryset = queryset.filter(operation_date__lte=self.date_to)
        if self.permanence_id:
            queryset = queryset.filter(permanence_id=self.permanence_id)
        if self.producer_id:
            queryset = queryset.filter(producer_id=self.producer_id)
        if self.customer_id:
            queryset = queryset.filter(customer_id=self.customer_id)
        if self.group_id and AccountingPolicy.use_groups():
            queryset = queryset.filter(customer__group_id=self.group_id)
        if self.operation_status:
            queryset = queryset.filter(operation_status=self.operation_status)
        return queryset.select_related(
            "permanence",
            "producer",
            "customer",
        ).order_by("-operation_date", "-id")


def export_purchase_lines(filters=None):
    filters = filters or AccountingExportFilters()
    if not AccountingPolicy.manage_accounting():
        return None
    header = [
        (_("Permanence"), 25),
        (_("Date"), 12),
        (_("Offer"), 30),
        (_("Producer"), 25),
        (_("Member"), 25),
        (_("Ordered"), 12),
        (_("Prepared"), 12),
        (_("Received"), 12),
        (_("Invoiced"), 12),
        (_("Origin"), 18),
    ]
    wb, ws = new_landscape_a4_sheet(
        None,
        _("Purchase lines"),
        _("Real accounting only"),
        header,
    )
    row = 2
    for purchase in filters.purchase_lines().iterator(chunk_size=500):
        ws.cell(row=row, column=1, value=str(purchase.permanence))
        ws.cell(row=row, column=2, value=purchase.permanence.permanence_date)
        ws.cell(row=row, column=3, value=purchase.offer_item.get_long_name_with_customer_price())
        ws.cell(row=row, column=4, value=purchase.producer.short_profile_name)
        ws.cell(row=row, column=5, value=purchase.customer.short_basket_name)
        ws.cell(row=row, column=6, value=purchase.quantity_ordered)
        ws.cell(row=row, column=7, value=purchase.quantity_prepared)
        ws.cell(row=row, column=8, value=purchase.quantity_received)
        ws.cell(row=row, column=9, value=purchase.quantity_invoiced)
        ws.cell(row=row, column=10, value=purchase.origin)
        row += 1
    return wb


def export_preparation_trace(filters=None):
    from repanier.models.preparation import DepositReceipt, PreparationSyncEvent

    filters = filters or AccountingExportFilters()
    queryset = PreparationSyncEvent.objects.filter(
        permanence__is_demo=False,
    )
    if filters.permanence_id:
        queryset = queryset.filter(permanence_id=filters.permanence_id)

    header = [
        (_("Permanence"), 25),
        (_("UUID"), 38),
        (_("Operation"), 18),
        (_("Origin"), 16),
        (_("Validated by"), 22),
        (_("Validated at"), 22),
        (_("Accounting applied"), 22),
        (_("Status"), 15),
        (_("Conflict"), 25),
    ]
    wb, ws = new_landscape_a4_sheet(
        None,
        _("Preparation trace"),
        _("Real accounting only"),
        header,
    )
    row = 2
    for event in queryset.select_related(
        "permanence",
        "purchase",
        "purchase__offer_item",
        "validated_by",
    ).order_by("permanence_id", "client_timestamp", "id"):
        ws.cell(row=row, column=1, value=str(event.permanence))
        ws.cell(row=row, column=2, value=str(event.uuid))
        ws.cell(row=row, column=3, value=event.operation)
        ws.cell(row=row, column=4, value=event.purchase.origin if event.purchase else "")
        ws.cell(row=row, column=5, value=str(event.validated_by) if event.validated_by else "")
        ws.cell(row=row, column=6, value=event.validated_at)
        ws.cell(row=row, column=7, value=event.accounting_applied_at)
        ws.cell(row=row, column=8, value=event.accounting_status or event.status)
        ws.cell(row=row, column=9, value=event.conflict_reason)
        row += 1

    receipt_qs = DepositReceipt.objects.filter(permanence__is_demo=False)
    if filters.permanence_id:
        receipt_qs = receipt_qs.filter(permanence_id=filters.permanence_id)
    wb, receipts_ws = new_landscape_a4_sheet(
        wb,
        _("Deposit receipts"),
        _("Real accounting only"),
        [
            (_("Permanence"), 25),
            (_("UUID"), 38),
            (_("Customer"), 22),
            (_("Container"), 22),
            (_("Returned"), 12),
            (_("Missing"), 12),
            (_("Credit"), 12),
            (_("Accounting applied"), 22),
        ],
    )
    row = 2
    for receipt in receipt_qs.select_related(
        "permanence",
        "customer",
        "container_type",
    ).order_by("permanence_id", "client_timestamp", "id"):
        receipts_ws.cell(row=row, column=1, value=str(receipt.permanence))
        receipts_ws.cell(row=row, column=2, value=str(receipt.uuid))
        receipts_ws.cell(row=row, column=3, value=str(receipt.customer) if receipt.customer else "")
        receipts_ws.cell(row=row, column=4, value=str(receipt.container_type))
        receipts_ws.cell(row=row, column=5, value=receipt.returned_count)
        receipts_ws.cell(row=row, column=6, value=receipt.missing_count)
        receipts_ws.cell(row=row, column=7, value=receipt.credit_amount.amount)
        receipts_ws.cell(row=row, column=8, value=receipt.accounting_applied_at)
        row += 1
    return wb


def _http_response(wb, filename):
    if not isinstance(wb, Workbook):
        raise TypeError("An openpyxl Workbook is required")
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="{}.xlsx"'.format(
        slugify(filename) or "accounting-export"
    )
    return response


def export_producer_closures(filters=None):
    filters = filters or AccountingExportFilters()
    if not AccountingPolicy.manage_accounting():
        return None

    wb = None
    header = [
        (_("Permanence"), 25),
        (_("Date"), 12),
        (_("Producer"), 25),
        (_("Status"), 15),
        (_("Calculated"), 15),
        (_("Claimed"), 15),
        (_("Booked"), 15),
        (_("Reference"), 20),
    ]
    wb, ws = new_landscape_a4_sheet(
        wb,
        _("Producer closures"),
        _("Accounting export"),
        header,
    )
    row = 2
    for invoice in filters.producer_closures().iterator(chunk_size=500):
        ws.cell(row=row, column=1, value=invoice.permanence.get_permanence_display())
        ws.cell(row=row, column=2, value=invoice.permanence.permanence_date)
        ws.cell(row=row, column=3, value=invoice.producer.short_profile_name)
        ws.cell(row=row, column=4, value=invoice.get_status_display())
        ws.cell(row=row, column=5, value=invoice.calculated_invoiced_balance.amount)
        ws.cell(row=row, column=6, value=invoice.to_be_invoiced_balance.amount)
        ws.cell(row=row, column=7, value=invoice.get_total_price_with_tax().amount)
        ws.cell(row=row, column=8, value=invoice.invoice_reference)
        row += 1

    return wb


def export_member_accounts(filters=None):
    filters = filters or AccountingExportFilters()
    if not AccountingPolicy.manage_member_balances():
        return None

    header = [
        (_("Member"), 25),
        (_("Group"), 20),
        (_("Initial balance"), 15),
        (_("Balance"), 15),
        (_("Email"), 25),
    ]
    wb, ws = new_landscape_a4_sheet(
        None,
        _("Member accounts"),
        _("Accounting export"),
        header,
    )
    row = 2
    for customer in filters.member_accounts().iterator(chunk_size=500):
        ws.cell(row=row, column=1, value=customer.short_basket_name)
        ws.cell(row=row, column=2, value=customer.group.short_basket_name if customer.group else "")
        ws.cell(row=row, column=3, value=customer.initial_balance.amount)
        ws.cell(row=row, column=4, value=customer.balance.amount)
        ws.cell(row=row, column=5, value=customer.user.email if customer.user else "")
        row += 1

    if AccountingPolicy.manage_bank_account():
        wb, movements_ws = new_landscape_a4_sheet(
            wb,
            _("Member movements"),
            _("Accounting export"),
            [
                (_("Date"), 12),
                (_("Member"), 25),
                (_("Cash in"), 15),
                (_("Cash out"), 15),
                (_("Status"), 15),
                (_("Comment"), 40),
            ],
        )
        row = 2
        for movement in filters.bank_movements().iterator(chunk_size=500):
            if movement.customer_id is None:
                continue
            movements_ws.cell(row=row, column=1, value=movement.operation_date)
            movements_ws.cell(row=row, column=2, value=movement.customer.short_basket_name)
            movements_ws.cell(row=row, column=3, value=movement.bank_amount_in.amount)
            movements_ws.cell(row=row, column=4, value=movement.bank_amount_out.amount)
            movements_ws.cell(row=row, column=5, value=movement.get_operation_status_display())
            movements_ws.cell(row=row, column=6, value=movement.operation_comment)
            row += 1

    return wb


def export_closing_producer_response(filters=None):
    wb = export_producer_closures(filters)
    if wb is None:
        return None
    response = _http_response(wb, "producer-closures")
    return response


def export_member_accounts_response(filters=None):
    wb = export_member_accounts(filters)
    if wb is None:
        return None
    response = _http_response(wb, "member-accounts")
    return response
