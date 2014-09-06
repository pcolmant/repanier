# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from repanier.const import *
from repanier.models import Product, Product_Translation
from repanier.tools import cap


def flip_flop_is_into_offer(queryset):
    for product in queryset.order_by():
        if product.is_active:
            product.is_into_offer = not product.is_into_offer
            product.save(update_fields=['is_into_offer'])


def admin_duplicate(queryset):
    user_message = _("The product is duplicated.")
    user_message_level = messages.INFO
    product_count = 0
    long_name_postfix = unicode(_(" (COPY)"))
    max_length = Product_Translation._meta.get_field('long_name').max_length - len(long_name_postfix)
    for product in queryset:
        product_count += 1
        new_long_name = cap(product.long_name, max_length).decode("utf8") + long_name_postfix
        old_product_production_mode = product.production_mode.all()
        product.id = None
        product.reference = None
        product.save()
        for production_mode in old_product_production_mode:
            product.production_mode.add(production_mode.id)
        Product_Translation.objects.create(
            master_id=product.id,
            long_name=new_long_name,
            offer_description='',
            language_code=translation.get_language()
        )

    if product_count > 1:
        user_message = _("The products are duplicated.")
    return user_message, user_message_level


