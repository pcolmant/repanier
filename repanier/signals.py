from repanier.models import OfferItem, OfferItemSend, OfferItemClosed, ProducerInvoice
from django.db.models import F
from django.db.models.signals import pre_save, post_init
from django.dispatch import receiver

from repanier.const import DECIMAL_ZERO


@receiver(post_init, sender=OfferItem)
def offer_item_post_init(sender, **kwargs):
    offer_item = kwargs["instance"]
    if offer_item.id is None:
        offer_item.previous_add_2_stock = DECIMAL_ZERO
        offer_item.previous_producer_unit_price = DECIMAL_ZERO
        offer_item.previous_unit_deposit = DECIMAL_ZERO
    else:
        offer_item.previous_add_2_stock = offer_item.add_2_stock
        offer_item.previous_producer_unit_price = offer_item.producer_unit_price.amount
        offer_item.previous_unit_deposit = offer_item.unit_deposit.amount


@receiver(pre_save, sender=OfferItem)
def offer_item_pre_save(sender, **kwargs):
    offer_item = kwargs["instance"]
    import ipdb

    ipdb.set_trace()
    offer_item.recalculate_prices(
        offer_item.producer_price_are_wo_vat,
        offer_item.is_resale_price_fixed,
        offer_item.price_list_multiplier,
    )
    if offer_item.manage_replenishment:
        if (
            offer_item.previous_add_2_stock != offer_item.add_2_stock
            or offer_item.previous_producer_unit_price
            != offer_item.producer_unit_price.amount
            or offer_item.previous_unit_deposit != offer_item.unit_deposit.amount
        ):
            previous_producer_price = (
                offer_item.previous_producer_unit_price
                + offer_item.previous_unit_deposit
            ) * offer_item.previous_add_2_stock
            producer_price = (
                offer_item.producer_unit_price.amount + offer_item.unit_deposit.amount
            ) * offer_item.add_2_stock
            delta_add_2_stock_invoiced = (
                offer_item.add_2_stock - offer_item.previous_add_2_stock
            )
            delta_producer_price = producer_price - previous_producer_price
            ProducerInvoice.objects.filter(
                producer_id=offer_item.producer_id,
                permanence_id=offer_item.permanence_id,
            ).update(
                total_price_with_tax=F("total_price_with_tax") + delta_producer_price
            )
            offer_item.quantity_invoiced += delta_add_2_stock_invoiced
            offer_item.total_purchase_with_tax.amount += delta_producer_price
            # Do not do it twice
            offer_item.previous_add_2_stock = offer_item.add_2_stock
            offer_item.previous_producer_unit_price = (
                offer_item.producer_unit_price.amount
            )
            offer_item.previous_unit_deposit = offer_item.unit_deposit.amount


@receiver(post_init, sender=OfferItemSend)
def offer_item_send_post_init(sender, **kwargs):
    offer_item_post_init(sender, **kwargs)


@receiver(pre_save, sender=OfferItemSend)
def offer_item_send_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)


@receiver(post_init, sender=OfferItemClosed)
def offer_item_closed_post_init(sender, **kwargs):
    offer_item_post_init(sender, **kwargs)


@receiver(pre_save, sender=OfferItemClosed)
def offer_item_closed_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)