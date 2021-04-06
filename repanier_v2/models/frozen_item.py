from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField

from repanier_v2.const import (
    DECIMAL_ZERO,
    LIMIT_ORDER_QTY_ITEM, EMPTY_STRING, LUT_PRODUCT_ORDER_UNIT, PRODUCT_ORDER_UNIT_PC, LUT_ALL_VAT, DICT_VAT_DEFAULT,
    LUT_PRODUCT_PLACEMENT, PRODUCT_PLACEMENT_BASKET,
)
from repanier_v2.fields.RepanierMoneyField import ModelMoneyField
from repanier_v2.picture.const import SIZE_L
from repanier_v2.picture.fields import RepanierPictureField


class FrozenItem(models.Model):
    name = models.CharField(
        _("Long name"), max_length=100, default=EMPTY_STRING, blank=True
    )
    cache_part_a = HTMLField(default=EMPTY_STRING, blank=True)
    cache_part_b = HTMLField(default=EMPTY_STRING, blank=True)
    order = models.ForeignKey(
        "Order",
        verbose_name=_("Order"),
        on_delete=models.PROTECT,
        db_index=True,
    )
    live_item = models.ForeignKey(
        "LiveItem", verbose_name=_("Live item"), on_delete=models.PROTECT, blank=True
    )
    order_sort_order = (models.IntegerField(default=0, db_index=True),)
    qty_sold = models.DecimalField(
        max_digits=9,
        decimal_places=4,
        default=DECIMAL_ZERO,
    )
    can_be_sold = models.BooleanField(_("Can be sold"), default=True)
    can_be_displayed = models.BooleanField(_("Can be displayed"), default=True)
    is_a_box_content = models.BooleanField(default=False)
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        "Department",
        related_name="+",
        verbose_name=_("Department"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )
    caption = (
        models.CharField(
            _("Caption"), max_length=100, default=EMPTY_STRING, blank=True
        ),
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="product",
        size=SIZE_L,
    )
    reference = models.CharField(
        _("Reference"), max_length=36, blank=True, default=EMPTY_STRING
    )

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("Order unit"),
    )
    average_weight = models.DecimalField(
        _("Average weight / capacity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    producer_price = ModelMoneyField(
        _("Producer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    purchase_price = ModelMoneyField(
        _("Purchase tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    customer_price = ModelMoneyField(
        _("Customer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    tax_level = models.CharField(
        max_length=3,
        choices=LUT_ALL_VAT,
        default=DICT_VAT_DEFAULT,
        verbose_name=_("Tax rate"),
    )
    wrapped = models.BooleanField(
        _("Individually wrapped by the producer"), default=False
    )
    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("Product placement"),
    )
    is_box = models.BooleanField(default=False)
    is_fixed_price = models.BooleanField(default=False)

    def get_customer_alert_order_quantity(self, q_previous_purchase=DECIMAL_ZERO):
        if not self.can_be_sold or not self.can_be_displayed:
            q_alert = 0
        else:
            q_alert = (
                    self.product.customer_minimum_order_quantity
                    + self.product.customer_increment_order_quantity
                    * (LIMIT_ORDER_QTY_ITEM - 1)
            )
            if self.product.max_sale_qty > 0:
                q_available = max(
                    DECIMAL_ZERO,
                    self.product.max_sale_qty - self.qty_sold + q_previous_purchase,
                )
                q_alert = min(q_alert, q_available)
        return q_alert

    class Meta:
        verbose_name = _("Product of an order")
        verbose_name_plural = _("Products of an order")
        unique_together = ("order", "live_item")


class FrozenItemWoReceiver(FrozenItem):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")


class FrozenItemSend(FrozenItem):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")


class FrozenItemClosed(FrozenItem):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")
