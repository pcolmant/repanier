# -*- coding: utf-8
from __future__ import unicode_literals

import time

from django.apps import AppConfig
from django.conf import settings
from django.db import connection
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

REPANIER_SETTINGS_CONFIG = None
REPANIER_SETTINGS_TEST_MODE = None
REPANIER_SETTINGS_GROUP_NAME = None
REPANIER_SETTINGS_PERMANENCE_NAME = None
REPANIER_SETTINGS_PERMANENCES_NAME = None
REPANIER_SETTINGS_PERMANENCE_ON_NAME = None
REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = None
REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_CANCEL_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = None
REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = None
REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = None
REPANIER_SETTINGS_INVOICE = None
REPANIER_SETTINGS_CLOSE_WO_SENDING = None
REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = None
REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM = None
REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = None
REPANIER_SETTINGS_BANK_ACCOUNT = None
REPANIER_SETTINGS_VAT_ID = None
REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = None
REPANIER_SETTINGS_SMS_GATEWAY_MAIL = None
REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS = None
REPANIER_SETTINGS_MEMBERSHIP_FEE = None
REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = None
REPANIER_SETTINGS_CURRENCY_DISPLAY = None
REPANIER_SETTINGS_AFTER_AMOUNT = None
REPANIER_SETTINGS_CURRENCY_XLSX = None
REPANIER_SETTINGS_HOME_SITE = None
REPANIER_SETTINGS_TRANSPORT = None
REPANIER_SETTINGS_MIN_TRANSPORT = None


class RepanierSettings(AppConfig):
    name = 'repanier'
    verbose_name = "Repanier"

    def ready(self):
        # Imports are inside the function because its point is to avoid importing
        # the models when django.contrib."MODELS" isn't installed.
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.sites.models import Site
        # If PostgreSQL service is not started the const may not be set
        # Django doesn't complain
        # This happens when the server starts at power up
        # first launching uwsgi before PostgreSQL
        db_started = False
        while not db_started:
            try:
                db_started = connection.cursor() is not None
            except:
                time.sleep(1)
        from models import Configuration, LUT_DepartmentForCustomer, Staff
        from const import DECIMAL_ONE, PERMANENCE_NAME_PERMANENCE, EMPTY_STRING, CURRENCY_EUR, ORDER_GROUP, \
            INVOICE_GROUP, CONTRIBUTOR_GROUP, COORDINATION_GROUP, WEBMASTER_GROUP
        try:
            # Create if needed and load RepanierSettings var when performing config.save()
            translation.activate(settings.LANGUAGE_CODE)
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
                    bank_account="BE99 9999 9999 9999",
                    vat_id=EMPTY_STRING,
                    sms_gateway_mail=EMPTY_STRING,
                    currency=CURRENCY_EUR
                )
            config.save()
            Staff.objects.rebuild()
            # Create groups with correct rights
            order_group = Group.objects.filter(name=ORDER_GROUP).only('id').order_by('?').first()
            if order_group is None:
                order_group = Group.objects.create(name=ORDER_GROUP)
            invoice_group = Group.objects.filter(name=INVOICE_GROUP).only('id').order_by('?').first()
            if invoice_group is None:
                invoice_group = Group.objects.create(name=INVOICE_GROUP)
            contributor_group = Group.objects.filter(name=CONTRIBUTOR_GROUP).only('id').order_by('?').first()
            if contributor_group is None:
                contributor_group = Group.objects.create(name=CONTRIBUTOR_GROUP)
            coordination_group = Group.objects.filter(name=COORDINATION_GROUP).only('id').order_by('?').first()
            if coordination_group is None:
                coordination_group = Group.objects.create(name=COORDINATION_GROUP)
            content_types = ContentType.objects.exclude(
                app_label__in=[
                    'admin',
                    # 'aldryn_bootstrap3',
                    'auth',
                    'cascade_dummy',
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
            ).only('id').order_by('?')
            permissions = Permission.objects.filter(
                content_type__in=content_types
            ).only('id').order_by('?')
            order_group.permissions.set(permissions)
            invoice_group.permissions.set(permissions)
            coordination_group.permissions.set(permissions)
            contributor_group.permissions.set(permissions)
            # WEBMASTER
            webmaster_group = Group.objects.filter(name=WEBMASTER_GROUP).only('id').order_by('?').first()
            if webmaster_group is None:
                webmaster_group = Group.objects.create(name=WEBMASTER_GROUP)
            content_types = ContentType.objects.exclude(
                app_label__in=[
                    'repanier',
                    'admin',
                    'auth',
                    'contenttypes',
                    'menus',
                    'repanier',
                    'reversion',
                    'sessions',
                    'sites',
                ]
            ).only('id').order_by('?')
            permissions = Permission.objects.filter(
                content_type__in=content_types
            ).only('id').order_by('?')
            webmaster_group.permissions.set(permissions)
            if LUT_DepartmentForCustomer.objects.count() == 0:
                # Generate a template of LUT_DepartmentForCustomer
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Vegetables"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Basket of vegetables"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Salads"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Tomatoes"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Potatoes"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Greens"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Cabbage"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Fruits"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Basket of fruits"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Apples"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Pears"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Plums"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Bakery"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Flour"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Bread"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Pastry"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Butchery"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Delicatessen"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Chicken"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Pork"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Beef"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Beef and pork"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Veal"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Lamb"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Grocery"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Takeaway"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Pasta"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Chocolates"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Oils"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Eggs"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Jams"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Cookies"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Creamery"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Dairy"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Cow cheese"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Goat cheese"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Sheep cheese"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Mixed cheese"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Icecream"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Cup of icecream"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Icecream per liter"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Icecream in frisco"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Icecream cake"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Sorbet"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Cup of sorbet"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Sorbet per liter"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Drink"))
                LUT_DepartmentForCustomer.objects.create(short_name=_("Juices"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Coffees"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Teas"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Herbal teas"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Wines"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Aperitifs"), parent=parent)
                LUT_DepartmentForCustomer.objects.create(short_name=_("Liqueurs"), parent=parent)
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Hygiene"))
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Deposit"))
                parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Subscription"))

        except Exception as error_str:
            print("##################################")
            print(error_str)
            print("##################################")
            other = _("Other qty")
