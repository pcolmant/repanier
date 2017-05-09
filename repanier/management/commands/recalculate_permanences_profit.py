# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from repanier.const import PERMANENCE_CLOSED
from repanier.models import Permanence
from repanier.tools import recalculate_order_amount


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate permanence profit'

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(
            # id__in=[59, 58],
                status__gte=PERMANENCE_CLOSED
        ).order_by('?'):
            print ("%s %s" % (permanence.permanence_date, permanence.get_status_display()))
            # recalculate_order_amount(
            #     permanence_id=permanence.id,
            #     re_init=True
            # )
            permanence.recalculate_profit()
            permanence.save()

