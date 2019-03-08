# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import translation
from parler.models import TranslationDoesNotExist

from repanier.const import EMPTY_STRING, DECIMAL_ONE
from repanier.models import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.lut import LUT_PermanenceRole
from repanier.models.producer import Producer
from repanier.models.staff import Staff


class Command(BaseCommand):
    help = "Anonymize customers, staff and producers"

    def add_arguments(self, parser):
        parser.add_argument(
            '--coordinator_password',
            nargs=1,
            type=str,
            action='store',
            default=['password'],
            help='set the coordinator password (default="password")'
        )
        parser.add_argument(
            '--coordinator_email',
            nargs=1,
            type=str,
            action='store',
            default=['coordinator@repanier.be'],
            help='Set the coordinator (default="coordiantor")'
        )
        parser.add_argument(
            '--reset_admin',
            action='store_true',
            help='If present, reset the admin account'
        )

    def handle(self, *args, **options):
        if not settings.REPANIER_SETTINGS_DEMO:
            self.stdout.write(self.style.ERROR("Command not executed because the site is not in DEMO MODE"))
            exit()
        translation.activate(settings.LANGUAGE_CODE)
        config = Configuration.objects.filter(id=DECIMAL_ONE).first()
        if config is None:
            exit()
        config.bank_account = "BE99 9999 9999 9999"
        config.vat_id = EMPTY_STRING
        config.save()
        config.init_email()
        for customer in Customer.objects.all().order_by('?'):
            customer.anonymize(also_group=True)
            customer.user.set_password("customer")
            customer.user.save()
            print("Customer anonymized : {}".format(customer))
        for staff in Staff.objects.all().order_by('?'):
            staff.anonymize()
            print("Staff anonymized : {}".format(staff))
        coordinator_password = options['coordinator_password'][0]
        coordinator_email = options['coordinator_email'][0].lower()
        coordinator = Staff.get_or_create_any_coordinator()
        coordinator.user.set_password(coordinator_password)
        coordinator.user.email = coordinator_email
        coordinator.user.save()
        for producer in Producer.objects.all().order_by('?'):
            producer.anonymize(also_group=True)
            print("Producer anonymized : {}".format(producer))
        for permanence_role in LUT_PermanenceRole.objects.all().order_by('?'):
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                permanence_role.set_current_language(language_code)
                try:
                    permanence_role.description = EMPTY_STRING
                    permanence_role.save_translations()
                except TranslationDoesNotExist:
                    pass
        BankAccount.objects.filter(customer__isnull=False).order_by('?').update(operation_comment=EMPTY_STRING)

        if options['reset_admin']:
            self.stdout.write(self.style.SUCCESS("Reset admin to admin/admin"))
            for user in User.objects.filter(is_superuser=True):
                str_id = str(user.id)
                user.username = user.email = "{}@repanier.be".format(str_id)
                user.first_name = EMPTY_STRING
                user.last_name = str_id
                user.is_staff = False
                user.is_superuser = False
                user.set_password(None)
                user.save()
            User.objects.create_user(username="admin", email="admin@repanier.be", password="admin",
                                     first_name=EMPTY_STRING, last_name="admin", is_staff=True, is_superuser=True)
        self.stdout.write(self.style.SUCCESS("Successfully anonymized customers, staff and producers"))
