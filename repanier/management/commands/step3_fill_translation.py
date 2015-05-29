# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from repanier.const import *
from repanier.models import LUT_DepartmentForCustomer, LUT_PermanenceRole, LUT_ProductionMode, Product, Permanence


class Command(BaseCommand):
    args = '<none>'
    help = 'Fill translation'

    def handle(self, *args, **options):
        LUT_DepartmentForCustomer.objects.rebuild()
        LUT_PermanenceRole.objects.rebuild()
        LUT_ProductionMode.objects.rebuild()
        translation.activate('fr')
        for obj in LUT_DepartmentForCustomer.objects.all():
            if obj.short_name_fr is not None:
                obj.short_name=obj.short_name_fr
            if obj.description_fr is not None:
                obj.description=obj.description_fr
            obj.save()
        for obj in LUT_PermanenceRole.objects.all():
            if obj.short_name_fr is not None:
                obj.short_name=obj.short_name_fr
            if obj.description_fr is not None:
                obj.description=obj.description_fr
            obj.save()
        for obj in LUT_ProductionMode.objects.all():
            if obj.short_name_fr is not None:
                obj.short_name=obj.short_name_fr
            if obj.description_fr is not None:
                obj.description=obj.description_fr
            obj.save()
        for product in Product.objects.all():
            product.production_mode.add(product.production_mode_1N_id)
            if product.long_name_fr is not None:
                product.long_name = product.long_name_fr
            if product.offer_description_fr is not None:
                product.offer_description = product.offer_description_fr
            product.save()
        for obj in Permanence.objects.all():
            if obj.short_name_fr is not None:
                obj.short_name=obj.short_name_fr
            if obj.offer_description_fr is not None:
                obj.offer_description=obj.offer_description_fr
            if obj.invoice_description_fr is not None:
                obj.invoice_description=obj.invoice_description_fr
            obj.save()

