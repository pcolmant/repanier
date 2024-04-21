import logging

from django.core.validators import MinValueValidator
from django.db import transaction
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.models.invoice import (
    CustomerInvoice,
    ProducerInvoice,
    CustomerProducerInvoice,
)
from repanier.tools import cap

logger = logging.getLogger(__name__)


class PurchaseManager(models.Manager):
    def get_invoices(self, permanence=None, year=None, customer=None, producer=None):
        purchase_set = (
            super().get_queryset().order_by("permanence", "customer", "producer", "offer_item")
        )
        if permanence is not None:
            purchase_set = purchase_set.filter(permanence_id=permanence.id)
        if year is not None:
            purchase_set = purchase_set.filter(permanence__permanence_date__year=year)
        if customer is not None:
            purchase_set = purchase_set.filter(
                customer_invoice__customer_charged_id=customer.id
            )
        if producer is not None:
            purchase_set = purchase_set.filter(producer_id=producer.id)
        return purchase_set


class Purchase(models.Model):
    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=_("Sale"),
        on_delete=models.PROTECT,
        db_index=True,
    )
    status = models.CharField(
        max_length=3,
        choices=SaleStatus.choices,
        default=SaleStatus.PLANNED,
        verbose_name=_("Accounting entry status"),
    )
    offer_item = models.ForeignKey(
        "OfferItem", verbose_name=_("Offer item"), on_delete=models.PROTECT
    )
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    customer = models.ForeignKey(
        "Customer", verbose_name=_("Customer"), on_delete=models.PROTECT, db_index=True
    )
    customer_producer_invoice = models.ForeignKey(
        "CustomerProducerInvoice", on_delete=models.PROTECT, db_index=True
    )
    producer_invoice = models.ForeignKey(
        "ProducerInvoice",
        verbose_name=_("Accounting entry"),
        on_delete=models.PROTECT,
        db_index=True,
    )
    customer_invoice = models.ForeignKey(
        "CustomerInvoice",
        verbose_name=_("Accounting entry"),
        on_delete=models.PROTECT,
        db_index=True,
    )

    is_box = models.BooleanField(default=False)
    is_box_content = models.BooleanField(default=False)

    quantity_ordered = models.DecimalField(
        _("Quantity ordered"), max_digits=9, decimal_places=4, default=DECIMAL_ZERO
    )
    quantity_confirmed = models.DecimalField(
        _("Quantity confirmed"), max_digits=9, decimal_places=4, default=DECIMAL_ZERO
    )
    # 0 if this is not a KG product -> the preparation list for this product will be produced by family
    # qty if not -> the preparation list for this product will be produced by qty then by family
    quantity_for_preparation_sort_order = models.DecimalField(
        _("Quantity for preparation order_by"),
        max_digits=9,
        decimal_places=4,
        default=DECIMAL_ZERO,
    )
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via permanence.send_to_producer()
    quantity_invoiced = models.DecimalField(
        _("Quantity accounted for"), max_digits=9, decimal_places=4, default=DECIMAL_ZERO
    )
    purchase_price = ModelRepanierMoneyField(
        _("Producer row price"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    selling_price = ModelRepanierMoneyField(
        _("Customer row price"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )

    producer_vat = ModelRepanierMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    customer_vat = ModelRepanierMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    deposit = ModelRepanierMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    price_list_multiplier = models.DecimalField(
        _(
            "Coefficient applied to the producer tariff to calculate the customer tariff"
        ),
        help_text=_(
            "This multiplier is applied to each price automatically imported/pushed."
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    is_resale_price_fixed = models.BooleanField(
        _("Customer prices are set by the producer"), default=False
    )
    comment = models.CharField(
        _("Comment"), max_length=100, blank=True, default=EMPTY_STRING
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True, db_index=True)

    def get_customer_unit_price(self):
        offer_item = self.offer_item
        price_list_multiplier = offer_item.get_price_list_multiplier(
            self.customer_invoice
        )
        return offer_item.get_customer_unit_price(price_list_multiplier)

    get_customer_unit_price.short_description = _("Customer unit price")

    def get_customer_unit_vat(self):
        offer_item = self.offer_item
        if self.price_list_multiplier == DECIMAL_ONE:
            return offer_item.customer_vat.amount
        else:
            return (
                offer_item.customer_vat.amount * self.price_list_multiplier
            ).quantize(RoundUpTo.FOUR_DECIMALS)

    def get_producer_unit_vat(self):
        offer_item = self.offer_item
        if offer_item.manage_production:
            return self.get_customer_unit_vat()
        return offer_item.producer_vat.amount

    def get_selling_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.selling_price

    get_selling_price.short_description = _("Row amount")

    def get_producer_unit_price(self):
        offer_item = self.offer_item
        # if offer_item.manage_production:
        #     return self.get_customer_unit_price()
        return offer_item.producer_unit_price.amount

    get_producer_unit_price.short_description = _("Producer unit price")

    def get_html_producer_unit_price(self):
        if self.offer_item is not None:
            return format_html("<b>{}</b>", self.get_producer_unit_price())
        return EMPTY_STRING

    get_html_producer_unit_price.short_description = _("Producer unit price")

    def get_html_unit_deposit(self):
        if self.offer_item is not None:
            return mark_safe(
                _("<b>%(price)s</b>") % {"price": self.offer_item.unit_deposit}
            )
        return EMPTY_STRING

    get_html_unit_deposit.short_description = _("Deposit")

    def get_permanence_display(self):
        return self.permanence.get_permanence_display()

    get_permanence_display.short_description = _("Permanence")

    def get_delivery_display(self):
        if self.customer_invoice is None:
            return EMPTY_STRING
        return self.customer_invoice.get_delivery_display()

    get_delivery_display.short_description = _("Delivery point")

    def get_quantity(self):
        if self.status < SaleStatus.WAIT_FOR_SEND:
            return self.quantity_ordered
        else:
            return self.quantity_invoiced

    get_quantity.short_description = _("Quantity accounted for")

    def set_quantity(self, quantity):
        if self.status < SaleStatus.WAIT_FOR_SEND:
            self.quantity_ordered = quantity
        else:
            self.quantity_invoiced = quantity

    def get_producer_quantity(self):
        if self.status < SaleStatus.WAIT_FOR_SEND:
            return self.quantity_ordered
        else:
            offer_item = self.offer_item
            if offer_item.order_unit == OrderUnit.PC_KG:
                if offer_item.order_average_weight > DECIMAL_ZERO:
                    return (
                        self.quantity_invoiced / offer_item.order_average_weight
                    ).quantize(RoundUpTo.FOUR_DECIMALS)
            return self.quantity_invoiced

    def get_long_name_with_customer_price(self):
        return self.offer_item.get_long_name_with_customer_price()

    def set_comment(self, comment):
        if comment:
            if self.comment:
                self.comment = cap("{}, {}".format(self.comment, comment), 100)
            else:
                self.comment = cap(comment, 100)

    @transaction.atomic
    def save(self, *args, **kwargs):
        # logger.info("purchase save : {}".format(self.pk))
        if not self.pk:
            # This code only happens if the objects is not in the database yet.
            # Otherwise it would have pk
            self.customer_invoice = CustomerInvoice.get_or_create_invoice(
                permanence_id=self.permanence_id,
                customer_id=self.customer_id,
                status=self.status,
            )
            self.producer_invoice = ProducerInvoice.get_or_create_invoice(
                permanence_id=self.permanence_id,
                producer_id=self.producer_id,
                status=self.status,
            )
            self.customer_producer_invoice = (
                CustomerProducerInvoice.get_or_create_invoice(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_id,
                    producer_id=self.producer_id,
                )
            )
        super().save(*args, **kwargs)

    def __str__(self):
        if hasattr(self, "offer_item"):
            return "{} > {} > {}".format(
                self.permanence,
                self.customer,
                self.offer_item.get_long_name_with_customer_price(),
            )
        else:
            return EMPTY_STRING
        # Use to not display label (inline_admin_form.original) into the inline form (tabular.html)
        # return EMPTY_STRING

    objects = PurchaseManager()

    class Meta:
        verbose_name = _("Purchase")
        verbose_name_plural = _("Purchases")
        # ordering = ("permanence", "customer", "offer_item", "is_box_content")
        unique_together = ("customer", "offer_item", "is_box_content")
        # UniqueConstraint(
        #     fields=["customer", "offer_item", "is_box_content"], name="unique01"
        # )
        indexes = [
            models.Index(
                fields=["permanence", "customer_invoice"],
                name="repanier_purchase_idx01",
            ),
            models.Index(
                fields=["permanence", "producer"], name="repanier_purchase_idx02"
            ),
            models.Index(
                fields=["permanence", "customer"], name="repanier_purchase_idx03"
            ),
            models.Index(
                fields=["permanence", "producer", "customer"],
                name="repanier_purchase_idx04",
            ),
            models.Index(
                fields=[
                    "offer_item",
                    "status",
                ],
                name="repanier_purchase_idx05",
            ),
        ]


class PurchaseWoReceiver(Purchase):
    def __str__(self):
        return EMPTY_STRING

    class Meta:
        proxy = True
        verbose_name = _("Purchase")
        verbose_name_plural = _("Purchases")
