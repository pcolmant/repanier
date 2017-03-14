# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from repanier.task import task_order


class Command(BaseCommand):
    args = '<none>'
    help = 'Pre open orders planned up to 3 days in the future'

    def handle(self, *args, **options):
        something_to_pre_open = task_order.automatically_pre_open()
        if something_to_pre_open:
            self.stdout.write('At least one order being pre opened')
        else:
            self.stdout.write('Nothing to pre open')
