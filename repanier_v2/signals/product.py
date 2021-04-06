import uuid

from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.text import capfirst

from repanier_v2.const import (
    PRODUCT_ORDER_UNIT_PC,
    PRODUCT_ORDER_UNIT_PC_PRICE_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_LT,
    PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    DECIMAL_ZERO,
    PRODUCT_ORDER_UNIT_PC_KG,
    PRODUCT_ORDER_UNIT_DEPOSIT,
    PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
    VAT_100,
    PRODUCT_ORDER_UNIT_KG,
    PRODUCT_ORDER_UNIT_LT,
    DECIMAL_ONE,
)
from repanier_v2.models import Product, Product_Translation


@receiver(pre_save, sender=Product)
def product_pre_save(sender, **kwargs):
    product = kwargs["instance"]
    producer = product.producer

    if product.order_unit not in [
        PRODUCT_ORDER_UNIT_PC,
        PRODUCT_ORDER_UNIT_PC_PRICE_KG,
        PRODUCT_ORDER_UNIT_PC_PRICE_LT,
        PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    ]:
        product.unit_deposit = DECIMAL_ZERO
    if product.order_unit == PRODUCT_ORDER_UNIT_PC:
        product.order_average_weight = 1
    elif product.order_unit not in [
        PRODUCT_ORDER_UNIT_PC_KG,
        PRODUCT_ORDER_UNIT_PC_PRICE_KG,
        PRODUCT_ORDER_UNIT_PC_PRICE_LT,
        PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    ]:
        product.order_average_weight = DECIMAL_ZERO
    if product.order_unit in [
        PRODUCT_ORDER_UNIT_DEPOSIT,
        PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
    ]:
        # No VAT on those products
        product.vat_level = VAT_100
    if product.order_unit not in [
        PRODUCT_ORDER_UNIT_PC_KG,
        PRODUCT_ORDER_UNIT_KG,
        PRODUCT_ORDER_UNIT_LT,
    ]:
        product.wrapped = False
    product.recalculate_prices(producer)

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
        product.reference = uuid.uuid4()
    # Update stock of boxes containing this product
    # for box_content in product.box_content.all():
    #     if box_content.box is not None:
    #         box_content.box.save_update_stock()


@receiver(post_save, sender=Product)
def product_post_save(sender, **kwargs):
    product = kwargs["instance"]
    from repanier_v2.models.box import BoxContent

    BoxContent.objects.filter(product_id=product.id).update(
        calculated_customer_content_price=F("content_quantity")
        * product.customer_unit_price.amount,
        calculated_content_deposit=F("content_quantity") * product.unit_deposit.amount,
    )


@receiver(pre_save, sender=Product_Translation)
def product_translation_pre_save(sender, **kwargs):
    translation = kwargs["instance"]
    translation.long_name = capfirst(translation.long_name)
