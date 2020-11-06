from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    args = "<none>"
    help = "Empty null fields"

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE repanier_bankaccount SET operation_comment = '' WHERE operation_comment IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_configuration SET bank_account = '' WHERE bank_account IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_configuration SET home_site = '/' WHERE home_site IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_configuration SET vat_id = '' WHERE vat_id IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET about_me = '' WHERE about_me IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET address = '' WHERE address IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET bank_account1 = '' WHERE bank_account1 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET bank_account2 = '' WHERE bank_account2 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET city = '' WHERE city IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET long_basket_name = '' WHERE long_basket_name IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET memo = '' WHERE memo IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET phone1 = '' WHERE phone1 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET phone2 = '' WHERE phone2 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_customer SET vat_id = '' WHERE vat_id IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_offeritem SET reference = '' WHERE reference IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET address = '' WHERE address IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET bank_account = '' WHERE bank_account IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET fax = '' WHERE fax IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET long_profile_name = '' WHERE long_profile_name IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET memo = '' WHERE memo IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET offer_uuid = '' WHERE offer_uuid IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET phone1 = '' WHERE phone1 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET phone2 = '' WHERE phone2 IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET uuid = '' WHERE uuid IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producer SET vat_id = '' WHERE vat_id IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_producerinvoice SET invoice_reference = '' WHERE invoice_reference IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_product SET reference = '' WHERE reference IS NULL"
                )
                cursor.execute(
                    "UPDATE repanier_purchase SET comment = '' WHERE comment IS NULL"
                )
        except:
            pass

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE repanier_producer SET city = '' WHERE city IS NULL"
                )
        except:
            pass
