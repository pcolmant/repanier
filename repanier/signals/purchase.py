from django.db.models import F
from django.db.models.signals import post_init, pre_save
from django.dispatch import receiver

from repanier.const import (
    DECIMAL_ZERO,
    EMPTY_STRING,
    PERMANENCE_WAIT_FOR_SEND,
    PRODUCT_ORDER_UNIT_PC_KG,
    TWO_DECIMALS,
    FOUR_DECIMALS,
)
from repanier.models import (
    Purchase,
    OfferItemReadOnly,
    CustomerProducerInvoice,
    ProducerInvoice,
)


@receiver(post_init, sender=Purchase)
def purchase_post_init(sender, **kwargs):
    purchase = kwargs["instance"]
    # logger.info("purchase post init : {}".format(purchase.id))
    if purchase.id is not None:
        purchase.previous_quantity_ordered = purchase.quantity_ordered
        purchase.previous_quantity_invoiced = purchase.quantity_invoiced
        purchase.previous_purchase_price = purchase.purchase_price.amount
        purchase.previous_selling_price = purchase.selling_price.amount
        purchase.previous_producer_vat = purchase.producer_vat.amount
        purchase.previous_customer_vat = purchase.customer_vat.amount
        purchase.previous_deposit = purchase.deposit.amount
        purchase.previous_comment = purchase.comment
    else:
        purchase.previous_quantity_ordered = DECIMAL_ZERO
        purchase.previous_quantity_invoiced = DECIMAL_ZERO
        purchase.previous_quantity = DECIMAL_ZERO
        purchase.previous_purchase_price = DECIMAL_ZERO
        purchase.previous_selling_price = DECIMAL_ZERO
        purchase.previous_producer_vat = DECIMAL_ZERO
        purchase.previous_customer_vat = DECIMAL_ZERO
        purchase.previous_deposit = DECIMAL_ZERO
        purchase.previous_comment = EMPTY_STRING


@receiver(pre_save, sender=Purchase)
def purchase_pre_save(sender, **kwargs):
    """
    Update the invoices (customer + producer) linked to a purchase when saving it.
    """

    purchase = kwargs["instance"]
    offer_item = purchase.offer_item
    # logger.info("purchase pre save : {}".format(purchase.id))
    if purchase.status < PERMANENCE_WAIT_FOR_SEND:
        quantity = purchase.quantity_ordered
        delta_quantity = quantity - purchase.previous_quantity_ordered
        if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            # This quantity is used to calculate the price
            # The unit price is for 1 kg.
            # 1 = 1 piece of order_average_weight
            # 2 = 2 pieces of order_average_weight
            quantity *= offer_item.order_average_weight

    else:
        quantity = purchase.quantity_invoiced
        delta_quantity = quantity - purchase.previous_quantity_invoiced

    price_list_multiplier = (
        purchase.price_list_multiplier
    ) = offer_item.get_price_list_multiplier(purchase.customer_invoice)
    producer_unit_price = offer_item.get_producer_unit_price(price_list_multiplier)
    customer_unit_price = offer_item.get_customer_unit_price(price_list_multiplier)
    unit_deposit = offer_item.get_unit_deposit()

    purchase.purchase_price.amount = (
        (producer_unit_price + unit_deposit) * quantity
    ).quantize(TWO_DECIMALS)
    purchase.selling_price.amount = (
        (customer_unit_price + unit_deposit) * quantity
    ).quantize(TWO_DECIMALS)

    delta_purchase_price = (
        purchase.purchase_price.amount - purchase.previous_purchase_price
    )
    delta_selling_price = (
        purchase.selling_price.amount - purchase.previous_selling_price
    )

    if (
        delta_quantity != DECIMAL_ZERO
        or delta_selling_price != DECIMAL_ZERO
        or delta_purchase_price != DECIMAL_ZERO
    ):

        purchase.vat_level = purchase.offer_item.vat_level
        purchase.producer_vat.amount = (
            purchase.get_producer_unit_vat() * quantity
        ).quantize(FOUR_DECIMALS)
        purchase.customer_vat.amount = (
            purchase.get_customer_unit_vat() * quantity
        ).quantize(FOUR_DECIMALS)

        purchase.deposit.amount = unit_deposit * quantity

        delta_purchase_vat = (
            purchase.producer_vat.amount - purchase.previous_producer_vat
        )
        delta_deposit = purchase.deposit.amount - purchase.previous_deposit

        OfferItemReadOnly.objects.filter(id=purchase.offer_item_id).update(
            quantity_invoiced=F("quantity_invoiced") + delta_quantity,
            total_purchase_with_tax=F("total_purchase_with_tax") + delta_purchase_price,
            total_selling_with_tax=F("total_selling_with_tax") + delta_selling_price,
        )
        purchase.offer_item = OfferItemReadOnly.objects.filter(
            id=purchase.offer_item_id
        ).first()

        CustomerProducerInvoice.objects.filter(
            id=purchase.customer_producer_invoice_id
        ).update(
            total_purchase_with_tax=F("total_purchase_with_tax") + delta_purchase_price,
            total_selling_with_tax=F("total_selling_with_tax") + delta_selling_price,
        )

        ProducerInvoice.objects.filter(id=purchase.producer_invoice_id).update(
            total_price_with_tax=F("total_price_with_tax") + delta_purchase_price,
            total_vat=F("total_vat") + delta_purchase_vat,
            total_deposit=F("total_deposit") + delta_deposit,
        )
    # Do not do it twice
    purchase.previous_quantity_ordered = purchase.quantity_ordered
    purchase.previous_quantity_invoiced = purchase.quantity_invoiced
    purchase.previous_purchase_price = purchase.purchase_price.amount
    purchase.previous_selling_price = purchase.selling_price.amount
