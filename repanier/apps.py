# -*- coding: utf-8
from __future__ import unicode_literals
from django.apps import AppConfig
from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from const import *

repanier_settings = {
    'GROUP_NAME': None,
    'PERMANENCE_NAME': None,
    'PERMANENCES_NAME': None,
    'PERMANENCE_ON_NAME': None,
    'SEND_MAIL_ONLY_TO_STAFF': None,
    'SEND_ORDER_TO_BOARD': None,
    'INVOICE': None,
    'STOCK': None,
    'DISPLAY_ANONYMOUS_ORDER_FORM': None,
    'DISPLAY_PRODUCERS_ON_ORDER_FORM': None,
    'BANK_ACCOUNT': None,
    'PRODUCER_ORDER_ROUNDED': None,
    'ACCEPT_CHILD_GROUP': None,
    'DISPLAY_VAT': None,
    'MAX_WEEK_WO_PARTICIPATION': None,
    'VAT_ID': None,
    'DELIVERY_POINT': None
}

class RepanierConfig(AppConfig):
    name = 'repanier'
    verbose_name = "Repanier"

    def ready(self):
        from models import Configuration
        try:
            config = Configuration.objects.filter(id=DECIMAL_ONE).first()
            if config is None:
                group_name = settings.ALLOWED_HOSTS[0]
                site = Site.objects.get_current()
                if site is not None:
                    site.name = group_name
                    site.domain = group_name
                    site.save()
                config = Configuration.objects.create(
                    group_name=group_name,
                    name=PERMANENCE_NAME_PERMANENCE,
                    send_mail_only_to_staff=True,
                    send_order_to_board=False,
                    invoice=True,
                    stock=False,
                    display_anonymous_order_form=False,
                    display_producer_on_order_form=True,
                    bank_account="BE99 9999 9999 9999",
                    producer_order_rounded=False,
                    accept_child_group=False,
                    display_vat=True,
                    max_week_wo_participation=Decimal('99'),
                    vat_id=EMPTY_STRING,
                    delivery_point=False
                )
            config.save()
        except Exception as error_str:
            print("##################################")
            print error_str
            print("##################################")
            other = _("Other qty")
