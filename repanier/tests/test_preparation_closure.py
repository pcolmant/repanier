import datetime
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from repanier import apps
from repanier.accounting_closing import ClosingBalance
from repanier.const import (
    AccountingMode,
    OrderUnit,
    PreparationOrigin,
    PreparationStatus,
    SaleStatus,
    Vat,
)
from repanier.models.customer import Customer
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
from repanier.preparation_closure import (
    ParcelDisposition,
    promote_preparation_to_accounting,
)


@override_settings(
    REPANIER_SETTINGS_MANAGE_ACCOUNTING=True,
    SECURE_SSL_REDIRECT=False,
)
class PreparationClosureTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="preparation-validator",
            email="validator@example.com",
            password="test-password",
        )
        self.customer = Customer.objects.create(
            user=self.user,
            short_basket_name="Validation",
            may_order=True,
        )
        self.producer = Producer.objects.create(
            short_profile_name="Validation producer",
        )
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
        )
        self.permanence.producers.add(self.producer)
        self.product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Validated product",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        self.offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=self.product,
            producer=self.producer,
            long_name_v2=self.product.long_name_v2,
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
            quantity_invoiced=Decimal("0"),
        )
        self.purchase = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=self.offer,
            producer=self.producer,
            customer=self.customer,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("2"),
            quantity_prepared=Decimal("2"),
            quantity_received=Decimal("2"),
            quantity_invoiced=Decimal("0"),
            preparation_status=PreparationStatus.VALIDATED,
            purchase_price=Decimal("2.00"),
            selling_price=Decimal("2.50"),
        )

    def test_classic_closure_does_not_require_mobile_validation(self):
        self.permanence.preparation_enabled = False
        self.permanence.save(update_fields=["preparation_enabled"])
        self.purchase.preparation_status = PreparationStatus.PREPARED
        self.purchase.save(update_fields=["preparation_status"])

        closing = ClosingBalance(self.permanence).check()

        self.assertNotIn(
            "PREPARATION_VALIDATION",
            [item["code"] for item in closing.blocking],
        )

    def test_mobile_closure_requires_all_lines_validated(self):
        self.purchase.preparation_status = PreparationStatus.PREPARED
        self.purchase.save(update_fields=["preparation_status"])

        closing = ClosingBalance(self.permanence).check()

        self.assertIn(
            "PREPARATION_VALIDATION",
            [item["code"] for item in closing.blocking],
        )

    def test_promotion_is_idempotent_and_updates_invoiced_quantity(self):
        event = PreparationSyncEvent.objects.create(
            permanence=self.permanence,
            purchase=self.purchase,
            uuid=uuid.uuid4(),
            client_timestamp=timezone.now(),
            operation="validate",
            status=PreparationSyncEvent.STATUS_APPLIED,
            payload={"uuid": str(uuid.uuid4())},
        )
        result = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
        )

        self.assertEqual(result["status"], "applied")
        self.purchase.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("2"))
        self.assertEqual(event.accounting_status, "applied")
        self.assertIsNotNone(event.accounting_applied_at)

        promoted_at = event.accounting_applied_at
        promote_preparation_to_accounting(self.permanence, user=self.user)
        event.refresh_from_db()
        self.assertEqual(event.accounting_applied_at, promoted_at)

    def test_uncertain_arrival_does_not_block_validated_preparation(self):
        from repanier.models.distribution import DistributionEvent, Offer

        offer = Offer.objects.create(title="Uncertain", is_uncertain_arrival=True)
        DistributionEvent.objects.create(
            permanence=self.permanence, offer=offer,
            distribution_date=self.permanence.permanence_date,
        )
        result = promote_preparation_to_accounting(self.permanence, user=self.user)
        self.assertEqual(result["status"], "applied")
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("2"))

    def test_deposit_credit_is_applied_once_on_repeated_promotion_and_recalculation(self):
        from repanier.models.invoice import CustomerInvoice

        invoice = CustomerInvoice.objects.get(
            permanence=self.permanence, customer=self.customer,
        )
        container = DepositContainerType.objects.create(
            code="CREDIT-ONCE", label="Credit", unit_credit=Decimal("1.25"),
        )
        DepositReceipt.objects.create(
            permanence=self.permanence, customer=self.customer,
            container_type=container, returned_count=1,
            credit_amount=Decimal("1.25"), status=PreparationSyncEvent.STATUS_APPLIED,
            client_timestamp=timezone.now(),
        )
        for _ in range(2):
            self.assertEqual(
                promote_preparation_to_accounting(self.permanence)["status"], "applied"
            )
            invoice.refresh_from_db()
            self.assertEqual(invoice.delta_price_with_tax.amount, Decimal("-1.25"))
        self.permanence.calculate_order_amount()
        invoice.refresh_from_db()
        self.assertEqual(invoice.delta_price_with_tax.amount, Decimal("-1.25"))

    def test_invalid_parcel_disposition_does_not_partially_promote(self):
        product = Product.objects.create(
            producer=self.producer, long_name_v2="Second", order_unit=OrderUnit.PC,
        )
        item = OfferItem.objects.create(
            permanence=self.permanence, producer=self.producer, product=product,
            long_name_v2="Second", order_unit=OrderUnit.PC,
        )
        second = Purchase.objects.create(
            permanence=self.permanence, offer_item=item, producer=self.producer,
            customer=self.customer, status=SaleStatus.SEND, quantity_ordered=1,
            quantity_prepared=1, quantity_received=1, quantity_invoiced=0,
            preparation_status=PreparationStatus.VALIDATED,
        )
        result = promote_preparation_to_accounting(
            self.permanence, parcel_dispositions={str(second.pk): "invalid"}
        )
        self.assertEqual(result["reason"], "invalid_parcel_disposition")
        self.purchase.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("0"))
        self.assertEqual(second.quantity_invoiced, Decimal("0"))

        result = promote_preparation_to_accounting(
            self.permanence, parcel_dispositions="{"
        )
        self.assertEqual(result["reason"], "invalid_parcel_dispositions")
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("0"))
        result = promote_preparation_to_accounting(
            self.permanence, parcel_dispositions=[]
        )
        self.assertEqual(result["reason"], "invalid_parcel_dispositions")

    def test_demo_permanence_cannot_be_promoted(self):
        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])

        result = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "demo_permanence")

    def test_substitution_lost_disposition_and_deposit_credit_are_consistent(self):
        from repanier.models.preparation import (
            DepositContainerType,
            DepositReceipt,
            PreparationSyncEvent,
        )

        target_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Lost substitution",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        target_offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=target_product,
            producer=self.producer,
            long_name_v2=target_product.long_name_v2,
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            quantity_invoiced=Decimal("0"),
        )
        target = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=target_offer,
            producer=self.producer,
            customer=self.customer,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("1"),
            quantity_prepared=Decimal("1"),
            quantity_received=Decimal("1"),
            quantity_invoiced=Decimal("0"),
            preparation_status=PreparationStatus.VALIDATED,
            origin=PreparationOrigin.SUBSTITUTION,
            substitution_source=self.purchase,
            purchase_price=Decimal("3.00"),
            selling_price=Decimal("3.50"),
        )
        PreparationSyncEvent.objects.create(
            permanence=self.permanence,
            purchase=target,
            uuid=uuid.uuid4(),
            client_timestamp=timezone.now(),
            operation="parcel_disposition",
            payload={
                "operation": "parcel_disposition",
                "purchase_id": target.id,
                "disposition": ParcelDisposition.LOST_IN_TRANSIT,
            },
            status=PreparationSyncEvent.STATUS_APPLIED,
        )
        container = DepositContainerType.objects.create(
            code="CLOSURE-CONTAINER",
            label="Closure container",
            unit_credit=Decimal("1.25"),
        )
        receipt = DepositReceipt.objects.create(
            uuid=uuid.uuid4(),
            permanence=self.permanence,
            customer=self.customer,
            container_type=container,
            returned_count=1,
            missing_count=0,
            credit_amount=Decimal("1.25"),
            status=PreparationSyncEvent.STATUS_APPLIED,
            client_timestamp=timezone.now(),
        )

        result = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
        )

        self.assertEqual(result["status"], "applied")
        target.refresh_from_db()
        receipt.refresh_from_db()
        self.assertEqual(target.quantity_invoiced, Decimal("0"))
        self.assertEqual(receipt.accounting_status, "applied")
        self.assertIsNotNone(receipt.accounting_applied_at)

    def test_persisted_lost_in_transit_disposition_is_used(self):
        from repanier.models.preparation import PreparationSyncEvent

        PreparationSyncEvent.objects.create(
            permanence=self.permanence,
            purchase=self.purchase,
            uuid=uuid.uuid4(),
            client_timestamp=timezone.now(),
            operation="parcel_disposition",
            payload={
                "operation": "parcel_disposition",
                "purchase_id": self.purchase.id,
                "disposition": ParcelDisposition.LOST_IN_TRANSIT,
            },
            status=PreparationSyncEvent.STATUS_APPLIED,
        )
        promote_preparation_to_accounting(self.permanence, user=self.user)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("0"))

    def test_lost_in_transit_is_zero_but_not_in_bl_is_received_quantity(self):
        lost = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
            parcel_dispositions={
                str(self.purchase.id): ParcelDisposition.LOST_IN_TRANSIT,
            },
        )
        self.assertEqual(lost["status"], "applied")
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("0"))

        normal = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
            parcel_dispositions={
                str(self.purchase.id): ParcelDisposition.NOT_IN_BL,
            },
        )
        self.assertEqual(normal["status"], "applied")
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("2"))

    def test_substitution_source_is_zero_and_target_is_invoiced(self):
        target_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Substitution target",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        target_offer = OfferItem.objects.create(
            permanence=self.permanence,
            product=target_product,
            producer=self.producer,
            long_name_v2=target_product.long_name_v2,
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            quantity_invoiced=Decimal("0"),
        )
        target = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=target_offer,
            producer=self.producer,
            customer=self.customer,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("2"),
            quantity_prepared=Decimal("1"),
            quantity_received=Decimal("1"),
            quantity_invoiced=Decimal("0"),
            preparation_status=PreparationStatus.VALIDATED,
            origin=PreparationOrigin.SUBSTITUTION,
            substitution_source=self.purchase,
            purchase_price=Decimal("3.00"),
            selling_price=Decimal("3.50"),
        )

        result = promote_preparation_to_accounting(
            self.permanence,
            user=self.user,
        )

        self.assertEqual(result["status"], "applied")
        self.purchase.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("0"))
        self.assertEqual(target.quantity_invoiced, Decimal("1"))
