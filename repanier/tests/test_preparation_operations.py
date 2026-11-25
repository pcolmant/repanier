import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from repanier import apps
from repanier.const import OrderUnit, PreparationOrigin, PreparationStatus, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.preparation import (
    DepositContainerType,
    DepositReceipt,
    PreparationSyncEvent,
)
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.preparation_sync import apply_preparation_sync


@override_settings(REPANIER_SETTINGS_MANAGE_ACCOUNTING=True)
class PreparationOperationsTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="operations@example.com",
            email="operations@example.com",
            password="password",
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Operations",
            may_order=True,
        )
        self.producer = Producer.objects.create(short_profile_name="Operations producer")
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
        )
        self.permanence.producers.add(self.producer)
        self.source_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Source",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        self.target_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Target",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        self.source_offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=self.source_product,
            producer=self.producer,
            long_name_v2=self.source_product.long_name_v2,
            order_unit=self.source_product.order_unit,
            producer_unit_price=self.source_product.producer_unit_price,
            customer_unit_price=self.source_product.customer_unit_price,
            quantity_invoiced=Decimal("1"),
        )
        self.target_offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=self.target_product,
            producer=self.producer,
            long_name_v2=self.target_product.long_name_v2,
            order_unit=self.target_product.order_unit,
            producer_unit_price=self.target_product.producer_unit_price,
            customer_unit_price=self.target_product.customer_unit_price,
            quantity_invoiced=Decimal("0"),
        )
        self.customer_invoice = CustomerInvoice.objects.create(
            permanence=self.permanence,
            customer=self.customer,
            customer_charged=self.customer,
            status=SaleStatus.SEND,
        )
        self.producer_invoice = ProducerInvoice.objects.create(
            permanence=self.permanence,
            producer=self.producer,
            status=SaleStatus.SEND,
        )
        self.customer_producer_invoice = CustomerProducerInvoice.objects.create(
            permanence=self.permanence,
            customer=self.customer,
            producer=self.producer,
        )
        self.source = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=self.source_offer,
            producer=self.producer,
            customer=self.customer,
            customer_invoice=self.customer_invoice,
            producer_invoice=self.producer_invoice,
            customer_producer_invoice=self.customer_producer_invoice,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("1"),
            quantity_prepared=Decimal("1"),
            quantity_received=Decimal("1"),
            preparation_status=PreparationStatus.PREPARED,
            quantity_invoiced=Decimal("1"),
            purchase_price=Decimal("2.00"),
            selling_price=Decimal("2.50"),
        )

    def test_substitution_resets_source_and_creates_target_with_link(self):
        old_quantity_ordered = self.source.quantity_ordered
        old_quantity_invoiced = self.source.quantity_invoiced
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(__import__("uuid").uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "substitute",
                "purchase_id": self.source.id,
                "target_offer_item_id": self.target_offer.id,
                "quantity": "1.0000",
            },
        )

        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.source.refresh_from_db()
        target = Purchase.objects.get(id=result["target_purchase_id"])
        self.assertEqual(self.source.quantity_prepared, Decimal("0"))
        self.assertEqual(self.source.quantity_received, Decimal("0"))
        self.assertEqual(self.source.quantity_ordered, old_quantity_ordered)
        self.assertEqual(self.source.quantity_invoiced, old_quantity_invoiced)
        self.assertEqual(target.origin, PreparationOrigin.SUBSTITUTION)
        self.assertEqual(target.substitution_source_id, self.source.id)

    def test_express_request_has_zero_ordered_quantity(self):
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(__import__("uuid").uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "express_request",
                "offer_item_id": self.target_offer.id,
                "customer_id": self.customer.id,
                "quantity": "2.0000",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        purchase = Purchase.objects.get(id=result["purchase_id"])
        self.assertEqual(purchase.quantity_ordered, Decimal("0"))
        self.assertEqual(purchase.origin, PreparationOrigin.EXPRESS_REQUEST)

    def test_deposit_receipt_credit_is_two_decimals(self):
        container = DepositContainerType.objects.create(
            code="CRATE",
            label="Crate",
            unit_credit=Decimal("1.25"),
            is_active=True,
        )
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(__import__("uuid").uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "deposit_receipt",
                "container_type_id": container.id,
                "customer_id": self.customer.id,
                "returned_count": 3,
                "missing_count": 1,
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.assertEqual(result["credit_amount"], "2.50")
        receipt = DepositReceipt.objects.get(uuid=result["uuid"])
        self.assertEqual(receipt.credit_amount.amount, Decimal("2.50"))

    def test_invalid_express_quantity_is_rejected_before_creation(self):
        customer_invoice_count = CustomerInvoice.objects.filter(
            permanence=self.permanence,
            customer=self.customer,
        ).count()
        producer_invoice_count = ProducerInvoice.objects.filter(
            permanence=self.permanence,
            producer=self.producer,
        ).count()
        cross_invoice_count = CustomerProducerInvoice.objects.filter(
            permanence=self.permanence,
            customer=self.customer,
            producer=self.producer,
        ).count()
        before = Purchase.objects.filter(
            permanence=self.permanence,
            origin=PreparationOrigin.EXPRESS_REQUEST,
        ).count()
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(__import__("uuid").uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "express_request",
                "offer_item_id": self.target_offer.id,
                "customer_id": self.customer.id,
                "quantity": "invalid",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "invalid_quantity")
        self.assertEqual(
            Purchase.objects.filter(
                permanence=self.permanence,
                origin=PreparationOrigin.EXPRESS_REQUEST,
            ).count(),
            before,
        )
        self.assertEqual(
            CustomerInvoice.objects.filter(
                permanence=self.permanence,
                customer=self.customer,
            ).count(),
            customer_invoice_count,
        )
        self.assertEqual(
            ProducerInvoice.objects.filter(
                permanence=self.permanence,
                producer=self.producer,
            ).count(),
            producer_invoice_count,
        )
        self.assertEqual(
            CustomerProducerInvoice.objects.filter(
                permanence=self.permanence,
                customer=self.customer,
                producer=self.producer,
            ).count(),
            cross_invoice_count,
        )

    def test_negative_substitution_quantity_is_rejected_before_mutation(self):
        old_prepared = self.source.quantity_prepared
        old_received = self.source.quantity_received
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(__import__("uuid").uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "substitute",
                "purchase_id": self.source.id,
                "target_offer_item_id": self.target_offer.id,
                "quantity": "-1",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "invalid_quantity")
        self.source.refresh_from_db()
        self.assertEqual(self.source.quantity_prepared, old_prepared)
        self.assertEqual(self.source.quantity_received, old_received)

    def test_deposit_receipt_disabled_is_rejected(self):
        container = DepositContainerType.objects.create(
            code="BOTTLE",
            label="Bottle",
            unit_credit=Decimal("0.50"),
            is_active=True,
        )
        previous = apps.REPANIER_SETTINGS_USE_DEPOSITS
        apps.REPANIER_SETTINGS_USE_DEPOSITS = False
        try:
            result = apply_preparation_sync(
                self.permanence,
                {
                    "uuid": str(__import__("uuid").uuid4()),
                    "client_timestamp": timezone.now().isoformat(),
                    "operation": "deposit_receipt",
                    "container_type_id": container.id,
                    "customer_id": self.customer.id,
                    "returned_count": 1,
                    "missing_count": 0,
                },
            )
        finally:
            apps.REPANIER_SETTINGS_USE_DEPOSITS = previous
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "deposits_disabled")
