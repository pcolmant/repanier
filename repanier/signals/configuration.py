from cms.toolbar_pool import toolbar_pool
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from menus.menu_pool import menu_pool

from repanier.const import (
    PermanenceName,
    Currency,
)
from repanier.models import Configuration


# @receiver(post_init, sender=Configuration)
# def configuration_post_init(sender, **kwargs):
#     config = kwargs["instance"]
#     if config.id is not None:
#         config.previous_email_host_password = config.email_host_password
#     else:
#         config.previous_email_host_password = EMPTY_STRING
#     config.email_host_password = EMPTY_STRING


# @receiver(pre_save, sender=Configuration)
# def configuration_pre_save(sender, **kwargs):
#     config = kwargs["instance"]
#     if not config.bank_account:
#         config.bank_account = None


@receiver(post_save, sender=Configuration)
def configuration_post_save(sender, **kwargs):
    import repanier.cms_toolbar
    from repanier import apps

    config = kwargs["instance"]
    if config.id is not None:
        apps.REPANIER_SETTINGS_CONFIG = config
        if config.name == PermanenceName.PERMANENCE:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Permanences")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Permanence of ")
        elif config.name == PermanenceName.CLOSURE:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Closures")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Closure of ")
        elif config.name == PermanenceName.DELIVERY:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Deliveries")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Delivery of ")
        elif config.name == PermanenceName.ORDER:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Orders")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Order of ")
        elif config.name == PermanenceName.OPENING:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Openings")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Opening of ")
        else:
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Distributions")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Distribution of ")
        apps.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = (
            config.max_week_wo_participation
        )
        apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = (
            config.send_abstract_order_mail_to_customer
        )
        apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = (
            config.send_order_mail_to_board
        )
        apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = (
            config.send_invoice_mail_to_customer
        )
        apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = (
            config.send_invoice_mail_to_producer
        )
        apps.REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = (
            config.display_anonymous_order_form
        )
        apps.REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = config.display_who_is_who
        apps.REPANIER_SETTINGS_XLSX_PORTRAIT = config.xlsx_portrait
        apps.REPANIER_SETTINGS_BANK_ACCOUNT = config.bank_account
        apps.REPANIER_SETTINGS_VAT_ID = config.vat_id
        apps.REPANIER_SETTINGS_MEMBERSHIP_FEE = config.membership_fee
        apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = config.membership_fee_duration

        if config.currency == Currency.EUR:
            currency_display = Currency.EUR.label
            apps.REPANIER_SETTINGS_AFTER_AMOUNT = True
        elif config.currency == Currency.LOC:
            currency_display = Currency.LOC.label
            apps.REPANIER_SETTINGS_AFTER_AMOUNT = True
        else:
            currency_display = Currency.CHF.label
            apps.REPANIER_SETTINGS_AFTER_AMOUNT = False

        apps.REPANIER_SETTINGS_CURRENCY_DISPLAY = currency_display
        currency_display_xlsx = currency_display.replace(".", "\.")
        apps.REPANIER_SETTINGS_CURRENCY_XLSX = f'_ {currency_display_xlsx} * #,##0.00_ ;_ {currency_display_xlsx} * -#,##0.00_ ;_ {currency_display_xlsx} * "-"??_ ;_ @_ '

        if config.home_site:
            apps.REPANIER_SETTINGS_HOME_SITE = config.home_site
        else:
            apps.REPANIER_SETTINGS_HOME_SITE = "/"
        menu_pool.clear()
        toolbar_pool.unregister(repanier.cms_toolbar.RepanierToolbar)
        toolbar_pool.register(repanier.cms_toolbar.RepanierToolbar)
        cache.clear()
