# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.models import Product
from repanier.tools import cap


def flip_flop_is_into_offer(queryset):
    for product in queryset.order_by():
        product.is_into_offer = not product.is_into_offer
        product.save(update_fields=['is_into_offer'])


def admin_duplicate(queryset):
    user_message = _("The product is duplicated.")
    user_message_level = messages.INFO
    product_count = 0
    duplicate_count = 0
    for product in queryset:
        product_count += 1
        long_name_postfix = unicode(_(" (COPY)"))
        max_length = Product._meta.get_field('long_name').max_length - len(long_name_postfix)
        product.long_name = cap(product.long_name, max_length).decode("utf8") + long_name_postfix
        product_set = Product.objects.filter(
            producer_id=product.producer_id,
            long_name=product.long_name).order_by()[:1]
        if product_set:
            # avoid to break the unique index : producer_id, long_name
            pass
        else:
            product.id = None
            product.save()
            duplicate_count += 1
    if product_count == duplicate_count:
        if product_count > 1:
            user_message = _("The products are duplicated.")
    else:
        if product_count == 1:
            user_message = _(
                "The product has not been duplicated because a product with the same long name already exists.")
            user_message_level = messages.ERROR
        else:
            user_message = _(
                "At least one product has not been duplicated because a product with the same long name already exists.")
            user_message_level = messages.WARNING
    return user_message, user_message_level


