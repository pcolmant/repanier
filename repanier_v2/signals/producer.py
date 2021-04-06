import uuid

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from repanier_v2.const import DECIMAL_ZERO, DECIMAL_ONE
from repanier_v2.models import Producer, Product
from repanier_v2.tools import update_offer_item


@receiver(pre_save, sender=Producer)
def producer_pre_save(sender, **kwargs):
    producer = kwargs["instance"]
    if producer.is_default:
        # The buying group may not be de activated
        producer.is_active = True
    if producer.email:
        producer.email = producer.email.lower()
    if producer.email2:
        producer.email2 = producer.email2.lower()
    if producer.email3:
        producer.email3 = producer.email3.lower()
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE


@receiver(post_save, sender=Producer)
def producer_post_save(sender, **kwargs):
    producer = kwargs["instance"]
    for a_product in Product.objects.filter(producer_id=producer.id).order_by("?"):
        a_product.save()
    update_offer_item(producer_id=producer.id)
