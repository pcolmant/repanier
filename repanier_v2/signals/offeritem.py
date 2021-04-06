from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier_v2.models import OfferItem, OfferItemSend, OfferItemClosed


@receiver(pre_save, sender=OfferItem)
def offer_item_pre_save(sender, **kwargs):
    offer_item = kwargs["instance"]

    offer_item.recalculate_prices(offer_item.producer)


@receiver(pre_save, sender=OfferItemSend)
def offer_item_send_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)


@receiver(pre_save, sender=OfferItemClosed)
def offer_item_closed_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)
