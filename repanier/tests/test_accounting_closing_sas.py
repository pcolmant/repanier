import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repanier.accounting_closing import ClosingBalance
from repanier.admin.rule_of_3_per_product import OfferItemSendForm
from repanier.const import DECIMAL_ZERO, OrderUnit, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase

D = Decimal


@override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=True)
class ClosingSasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="sas@example.com",
            email="sas@example.com",
            password="password",
        )
        cls.customer = Customer.objects.create(
            user=cls.user,
            short_basket_name="SAS",
            may_order=True,
        )
        cls.producer = Producer.objects.create(short_profile_name="SAS producer")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
        )
        cls.permanence.producers.add(cls.producer)
        cls.product = Product.objects.create(
            producer=cls.producer,
            long_name_v2="SAS product",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.00"),
            customer_unit_price=D("2.50"),
            unit_deposit=D("0"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.product.is_into_offer = True
        cls.product.save()
        cls.offer_item = OfferItem.objects.create(
            permanence=cls.permanence,
            product=cls.product,
            producer=cls.producer,
            long_name_v2=cls.product.long_name_v2,
            order_unit=cls.product.order_unit,
            producer_unit_price=cls.product.producer_unit_price,
            customer_unit_price=cls.product.customer_unit_price,
            unit_deposit=cls.product.unit_deposit,
            quantity_invoiced=D("1"),
        )
        cls.customer_invoice = CustomerInvoice.objects.create(
            permanence=cls.permanence,
            customer=cls.customer,
            customer_charged=cls.customer,
            status=SaleStatus.SEND,
        )
        cls.producer_invoice = ProducerInvoice.objects.create(
            permanence=cls.permanence,
            producer=cls.producer,
            status=SaleStatus.SEND,
        )
        cls.customer_producer_invoice = CustomerProducerInvoice.objects.create(
            permanence=cls.permanence,
            customer=cls.customer,
            producer=cls.producer,
        )
        cls.purchase = Purchase.objects.create(
            permanence=cls.permanence,
            offer_item=cls.offer_item,
            producer=cls.producer,
            customer=cls.customer,
            customer_invoice=cls.customer_invoice,
            producer_invoice=cls.producer_invoice,
            customer_producer_invoice=cls.customer_producer_invoice,
            status=SaleStatus.SEND,
            quantity_ordered=D("1"),
            quantity_invoiced=D("1"),
            purchase_price=D("2.00"),
            selling_price=D("2.50"),
        )

    def test_punctual_offer_item_change_does_not_change_catalogue(self):
        original_catalogue = D(str(self.product.producer_unit_price.amount))
        self.offer_item.producer_unit_price.amount = D("3.00")
        self.offer_item.save(update_fields=["producer_unit_price"])

        self.product.refresh_from_db()
        self.assertEqual(self.product.producer_unit_price.amount, original_catalogue)
        self.assertEqual(self.offer_item.producer_unit_price.amount, D("3.00"))

    def test_catalogue_change_updates_only_the_current_offer_item(self):
        future_offer_item = OfferItem.objects.create(
            permanence=Permanence.objects.create(
                permanence_date=datetime.date.today() + datetime.timedelta(days=7),
                status=SaleStatus.PLANNED,
            ),
            product=self.product,
            producer=self.producer,
            long_name_v2=self.product.long_name_v2,
            order_unit=self.product.order_unit,
            producer_unit_price=self.product.producer_unit_price,
            customer_unit_price=self.product.customer_unit_price,
            unit_deposit=self.product.unit_deposit,
        )

        self.product.producer_unit_price.amount = D("4.00")
        self.product.save(update_fields=["producer_unit_price"])
        self.offer_item.producer_unit_price.amount = D("4.00")
        self.offer_item.save(update_fields=["producer_unit_price"])

        future_offer_item.refresh_from_db()
        self.assertEqual(future_offer_item.producer_unit_price.amount, D("2.00"))
        self.assertEqual(self.offer_item.producer_unit_price.amount, D("4.00"))

    def test_late_product_purchase_keeps_ordered_quantity_zero_and_links(self):
        new_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Late SAS product",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("3.00"),
            customer_unit_price=D("3.50"),
            unit_deposit=D("0"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        new_offer_item = OfferItem.objects.create(
            permanence=self.permanence,
            product=new_product,
            producer=self.producer,
            long_name_v2=new_product.long_name_v2,
            order_unit=new_product.order_unit,
            producer_unit_price=new_product.producer_unit_price,
            customer_unit_price=new_product.customer_unit_price,
            unit_deposit=new_product.unit_deposit,
            quantity_invoiced=D("1"),
        )
        new_purchase = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=new_offer_item,
            producer=self.producer,
            customer=self.customer,
            customer_invoice=self.customer_invoice,
            producer_invoice=self.producer_invoice,
            customer_producer_invoice=self.customer_producer_invoice,
            status=SaleStatus.SEND,
            quantity_ordered=DECIMAL_ZERO,
            quantity_invoiced=D("1"),
            purchase_price=D("3.00"),
            selling_price=D("3.50"),
        )

        balance = ClosingBalance(self.permanence).check()
        self.assertEqual(new_purchase.quantity_ordered, DECIMAL_ZERO)
        self.assertEqual(new_purchase.customer_invoice, self.customer_invoice)
        self.assertEqual(new_purchase.producer_invoice, self.producer_invoice)
        self.assertEqual(
            new_purchase.customer_producer_invoice,
            self.customer_producer_invoice,
        )
        self.assertTrue(
            any(item["code"] == "LATE_PRODUCT" for item in balance.warnings)
        )

    def test_incomplete_purchase_is_blocking(self):
        other_permanence = Permanence.objects.create(
            permanence_date=datetime.date.today() + datetime.timedelta(days=14),
            status=SaleStatus.SEND,
        )
        other_customer_invoice = CustomerInvoice.objects.create(
            permanence=other_permanence,
            customer=self.customer,
            customer_charged=self.customer,
            status=SaleStatus.SEND,
        )
        other_producer_invoice = ProducerInvoice.objects.create(
            permanence=other_permanence,
            producer=self.producer,
            status=SaleStatus.SEND,
        )
        other_customer_producer_invoice = CustomerProducerInvoice.objects.create(
            permanence=other_permanence,
            customer=self.customer,
            producer=self.producer,
        )
        Purchase.objects.filter(pk=self.purchase.pk).update(
            customer_invoice=other_customer_invoice,
            producer_invoice=other_producer_invoice,
            customer_producer_invoice=other_customer_producer_invoice,
        )
        balance = ClosingBalance(self.permanence).check()
        self.assertFalse(balance.is_valid)
        self.assertTrue(
            any(item["code"] == "PURCHASE_LINKS" for item in balance.blocking)
        )

    def test_simple_orders_disables_blocking_accounting_audit(self):
        from django.test.utils import override_settings

        with override_settings(
            REPANIER_SETTINGS_MANAGE_ACCOUNTING=True
        ):
            from repanier import apps
            from repanier.const import AccountingMode

            previous = apps.REPANIER_SETTINGS_ACCOUNTING_MODE
            apps.REPANIER_SETTINGS_ACCOUNTING_MODE = AccountingMode.SIMPLE_ORDERS
            try:
                balance = ClosingBalance(self.permanence).check()
                audit_codes = [
                    item["code"]
                    for item in balance.blocking
                    if item["code"].startswith("AUDIT_")
                ]
                self.assertEqual(audit_codes, [])
            finally:
                apps.REPANIER_SETTINGS_ACCOUNTING_MODE = previous

    def test_adjustment_rejected_when_accounting_disabled(self):
        from django.test.utils import override_settings
        from repanier.accounting_closing import create_accounting_adjustment
        from django.core.exceptions import ValidationError

        with override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=False):
            with self.assertRaises(ValidationError):
                create_accounting_adjustment(
                    permanence=self.permanence,
                    customer=self.customer,
                    offer_item=self.offer_item,
                    quantity=D("1"),
                )

    def test_adjustment_rejected_for_demo_permanence(self):
        from django.core.exceptions import ValidationError
        from repanier.accounting_closing import create_accounting_adjustment

        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])
        with self.assertRaises(ValidationError):
            create_accounting_adjustment(
                permanence=self.permanence,
                customer=self.customer,
                offer_item=self.offer_item,
                quantity=D("1"),
            )

    def test_adjustment_customers_exclude_inactive_anonymized_and_cannot_order(self):
        inactive_user = User.objects.create_user(
            username="inactive-member",
            email="inactive@example.com",
            password="test-password",
        )
        inactive = Customer.objects.create(
            user=inactive_user,
            short_basket_name="Inactive",
            may_order=True,
            is_active=False,
        )
        anonymized_user = User.objects.create_user(
            username="anonymous-member",
            email="anonymous@example.com",
            password="test-password",
        )
        anonymized = Customer.objects.create(
            user=anonymized_user,
            short_basket_name="Anonymized",
            may_order=True,
            is_anonymized=True,
        )
        eligible = Customer.objects.filter(
            may_order=True,
            is_active=True,
            is_anonymized=False,
        )
        self.assertIn(self.customer, eligible)
        self.assertNotIn(inactive, eligible)
        self.assertNotIn(anonymized, eligible)

    def test_confirm_invoice_template_has_no_nested_forms(self):
        from django.template.loader import get_template

        source = get_template(
            "repanier/admin/confirm_invoice.html"
        ).template.source
        self.assertEqual(source.count("<form "), 2)
        self.assertEqual(source.count("</form>"), 2)
        main_start = source.find('<form action="{{ form_url }}"')
        main_close = source.find("</form>", main_start)
        adjustment_start = source.find('<form method="post"', main_close)
        adjustment_close = source.find("</form>", adjustment_start)
        self.assertLess(main_start, main_close)
        self.assertLess(main_close, adjustment_start)
        self.assertLess(adjustment_start, adjustment_close)

    def test_check_closing_balance_wrapper_and_adjustment_origin(self):
        from repanier.accounting_closing import (
            check_closing_balance,
            create_accounting_adjustment,
        )
        from repanier.const import PreparationOrigin

        balance = check_closing_balance(self.permanence)
        self.assertTrue(
            hasattr(balance, "blocking") and hasattr(balance, "warnings")
        )

        new_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Late SAS product",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("3.00"),
            customer_unit_price=D("3.50"),
            unit_deposit=D("0"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        adjustment_offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=new_product,
            producer=self.producer,
            long_name_v2=new_product.long_name_v2,
            order_unit=new_product.order_unit,
            producer_unit_price=new_product.producer_unit_price,
            customer_unit_price=new_product.customer_unit_price,
            unit_deposit=new_product.unit_deposit,
            quantity_invoiced=D("0"),
        )
        purchase = create_accounting_adjustment(
            permanence=self.permanence,
            customer=self.customer,
            offer_item=adjustment_offer,
            quantity=D("1"),
        )
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity_ordered, DECIMAL_ZERO)
        self.assertEqual(
            purchase.origin,
            PreparationOrigin.ACCOUNTING_ADJUSTMENT,
        )

        first_quantity = purchase.quantity_invoiced
        purchase_again = create_accounting_adjustment(
            permanence=self.permanence,
            customer=self.customer,
            offer_item=adjustment_offer,
            quantity=D("1"),
        )
        self.assertEqual(purchase_again.pk, purchase.pk)
        purchase_again.refresh_from_db()
        self.assertEqual(
            purchase_again.quantity_invoiced,
            first_quantity + D("1"),
        )
        self.assertEqual(
            purchase_again.purchase_price.amount,
            purchase.purchase_price.amount * 2,
        )
        self.assertEqual(
            purchase_again.selling_price.amount,
            purchase.selling_price.amount * 2,
        )
        purchase_again.producer_invoice.refresh_from_db()
        purchase_again.customer_invoice.refresh_from_db()
        purchase_again.customer_producer_invoice.refresh_from_db()
        self.assertEqual(
            purchase_again.customer_producer_invoice.total_purchase_with_tax.amount,
            sum(p.purchase_price.amount for p in Purchase.objects.filter(
                customer_producer_invoice=purchase_again.customer_producer_invoice
            )),
        )
        self.assertEqual(
            purchase_again.customer_invoice.total_price_with_tax.amount,
            sum(p.selling_price.amount for p in Purchase.objects.filter(
                customer_invoice=purchase_again.customer_invoice
            )),
        )

    def test_adjustment_rejects_closed_permanence_and_nonfinite_quantity(self):
        from django.core.exceptions import ValidationError
        from repanier.accounting_closing import create_accounting_adjustment

        for quantity in (D("NaN"), D("Infinity"), D("0.00001")):
            with self.assertRaises(ValidationError):
                create_accounting_adjustment(
                    permanence=self.permanence, customer=self.customer,
                    offer_item=self.offer_item, quantity=quantity,
                )
        self.permanence.status = SaleStatus.INVOICED
        self.permanence.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            create_accounting_adjustment(
                permanence=self.permanence, customer=self.customer,
                offer_item=self.offer_item, quantity=D("1"),
            )

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_htmx_product_panel_is_scoped_and_links_to_delivery_and_catalogue(self):
        admin = User.objects.create_superuser(username="closing-admin", email="admin@example.com")
        self.client.force_login(admin)
        url = reverse("admin:permanence-closing-products", args=[self.permanence.pk])
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertContains(response, self.offer_item.long_name_v2)
        self.assertContains(response, reverse("admin:repanier_offeritemsend_change", args=[self.offer_item.pk]))
        self.assertContains(response, reverse("admin:repanier_product_change", args=[self.product.pk]))
        self.assertNotContains(response, "<html")
        self.assertContains(self.client.get(url), "<html")
        closing = self.client.get(reverse("admin:permanence-closing-balance", args=[self.permanence.pk]))
        self.assertContains(closing, f'hx-get="{url}"')
        self.assertContains(closing, 'name="product_id"')
        delivery_form = self.client.get(
            reverse("admin:repanier_offeritemsend_change", args=[self.offer_item.pk])
        )
        self.assertEqual(delivery_form.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_closing_adds_unordered_offer_to_all_invoices(self):
        from repanier.models.bankaccount import BankAccount

        admin = User.objects.create_superuser(username="closing-add-admin", email="admin@example.com")
        self.client.force_login(admin)
        new_product = Product.objects.create(
            producer=self.producer, long_name_v2="Unordered product",
            producer_unit_price=D("3.00"), order_unit=OrderUnit.PC,
        )
        new_offer = OfferItem.objects.create(
            permanence=self.permanence, product=new_product, producer=self.producer,
            long_name_v2=new_product.long_name_v2, order_unit=new_product.order_unit,
            producer_unit_price=new_product.producer_unit_price,
            customer_unit_price=new_product.customer_unit_price,
        )
        bank_count = BankAccount.objects.count()
        response = self.client.post(
            reverse("admin:permanence-closing-balance-adjustment", args=[self.permanence.pk]),
            {"customer_id": self.customer.pk, "offer_item_id": new_offer.pk, "quantity": "2"},
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get(customer=self.customer, offer_item=new_offer)
        self.assertEqual(purchase.quantity_ordered, 0)
        self.assertEqual(purchase.quantity_invoiced, 2)
        self.assertEqual(purchase.customer_invoice_id, self.customer_invoice.pk)
        self.assertEqual(purchase.producer_invoice_id, self.producer_invoice.pk)
        self.assertEqual(purchase.customer_producer_invoice_id, self.customer_producer_invoice.pk)
        self.assertEqual(BankAccount.objects.count(), bank_count)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_closing_adds_catalogue_product_not_in_the_delivery(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        from repanier.const import BankMovement
        from repanier.models.bankaccount import BankAccount
        from repanier.models.distribution import DistributionEvent, PickupSlot

        admin = User.objects.create_superuser(username="closing-catalogue-admin", email="admin@example.com")
        self.client.force_login(admin)
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Test opening anchor",
        )
        distribution = DistributionEvent.objects.create(
            permanence=self.permanence, distribution_date=self.permanence.permanence_date,
        )
        PickupSlot.objects.create(
            distribution_event=distribution, location="Test",
            starts_at=timezone.now(), ends_at=timezone.now(),
        )
        product = Product.objects.create(
            producer=self.producer, long_name_v2="New delivery product",
            producer_unit_price=D("3.00"), order_unit=OrderUnit.PC,
        )
        bank_count = BankAccount.objects.count()
        response = self.client.post(
            reverse("admin:permanence-closing-balance-adjustment", args=[self.permanence.pk]),
            {"customer_id": self.customer.pk, "product_id": product.pk, "quantity": "2"},
        )
        self.assertEqual(response.status_code, 302)
        offer = OfferItem.objects.get(permanence=self.permanence, product=product)
        purchase = Purchase.objects.get(customer=self.customer, offer_item=offer)
        self.assertEqual(purchase.quantity_ordered, 0)
        self.assertEqual(purchase.quantity_invoiced, 2)
        self.assertEqual(purchase.customer_invoice_id, self.customer_invoice.pk)
        self.assertEqual(purchase.producer_invoice_id, self.producer_invoice.pk)
        self.assertEqual(purchase.customer_producer_invoice_id, self.customer_producer_invoice.pk)
        self.assertEqual(purchase.purchase_price.amount, D("6.00"))
        self.assertEqual(BankAccount.objects.count(), bank_count)
        out = StringIO()
        call_command("audit_accounting", stdout=out)
        self.assertEqual(out.getvalue().count("0 finding(s)"), 6)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_closing_rejects_foreign_catalogue_product(self):
        from repanier.accounting_closing import create_catalogue_adjustment
        from django.core.exceptions import ValidationError

        other = Producer.objects.create(short_profile_name="Unrelated supplier")
        product = Product.objects.create(producer=other, long_name_v2="Foreign product")
        with self.assertRaises(ValidationError):
            create_catalogue_adjustment(
                permanence=self.permanence, customer=self.customer, product=product, quantity=D("1"),
            )
        self.assertFalse(OfferItem.objects.filter(permanence=self.permanence, product=product).exists())

    def test_invalid_catalogue_adjustment_rolls_back_new_offer(self):
        from repanier.accounting_closing import create_catalogue_adjustment
        from django.core.exceptions import ValidationError

        product = Product.objects.create(producer=self.producer, long_name_v2="No quantity product")
        with self.assertRaises(ValidationError):
            create_catalogue_adjustment(
                permanence=self.permanence, customer=self.customer, product=product, quantity=D("0"),
            )
        self.assertFalse(OfferItem.objects.filter(permanence=self.permanence, product=product).exists())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_delivery_form_changes_prices_and_quantity_without_or_with_catalogue(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from repanier.const import BankMovement
        from repanier.models.bankaccount import BankAccount

        admin = User.objects.create_superuser(username="closing-price-admin", email="admin@example.com")
        self.client.force_login(admin)
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Test opening anchor",
        )
        other_user = User.objects.create_user(username="other-closing-member")
        other_customer = Customer.objects.create(user=other_user, short_basket_name="Z other")
        other_purchase = Purchase.objects.create(
            permanence=self.permanence, offer_item=self.offer_item,
            producer=self.producer, customer=other_customer, status=SaleStatus.SEND,
            quantity_ordered=D("1"), quantity_invoiced=D("1"),
        )
        bank_count = BankAccount.objects.count()
        url = reverse("admin:repanier_offeritemsend_change", args=[self.offer_item.pk])
        initial = self.client.get(url)
        inline = initial.context["inline_admin_formsets"][0].formset
        prefix = inline.prefix
        self.assertIn("update_catalogue_prices", initial.content.decode())

        def submit(price, quantity, catalogue=False):
            data = {
                "permanence": str(self.permanence.pk),
                "producer_unit_price": price,
                "unit_deposit": "0",
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "1",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-id": str(self.purchase.pk),
                f"{prefix}-0-offer_item": str(self.offer_item.pk),
                f"{prefix}-0-customer": str(self.customer.pk),
                f"{prefix}-0-quantity_invoiced": quantity,
                f"{prefix}-0-purchase_price": "2.00",
                f"{prefix}-0-comment": "",
                "_save": "Save",
            }
            if catalogue:
                data["update_catalogue_prices"] = "on"
            response = self.client.post(url, data)
            if response.status_code != 302:
                form = response.context["adminform"].form
                formsets = response.context["inline_admin_formsets"]
                self.fail(f"Form errors: {form.errors}; inline errors: {[f.formset.errors for f in formsets]}")

        submit("3.00", "2")
        self.product.refresh_from_db()
        self.offer_item.refresh_from_db()
        self.purchase.refresh_from_db()
        self.assertEqual(self.product.producer_unit_price.amount, D("2.00"))
        self.assertEqual(self.offer_item.producer_unit_price.amount, D("3.00"))
        self.assertEqual(self.purchase.quantity_invoiced, D("2"))
        self.assertEqual(self.purchase.purchase_price.amount, D("6.00"))
        self.producer_invoice.refresh_from_db()
        other_purchase.refresh_from_db()
        self.assertEqual(other_purchase.purchase_price.amount, D("3.00"))
        self.assertEqual(self.producer_invoice.total_price_with_tax.amount, D("9.00"))

        submit("4.00", "2", catalogue=True)
        self.product.refresh_from_db()
        self.offer_item.refresh_from_db()
        self.purchase.refresh_from_db()
        self.assertEqual(self.product.producer_unit_price.amount, D("4.00"))
        self.assertNotEqual(self.product.customer_unit_price.amount, D("2.50"))
        self.assertEqual(
            self.offer_item.customer_unit_price.amount,
            self.product.customer_unit_price.amount,
        )
        self.assertEqual(self.purchase.purchase_price.amount, D("8.00"))
        other_purchase.refresh_from_db()
        self.assertEqual(other_purchase.purchase_price.amount, D("4.00"))
        self.assertEqual(BankAccount.objects.count(), bank_count)
        out = StringIO()
        try:
            call_command("audit_accounting", stdout=out)
        except CommandError:
            self.fail(out.getvalue())
        self.assertEqual(out.getvalue().count("0 finding(s)"), 6)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_htmx_product_panel_rejects_demo(self):
        admin = User.objects.create_superuser(username="closing-admin-demo", email="admin@example.com")
        self.client.force_login(admin)
        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])
        response = self.client.get(
            reverse("admin:permanence-closing-products", args=[self.permanence.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_catalogue_update_recomputes_vat_for_wo_vat_producer_and_spares_other_permanences(self):
        admin = User.objects.create_superuser(username="closing-vat-admin", email="admin@example.com")
        self.client.force_login(admin)
        Producer.objects.filter(pk=self.producer.pk).update(
            producer_price_are_wo_vat=True, price_list_multiplier=D("1.20")
        )
        Product.objects.filter(pk=self.product.pk).update(vat_level=Vat.VAT_400)
        OfferItem.objects.filter(pk=self.offer_item.pk).update(vat_level=Vat.VAT_400)
        other_permanence = Permanence.objects.create(
            permanence_date=datetime.date.today() + datetime.timedelta(days=7),
            status=SaleStatus.OPENED,
        )
        other_offer = OfferItem.objects.create(
            permanence=other_permanence,
            product=self.product,
            producer=self.producer,
            long_name_v2=self.product.long_name_v2,
            order_unit=self.product.order_unit,
            producer_unit_price=D("2.00"),
            customer_unit_price=D("2.50"),
            unit_deposit=D("0"),
        )
        url = reverse("admin:repanier_offeritemsend_change", args=[self.offer_item.pk])
        prefix = self.client.get(url).context["inline_admin_formsets"][0].formset.prefix
        data = {
            "permanence": str(self.permanence.pk),
            "producer_unit_price": "4.00",
            "unit_deposit": "0",
            "update_catalogue_prices": "on",
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-id": str(self.purchase.pk),
            f"{prefix}-0-offer_item": str(self.offer_item.pk),
            f"{prefix}-0-customer": str(self.customer.pk),
            f"{prefix}-0-quantity_invoiced": "1",
            f"{prefix}-0-purchase_price": "2.00",
            f"{prefix}-0-comment": "",
            "_save": "Save",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.offer_item.refresh_from_db()
        other_offer.refresh_from_db()
        self.assertEqual(self.product.producer_unit_price.amount, D("4.00"))
        self.assertEqual(self.product.producer_vat.amount, D("0.24"))
        self.assertEqual(self.product.customer_vat.amount, D("0.288"))
        self.assertEqual(self.product.customer_unit_price.amount, D("5.09"))
        self.assertEqual(
            self.offer_item.customer_unit_price.amount,
            self.product.customer_unit_price.amount,
        )
        self.assertEqual(self.offer_item.customer_vat.amount, self.product.customer_vat.amount)
        self.assertEqual(other_offer.producer_unit_price.amount, D("2.00"))
        self.assertEqual(other_offer.customer_unit_price.amount, D("2.50"))

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_invoice_view_rejects_demo(self):
        admin = User.objects.create_superuser(username="invoice-admin-demo", email="admin@example.com")
        self.client.force_login(admin)
        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])
        response = self.client.get(
            reverse("admin:permanence-invoice", args=[self.permanence.pk])
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_invoice_view_rejects_staff_without_invoice_manager_role(self):
        staff = User.objects.create_user(
            username="order-only-staff", email="order-only@example.com",
            password="pw", is_staff=True,
        )
        self.client.force_login(staff)
        for method in (self.client.get, self.client.post):
            response = method(
                reverse("admin:permanence-invoice", args=[self.permanence.pk])
            )
            self.assertNotEqual(response.status_code, 200)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)

    def test_invoice_view_calls_role_check_directly(self):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        from repanier.admin.permanence_done import PermanenceDoneAdmin
        from repanier.models import PermanenceDone
        from django.contrib import admin as django_admin

        request = RequestFactory().get("/")
        request.user = self.user
        request.user.is_invoice_manager = False
        model_admin = PermanenceDoneAdmin(PermanenceDone, django_admin.site)
        with self.assertRaises(PermissionDenied):
            model_admin.invoice(request, permanence_id=self.permanence.pk)

    def test_closing_blocks_without_bank_anchor(self):
        from repanier.const import BankMovement
        from repanier.models.bankaccount import BankAccount

        closing = ClosingBalance(self.permanence).check()
        self.assertIn("BANK_ANCHOR_MISSING", [f["code"] for f in closing.blocking])
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Test opening anchor",
        )
        closing = ClosingBalance(self.permanence).check()
        self.assertNotIn("BANK_ANCHOR_MISSING", [f["code"] for f in closing.blocking])

    def test_closing_flags_missing_customer_producer_invoice_without_crashing(self):
        Purchase.objects.filter(pk=self.purchase.pk).update(
            customer_producer_invoice=None
        )
        closing = ClosingBalance(self.permanence).check()
        self.assertIn("PURCHASE_LINKS", [f["code"] for f in closing.blocking])

    def test_quantity_gap_is_compared_to_the_ordered_quantity(self):
        Permanence.objects.filter(pk=self.permanence.pk).update(
            preparation_enabled=True
        )
        self.permanence.refresh_from_db()

        def gap_codes(**quantities):
            Purchase.objects.filter(pk=self.purchase.pk).update(**quantities)
            return [
                w["code"] for w in ClosingBalance(self.permanence).check().warnings
            ]

        self.assertNotIn(
            "PREPARATION_QUANTITY_GAP",
            gap_codes(quantity_prepared=D("1"), quantity_received=D("1")),
        )
        self.assertIn(
            "PREPARATION_QUANTITY_GAP",
            gap_codes(quantity_prepared=D("0"), quantity_received=D("0")),
        )
        self.assertIn(
            "PREPARATION_QUANTITY_GAP",
            gap_codes(quantity_prepared=D("1"), quantity_received=D("2")),
        )

    def test_failed_invoicing_rolls_back_producer_invoice_changes(self):
        from unittest import mock
        from django.contrib import admin as django_admin
        from repanier.admin.permanence_done import PermanenceDoneAdmin
        from repanier.models import PermanenceDone

        class FakeForm:
            cleaned_data = {
                "id": self.producer.pk,
                "selected": True,
                "to_be_invoiced_balance": D("2.00"),
                "invoice_reference": "REF-1",
            }

            def is_valid(self):
                return True

        request = mock.Mock()
        request.POST = {}
        request.user = self.user
        model_admin = PermanenceDoneAdmin(PermanenceDone, django_admin.site)
        with mock.patch.object(Permanence, "invoice", return_value=None):
            outcome, errors = model_admin._apply_invoice(
                request, self.permanence, datetime.date.today(), [FakeForm()]
            )
        self.assertEqual(outcome, "rejected")
        self.assertTrue(errors)
        self.producer_invoice.refresh_from_db()
        self.assertFalse(self.producer_invoice.to_be_paid)
        self.assertEqual(self.producer_invoice.invoice_reference, "")
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)

    def test_pickup_slot_rejects_end_before_start(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        from repanier.models.distribution import DistributionEvent, PickupSlot

        distribution = DistributionEvent.objects.create(
            permanence=self.permanence, distribution_date=self.permanence.permanence_date,
        )
        now = timezone.now()
        PickupSlot(
            distribution_event=distribution, location="Ok",
            starts_at=now, ends_at=now,
        ).full_clean()
        with self.assertRaises(ValidationError):
            PickupSlot(
                distribution_event=distribution, location="Bad",
                starts_at=now, ends_at=now - datetime.timedelta(hours=1),
            ).full_clean()
