import datetime
from io import BytesIO

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from openpyxl import load_workbook

from repanier import apps
from repanier.const import AccountingMode, OrderUnit, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.offeritem import OfferItem
from repanier.models.product import Product
from repanier.models.producer import Producer
from repanier.views.accounting_exports_view import AccountingExportFilterForm
from repanier.xlsx.xlsx_accounting_exports import (
    AccountingExportFilters,
    export_member_accounts,
    export_member_accounts_response,
    export_producer_closures,
    export_closing_producer_response,
    export_purchase_lines,
)


@override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=True)
class AccountingExportsTest(TestCase):
    def setUp(self):
        self.previous_mode = apps.REPANIER_SETTINGS_ACCOUNTING_MODE
        self.previous_groups = apps.REPANIER_SETTINGS_USE_GROUPS
        self.previous_deposits = apps.REPANIER_SETTINGS_USE_DEPOSITS
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = AccountingMode.INTERNAL_BANK
        apps.REPANIER_SETTINGS_USE_GROUPS = True
        apps.REPANIER_SETTINGS_USE_DEPOSITS = True

        producer_user = User.objects.create_user(
            username="export-producer",
            email="export-producer@example.com",
            password="password",
        )
        member_user = User.objects.create_user(
            username="export-member",
            email="export-member@example.com",
            password="password",
        )
        self.member = Customer.objects.create(
            user=member_user,
            short_basket_name="Export member",
            may_order=True,
        )
        self.producer = Producer.objects.create(short_profile_name="Export producer")
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.INVOICED,
        )
        self.permanence.producers.add(self.producer)
        ProducerInvoice.objects.create(
            permanence=self.permanence,
            producer=self.producer,
            status=SaleStatus.INVOICED,
            to_be_paid=True,
            invoice_reference="EXPORT-1",
        )

    def tearDown(self):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = self.previous_mode
        apps.REPANIER_SETTINGS_USE_GROUPS = self.previous_groups
        apps.REPANIER_SETTINGS_USE_DEPOSITS = self.previous_deposits

    def test_filter_form_accepts_combined_filters(self):
        form = AccountingExportFilterForm(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "permanence": self.permanence.pk,
                "producer": self.producer.pk,
                "status": SaleStatus.INVOICED,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_producer_closure_export_is_xlsx(self):
        filters = AccountingExportFilters(
            {
                "permanence": str(self.permanence.pk),
                "producer": str(self.producer.pk),
                "status": SaleStatus.INVOICED,
            }
        )
        wb = export_producer_closures(filters)
        self.assertIsNotNone(wb)
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        workbook = load_workbook(buffer, data_only=True)
        self.assertIn("Producer closures", workbook.sheetnames)

    def test_member_account_export_is_xlsx(self):
        wb = export_member_accounts()
        self.assertIsNotNone(wb)
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        workbook = load_workbook(buffer, data_only=True)
        self.assertIn("Member accounts", workbook.sheetnames)

    def test_producer_closure_http_response(self):
        response = export_closing_producer_response(
            AccountingExportFilters({"permanence": str(self.permanence.pk)})
        )
        self.assertIsNotNone(response)
        self.assertIn(
            "application/vnd.openxmlformats",
            response["Content-Type"],
        )
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        self.assertIn("Producer closures", workbook.sheetnames)

    def test_member_account_http_response(self):
        response = export_member_accounts_response()
        self.assertIsNotNone(response)
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        self.assertIn("Member accounts", workbook.sheetnames)

    def test_simple_orders_disables_exports(self):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = AccountingMode.SIMPLE_ORDERS
        self.assertIsNone(export_producer_closures())
        self.assertIsNone(export_member_accounts())

    def test_producer_seller_disables_member_bank_sheet(self):
        apps.REPANIER_SETTINGS_ACCOUNTING_MODE = AccountingMode.PRODUCER_SELLER
        wb = export_member_accounts()
        if wb is not None:
            self.assertNotIn("Member movements", wb.sheetnames)

    def test_groups_disabled_filters_out_group_memberships(self):
        apps.REPANIER_SETTINGS_USE_GROUPS = False
        filters = AccountingExportFilters({"group": "1"})
        customers = filters.member_accounts()
        self.assertEqual(customers.count(), 1)
        self.assertIsNone(customers.first().group)

    def test_offer_filter_is_accepted(self):
        product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Export offer",
            order_unit=OrderUnit.PC,
            producer_unit_price="2.00",
            customer_unit_price="2.50",
            vat_level=Vat.VAT_100,
            stock="99",
        )
        offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=product,
            producer=self.producer,
            long_name_v2="Export offer",
            order_unit=OrderUnit.PC,
            producer_unit_price="2.00",
            customer_unit_price="2.50",
        )
        form = AccountingExportFilterForm(
            {
                "offer": str(offer.pk),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        filters = AccountingExportFilters(
            {
                "offer": str(offer.pk),
            }
        )
        closures = filters.producer_closures()
        no_offer_closures = AccountingExportFilters().producer_closures()
        self.assertEqual(closures.count(), no_offer_closures.count())
        self.assertEqual(
            filters.purchase_lines().count(),
            0,
        )
        wb = export_purchase_lines(filters)
        self.assertIsNotNone(wb)
        self.assertIn("Purchase lines", wb.sheetnames)

    def test_purchase_lines_exclude_demo_permanences(self):
        demo = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.INVOICED,
            is_demo=True,
        )
        filters = AccountingExportFilters({"permanence": str(demo.pk)})
        self.assertEqual(filters.purchase_lines().count(), 0)
        wb = export_purchase_lines(filters)
        self.assertIsNotNone(wb)

    def test_status_filter(self):
        filters = AccountingExportFilters({"status": SaleStatus.INVOICED})
        invoices = filters.producer_closures()
        self.assertEqual(invoices.count(), 1)

    def test_operation_status_filter(self):
        from repanier.const import BankMovement

        filters = AccountingExportFilters(
            {"operation_status": BankMovement.PAYMENT_RECEIVED}
        )
        movements = filters.bank_movements()
        self.assertEqual(movements.count(), 0)

    @override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=False)
    def test_legacy_no_accounting_disables_exports(self):
        self.assertIsNone(export_producer_closures())
        self.assertIsNone(export_member_accounts())
