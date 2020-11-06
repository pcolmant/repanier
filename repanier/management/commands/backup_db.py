import os
from subprocess import call

from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

# sudo -u postgres psql
# CREATE DATABASE ptidej OWNER pi;
# gunzip ptidej-db.bak.XYZT.gz
#  pg_restore  --username=pi --format=c --no-owner --dbname=ptidej ptidej-db.bak.XYZT
from repanier.const import DECIMAL_ZERO
from repanier.models.customer import Customer


class Command(BaseCommand):
    args = "<none>"
    help = "Backup the db and send it by mail to the admin"

    def handle(self, *args, **options):
        db_name = settings.DJANGO_SETTINGS_DATABASE_NAME
        db_user = settings.DJANGO_SETTINGS_DATABASE_USER
        backup_file = NamedTemporaryFile(
            prefix="{}-db.bak.".format(db_name), suffix=".gz"
        )

        # pg_restore  -Fc -U _0_prd_example -C -c --no-owner --dbname=_0_prd_example db.bak

        result = call(
            "pg_dump -Fc -U {} {} | gzip".format(db_user, db_name),
            stdout=backup_file,
            shell=True,
        )
        if result == 0:
            migrations_files = NamedTemporaryFile(
                prefix="{}-mig.bak.".format(db_name), suffix=".gz"
            )
            repanier_path = os.path.join(
                os.path.dirname(settings.PROJECT_DIR), "repanier"
            )
            result = call(
                "cd {} && tar -zcf {} migrations{}*.py".format(
                    repanier_path, migrations_files.name, os.sep
                ),
                stdout=migrations_files,
                shell=True,
            )

            if result == 0:
                email = EmailMultiAlternatives(
                    subject="Backup {}".format(db_name),
                    body="Backup of the DB : {}".format(db_name),
                    to=[v for k, v in settings.ADMINS],
                )
                email.attach_file(os.path.abspath(backup_file.name), "application/zip")
                email.attach_file(
                    os.path.abspath(migrations_files.name), "application/zip"
                )
                email.send()
                for customer in Customer.objects.filter(
                    represent_this_buyinggroup=False,
                    subscribe_to_email=False,
                    is_group=False,
                    is_anonymized=False,
                ).order_by("?"):
                    if (
                        customer.get_purchase_counter() <= 0
                        and customer.get_participation_counter() <= 0
                        and customer.get_admin_balance().amount == DECIMAL_ZERO
                    ):
                        customer.is_active = False
                        customer.anonymize()
