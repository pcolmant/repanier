# -*- coding: utf-8
from __future__ import unicode_literals
from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from const import *
from django.contrib.contenttypes.models import ContentType

REPANIER_SETTINGS_CONFIG = None
REPANIER_SETTINGS_TEST_MODE = None
REPANIER_SETTINGS_GROUP_NAME = None
REPANIER_SETTINGS_PERMANENCE_NAME = None
REPANIER_SETTINGS_PERMANENCES_NAME = None
REPANIER_SETTINGS_PERMANENCE_ON_NAME = None
REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = None
REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = None
REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_INVOICE= None
REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = None
REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM = None
REPANIER_SETTINGS_BANK_ACCOUNT = None
REPANIER_SETTINGS_DELIVERY_POINT = None
REPANIER_SETTINGS_DISPLAY_VAT = None
REPANIER_SETTINGS_VAT_ID = None
REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = None

class RepanierSettings(AppConfig):
    name = 'repanier'
    verbose_name = "Repanier"

    def ready(self):
        from models import Configuration
        try:
            # Create if needed and load RepanierSettings var when performing config.save()
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
                    send_abstract_order_mail_to_customer=False,
                    send_invoice_mail_to_producer=False,
                    send_abstract_order_mail_to_producer=False,
                    send_order_mail_to_board=False,
                    invoice=True,
                    display_anonymous_order_form=False,
                    display_producer_on_order_form=False,
                    bank_account="BE99 9999 9999 9999",
                    delivery_point=False,
                    display_vat=False,
                    vat_id=EMPTY_STRING,
                    page_break_on_customer_check=False
                )
            config.save()
            # Create groups with correct rights
            order_group = Group.objects.filter(name=ORDER_GROUP).only('id').order_by().first()
            if order_group is None:
                order_group = Group.objects.create(name=ORDER_GROUP)
            invoice_group = Group.objects.filter(name=INVOICE_GROUP).only('id').order_by().first()
            if invoice_group is None:
                invoice_group = Group.objects.create(name=INVOICE_GROUP)
            coordination_group = Group.objects.filter(name=COORDINATION_GROUP).only('id').order_by().first()
            if coordination_group is None:
                coordination_group = Group.objects.create(name=COORDINATION_GROUP)
            content_types = ContentType.objects.exclude(
                app_label__in=[
                    'admin',
                    'aldryn_bootstrap3',
                    'auth',
                    'cms',
                    'cmsplugin_cascade',
                    'cmsplugin_filer_file',
                    'cmsplugin_filer_folder',
                    'cmsplugin_filer_image',
                    'cmsplugin_filer_link',
                    'cmsplugin_filer_video',
                    'contenttypes',
                    'djangocms_text_ckeditor',
                    'easy_thumbnails',
                    'filer'
                    'menus',
                    'reversion',
                    'sessions',
                    'sites',
                ]
            ).only('id').order_by()
            permissions = Permission.objects.filter(
                content_type__in=content_types
            ).only('id').order_by()
            order_group.permissions = permissions
            invoice_group.permissions = permissions
            coordination_group.permissions = permissions
            content_types = ContentType.objects.exclude(
                app_label__in=[
                    'admin',
                    'auth',
                    'contenttypes',
                    'filer'
                    'menus',
                    'repanier',
                    'reversion',
                    'sessions',
                    'sites',
                ]
            ).only('id').order_by()
            permissions = Permission.objects.filter(
                content_type__in=content_types
            ).only('id').order_by()
            webmaster_group = Group.objects.filter(name=WEBMASTER_GROUP).only('id').order_by().first()
            if webmaster_group is None:
                webmaster_group = Group.objects.create(name=WEBMASTER_GROUP)
            webmaster_group.permissions = permissions

        except Exception as error_str:
            print("##################################")
            print error_str
            print("##################################")
            other = _("Other qty")
