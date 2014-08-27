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

class Command(BaseCommand):
    args = '<none>'
    help = 'Backup the db and send it by mail to the admin'

    def handle(self, *args, **options):
        db_name = settings.DATABASES['default']['NAME']
        db_user = settings.DATABASES['default']['USER']
        backup_file = NamedTemporaryFile(prefix=db_name + '-db.bak.', suffix='.gz')
        result = call("pg_dump -Fc -U " + db_user + " " + db_name + " | gzip", stdout=backup_file, shell=True)
        if result == 0:
            email = EmailMultiAlternatives(
                "Backup " + db_name,
                "Backup of the DB : " + db_name,
                settings.DEFAULT_FROM_EMAIL,
                [os.getenv('DJANGO_SETTINGS_MODULE_ADMIN_EMAIL', 'pcolmant@gmail.com')]
            )
            email.attach_file(os.path.abspath(backup_file.name),
                              'application/zip')
            if not settings.DEBUG:
                email.send()
            else:
                email.to = [v for k, v in settings.ADMINS]
                email.cc = []
                email.bcc = []
                email.send()
