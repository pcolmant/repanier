from django.conf import settings
from django.db import models
from django.db.models import Sum, DecimalField
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField

from repanier.const import (
    DECIMAL_ZERO,
    EMPTY_STRING,
    DECIMAL_ONE,
    RoundUpTo,
    SaleStatus,
    OrderUnit,
)
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.models.item import Item


class OfferItem(Item):
    long_name_v2 = models.CharField(
        _("Long name"), max_length=100, default=EMPTY_STRING, blank=True
    )
    cache_part_a_v2 = HTMLField(default=EMPTY_STRING, blank=True)
    cache_part_b_v2 = HTMLField(default=EMPTY_STRING, blank=True)
    order_sort_order_v2 = models.IntegerField(default=0, db_index=True)
    preparation_sort_order_v2 = models.IntegerField(default=0, db_index=True)
    producer_sort_order_v2 = models.IntegerField(default=0, db_index=True)
    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=_("Sale"),
        on_delete=models.PROTECT,
        db_index=True,
    )
    product = models.ForeignKey(
        "Product", verbose_name=_("Product"), on_delete=models.PROTECT
    )
    # is a box content
    is_box_content = models.BooleanField(default=False)
    is_resale_price_fixed = models.BooleanField(
        _("The resale price is fixed (boxes, deposit)"), default=False
    )

    # Calculated with Purchase : Total producer purchase price vat included
    total_purchase_with_tax = ModelRepanierMoneyField(
        _("Accounted to the producer w VAT"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    # Calculated with Purchase : Total customer selling price vat included
    total_selling_with_tax = ModelRepanierMoneyField(
        _("Accounted to the customer w VAT"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )

    # Calculated with Purchase : Quantity invoiced to all customers
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via permanence.send_to_producer()
    quantity_invoiced = models.DecimalField(
        _("Quantity accounted for"),
        max_digits=9,
        decimal_places=4,
        default=DECIMAL_ZERO,
    )
    use_order_unit_converted = models.BooleanField(default=False)

    may_order = models.BooleanField(_("May order"), default=True)
    manage_production = models.BooleanField(default=False)

    def get_q_alert(self, q_previous_order=DECIMAL_ZERO):
        return self.product.get_q_alert(
            quantity_invoiced=self.quantity_invoiced - q_previous_order
        )

    def get_quantity_invoiced(self):
        if self.quantity_invoiced != 0:
            return mark_safe(
                _("%(qty)s") % {"qty": number_format(self.quantity_invoiced, 2)}
            )
        return EMPTY_STRING

    get_quantity_invoiced.short_description = _("Quantity sold")
    get_quantity_invoiced.admin_order_field = "quantity_invoiced"

    def get_producer_unit_price_invoiced(self):
        if self.producer_unit_price.amount > self.customer_unit_price.amount:
            return self.customer_unit_price
        else:
            return self.producer_unit_price

    def get_producer_row_price_invoiced(self):
        if self.producer_unit_price.amount > self.customer_unit_price.amount:
            return self.total_selling_with_tax
        else:
            return self.total_purchase_with_tax

    def get_price_list_multiplier(self, customer_invoice):
        price_list_multiplier = DECIMAL_ONE
        if not self.is_resale_price_fixed:
            price_list_multiplier = customer_invoice.price_list_multiplier
        return price_list_multiplier

    def get_customer_unit_price(self, price_list_multiplier):
        if price_list_multiplier == DECIMAL_ONE:
            return self.customer_unit_price.amount
        else:
            return (self.customer_unit_price.amount * price_list_multiplier).quantize(
                RoundUpTo.TWO_DECIMALS
            )

    def get_producer_unit_price(self, price_list_multiplier=None):
        if self.manage_production:
            return self.get_customer_unit_price(price_list_multiplier)
        return self.producer_unit_price.amount

    def get_unit_deposit(self):
        return self.unit_deposit.amount

    def get_html_producer_price_purchased(self):
        price = self.total_purchase_with_tax
        if price != DECIMAL_ZERO:
            return mark_safe(_("<b>%(price)s</b>") % {"price": price})
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = _("Row amount")
    get_html_producer_price_purchased.admin_order_field = "total_purchase_with_tax"

    def get_html_like(self, user):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
            return mark_safe(
                '<span class="glyphicon glyphicon-heart{}" onclick="like_ajax({});return false;"></span>'.format(
                    EMPTY_STRING
                    if self.product.likes.filter(id=user.id).only("id").exists()
                    else "-empty",
                    self.id,
                )
            )
        else:
            return mark_safe(
                '<span class="fa{} fa-heart" onclick="like_ajax({});return false;"></span>'.format(
                    "s"
                    if self.product.likes.filter(id=user.id).only("id").exists()
                    else "r",
                    self.id,
                )
            )

    def get_order_name(self):
        qty_display = self.get_qty_display()
        if qty_display:
            return "{} {}".format(
                self.long_name_v2,
                qty_display,
            )
        return "{}".format(self.long_name_v2)

    def get_qty_display(self):
        if self.use_order_unit_converted:
            # The only conversion done in permanence concerns OrderUnit.PC_KG
            # so we are sure that self.order_unit == OrderUnit.PC_KG
            qty_display = self.get_display(
                qty=1,
                order_unit=OrderUnit.KG,
                with_qty_display=False,
                with_price_display=False,
            )
        else:
            qty_display = self.get_display(
                qty=1,
                order_unit=self.order_unit,
                with_qty_display=False,
                with_price_display=False,
            )
        return qty_display

    def __str__(self):
        return self.get_long_name_with_producer_price()

    class Meta:
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")
        unique_together = ("permanence", "product")


class OfferItemReadOnly(OfferItem):
    def calculate_order_amount(self, status: SaleStatus):
        from repanier.models.purchase import PurchaseWoReceiver

        query_set = PurchaseWoReceiver.objects.filter(
            offer_item_id=self.id, status__lt=SaleStatus.SEND
        )

        result_set = query_set.aggregate(
            quantity_ordered=Sum(
                "quantity_ordered",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            quantity_invoiced=Sum(
                "quantity_invoiced",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            purchase_price=Sum(
                "purchase_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            selling_price=Sum(
                "selling_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        if status < SaleStatus.WAIT_FOR_SEND:
            self.quantity_invoiced = (
                result_set["quantity_ordered"]
                if result_set["quantity_ordered"] is not None
                else DECIMAL_ZERO
            )
        else:
            self.quantity_invoiced = (
                result_set["quantity_invoiced"]
                if result_set["quantity_invoiced"] is not None
                else DECIMAL_ZERO
            )
        self.total_purchase_with_tax.amount = (
            result_set["purchase_price"]
            if result_set["purchase_price"] is not None
            else DECIMAL_ZERO
        )
        self.total_selling_with_tax.amount = (
            result_set["selling_price"]
            if result_set["selling_price"] is not None
            else DECIMAL_ZERO
        )

        query_set = PurchaseWoReceiver.objects.filter(
            offer_item_id=self.id, status__gte=SaleStatus.SEND
        )

        result_set = query_set.aggregate(
            quantity_invoiced=Sum(
                "quantity_invoiced",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            purchase_price=Sum(
                "purchase_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            selling_price=Sum(
                "selling_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        self.quantity_invoiced += (
            result_set["quantity_invoiced"]
            if result_set["quantity_invoiced"] is not None
            else DECIMAL_ZERO
        )
        self.total_purchase_with_tax.amount += (
            result_set["purchase_price"]
            if result_set["purchase_price"] is not None
            else DECIMAL_ZERO
        )
        self.total_selling_with_tax.amount += (
            result_set["selling_price"]
            if result_set["selling_price"] is not None
            else DECIMAL_ZERO
        )

    def get_producer_quantity(self, status: SaleStatus):
        if status < SaleStatus.WAIT_FOR_SEND:
            return self.quantity_invoiced
        else:
            if self.order_unit == OrderUnit.PC_KG:
                if self.order_average_weight != 0:
                    return (
                        self.quantity_invoiced / self.order_average_weight
                    ).quantize(RoundUpTo.FOUR_DECIMALS)
            return self.quantity_invoiced

    def __str__(self):
        return self.get_long_name_with_producer_price()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")


class OfferItemSend(OfferItem):
    def __str__(self):
        return self.get_long_name_with_producer_price()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")
