from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatedFields

from repanier.const import (
    DECIMAL_ZERO,
    EMPTY_STRING,
    PRODUCT_ORDER_UNIT_KG,
)
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.models.item import Item


class OfferItem(Item):
    translations = TranslatedFields(
        long_name=models.CharField(
            _("Long name"), max_length=100, default=EMPTY_STRING, blank=True
        ),
        cache_part_a=HTMLField(default=EMPTY_STRING, blank=True),
        cache_part_b=HTMLField(default=EMPTY_STRING, blank=True),
        # Language dependant customer sort order for optimization
        order_sort_order=models.IntegerField(default=0, db_index=True),
        # Language dependant preparation sort order for optimization
        preparation_sort_order=models.IntegerField(default=0, db_index=True),
        # Language dependant producer sort order for optimization
        producer_sort_order=models.IntegerField(default=0, db_index=True),
    )
    long_name_v2 = models.CharField(
        _("Long name"), max_length=100, default=EMPTY_STRING, blank=True
    )
    cache_part_a_v2 = HTMLField(default=EMPTY_STRING, blank=True)
    cache_part_b_v2 = HTMLField(default=EMPTY_STRING, blank=True)
    # Language dependant customer sort order for optimization
    order_sort_order_v2 = models.IntegerField(default=0, db_index=True)
    # Language dependant preparation sort order for optimization
    preparation_sort_order_v2 = models.IntegerField(default=0, db_index=True)
    # Language dependant producer sort order for optimization
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

    producer_price_are_wo_vat = models.BooleanField(
        _("Producer price are without vat"), default=False
    )
    price_list_multiplier = models.DecimalField(
        _(
            "Coefficient applied to the producer tariff to calculate the customer tariff"
        ),
        help_text=_(
            "This multiplier is applied to each price automatically imported/pushed."
        ),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    is_resale_price_fixed = models.BooleanField(
        _("The resale price is fixed (boxes, deposit)"), default=False
    )

    # Calculated with Purchase : Total producer purchase price vat included
    total_purchase_with_tax = ModelRepanierMoneyField(
        _("Producer amount invoiced"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    # Calculated with Purchase : Total customer selling price vat included
    total_selling_with_tax = ModelRepanierMoneyField(
        _("Invoiced to the customer w TVA"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )

    # Calculated with Purchase : Quantity invoiced to all customers
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via permanence.recalculate_order_amount(..., send_to_producer=True)
    quantity_invoiced = models.DecimalField(
        _("Qty invoiced"), max_digits=9, decimal_places=4, default=DECIMAL_ZERO
    )
    use_order_unit_converted = models.BooleanField(default=False)

    may_order = models.BooleanField(_("May order"), default=True)
    manage_production = models.BooleanField(default=False)

    def get_quantity_invoiced(self):
        if self.quantity_invoiced != 0:
            return mark_safe(
                _("%(qty)s") % {"qty": number_format(self.quantity_invoiced, 2)}
            )
        return EMPTY_STRING

    get_quantity_invoiced.short_description = _(
        "Quantity sold"
    )
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

    def get_html_producer_price_purchased(self):
        price = self.total_purchase_with_tax
        if price != DECIMAL_ZERO:
            return mark_safe(_("<b>%(price)s</b>") % {"price": price})
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = _("Producer amount invoiced")
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
        if self.is_box:
            # To avoid unicode error in email_offer.send_open_order
            qty_display = EMPTY_STRING # BOX_UNICODE
        else:
            if self.use_order_unit_converted:
                # The only conversion done in permanence concerns PRODUCT_ORDER_UNIT_PC_KG
                # so we are sure that self.order_unit == PRODUCT_ORDER_UNIT_PC_KG
                qty_display = self.get_display(
                    qty=1,
                    order_unit=PRODUCT_ORDER_UNIT_KG,
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
        # index_together = [
        #     ["id", "order_unit"]
        # ]


class OfferItemReadOnly(OfferItem):
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
