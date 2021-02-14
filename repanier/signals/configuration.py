from cms.toolbar_pool import toolbar_pool
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool

from repanier.const import (
    SALE_NAME_PERMANENCE,
    SALE_NAME_CLOSURE,
    SALE_NAME_DELIVERY,
    SALE_NAME_ORDER,
    SALE_NAME_OPENING,
    CURRENCY_LOC,
    CURRENCY_CHF,
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
    from repanier import globals

    config = kwargs["instance"]
    if config.id is not None:
        globals.REPANIER_SETTINGS_CONFIG = config
        if config.name == SALE_NAME_PERMANENCE:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Permanence")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Permanences")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Permanence of ")
        elif config.name == SALE_NAME_CLOSURE:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Closure")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Closures")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Closure of ")
        elif config.name == SALE_NAME_DELIVERY:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Delivery")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Deliveries")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Delivery of ")
        elif config.name == SALE_NAME_ORDER:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Order")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Orders")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Order of ")
        elif config.name == SALE_NAME_OPENING:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Opening")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Openings")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Opening of ")
        else:
            globals.REPANIER_SETTINGS_SALE_NAME = _("Distribution")
            globals.REPANIER_SETTINGS_PERMANENCES_NAME = _("Distributions")
            globals.REPANIER_SETTINGS_SALE_ON_NAME = _("Distribution of ")
        globals.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = (
            config.max_week_wo_participation
        )
        globals.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = (
            config.send_abstract_order_mail_to_customer
        )
        globals.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = (
            config.send_order_mail_to_board
        )
        globals.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = (
            config.send_invoice_mail_to_customer
        )
        globals.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = (
            config.send_invoice_mail_to_producer
        )
        globals.REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = (
            config.display_anonymous_order_form
        )
        globals.REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = config.display_who_is_who
        globals.REPANIER_SETTINGS_XLSX_PORTRAIT = config.xlsx_portrait
        # if config.bank_account is not None and len(config.bank_account.strip()) == 0:
        #     globals.REPANIER_SETTINGS_BANK_ACCOUNT = None
        # else:
        globals.REPANIER_SETTINGS_BANK_ACCOUNT = config.bank_account
        # if config.vat_id is not None and len(config.vat_id.strip()) == 0:
        #     globals.REPANIER_SETTINGS_VAT_ID = None
        # else:
        globals.REPANIER_SETTINGS_VAT_ID = config.vat_id
        globals.REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = (
            config.page_break_on_customer_check
        )
        globals.REPANIER_SETTINGS_MEMBERSHIP_FEE = config.membership_fee
        globals.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = (
            config.membership_fee_duration
        )
        if config.currency == CURRENCY_LOC:
            globals.REPANIER_SETTINGS_CURRENCY_DISPLAY = "✿"
            globals.REPANIER_SETTINGS_AFTER_AMOUNT = False
            globals.REPANIER_SETTINGS_CURRENCY_XLSX = (
                '_ ✿ * #,##0.00_ ;_ ✿ * -#,##0.00_ ;_ ✿ * "-"??_ ;_ @_ '
            )
        elif config.currency == CURRENCY_CHF:
            globals.REPANIER_SETTINGS_CURRENCY_DISPLAY = "Fr."
            globals.REPANIER_SETTINGS_AFTER_AMOUNT = False
            globals.REPANIER_SETTINGS_CURRENCY_XLSX = (
                '_ Fr\. * #,##0.00_ ;_ Fr\. * -#,##0.00_ ;_ Fr\. * "-"??_ ;_ @_ '
            )
        else:
            globals.REPANIER_SETTINGS_CURRENCY_DISPLAY = "€"
            globals.REPANIER_SETTINGS_AFTER_AMOUNT = True
            globals.REPANIER_SETTINGS_CURRENCY_XLSX = (
                '_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
            )
        if config.home_site:
            globals.REPANIER_SETTINGS_HOME_SITE = config.home_site
        else:
            globals.REPANIER_SETTINGS_HOME_SITE = "/"
        # config.email = settings.DJANGO_SETTINGS_EMAIL_HOST_USER
        menu_pool.clear()
        toolbar_pool.unregister(repanier.cms_toolbar.RepanierToolbar)
        toolbar_pool.register(repanier.cms_toolbar.RepanierToolbar)
        cache.clear()
