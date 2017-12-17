# -*- coding: utf-8

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.product import Product, product_pre_save


class Box(Product):

    def get_calculated_stock(self):
        # stock : max_digits=9, decimal_places=3 => 1000000 > max(stock)
        stock = DECIMAL_MAX_STOCK
        for box_content in BoxContent.objects.filter(
                box_id=self.id,
                product__limit_order_quantity_to_stock=True,
                content_quantity__gt=DECIMAL_ZERO,
                product__is_box=False  # Disallow recursivity
        ).prefetch_related(
            "product"
        ).only(
            "content_quantity", "product__stock", "product__limit_order_quantity_to_stock"
        ).order_by('?'):
            stock = min(stock, box_content.product.stock // box_content.content_quantity)
        return stock

    def get_calculated_price(self):
        result_set = BoxContent.objects.filter(box_id=self.id).aggregate(
            Sum('calculated_customer_content_price'),
            Sum('calculated_content_deposit')
        )
        box_price = result_set["calculated_customer_content_price__sum"] \
            if result_set["calculated_customer_content_price__sum"] is not None else DECIMAL_ZERO
        box_deposit = result_set["calculated_content_deposit__sum"] \
            if result_set["calculated_content_deposit__sum"] is not None else DECIMAL_ZERO

        return box_price, box_deposit

    def get_box_admin_display(self):
        return self.get_long_name()

    get_box_admin_display.short_description = _("Box")
    get_box_admin_display.allow_tags = False

    def __str__(self):
        # return super(Box, self).display()
        return "{}".format(self.safe_translation_getter('long_name', any_language=True))

    class Meta:
        proxy = True
        verbose_name = _("Box")
        verbose_name_plural = _("Boxes")
        # ordering = ("sort_order",)


@receiver(pre_save, sender=Box)
def box_pre_save(sender, **kwargs):
    box = kwargs["instance"]
    box.is_box = True
    # box.producer_id = Producer.objects.filter(
    #     represent_this_buyinggroup=True
    # ).order_by('?').only('id').first().id
    box.order_unit = PRODUCT_ORDER_UNIT_PC
    box.producer_unit_price = box.customer_unit_price
    box.producer_vat = box.customer_vat
    box.limit_order_quantity_to_stock = True
    if not box.is_active:
        box.is_into_offer = False
    # ! Important to initialise all fields of the box. Remember : a box is a product.
    product_pre_save(sender, **kwargs)


class BoxContent(models.Model):
    box = models.ForeignKey(
        'Box', verbose_name=_("Box"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("Product"), related_name='box_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    content_quantity = models.DecimalField(
        _("Fixed quantity per unit"),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    calculated_customer_content_price = ModelMoneyField(
        _("Customer content price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    calculated_content_deposit = ModelMoneyField(
        _("Content deposit"),
        help_text=_('Surcharge'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_calculated_customer_content_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.calculated_customer_content_price + self.calculated_content_deposit

    get_calculated_customer_content_price.short_description = (_("Customer content price"))
    get_calculated_customer_content_price.allow_tags = False

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        verbose_name = _("Box content")
        verbose_name_plural = _("Boxes content")
        unique_together = ("box", "product",)
        index_together = [
            ["product", "box"],
        ]


@receiver(pre_save, sender=BoxContent)
def box_content_pre_save(sender, **kwargs):
    box_content = kwargs["instance"]
    product_id = box_content.product_id
    if product_id is not None:
        product = Product.objects.filter(id=product_id).order_by('?').only(
            'customer_unit_price',
            'unit_deposit'
        ).first()
        if product is not None:
            box_content.calculated_customer_content_price.amount = box_content.content_quantity * product.customer_unit_price.amount
            box_content.calculated_content_deposit.amount = int(box_content.content_quantity) * product.unit_deposit.amount

