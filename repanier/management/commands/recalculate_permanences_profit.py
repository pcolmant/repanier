# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db.models import Sum

from repanier.models import BankAccount
from repanier.models import LUT_DeliveryPoint, DeliveryBoard
from repanier.models import CustomerInvoice, ProducerInvoice
from repanier.const import PERMANENCE_CLOSED, \
    PERMANENCE_INVOICED, PERMANENCE_ARCHIVED, PERMANENCE_SEND, DECIMAL_ZERO
from repanier.models import Permanence
from repanier.tools import reorder_offer_items, recalculate_order_amount

from repanier.task import task_invoice


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate permanence profit'

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(status__gte=PERMANENCE_CLOSED).order_by('?'):
            print ("%s %s" % (permanence.permanence_date, permanence.get_status_display()))
            permanence.recalculate_profit()
            permanence.save()

