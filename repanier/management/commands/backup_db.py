import glob
import os
from subprocess import call

from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from repanier.const import DECIMAL_ZERO
from repanier.models.customer import Customer

# cmd /c "copy /b _3_prd_lelensois-db.bak.001jfy7u.gz.part.aa+_3_prd_lelensois-db.bak.001jfy7u.gz.part.ab reconstructed_backup.gz"
# sudo -u postgres psql
# CREATE DATABASE ptidej OWNER pi;
# gunzip ptidej-db.bak.XYZT.gz
#  pg_restore  --username=pi --format=c --no-owner --dbname=ptidej ptidej-db.bak.XYZT

class Command(BaseCommand):
    args = "<none>"
    help = "Backup the db and send it by mail to the admin"

    # 10 MB pour tenir compte du surcoût Base64 SMTP
    SPLIT_SIZE_MB = 10

    def handle(self, *args, **options):

        db_name = settings.DJANGO_SETTINGS_DATABASE_NAME
        db_user = settings.DJANGO_SETTINGS_DATABASE_USER

        backup_file = NamedTemporaryFile(
            prefix=f"{db_name}-db.bak.",
            suffix=".gz",
        )

        result = call(
            f"pg_dump -Fc -U {db_user} {db_name} | gzip",
            stdout=backup_file,
            shell=True,
        )

        if result != 0:
            self.stderr.write("Database backup failed")
            return

        migrations_file = NamedTemporaryFile(
            prefix=f"{db_name}-mig.bak.",
            suffix=".gz",
        )

        repanier_path = os.path.join(
            os.path.dirname(settings.PROJECT_DIR),
            "repanier",
        )

        result = call(
            "cd {} && tar -zcf {} migrations{}{}{}*.py".format(
                repanier_path,
                migrations_file.name,
                os.sep,
                settings.DJANGO_SETTINGS_SITE_NAME,
                os.sep,
            ),
            shell=True,
        )

        if result != 0:
            self.stderr.write("Migration backup failed")
            return

        backup_size = os.path.getsize(backup_file.name)
        backup_size_mb = backup_size / 1024 / 1024

        self.stdout.write(
            f"Database backup size : {backup_size_mb:.2f} MB"
        )

        split_size_bytes = self.SPLIT_SIZE_MB * 1024 * 1024

        #
        # CAS 1 : Backup suffisamment petit
        #
        if backup_size <= split_size_bytes:

            email = EmailMultiAlternatives(
                subject=f"Backup {db_name}",
                body=(
                    f"Backup of database {db_name}\n\n"
                    f"Database size : {backup_size_mb:.2f} MB"
                ),
                to=[v for k, v in settings.ADMINS],
            )

            email.attach_file(
                os.path.abspath(backup_file.name),
                "application/gzip",
            )

            email.attach_file(
                os.path.abspath(migrations_file.name),
                "application/gzip",
            )

            try:
                email.send()
                self.stdout.write("Single email sent.")
            except Exception as e:
                self.stderr.write(
                    f"Email sending failed : {e}"
                )

        #
        # CAS 2 : Backup trop gros -> split
        #
        else:

            split_prefix = f"{backup_file.name}.part."

            result = call(
                f"split -b {self.SPLIT_SIZE_MB}M "
                f"{backup_file.name} "
                f"{split_prefix}",
                shell=True,
            )

            if result != 0:
                self.stderr.write("Split failed")
                return

            parts = sorted(
                glob.glob(f"{split_prefix}*")
            )

            total_parts = len(parts)

            self.stdout.write(
                f"Backup split into {total_parts} parts."
            )

            for idx, part in enumerate(parts, start=1):

                part_size_mb = (
                    os.path.getsize(part)
                    / 1024
                    / 1024
                )

                body = f"""
Backup of database {db_name}

Part {idx}/{total_parts}

Attached file:
{os.path.basename(part)}

Size:
{part_size_mb:.2f} MB


To rebuild the original backup on Linux:

cat {os.path.basename(backup_file.name)}.part.* > reconstructed_backup.gz

or

cat *.part.* > reconstructed_backup.gz


To rebuild on Windows:

copy /b part.aa+part.ab+part.ac reconstructed_backup.gz

Or with PowerShell:

cmd /c "copy /b part.aa+.part.ab+part.ac reconstructed_backup.gz"


The migrations archive is attached only to the first email.
"""

                email = EmailMultiAlternatives(
                    subject=(
                        f"Backup {db_name} "
                        f"({idx}/{total_parts})"
                    ),
                    body=body,
                    to=[v for k, v in settings.ADMINS],
                )

                email.attach_file(
                    os.path.abspath(part),
                    "application/octet-stream",
                )

                # joindre les migrations uniquement au premier mail
                if idx == 1:
                    email.attach_file(
                        os.path.abspath(
                            migrations_file.name
                        ),
                        "application/gzip",
                    )

                try:
                    email.send()

                    self.stdout.write(
                        f"Part {idx}/{total_parts} sent."
                    )

                except Exception as e:
                    self.stderr.write(
                        f"Failed sending part "
                        f"{idx}/{total_parts} : {e}"
                    )

        #
        # Anonymisation
        #
        for customer in Customer.objects.filter(
            represent_this_buyinggroup=False,
            is_group=False,
            is_anonymized=False,
        ):
            if (
                customer.get_purchase_counter() <= 0
                and customer.get_participation_counter() <= 0
                and customer.get_admin_balance().amount
                == DECIMAL_ZERO
            ):
                customer.anonymize()