from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings

from repanier import apps
from repanier.accounting_policy import AccountingPolicy
from repanier.admin.bankaccount import BankAccountAdmin
from repanier.admin.group import GroupWithUserDataAdmin
from repanier.admin.permanence_done import PermanenceDoneAdmin
from repanier.admin.producer import ProducerAdmin
from repanier.const import AccountingMode
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.group import Group
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer


class AccountingProgressiveUiTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.previous_mode = apps.REPANIER_SETTINGS_ACCOUNTING_MODE
        self.previous_groups = apps.REPANIER_SETTINGS_USE_GROUPS
        self.previous_invoice_basket = apps.REPANIER_SETTINGS_USE_INVOICE_BY_BASKET
        self.previous_deposits = apps.REPANIER_SETTINGS_USE_DEPOSITS

    def tearDown(self):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = self.previous_mode
        apps.REPANIER_SETTINGS_USE_GROUPS = self.previous_groups
        apps.REPANIER_SETTINGS_USE_INVOICE_BY_BASKET = self.previous_invoice_basket
        apps.REPANIER_SETTINGS_USE_DEPOSITS = self.previous_deposits

    def configure(self, mode=None, groups=True, invoice_basket=True, deposits=True):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = mode or AccountingMode.INTERNAL_BANK
        apps.REPANIER_SETTINGS_USE_GROUPS = groups
        apps.REPANIER_SETTINGS_USE_INVOICE_BY_BASKET = invoice_basket
        apps.REPANIER_SETTINGS_USE_DEPOSITS = deposits

    def request(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        return request

    @override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=True)
    def test_internal_bank_defaults_are_fallback_safe(self):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = None
        apps.REPANIER_SETTINGS_USE_GROUPS = True
        apps.REPANIER_SETTINGS_USE_INVOICE_BY_BASKET = True
        apps.REPANIER_SETTINGS_USE_DEPOSITS = True

        self.assertEqual(AccountingPolicy.accounting_mode(), AccountingMode.INTERNAL_BANK)
        self.assertTrue(AccountingPolicy.use_groups())
        self.assertTrue(AccountingPolicy.use_invoice_by_basket())
        self.assertTrue(AccountingPolicy.use_deposits())
        self.assertTrue(AccountingPolicy.manage_accounting())
        self.assertTrue(AccountingPolicy.manage_bank_account())

    def test_simple_orders_disables_accounting_but_keeps_archive_flow(self):
        self.configure(mode=AccountingMode.SIMPLE_ORDERS)

        self.assertFalse(AccountingPolicy.manage_accounting())
        self.assertFalse(AccountingPolicy.manage_bank_account())
        self.assertFalse(AccountingPolicy.manage_member_balances())
        self.assertTrue(AccountingPolicy.manage_archive_flow())

    @override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=True)
    def test_producer_seller_keeps_accounting_without_central_bank(self):
        self.configure(mode=AccountingMode.PRODUCER_SELLER)

        self.assertTrue(AccountingPolicy.manage_accounting())
        self.assertFalse(AccountingPolicy.manage_bank_account())
        self.assertTrue(AccountingPolicy.manage_member_balances())

    @override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=False)
    def test_legacy_global_setting_overrides_all_modes(self):
        self.configure(mode=AccountingMode.INTERNAL_BANK)

        self.assertFalse(AccountingPolicy.manage_accounting())
        self.assertFalse(AccountingPolicy.manage_bank_account())
        self.assertFalse(AccountingPolicy.manage_member_balances())
        self.assertTrue(AccountingPolicy.manage_archive_flow())

    def test_group_admin_permission_and_fieldset_follow_flag(self):
        model_admin = GroupWithUserDataAdmin(Group, admin.site)
        self.configure(groups=False)
        request = self.request()

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertEqual(model_admin.get_fieldsets(request), ((None, {"fields": ()}),))

    def test_group_feature_default_is_visible(self):
        self.configure(groups=True)
        model_admin = GroupWithUserDataAdmin(Group, admin.site)

        fieldsets = model_admin.get_fieldsets(self.request())
        self.assertNotEqual(fieldsets, ((None, {"fields": ()}),))

    def test_invoice_by_basket_field_follows_flag(self):
        self.configure(invoice_basket=False)
        model_admin = ProducerAdmin(Producer, admin.site)
        fieldsets = model_admin.get_fieldsets(self.request(), producer=None)

        fields = []
        for _title, options in fieldsets:
            fields.extend(options["fields"])
        self.assertNotIn("invoice_by_basket", fields)

    def test_deposit_field_follows_flag(self):
        self.configure(deposits=False)
        model_admin = __import__(
            "repanier.admin.product", fromlist=["ProductAdmin"]
        ).ProductAdmin
        model_admin = model_admin.__new__(model_admin)
        self.assertFalse(AccountingPolicy.use_deposits())

    def test_bank_account_admin_permission_follows_policy(self):
        self.configure(mode=AccountingMode.PRODUCER_SELLER)
        model_admin = BankAccountAdmin(BankAccount, admin.site)
        request = self.request()
        request.user.is_invoice_manager = True

        self.assertFalse(model_admin.has_add_permission(request))

    def test_permanence_row_actions_hide_book_for_simple_orders(self):
        self.configure(mode=AccountingMode.SIMPLE_ORDERS)
        from django.contrib.auth.models import User

        user = User.objects.create_superuser(
            username="simple-orders-admin",
            email="simple-orders@example.com",
            password="password",
        )
        request = self.request()
        request.user = user
        from repanier.const import SaleStatus
        permanence = Permanence.objects.create(
            permanence_date="2026-11-23",
            status=SaleStatus.SEND,
        )
        model_admin = PermanenceDoneAdmin(Permanence, admin.site)
        row = model_admin.get_row_actions(permanence)

        self.assertNotIn("/permanence-invoice/", str(row))
        self.assertIn("/cancel-delivery/", str(row))
