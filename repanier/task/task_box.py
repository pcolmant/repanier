# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.models.box import BoxContent
from repanier.models.product import Product_Translation
from repanier.tools import cap


def flip_flop_is_into_offer(queryset):
    for product in queryset.filter(is_active=True).order_by('?'):
        if product.limit_order_quantity_to_stock:
            if product.stock > DECIMAL_ZERO:
                product.is_into_offer = False
                product.stock = DECIMAL_ZERO
            else:
                product.is_into_offer = True
                product.stock = 999999
        else:
            product.is_into_offer = not product.is_into_offer
        product.save(update_fields=['is_into_offer', 'stock'])


def admin_duplicate(queryset):
    user_message = _("The box is duplicated.")
    user_message_level = messages.INFO
    box_count = 0
    long_name_postfix = "{}".format(_(" (COPY)"))
    max_length = Product_Translation._meta.get_field('long_name').max_length - len(long_name_postfix)
    for box in queryset:
        box_count += 1
        new_long_name = "{}{}".format(cap(box.long_name, max_length), _(" (COPY)"))
        old_product_production_mode = box.production_mode.all()
        previous_box_id = box.id
        box.id = None
        box.reference = None
        box.save()
        for production_mode in old_product_production_mode:
            box.production_mode.add(production_mode.id)
        Product_Translation.objects.create(
            master_id=box.id,
            long_name=new_long_name,
            offer_description=EMPTY_STRING,
            language_code=translation.get_language()
        )
        for box_content in BoxContent.objects.filter(
            box_id=previous_box_id
        ):
            box_content.id = None
            box_content.box_id=box.id
            box_content.save()
    if box_count > 1:
        user_message = _("The boxes are duplicated.")
    return user_message, user_message_level
