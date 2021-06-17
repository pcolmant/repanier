from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, DecimalField
from django.utils.translation import ugettext_lazy as _

from repanier_v2.const import *
from repanier_v2.fields.RepanierMoneyField import ModelMoneyField
from repanier_v2.models.product import Product


class Box(Product):
    def get_calculated_stock(self):
        # stock : max_digits=9, decimal_places=3 => 1000000 > max(stock)
        qty_on_sale = DECIMAL_MAX_STOCK
        for box_content in (
            BoxContent.objects.filter(
                box_id=self.id,
                content_quantity__gt=DECIMAL_ZERO,
                product__is_box=False,  # Disallow recursivity
            )
            .prefetch_related("product")
            .only(
                "content_quantity",
                "product__qty_on_sale",
            )
            .order_by("?")
        ):
            qty_on_sale = min(
                qty_on_sale,
                box_content.product.qty_on_sale // box_content.content_quantity,
            )
        return qty_on_sale

    def get_calculated_price(self):
        result_set = BoxContent.objects.filter(box_id=self.id).aggregate(
            price=Sum(
                "calculated_customer_content_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            deposit=Sum(
                "calculated_content_deposit",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        box_price = result_set["price"] or DECIMAL_ZERO
        box_deposit = result_set["deposit"] or DECIMAL_ZERO

        return RepanierMoney(box_price), RepanierMoney(box_deposit)

    def get_box_admin_display(self):
        return self.get_long_name()

    get_box_admin_display.short_description = _("Box")

    def __str__(self):
        # return super(Box, self).display()
        return "{}".format(self.safe_translation_getter("long_name", any_language=True))

    class Meta:
        proxy = True
        verbose_name = _("Box")
        verbose_name_plural = _("Boxes")
        # ordering = ["sort_order",]


class BoxContent(models.Model):
    box = models.ForeignKey(
        "Box",
        verbose_name=_("Box"),
        null=True,
        blank=True,
        db_index=True,
        on_delete=models.PROTECT,
    )
    product = models.ForeignKey(
        "Product",
        verbose_name=_("Product"),
        related_name="box_content",
        null=True,
        blank=True,
        db_index=True,
        on_delete=models.PROTECT,
    )
    content_quantity = models.DecimalField(
        _("Fixed quantity per unit"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    calculated_customer_content_price = ModelMoneyField(
        _("Calculated consumer tariff"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    calculated_content_deposit = ModelMoneyField(
        _("Content deposit"),
        help_text=_("Surcharge"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )

    def get_calculated_customer_content_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.calculated_customer_content_price + self.calculated_content_deposit

    get_calculated_customer_content_price.short_description = _(
        "Calculated consumer tariff"
    )

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        verbose_name = _("Box content")
        verbose_name_plural = _("Boxes content")
        db_table = "repanier_box_content"
        unique_together = (("box", "product"),)
        index_together = [["product", "box"]]