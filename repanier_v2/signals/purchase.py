from django.db.models import F
from django.db.models.signals import post_init, pre_save
from django.dispatch import receiver

from repanier_v2.const import (
    DECIMAL_ZERO,
    TWO_DECIMALS,
    FOUR_DECIMALS,
    DECIMAL_ONE,
)
from repanier_v2.models import (
    Purchase,
    OfferItemWoReceiver,
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)


@receiver(post_init, sender=Purchase)
def purchase_post_init(sender, **kwargs):
    purchase = kwargs["instance"]
    # logger.info("purchase post init : {}".format(purchase.id))
    if purchase.id is not None:
        purchase.previous_qty = purchase.qty
        purchase.previous_purchase_price = purchase.purchase_price.amount
        purchase.previous_selling_price = purchase.selling_price.amount
        purchase.previous_producer_vat = purchase.producer_vat.amount
        purchase.previous_customer_vat = purchase.customer_vat.amount
        purchase.previous_deposit = purchase.deposit.amount
    else:
        purchase.previous_qty = DECIMAL_ZERO
        purchase.previous_quantity = DECIMAL_ZERO
        purchase.previous_purchase_price = DECIMAL_ZERO
        purchase.previous_selling_price = DECIMAL_ZERO
        purchase.previous_producer_vat = DECIMAL_ZERO
        purchase.previous_customer_vat = DECIMAL_ZERO
        purchase.previous_deposit = DECIMAL_ZERO


@receiver(pre_save, sender=Purchase)
def purchase_pre_save(sender, **kwargs):
    """
    Update the invoices (customer + producer) linked to a purchase when saving it.
    """

    purchase = kwargs["instance"]
    # logger.info("purchase pre save : {}".format(purchase.id))
    if purchase.id is None:
        purchase.set_customer_price_list_multiplier()

    quantity = purchase.qty
    delta_quantity = quantity - purchase.previous_qty

    if purchase.is_box_content:
        if delta_quantity != DECIMAL_ZERO:
            OfferItemWoReceiver.objects.filter(id=purchase.offer_item_id).update(
                qty=F("qty") + delta_quantity
            )
    else:
        unit_deposit = purchase.get_unit_deposit()
        purchase.purchase_price.amount = (
            (purchase.get_producer_unit_price() + unit_deposit) * quantity
        ).quantize(TWO_DECIMALS)
        purchase.selling_price.amount = (
            (purchase.get_customer_unit_price() + unit_deposit) * quantity
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
            delta_selling_vat = (
                purchase.customer_vat.amount - purchase.previous_customer_vat
            )
            delta_deposit = purchase.deposit.amount - purchase.previous_deposit

            OfferItemWoReceiver.objects.filter(id=purchase.offer_item_id).update(
                qty=F("qty") + delta_quantity,
                total_purchase_with_tax=F("total_purchase_with_tax")
                + delta_purchase_price,
                total_selling_with_tax=F("total_selling_with_tax")
                + delta_selling_price,
            )
            purchase.offer_item = (
                OfferItemWoReceiver.objects.filter(id=purchase.offer_item_id)
                .order_by("?")
                .first()
            )
            CustomerInvoice.objects.filter(id=purchase.customer_invoice_id).update(
                total_price_with_tax=F("total_price_with_tax") + delta_selling_price,
                total_vat=F("total_vat") + delta_selling_vat,
                total_deposit=F("total_deposit") + delta_deposit,
            )

            CustomerProducerInvoice.objects.filter(
                id=purchase.customer_producer_invoice_id
            ).update(
                total_purchase_with_tax=F("total_purchase_with_tax")
                + delta_purchase_price,
                total_selling_with_tax=F("total_selling_with_tax")
                + delta_selling_price,
            )

            if (
                purchase.price_list_multiplier <= DECIMAL_ONE
                and not purchase.is_resale_price_fixed
            ):
                delta_purchase_price = delta_selling_price
                delta_purchase_vat = delta_selling_vat

            ProducerInvoice.objects.filter(id=purchase.producer_invoice_id).update(
                total_price_with_tax=F("total_price_with_tax") + delta_purchase_price,
                total_vat=F("total_vat") + delta_purchase_vat,
                total_deposit=F("total_deposit") + delta_deposit,
            )
