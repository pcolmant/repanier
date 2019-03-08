# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from repanier.task import task_order


class Command(BaseCommand):
    args = '<none>'
    help = 'Open pre opened orders'

    def handle(self, *args, **options):
        something_to_open = task_order.automatically_open()
        if something_to_open:
            self.stdout.write('At least one order being opened')
        else:
            self.stdout.write('Nothing to open')
