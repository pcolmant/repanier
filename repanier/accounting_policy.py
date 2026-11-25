from django.conf import settings

from repanier import apps
from repanier.const import AccountingMode


class AccountingPolicy:
    @classmethod
    def accounting_mode(cls):
        return getattr(apps, "REPANIER_SETTINGS_ACCOUNTING_MODE", None) or AccountingMode.INTERNAL_BANK

    @classmethod
    def use_groups(cls):
        return bool(getattr(apps, "REPANIER_SETTINGS_USE_GROUPS", True))

    @classmethod
    def use_invoice_by_basket(cls):
        return bool(getattr(apps, "REPANIER_SETTINGS_USE_INVOICE_BY_BASKET", True))

    @classmethod
    def use_deposits(cls):
        return bool(getattr(apps, "REPANIER_SETTINGS_USE_DEPOSITS", True))

    @classmethod
    def use_mobile_preparation(cls):
        return bool(
            getattr(apps, "REPANIER_SETTINGS_USE_MOBILE_PREPARATION", False)
        )

    @classmethod
    def manage_accounting(cls):
        return (
            bool(getattr(settings, "REPANIER_SETTINGS_MANAGE_ACCOUNTING", True))
            and cls.accounting_mode() != AccountingMode.SIMPLE_ORDERS
        )

    @classmethod
    def manage_bank_account(cls):
        return cls.manage_accounting() and cls.accounting_mode() == AccountingMode.INTERNAL_BANK

    @classmethod
    def manage_member_balances(cls):
        return cls.manage_accounting() and cls.accounting_mode() != AccountingMode.SIMPLE_ORDERS

    @classmethod
    def manage_permanence_accounting(cls):
        return cls.manage_accounting()

    @classmethod
    def manage_archive_flow(cls):
        return not cls.manage_accounting()

    @classmethod
    def is_internal_bank(cls):
        return cls.accounting_mode() == AccountingMode.INTERNAL_BANK

    @classmethod
    def is_producer_seller(cls):
        return cls.accounting_mode() == AccountingMode.PRODUCER_SELLER

    @classmethod
    def is_simple_orders(cls):
        return cls.accounting_mode() == AccountingMode.SIMPLE_ORDERS
