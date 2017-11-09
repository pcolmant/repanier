# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.models import ContractContent
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


def deselect_is_into_offer(queryset, contract=None):
    for product in queryset.filter(is_active=True, is_into_offer=True).order_by('?'):
        if contract is not None:
            contract_content = ContractContent.objects.filter(
                product=product,
                contract=contract
            ).order_by('?').first()
            if contract_content is not None and contract_content.permanences_dates is not None:
                contract_content.permanences_dates = None
                contract_content.not_permanences_dates = contract.permanences_dates
                contract_content.save(update_fields=['permanences_dates', 'not_permanences_dates'])
        else:
            product.is_into_offer = False
            product.save(update_fields=['is_into_offer'])


def admin_duplicate(queryset, producer):
    user_message = _("The product is duplicated.")
    user_message_level = messages.INFO
    product_count = 0
    long_name_postfix = "{}".format(_(" (COPY)"))
    max_length = Product_Translation._meta.get_field('long_name').max_length - len(long_name_postfix)
    for product in queryset:
        product_count += 1
        new_long_name = "{}{}".format(cap(product.long_name, max_length), _(" (COPY)"))
        old_product_production_mode = product.production_mode.all()
        product.id = None
        product.reference = None
        product.producer = producer
        product.save()
        for production_mode in old_product_production_mode:
            product.production_mode.add(production_mode.id)
        Product_Translation.objects.create(
            master_id=product.id,
            long_name=new_long_name,
            offer_description=EMPTY_STRING,
            language_code=translation.get_language()
        )

    if product_count > 1:
        user_message = _("The products are duplicated.")
    return user_message, user_message_level
