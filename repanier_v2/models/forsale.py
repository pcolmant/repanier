from django.db import models
from django.utils.translation import ugettext_lazy as _

from repanier_v2.models.item import Item
from repanier_v2.const import (
    DECIMAL_ZERO,
    LIMIT_ORDER_QTY_ITEM,
)


class ForSale(Item):
    sale = models.ForeignKey(
        "Sale",
        verbose_name=_("Sale"),
        on_delete=models.PROTECT,
        db_index=True,
    )
    product = models.ForeignKey(
        "Product", verbose_name=_("Product"), on_delete=models.PROTECT
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
        verbose_name = _("Product for sale")
        verbose_name_plural = _("Products for sale")
        unique_together = ("sale", "product")


class ForSaleWoReceiver(ForSale):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")


class ForSaleSend(ForSale):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")


class ForSaleClosed(ForSale):
    def __str__(self):
        return self.get_long_name_with_producer()

    class Meta:
        proxy = True
        verbose_name = _("Offer item")
        verbose_name_plural = _("Offer items")
