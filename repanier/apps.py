# -*- coding: utf-8
from __future__ import unicode_literals
from django.apps import AppConfig
from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from const import *

repanier_settings = {
    'CONFIG': None,
    'TEST_MODE': None,
    'GROUP_NAME': None,
    'PERMANENCE_NAME': None,
    'PERMANENCES_NAME': None,
    'PERMANENCE_ON_NAME': None,
    'MAX_WEEK_WO_PARTICIPATION': None,
    'SEND_OPENING_MAIL_TO_CUSTOMER': None,
    'SEND_ORDER_MAIL_TO_CUSTOMER': None,
    'SEND_ORDER_MAIL_TO_PRODUCER': None,
    'SEND_ORDER_MAIL_TO_BOARD': None,
    'SEND_INVOICE_MAIL_TO_CUSTOMER': None,
    'SEND_INVOICE_MAIL_TO_PRODUCER': None,
    'DISPLAY_ANONYMOUS_ORDER_FORM': None,
    'DISPLAY_PRODUCERS_ON_ORDER_FORM': None,
    'BANK_ACCOUNT': None,
    'PRODUCER_ORDER_ROUNDED': None,
    'PRODUCER_PRE_OPENING': None,
    'ACCEPT_CHILD_GROUP': None,
    'DELIVERY_POINT': None,
    'INVOICE': None,
    'STOCK': None,
    'DISPLAY_VAT': None,
    'VAT_ID': None,
    'PAGE_BREAK_ON_CUSTOMER_CHECK': None
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
                    test_mode=True,
                    name=PERMANENCE_NAME_PERMANENCE,
                    max_week_wo_participation=Decimal('99'),
                    send_opening_mail_to_customer=False,
                    send_order_mail_to_customer=False,
                    send_order_mail_to_producer=False,
                    send_invoice_mail_to_customer=False,
                    send_invoice_mail_to_producer=False,
                    send_order_mail_to_board=False,
                    invoice=True,
                    stock=False,
                    display_anonymous_order_form=False,
                    display_producer_on_order_form=False,
                    bank_account="BE99 9999 9999 9999",
                    producer_order_rounded=False,
                    producer_pre_opening=False,
                    accept_child_group=False,
                    delivery_point=False,
                    display_vat=False,
                    vat_id=EMPTY_STRING,
                    page_break_on_customer_check=False
                )
            config.save()
        except Exception as error_str:
            print("##################################")
            print error_str
            print("##################################")
            other = _("Other qty")
