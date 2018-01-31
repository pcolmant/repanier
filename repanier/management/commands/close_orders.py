# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from repanier.task import task_order


class Command(BaseCommand):
    args = '<none>'
    help = 'Closes now orders on due date'

    def handle(self, *args, **options):
        something_to_close = task_order.automatically_closed()
        if something_to_close:
            self.stdout.write('At least one order closed')
        else:
            self.stdout.write('Nothing to close')
