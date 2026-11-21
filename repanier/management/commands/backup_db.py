import glob
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from repanier.const import DECIMAL_ZERO
from repanier.models.customer import Customer


class Command(BaseCommand):
    help = "Backup database and migrations locally and/or by email to ADMINS, then anonymize inactive customers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-dir",
            type=str,
            default=None,
            help="Base directory to store local backups (e.g. /var/backups/repanier). If omitted, only email backup is performed.",
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=14,
            help="Number of days to keep local backups when --backup-dir is set (default: 14).",
        )
        parser.add_argument(
            "--split-size-mb",
            type=int,
            default=10,
            help="Max attachment size in MB before splitting email parts (default: 10).",
        )

    def handle(self, *args, **options):
        db_name = settings.DJANGO_SETTINGS_DATABASE_NAME
        db_user = settings.DJANGO_SETTINGS_DATABASE_USER
        db_password = settings.DJANGO_SETTINGS_DATABASE_PASSWORD
        db_host = settings.DJANGO_SETTINGS_DATABASE_HOST or "127.0.0.1"
        db_port = str(settings.DJANGO_SETTINGS_DATABASE_PORT or "5432")

        backup_dir_opt = options["backup_dir"]
        retention_days = options["retention_days"]
        split_size_mb = options["split_size_mb"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = None

        if backup_dir_opt:
            site_backup_dir = Path(backup_dir_opt) / db_name
            site_backup_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = tempfile.TemporaryDirectory()
            site_backup_dir = Path(temp_dir.name)

        try:
            db_backup_path = site_backup_dir / f"{db_name}-db_{timestamp}.bak"
            mig_backup_path = site_backup_dir / f"{db_name}-mig_{timestamp}.tar.gz"

            # 1. Dump PostgreSQL format custom (-Fc intègre déjà la compression zlib)
            env = os.environ.copy()
            if db_password:
                env["PGPASSWORD"] = db_password

            dump_cmd = [
                "pg_dump",
                "-Fc",
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                "-f", str(db_backup_path),
                db_name,
            ]
            res_db = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
            if res_db.returncode != 0 or not db_backup_path.exists() or db_backup_path.stat().st_size == 0:
                self.stderr.write(f"Database backup failed: {res_db.stderr}")
                return

            # 2. Archive des migrations du site
            repanier_path = Path(settings.PROJECT_DIR).parent / "repanier"
            mig_rel_dir = Path("migrations") / settings.DJANGO_SETTINGS_SITE_NAME
            mig_files = list((repanier_path / mig_rel_dir).glob("*.py"))

            if mig_files:
                tar_cmd = [
                    "tar",
                    "-zcf",
                    str(mig_backup_path),
                    "-C",
                    str(repanier_path),
                    *[str(mig_rel_dir / f.name) for f in mig_files],
                ]
                res_mig = subprocess.run(tar_cmd, capture_output=True, text=True)
                if res_mig.returncode != 0:
                    self.stderr.write(f"Migration backup failed: {res_mig.stderr}")
                    return

            # 3. Rotation locale si --backup-dir est défini
            if backup_dir_opt and retention_days > 0:
                cutoff = time.time() - (retention_days * 86400)
                for old_file in site_backup_dir.iterdir():
                    if old_file.is_file() and old_file.stat().st_mtime < cutoff:
                        old_file.unlink()

            # 4. Envoi par e-mail aux ADMINS
            backup_size = db_backup_path.stat().st_size
            backup_size_mb = backup_size / 1024 / 1024
            if backup_dir_opt:
                self.stdout.write(f"Database backup saved locally ({backup_size_mb:.2f} MB): {db_backup_path}")

            split_size_bytes = split_size_mb * 1024 * 1024
            admins = [v for _, v in settings.ADMINS]

            if not admins:
                self.stdout.write("No ADMINS configured, skipping email dispatch.")
            elif backup_size <= split_size_bytes:
                email = EmailMultiAlternatives(
                    subject=f"Backup {db_name}",
                    body=f"Backup of database {db_name}\n\nDatabase size : {backup_size_mb:.2f} MB",
                    to=admins,
                )
                email.attach_file(str(db_backup_path), "application/octet-stream")
                if mig_backup_path.exists():
                    email.attach_file(str(mig_backup_path), "application/gzip")
                try:
                    email.send()
                    self.stdout.write("Single backup email sent.")
                except Exception as e:
                    self.stderr.write(f"Email sending failed: {e}")
            else:
                split_prefix = f"{db_backup_path}.part."
                subprocess.run(
                    ["split", "-b", f"{split_size_mb}M", str(db_backup_path), split_prefix],
                    check=True,
                )
                parts = sorted(glob.glob(f"{split_prefix}*"))
                total_parts = len(parts)
                try:
                    for idx, part in enumerate(parts, start=1):
                        part_size_mb = os.path.getsize(part) / 1024 / 1024
                        body = (
                            f"Backup of database {db_name} - Part {idx}/{total_parts} ({part_size_mb:.2f} MB)\n\n"
                            f"Rebuild on Linux: cat {db_backup_path.name}.part.* > {db_backup_path.name}\n"
                            f"Restore: pg_restore --username={db_user} --format=c --no-owner --dbname={db_name} {db_backup_path.name}\n"
                        )
                        email = EmailMultiAlternatives(
                            subject=f"Backup {db_name} ({idx}/{total_parts})",
                            body=body,
                            to=admins,
                        )
                        email.attach_file(part, "application/octet-stream")
                        if idx == 1 and mig_backup_path.exists():
                            email.attach_file(str(mig_backup_path), "application/gzip")
                        email.send()
                        self.stdout.write(f"Part {idx}/{total_parts} sent.")
                except Exception as e:
                    self.stderr.write(f"Failed sending split backup: {e}")
                finally:
                    for part in parts:
                        if os.path.exists(part):
                            os.remove(part)

            # 5. Anonymisation RGPD des comptes sans historique ni solde
            for customer in Customer.objects.filter(
                represent_this_buyinggroup=False,
                is_group=False,
                is_anonymized=False,
            ):
                if (
                    customer.get_purchase_counter() <= 0
                    and customer.get_participation_counter() <= 0
                    and customer.get_admin_balance().amount == DECIMAL_ZERO
                ):
                    customer.anonymize()
        finally:
            if temp_dir:
                temp_dir.cleanup()