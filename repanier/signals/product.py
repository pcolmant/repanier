import uuid

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import capfirst
from repanier.const import (
    DECIMAL_ZERO,
    DECIMAL_ONE,
    OrderUnit,
    Vat,
)
from repanier.models import Product


@receiver(pre_save, sender=Product)
def product_pre_save(sender, **kwargs):
    product = kwargs["instance"]
    producer = product.producer

    if product.order_unit not in [
        OrderUnit.PC,
        OrderUnit.PC_PRICE_KG,
        OrderUnit.PC_PRICE_LT,
        OrderUnit.PC_PRICE_PC,
    ]:
        product.unit_deposit = DECIMAL_ZERO
    if product.order_unit == OrderUnit.PC:
        product.order_average_weight = 1
    elif product.order_unit not in [
        OrderUnit.PC_KG,
        OrderUnit.PC_PRICE_KG,
        OrderUnit.PC_PRICE_LT,
        OrderUnit.PC_PRICE_PC,
    ]:
        product.order_average_weight = DECIMAL_ZERO
    if product.order_unit in [
        OrderUnit.DEPOSIT,
        OrderUnit.MEMBERSHIP_FEE,
    ]:
        # No VAT on those products
        product.vat_level = Vat.VAT_100
    if product.order_unit not in [
        OrderUnit.PC_KG,
        OrderUnit.KG,
        OrderUnit.LT,
    ]:
        product.wrapped = False
    product.recalculate_prices()

    if not product.is_active:
        product.is_into_offer = False

    if product.customer_increment_order_quantity <= DECIMAL_ZERO:
        product.customer_increment_order_quantity = DECIMAL_ONE
    if product.customer_minimum_order_quantity <= DECIMAL_ZERO:
        product.customer_minimum_order_quantity = (
            product.customer_increment_order_quantity
        )
    if product.order_average_weight <= DECIMAL_ZERO:
        product.order_average_weight = DECIMAL_ONE

    if not product.reference:
        product.reference = uuid.uuid1()

    product.long_name_v2 = capfirst(product.long_name_v2)
