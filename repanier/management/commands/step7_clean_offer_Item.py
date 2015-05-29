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
    help = 'Recalculate Producer Invoice'

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(status=PERMANENCE_SEND).order_by():
            print('--------------------------')
            print permanence
            recalculate_order_amount(
                permanence_id=permanence.id,
                permanence_status=permanence.status,
                migrate=True

            )

