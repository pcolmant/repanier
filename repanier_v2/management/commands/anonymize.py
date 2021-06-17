from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import translation
from parler.models import TranslationDoesNotExist

from repanier_v2.const import EMPTY_STRING, DECIMAL_ONE
from repanier_v2.models import BankAccount
from repanier_v2.models.configuration import Configuration
from repanier_v2.models.customer import Customer
from repanier_v2.models.lut import LUT_PermanenceRole
from repanier_v2.models.producer import Producer
from repanier_v2.models.staff import Staff


class Command(BaseCommand):
    help = "Anonymize customers and producers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--coordinator_password",
            nargs=1,
            type=str,
            action="store",
            default=["password"],
            help='set the coordinator password (default="password")',
        )
        parser.add_argument(
            "--coordinator_email",
            nargs=1,
            type=str,
            action="store",
            default=["coordinator@repanier_v2.be"],
            help='Set the coordinator (default="coordiantor")',
        )
        parser.add_argument(
            "--reset_admin",
            action="store_true",
            help="If present, reset the admin account",
        )

    def handle(self, *args, **options):
        if not settings.REPANIER_SETTINGS_DEMO:
            self.stdout.write(
                self.style.ERROR(
                    "Command not executed because the site is not in DEMO MODE"
                )
            )
            exit()
        config = Configuration.objects.filter(id=DECIMAL_ONE).first()
        if config is None:
            exit()
        config.bank_account = "BE99 9999 9999 9999"
        config.vat_id = EMPTY_STRING
        config.save()
        config.init_email()
        for customer in Customer.objects.all().order_by("?"):
            customer.anonymize(also_group=True)
            customer.user.set_password("customer")
            customer.user.save()
            print("Customer anonymized : {}".format(customer))
        coordinator_password = options["coordinator_password"][0]
        coordinator_email = options["coordinator_email"][0].lower()
        coordinator = Staff.get_or_create_any_coordinator()
        coordinator.user.set_password(coordinator_password)
        coordinator.user.email = coordinator_email
        coordinator.user.save()
        for producer in Producer.objects.all().order_by("?"):
            producer.anonymize(also_group=True)
            print("Producer anonymized : {}".format(producer))
        for permanence_role in LUT_PermanenceRole.objects.all().order_by("?"):
            permanence_role.description = EMPTY_STRING
            permanence_role.save_translations()
        BankAccount.objects.filter(customer__isnull=False).order_by("?").update(
            operation_comment=EMPTY_STRING
        )

        if options["reset_admin"]:
            self.stdout.write(self.style.SUCCESS("Reset admin to admin/admin"))
            for user in User.objects.filter(is_superuser=True):
                str_id = str(user.id)
                user.username = user.email = "{}@repanier_v2.be".format(str_id)
                user.first_name = EMPTY_STRING
                user.last_name = str_id
                user.is_staff = False
                user.is_superuser = False
                user.set_password(None)
                user.save()
            User.objects.create_user(
                username="admin",
                email="admin@repanier_v2.be",
                password="admin",
                first_name=EMPTY_STRING,
                last_name="admin",
                is_staff=True,
                is_superuser=True,
            )
        self.stdout.write(
            self.style.SUCCESS("Successfully anonymized customers, staff and producers")
        )