# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from subprocess import call
import os

# sudo -u postgres psql
# CREATE DATABASE ptidej OWNER pi;
# gunzip ptidej-db.bak.XYZT.gz
#  pg_restore  --username=pi --format=c --no-owner --dbname=ptidej ptidej-db.bak.XYZT
from repanier.const import DECIMAL_ZERO
from repanier.models.customer import Customer


class Command(BaseCommand):
    args = '<none>'
    help = 'Backup the db and send it by mail to the admin'

    def handle(self, *args, **options):
        db_name = settings.DATABASES['default']['NAME']
        db_user = settings.DATABASES['default']['USER']
        backup_file = NamedTemporaryFile(prefix=db_name + '-db.bak.', suffix='.gz')
        # pg_dump  -Fc -U pi _8_dev_gassines -f db.bak

        # sudo /etc/init.d/postgresql restart
        # sudo -u postgres psql
        # drop database _8_dev_gassines;
        # CREATE DATABASE _8_dev_gassines WITH TEMPLATE = template0 OWNER = pi ENCODING = 'UTF8' LC_COLLATE = 'fr_BE.UTF-8' LC_CTYPE = 'fr_BE.UTF-8';
        # \q
        # pg_restore  --username=pi --format=c --no-owner --dbname=_8_dev_gassines db.bak

        result = call("pg_dump -Fc -U " + db_user + " " + db_name + " | gzip", stdout=backup_file, shell=True)
        if result == 0:
            migrations_files = NamedTemporaryFile(prefix=db_name + '-mig.bak.', suffix='.gz')
            repanier_path = "{}{}{}".format(os.path.dirname(settings.PROJECT_DIR), os.sep, "repanier")
            result = call("cd {} && tar -zcf {} migrations{}*.py".format(repanier_path, migrations_files.name, os.sep),
                          stdout=migrations_files, shell=True)

            if result == 0:
                email = EmailMultiAlternatives(
                    subject="Backup " + db_name,
                    body="Backup of the DB : " + db_name,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[v for k, v in settings.ADMINS]
                )
                email.attach_file(os.path.abspath(backup_file.name),
                                  'application/zip')
                email.attach_file(os.path.abspath(migrations_files.name),
                                  'application/zip')
                email.send()
                for customer in Customer.objects.filter(
                    represent_this_buyinggroup=False,
                    subscribe_to_email=False,
                    is_group=False,
                    is_anonymized=False,
                ).order_by('?'):
                    if customer.get_purchase() <= 0 and customer.get_participation() <= 0 and customer.get_admin_balance().amount == DECIMAL_ZERO:
                        customer.is_active = False
                        customer.anonymize()
