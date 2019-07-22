import uuid

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from repanier.const import DECIMAL_ZERO, DECIMAL_ONE
from repanier.models import Producer, Product
from repanier.tools import update_offer_item


@receiver(pre_save, sender=Producer)
def producer_pre_save(sender, **kwargs):
    producer = kwargs["instance"]
    if producer.represent_this_buyinggroup:
        # The buying group may not be de activated
        producer.is_active = True
    if producer.email:
        producer.email = producer.email.lower()
    if producer.email2:
        producer.email2 = producer.email2.lower()
    if producer.email3:
        producer.email3 = producer.email3.lower()
    if producer.producer_pre_opening:
        # Used to make difference between the stock of the group and the stock of the producer
        producer.manage_replenishment = False
        producer.is_resale_price_fixed = False
    elif producer.manage_replenishment:
        # Needed to compute ProducerInvoice.total_price_with_tax
        producer.invoice_by_basket = False
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE
    if not producer.uuid:
        producer.uuid = uuid.uuid1()


@receiver(post_save, sender=Producer)
def producer_post_save(sender, **kwargs):
    producer = kwargs["instance"]
    for a_product in Product.objects.filter(producer_id=producer.id).order_by("?"):
        a_product.save()
    update_offer_item(producer_id=producer.id)
