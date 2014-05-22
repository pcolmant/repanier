# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from repanier import tasks

class Command(BaseCommand):
    args = '<none>'
    help = 'Closes now orders on due date'

    def handle(self, *args, **options):
		something_to_close = tasks.close_orders_now()
		if something_to_close:
			self.stdout.write('At least on order being closed')
		else:
			self.stdout.write('Nothing to close')
