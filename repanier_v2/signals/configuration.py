from cms.toolbar_pool import toolbar_pool
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from menus.menu_pool import menu_pool

from repanier_v2.const import (
    CURRENCY_LOC,
    CURRENCY_CHF,
)
from repanier_v2.models import Configuration


@receiver(post_save, sender=Configuration)
def configuration_post_save(sender, **kwargs):
    import repanier_v2.cms_toolbar
    from repanier_v2 import globals

    config = kwargs["instance"]
    if config.id is not None:
        globals.REPANIER_SETTINGS_CONFIG = config
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
        toolbar_pool.unregister(repanier_v2.cms_toolbar.RepanierToolbar)
        toolbar_pool.register(repanier_v2.cms_toolbar.RepanierToolbar)
        cache.clear()
