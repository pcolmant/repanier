# -*- coding: utf-8 -*-
import uuid
from django.conf import settings
from django.contrib.contenttypes.management import update_all_contenttypes
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.management import create_permissions
from django.db.models import get_models, get_app
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import translation
from repanier.const import *
from repanier.models import LUT_DepartmentForCustomer, LUT_PermanenceRole, LUT_ProductionMode, Product, Permanence, \
    OfferItem, Purchase, Producer, BankAccount, ProducerInvoice, CustomerInvoice, PermanenceBoard
from repanier.tools import recalculate_order_amount


class Command(BaseCommand):
    args = '<none>'
    help = 'Fill translation'

    def handle(self, *args, **options):
        cur_language = translation.get_language()
        for permanence in Permanence.objects.all().order_by():
            recalculate_order_amount(
                permanence_id=permanence.id,
                permanence_status=permanence.status,
                send_to_producer=True,
                migrate=True
            )
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                translation.activate(language["code"])
                i = 0
                for offer_item in OfferItem.objects.filter(
                    permanence_id=permanence.id,
                    translations__language_code=language["code"]
                ).order_by().order_by(
                        "department_for_customer__tree_id",
                        "department_for_customer__lft",
                        "translations__long_name",
                        "order_average_weight",
                        "producer__short_profile_name"
                ):
                    offer_item.order_sort_order = i
                    offer_item.save_translations()
                    i += 1
        translation.activate(cur_language)
        update_all_contenttypes()
        create_permissions(get_app("repanier"), get_models(), options.get('verbosity', 0))

