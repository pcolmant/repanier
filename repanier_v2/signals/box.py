from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier_v2.const import PRODUCT_ORDER_UNIT_PC
from repanier_v2.models import BoxContent, Product, Box
from repanier_v2.signals.product import product_pre_save


@receiver(pre_save, sender=Box)
def box_pre_save(sender, **kwargs):
    box = kwargs["instance"]
    box.is_box = True
    box.order_unit = PRODUCT_ORDER_UNIT_PC
    box.producer_unit_price = box.customer_unit_price
    box.producer_vat = box.customer_vat
    # ! Important to initialise all fields of the box. Remember : a box is a product.
    product_pre_save(sender, **kwargs)


@receiver(pre_save, sender=BoxContent)
def box_content_pre_save(sender, **kwargs):
    box_content = kwargs["instance"]
    product_id = box_content.product_id
    if product_id is not None:
        product = (
            Product.objects.filter(id=product_id)
            .order_by("?")
            .only("customer_unit_price", "unit_deposit")
            .first()
        )
        if product is not None:
            box_content.calculated_customer_content_price.amount = (
                box_content.content_quantity * product.customer_unit_price.amount
            )
            box_content.calculated_content_deposit.amount = (
                int(box_content.content_quantity) * product.unit_deposit.amount
            )
