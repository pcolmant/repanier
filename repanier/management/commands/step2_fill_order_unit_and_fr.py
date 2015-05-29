# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from repanier.const import *
from repanier.models import LUT_DepartmentForCustomer, LUT_PermanenceRole, LUT_ProductionMode, Product, Permanence


class Command(BaseCommand):
    args = '<none>'
    help = 'Fill order unit field and migrate non fr to fr'

    def handle(self, *args, **options):
        LUT_DepartmentForCustomer.objects.all().update(
            short_name_fr=F('short_name'),
            description_fr=F('description')
        )
        LUT_PermanenceRole.objects.all().update(
            short_name_fr=F('short_name'),
            description_fr=F('description')
        )
        LUT_ProductionMode.objects.all().update(
            short_name_fr=F('short_name'),
            description_fr=F('description')
        )
        for product in Product.objects.all():
            product.long_name_fr = product.long_name
            product.offer_description_fr = product.offer_description
            product.production_mode_1N = product.production_mode
            if product.order_unit in [
                PRODUCT_ORDER_UNIT_NAMED_LT,
                PRODUCT_ORDER_UNIT_NAMED_PC,
                PRODUCT_ORDER_UNIT_NAMED_KG
            ]:
                product.wrapped = True
            else:
                product.wrapped = False
            if product.order_unit==PRODUCT_ORDER_UNIT_LOOSE_PC:
                product.order_unit=PRODUCT_ORDER_UNIT_PC
            elif product.order_unit==PRODUCT_ORDER_UNIT_LOOSE_KG:
                product.order_unit=PRODUCT_ORDER_UNIT_KG
            elif product.order_unit==PRODUCT_ORDER_UNIT_LOOSE_PC_KG:
                product.order_unit=PRODUCT_ORDER_UNIT_PC_KG
            elif product.order_unit==PRODUCT_ORDER_UNIT_NAMED_LT:
                product.order_unit=PRODUCT_ORDER_UNIT_LT
            elif product.order_unit==PRODUCT_ORDER_UNIT_LOOSE_BT_LT:
                product.order_unit=PRODUCT_ORDER_UNIT_PC_PRICE_LT
            elif product.order_unit==PRODUCT_ORDER_UNIT_NAMED_PC:
                product.order_unit=PRODUCT_ORDER_UNIT_PC
            elif product.order_unit==PRODUCT_ORDER_UNIT_NAMED_KG:
                product.order_unit=PRODUCT_ORDER_UNIT_KG
            elif product.order_unit==PRODUCT_ORDER_UNIT_NAMED_PC_KG:
                product.order_unit=PRODUCT_ORDER_UNIT_PC_KG
            product.save()
        Permanence.objects.all().update(
            short_name_fr=F('short_name'),
            offer_description_fr=F('offer_description'),
            invoice_description_fr=F('invoice_description'))
