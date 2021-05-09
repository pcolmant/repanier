from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    args = "<none>"
    help = "Update DB fields"

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE repanier_product SET "
                    "long_name_v2 = concat(upper(left(long_name_v2, 1)), right(long_name_v2, -1)) "
                    # "WHERE limit_order_quantity_to_stock = false "
                )
                cursor.execute(
                    "UPDATE repanier_customer SET "
                    "group_id = b.customer_responsible_id "
                    "FROM ( "
                    "  SELECT "
                    "  id, "
                    "  customer_responsible_id "
                    "  FROM repanier_lut_deliverypoint"
                    ") AS b "
                    "WHERE repanier_customer.delivery_point_id = b.id "
                )
                cursor.execute(
                    "UPDATE repanier_lut_deliverypoint SET "
                    " group_id = customer_responsible_id "
                    # "WHERE limit_order_quantity_to_stock = false "
                )
        except:
            pass
