from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction
from django.db.models import F, Q, Sum

from repanier.accounting_policy import AccountingPolicy
from repanier.const import (
    BankMovement,
    DECIMAL_ZERO,
    OrderUnit,
    PreparationOrigin,
    PreparationStatus,
    SaleStatus,
)
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.preparation import PreparationSyncEvent
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.models.purchase import Purchase


class ClosingBalance:
    def __init__(self, permanence):
        self.permanence = permanence
        self.blocking = []
        self.warnings = []

    def add_blocking(self, code, message, category="accounting"):
        self.blocking.append({
            "code": code,
            "message": str(message),
            "category": category,
        })

    def add_warning(self, code, message, category="accounting"):
        self.warnings.append({
            "code": code,
            "message": str(message),
            "category": category,
        })

    @property
    def is_valid(self):
        return not self.blocking

    def check(self):
        if getattr(self.permanence, "is_demo", False):
            self.add_blocking(
                "DEMO",
                "Demo/test permanences cannot enter real accounting closure.",
                "isolation",
            )
            return self

        if self.permanence.status != SaleStatus.SEND:
            self.add_blocking(
                "STATUS",
                "This permanence is not in the closing state.",
                "status",
            )

        if getattr(self.permanence, "preparation_enabled", False):
            unvalidated = Purchase.objects.filter(
                permanence=self.permanence,
            ).exclude(preparation_status=PreparationStatus.VALIDATED)
            if unvalidated.exists():
                self.add_blocking(
                    "PREPARATION_VALIDATION",
                    "All mobile-preparation purchases must be validated before accounting closure.",
                    "preparation",
                )

            quantity_gaps = Purchase.objects.filter(
                permanence=self.permanence,
            ).filter(
                ~Q(quantity_prepared=F("quantity_ordered"))
                | ~Q(quantity_received=F("quantity_ordered"))
            )
            if quantity_gaps.exists():
                self.add_warning(
                    "PREPARATION_QUANTITY_GAP",
                    "Prepared or received quantities differ from the recorded order.",
                    "quantity",
                )

            unsettled = PreparationSyncEvent.objects.filter(
                permanence=self.permanence,
            ).exclude(
                status__in=[
                    PreparationSyncEvent.STATUS_APPLIED,
                    PreparationSyncEvent.STATUS_REJECTED,
                ]
            )
            if unsettled.exists():
                self.add_blocking(
                    "PREPARATION_SYNC_PENDING",
                    "Preparation synchronization events are pending or conflicting.",
                    "synchronization",
                )

            if PreparationSyncEvent.objects.filter(
                permanence=self.permanence,
                status=PreparationSyncEvent.STATUS_CONFLICT,
            ).exists():
                self.add_blocking(
                    "PREPARATION_SYNC_CONFLICT",
                    "Preparation synchronization conflicts must be resolved.",
                    "synchronization",
                )

        incomplete_purchases = Purchase.objects.filter(
            permanence_id=self.permanence.id,
        ).exclude(
            customer_id__isnull=False,
            producer_id__isnull=False,
            offer_item_id__isnull=False,
            customer_invoice_id__isnull=False,
            producer_invoice_id__isnull=False,
            customer_producer_invoice_id__isnull=False,
        )
        if incomplete_purchases.exists():
            self.add_blocking(
                "PURCHASE_LINKS",
                "One or more purchase lines are missing required links.",
            )

        incoherent_links = False
        for purchase in Purchase.objects.filter(
            permanence_id=self.permanence.id
        ).select_related(
            "customer_invoice",
            "producer_invoice",
            "customer_producer_invoice",
        ):
            if (
                purchase.customer_invoice is None
                or purchase.producer_invoice is None
                or purchase.customer_producer_invoice is None
                or purchase.customer_invoice.permanence_id != self.permanence.id
                or purchase.producer_invoice.permanence_id != self.permanence.id
                or purchase.customer_producer_invoice.permanence_id != self.permanence.id
            ):
                incoherent_links = True
                break
        if incoherent_links:
            self.add_blocking(
                "PURCHASE_LINKS",
                "One or more purchase lines point to accounting books of another permanence.",
            )

        without_quantity = Purchase.objects.filter(
            permanence_id=self.permanence.id,
            quantity_invoiced=DECIMAL_ZERO,
        ).exclude(quantity_ordered=DECIMAL_ZERO)
        if without_quantity.exists():
            self.add_warning(
                "ZERO_INVOICED_QUANTITY",
                "One or more ordered lines have no invoiced quantity.",
                "quantity",
            )

        added_late = Purchase.objects.filter(
            permanence_id=self.permanence.id,
            quantity_ordered=DECIMAL_ZERO,
        ).exclude(quantity_invoiced=DECIMAL_ZERO)
        if added_late.exists():
            self.add_warning(
                "LATE_PRODUCT",
                "Products added during closure with no originally ordered quantity.",
                "quantity",
            )

        if AccountingPolicy.manage_accounting():
            if not CustomerInvoice.objects.filter(
                permanence_id=self.permanence.id
            ).exists():
                self.add_blocking(
                    "CUSTOMER_BOOKS",
                    "No customer accounting books exist for this permanence.",
                )
            if not ProducerInvoice.objects.filter(
                permanence_id=self.permanence.id
            ).exists():
                self.add_warning(
                    "PRODUCER_BOOKS",
                    "No producer accounting books exist for this permanence.",
                )

        if AccountingPolicy.manage_bank_account():
            latest = BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL,
                permanence_id__isnull=True,
            ).first()
            if latest is not None and latest.operation_date is None:
                self.add_blocking(
                    "BANK_ANCHOR",
                    "The latest bank anchor has no operation date.",
                )

        if (
            AccountingPolicy.manage_permanence_accounting()
            and BankAccount.get_latest_total() is None
        ):
            # Permanence.invoice() cannot invoice without this anchor
            self.add_blocking(
                "BANK_ANCHOR_MISSING",
                "No latest bank total exists: the permanence cannot be invoiced.",
            )

        if (
            getattr(settings, "REPANIER_SETTINGS_MANAGE_ACCOUNTING", True)
            and AccountingPolicy.manage_accounting()
        ):
            customer_total = Purchase.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("selling_price"))["total"] or DECIMAL_ZERO
            customer_books = CustomerInvoice.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("total_price_with_tax"))["total"] or DECIMAL_ZERO
            if getattr(customer_total, "amount", customer_total) != getattr(
                customer_books, "amount", customer_books
            ):
                self.add_blocking(
                    "AUDIT_C",
                    "Customer purchase totals differ from customer accounting books.",
                )

            producer_total = Purchase.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("purchase_price"))["total"] or DECIMAL_ZERO
            producer_books = ProducerInvoice.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("total_price_with_tax"))["total"] or DECIMAL_ZERO
            if getattr(producer_total, "amount", producer_total) != getattr(
                producer_books, "amount", producer_books
            ):
                self.add_blocking(
                    "AUDIT_D",
                    "Producer purchase totals differ from producer accounting books.",
                )
        elif not getattr(settings, "REPANIER_SETTINGS_MANAGE_ACCOUNTING", True):
            customer_total = Purchase.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("selling_price"))["total"] or DECIMAL_ZERO
            customer_books = CustomerInvoice.objects.filter(
                permanence_id=self.permanence.id
            ).aggregate(total=Sum("total_price_with_tax"))["total"] or DECIMAL_ZERO
            if getattr(customer_total, "amount", customer_total) != getattr(
                customer_books, "amount", customer_books
            ):
                self.add_warning(
                    "AUDIT_C",
                    "Customer purchase totals differ from the pending customer books.",
                )

        return self


def check_closing_balance(permanence):
    return ClosingBalance(permanence).check()


@transaction.atomic
def create_accounting_adjustment(*, permanence, customer, offer_item, quantity):
    if not AccountingPolicy.manage_permanence_accounting():
        raise ValidationError(
            "Accounting adjustment is not available in this accounting mode."
        )
    permanence = Permanence.objects.select_for_update().get(pk=permanence.pk)
    if permanence.is_demo:
        raise ValidationError(
            "Demo permanences cannot create accounting adjustments."
        )
    if permanence.status != SaleStatus.SEND:
        raise ValidationError("Only a permanence awaiting invoicing can be adjusted.")
    if (
        not getattr(customer, "may_order", False)
        or not getattr(customer, "is_active", False)
        or getattr(customer, "is_anonymized", False)
    ):
        raise ValidationError(
            "The customer is not eligible for accounting adjustments."
        )
    quantity = Decimal(str(quantity))
    if not quantity.is_finite() or quantity <= DECIMAL_ZERO:
        raise ValidationError(
            "Accounting adjustment quantity must be positive."
        )
    DecimalValidator(9, 4)(quantity)
    if offer_item.permanence_id != permanence.id:
        raise ValidationError(
            "The offer item must belong to this permanence."
        )

    customer_invoice = CustomerInvoice.get_or_create_invoice(
        permanence_id=permanence.id,
        customer_id=customer.id,
        status=permanence.status,
    )
    producer_invoice = ProducerInvoice.get_or_create_invoice(
        permanence_id=permanence.id,
        producer_id=offer_item.producer_id,
        status=permanence.status,
    )
    customer_producer_invoice = CustomerProducerInvoice.get_or_create_invoice(
        permanence_id=permanence.id,
        customer_id=customer.id,
        producer_id=offer_item.producer_id,
    )
    purchase = Purchase.objects.select_for_update().filter(
        permanence=permanence,
        customer=customer,
        offer_item=offer_item,
        is_box_content=False,
    ).first()
    if purchase is None:
        purchase = Purchase.objects.create(
            permanence=permanence,
            offer_item=offer_item,
            producer=offer_item.producer,
            customer=customer,
            customer_invoice=customer_invoice,
            producer_invoice=producer_invoice,
            customer_producer_invoice=customer_producer_invoice,
            status=permanence.status,
            quantity_ordered=DECIMAL_ZERO,
            quantity_invoiced=quantity,
            quantity_prepared=quantity,
            quantity_received=quantity,
            preparation_status=(
                PreparationStatus.VALIDATED
                if getattr(permanence, "preparation_enabled", False)
                else PreparationStatus.ORDERED
            ),
            origin=PreparationOrigin.ACCOUNTING_ADJUSTMENT,
            purchase_price=offer_item.producer_unit_price,
            selling_price=offer_item.customer_unit_price,
        )
    else:
        for field in ("quantity_invoiced", "quantity_prepared", "quantity_received"):
            new_quantity = getattr(purchase, field) + quantity
            DecimalValidator(9, 4)(new_quantity)
            setattr(purchase, field, new_quantity)
        purchase.origin = PreparationOrigin.ACCOUNTING_ADJUSTMENT
        purchase.save()
    permanence.calculate_order_amount()
    return purchase


@transaction.atomic
def create_catalogue_adjustment(*, permanence, customer, product, quantity):
    permanence = Permanence.objects.select_for_update().get(pk=permanence.pk)
    if permanence.is_demo or permanence.status != SaleStatus.SEND:
        raise ValidationError("Only a real permanence awaiting invoicing can be adjusted.")
    product = Product.objects.select_for_update().get(pk=product.pk)
    if (
        not product.is_active
        or product.is_box
        or product.order_unit >= OrderUnit.DEPOSIT
        or not permanence.producers.filter(pk=product.producer_id).exists()
    ):
        raise ValidationError("The catalogue product is not eligible for this permanence.")
    from repanier.models.offeritem import OfferItem

    offer_item = OfferItem.objects.filter(permanence=permanence, product=product).first()
    if offer_item is None:
        offer_item = product.get_or_create_offer_item(permanence)
    return create_accounting_adjustment(
        permanence=permanence, customer=customer, offer_item=offer_item, quantity=quantity,
    )
