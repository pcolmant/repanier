# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Delete empty translations"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM repanier_deliveryboard_translation WHERE delivery_comment = \'\'")
            cursor.execute("DELETE FROM repanier_lut_departmentforcustomer_translation WHERE short_name = \'\'")
            cursor.execute("DELETE FROM repanier_lut_permanencerole_translation WHERE short_name = \'\'")
            cursor.execute("DELETE FROM repanier_lut_productionmode_translation WHERE short_name = \'\'")
            cursor.execute("DELETE FROM repanier_product_translation WHERE long_name = \'\'")
            cursor.execute("DELETE FROM repanier_staff_translation WHERE long_name = \'\'")
