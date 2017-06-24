# -*- coding: utf-8 -*-
from django.core.cache import cache
from django.core.management.base import BaseCommand
from menus.menu_pool import menu_pool

from repanier.const import *
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence


class Command(BaseCommand):
    args = '<none>'
    help = 'Back to send'

    def handle(self, *args, **options):
        permanence = Permanence.objects.filter(id=6).order_by('?').first()
        if PERMANENCE_PLANNED == permanence.status and permanence.highest_status == PERMANENCE_SEND:
            OfferItem.objects.filter(permanence_id=permanence.id).update(is_active=True)
            permanence.status = PERMANENCE_SEND
            permanence.save(update_fields=['status'])
            menu_pool.clear()
            cache.clear()

