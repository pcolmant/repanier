from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.models import Product
from repanier.tools import cap


def flip_flop_is_into_offer(queryset):
    for product in queryset.filter(is_active=True):
        product.is_into_offer = not product.is_into_offer
        product.save(update_fields=["is_into_offer", "stock"])


def admin_duplicate(product, producer):
    user_message = _("The product is duplicated.")
    user_message_level = messages.INFO
    long_name_postfix = "{}".format(_(" (COPY)"))
    max_length = Product._meta.get_field("long_name_v2").max_length - len(
        long_name_postfix
    )
    new_long_name = "{}{}".format(
        cap(product.long_name_v2, max_length), long_name_postfix
    )
    old_product_production_mode = product.production_mode.all()
    product.id = None
    product.reference = None
    product.producer = producer
    product.long_name_v2 = new_long_name
    product.offer_description_v2 = EMPTY_STRING
    product.save()
    for production_mode in old_product_production_mode:
        product.production_mode.add(production_mode.id)
    return user_message, user_message_level
