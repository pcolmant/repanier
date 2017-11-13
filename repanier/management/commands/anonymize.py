# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from parler.models import TranslationDoesNotExist

from repanier.const import EMPTY_STRING, DECIMAL_ONE
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.lut import LUT_PermanenceRole
from repanier.models.producer import Producer
from repanier.models.staff import Staff


class Command(BaseCommand):
    args = "<none>"
    help = "Anonymize customers, staff and producers"

    def handle(self, *args, **options):
        if not settings.DJANGO_SETTINGS_DEMO:
            print("Command not executed because the site is not in DEMO MODE")
            exit()
        translation.activate(settings.LANGUAGE_CODE)
        config = Configuration.objects.filter(id=DECIMAL_ONE).first()
        if config is None:
            exit()
        config.bank_account = "BE99 9999 9999 9999"
        config.vat_id = EMPTY_STRING
        config.sms_gateway_mail = EMPTY_STRING
        config.email_is_custom = False
        config.email_host = "smtp.gmail.com"
        config.email_port = 587
        config.email_use_tls = True
        config.email_host_user = "username@gmail.com"
        config.email_host_password = EMPTY_STRING
        config.save()
        config.init_email()
        for customer in Customer.objects.all().order_by('?'):
            customer.anonymize()
            print("Customer anonymized : {}".format(customer))
        for staff in Staff.objects.all().order_by('?'):
            staff.anonymize()
            print("Staff anonymized : {}".format(staff))
        for producer in Producer.objects.all().order_by('?'):
            producer.anonymize()
            print("Producer anonymized : {}".format(producer))
        for permanence_role in LUT_PermanenceRole.objects.all().order_by('?'):
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                permanence_role.set_current_language(language_code)
                try:
                    permanence_role.description = EMPTY_STRING
                    permanence_role.save_translation()
                except TranslationDoesNotExist:
                    pass
