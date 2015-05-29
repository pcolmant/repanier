# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from repanier.const import *
from repanier.models import Permanence, OfferItem
from repanier.tools import recalculate_order_amount


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate order amount'

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(
                # status=PERMANENCE_SEND
                status__in=[PERMANENCE_SEND, PERMANENCE_DONE]
        ).order_by('permanence_date'):
            print "%s" % permanence
            recalculate_order_amount(permanence_id=permanence.id,
                 permanence_status=PERMANENCE_SEND,
                 migrate=True)

