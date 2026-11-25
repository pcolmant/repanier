import datetime
import uuid
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core import signing
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from repanier.const import (
    DECIMAL_ZERO,
    OrderUnit,
    PreparationOrigin,
    PreparationStatus,
    SaleStatus,
    Vat,
)
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.preparation import PreparationSyncEvent
from repanier.models.preparation import DepositContainerType, DepositReceipt
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.preparation_sync import (
    make_preparation_token,
    resolve_preparation_token,
    revoke_preparation_access,
    apply_preparation_sync,
)


class PreparationSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="prep@example.com",
            email="prep@example.com",
            password="password",
        )
        self.customer = Customer.objects.create(
            user=self.user,
            short_basket_name="Prep customer",
            may_order=True,
        )
        self.producer = Producer.objects.create(short_profile_name="Prep producer")
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
        )
        self.permanence.producers.add(self.producer)
        self.product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Prep product",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
            vat_level=Vat.VAT_100,
            stock="99",
        )
        self.offer_item = OfferItem.objects.create(
            permanence=self.permanence,
            product=self.product,
            producer=self.producer,
            long_name_v2=self.product.long_name_v2,
            order_unit=self.product.order_unit,
            producer_unit_price=self.product.producer_unit_price,
            customer_unit_price=self.product.customer_unit_price,
            unit_deposit=self.product.unit_deposit,
            quantity_invoiced=Decimal("1.0000"),
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
        self.purchase = Purchase.objects.create(
            permanence=self.permanence,
            offer_item=self.offer_item,
            producer=self.producer,
            customer=self.customer,
            customer_invoice=self.customer_invoice,
            producer_invoice=self.producer_invoice,
            customer_producer_invoice=self.customer_producer_invoice,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("1.0000"),
            quantity_invoiced=Decimal("1.0000"),
            purchase_price=Decimal("2.00"),
            selling_price=Decimal("2.50"),
        )

    def test_signed_token_resolves_and_revoke_blocks_it(self):
        token = make_preparation_token(self.permanence.id)
        self.assertEqual(
            resolve_preparation_token(token),
            self.permanence,
        )
        revoke_preparation_access(self.permanence.id)
        self.assertIsNone(resolve_preparation_token(token))

    def _group_handover(self, quantity="1"):
        from repanier.models.deliveryboard import DeliveryBoard
        from repanier.models.lut import LUT_DeliveryPoint

        group_user = User.objects.create_user(username="handover-group")
        group = Customer.objects.create(
            user=group_user, short_basket_name="Handover group", is_group=True,
        )
        point = LUT_DeliveryPoint.objects.create(short_name_v2="Group", group=group)
        board = DeliveryBoard.objects.create(permanence=self.permanence, delivery_point=point)
        self.customer_invoice.delivery = board
        self.customer_invoice.customer_charged = group
        self.customer_invoice.save(update_fields=["delivery", "customer_charged"])
        Purchase.objects.filter(pk=self.purchase.pk).update(
            quantity_prepared=Decimal("1"), quantity_received=Decimal(quantity),
            preparation_status=PreparationStatus.HANDED_TO_GROUP,
        )
        for operation in ("receive", "hand_to_group"):
            PreparationSyncEvent.objects.create(
                permanence=self.permanence, purchase=self.purchase, operation=operation,
                client_timestamp=timezone.now(), status=PreparationSyncEvent.STATUS_APPLIED,
                payload={"quantity": quantity} if operation == "receive" else {},
            )

    def test_group_auto_validation_is_idempotent_and_dry_run_is_read_only(self):
        from repanier.models.bankaccount import BankAccount

        self._group_handover()
        bank_before = list(BankAccount.objects.values_list(
            "id", "bank_amount_in", "bank_amount_out", "operation_status"
        ).order_by("id"))
        self.producer.refresh_from_db()
        producer_balance = self.producer.balance.amount
        Purchase.objects.filter(pk=self.purchase.pk).update(
            purchase_price=Decimal("99"), selling_price=Decimal("99"),
        )
        self.producer_invoice.refresh_from_db()
        producer_invoice_total = self.producer_invoice.total_price_with_tax.amount
        output = StringIO()
        call_command("auto_validate_group_deliveries", days=0, dry_run=True, stdout=output)
        self.assertIn("1 purchase(s) candidate", output.getvalue())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        before = self.purchase.quantity_invoiced
        call_command("auto_validate_group_deliveries", days=0, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.VALIDATED)
        self.assertEqual(self.purchase.quantity_invoiced, before)
        self.producer_invoice.refresh_from_db()
        self.assertEqual(self.producer_invoice.total_price_with_tax.amount, producer_invoice_total)
        self.producer.refresh_from_db()
        self.assertEqual(self.producer.balance.amount, producer_balance)
        self.assertEqual(
            list(BankAccount.objects.values_list(
                "id", "bank_amount_in", "bank_amount_out", "operation_status"
            ).order_by("id")),
            bank_before,
        )
        output = StringIO()
        call_command("auto_validate_group_deliveries", days=0, stdout=output)
        self.assertIn("0 purchase(s) validated", output.getvalue())

    def test_group_prepare_receive_handover_then_tacit_validation(self):
        self._group_handover()
        PreparationSyncEvent.objects.filter(purchase=self.purchase).delete()
        Purchase.objects.filter(pk=self.purchase.pk).update(
            quantity_prepared=0, quantity_received=0,
            preparation_status=PreparationStatus.ORDERED,
        )
        base = timezone.now()
        for offset, operation in enumerate(("prepare", "receive", "hand_to_group")):
            result = apply_preparation_sync(self.permanence, {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": (base + datetime.timedelta(milliseconds=offset)).isoformat(),
                "operation": operation,
                "purchase_id": self.purchase.pk,
                "quantity": "1",
            })
            self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        call_command("auto_validate_group_deliveries", days=0, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.VALIDATED)

    def test_snapshot_uses_chosen_group_delivery_not_customer_membership(self):
        from django.urls import reverse

        self._group_handover()
        token = make_preparation_token(self.permanence.id)
        response = self.client.get(reverse("repanier:preparation_snapshot", args=[token]), follow=True)
        self.assertEqual(response.status_code, 200)
        line = response.json()["purchases"][0]
        self.assertTrue(line["in_group"])
        self.assertEqual(line["group_id"], self.customer_invoice.delivery.delivery_point.group_id)
        self.customer_invoice.delivery = None
        self.customer_invoice.save(update_fields=["delivery"])
        response = self.client.get(reverse("repanier:preparation_snapshot", args=[token]), follow=True)
        self.assertFalse(response.json()["purchases"][0]["in_group"])

    def test_group_discrepancy_is_not_automatically_validated(self):
        from repanier.models.bankaccount import BankAccount

        self._group_handover(quantity="0")
        self.producer.refresh_from_db()
        producer_balance = self.producer.balance.amount
        movement_count = BankAccount.objects.count()
        errors = StringIO()
        call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertEqual(self.purchase.quantity_invoiced, Decimal("1"))
        self.assertIn("quantity discrepancy", errors.getvalue())
        self.producer.refresh_from_db()
        self.assertEqual(self.producer.balance.amount, producer_balance)
        self.assertEqual(BankAccount.objects.count(), movement_count)

    def test_individual_handover_is_not_group_validated(self):
        self._group_handover()
        self.customer_invoice.delivery = None
        self.customer_invoice.save(update_fields=["delivery"])
        call_command("auto_validate_group_deliveries", days=0, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)

    def test_group_demo_conflict_and_delay_are_excluded(self):
        self._group_handover()
        call_command("auto_validate_group_deliveries", days=2, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])
        call_command("auto_validate_group_deliveries", days=0, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.permanence.is_demo = False
        self.permanence.save(update_fields=["is_demo"])
        for status in (
            PreparationSyncEvent.STATUS_CONFLICT,
            PreparationSyncEvent.STATUS_REJECTED,
            PreparationSyncEvent.STATUS_CREATED,
        ):
            event = PreparationSyncEvent.objects.create(
                permanence=self.permanence, purchase=self.purchase,
                operation="receive", client_timestamp=timezone.now(), status=status,
            )
            call_command("auto_validate_group_deliveries", days=0, stderr=StringIO(), stdout=StringIO())
            self.purchase.refresh_from_db()
            self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
            event.delete()

    def test_invoiced_permanence_is_never_tacitly_validated(self):
        self._group_handover()
        self.permanence.status = SaleStatus.INVOICED
        self.permanence.save(update_fields=["status"])
        call_command("auto_validate_group_deliveries", days=0, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)

    def test_equal_actual_quantities_do_not_hide_difference_from_order(self):
        self._group_handover(quantity="1")
        Purchase.objects.filter(pk=self.purchase.pk).update(quantity_ordered=Decimal("2"))
        errors = StringIO()
        call_command("auto_validate_group_deliveries", days=0, dry_run=True, stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertIn("quantity discrepancy", errors.getvalue())
        call_command("auto_validate_group_deliveries", days=0, stderr=StringIO(), stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)

    def test_parcel_disposition_blocks_automatic_validation(self):
        self._group_handover()
        for disposition in ("not_in_bl", "lost_in_transit"):
            event = PreparationSyncEvent.objects.create(
                permanence=self.permanence, purchase=self.purchase,
                operation="parcel_disposition", client_timestamp=timezone.now(),
                status=PreparationSyncEvent.STATUS_APPLIED,
                payload={"disposition": disposition},
            )
            errors = StringIO()
            call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
            self.purchase.refresh_from_db()
            self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
            self.assertIn("parcel discrepancy", errors.getvalue())
            event.delete()

    def test_discrepancy_keeps_entire_group_delivery_pending(self):
        self._group_handover()
        second_user = User.objects.create_user(username="second-group-member")
        second_customer = Customer.objects.create(
            user=second_user, short_basket_name="Second group member",
        )
        second_invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=second_customer,
            customer_charged=self.customer_invoice.customer_charged,
            delivery=self.customer_invoice.delivery, status=SaleStatus.SEND,
        )
        second = Purchase(
            permanence=self.permanence, offer_item=self.offer_item, producer=self.producer,
            customer=second_customer, customer_invoice=second_invoice,
            quantity_ordered=1, quantity_invoiced=1, quantity_prepared=1,
            quantity_received=0, preparation_status=PreparationStatus.HANDED_TO_GROUP,
        )
        Purchase.objects.bulk_create([second])
        for operation, payload in (("receive", {"quantity": "0"}), ("hand_to_group", {})):
            PreparationSyncEvent.objects.create(
                permanence=self.permanence, purchase=second, operation=operation,
                client_timestamp=timezone.now(), status=PreparationSyncEvent.STATUS_APPLIED,
                payload=payload,
            )
        errors = StringIO()
        call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertEqual(second.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertIn("quantity discrepancy", errors.getvalue())
        Purchase.objects.filter(pk=second.pk).update(
            quantity_received=1, preparation_status=PreparationStatus.VALIDATED,
        )
        errors = StringIO()
        call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertIn("quantity discrepancy recorded", errors.getvalue())

    def test_recorded_quantity_discrepancy_and_missing_payload_block(self):
        self._group_handover()
        event = PreparationSyncEvent.objects.get(purchase=self.purchase, operation="receive")
        for payload, reason in (({"quantity": "0"}, "quantity discrepancy"), ({}, "ambiguous quantity")):
            event.payload = payload
            event.save(update_fields=["payload"])
            errors = StringIO()
            call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
            self.purchase.refresh_from_db()
            self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
            self.assertIn(reason, errors.getvalue())

    def test_default_delay_requires_both_old_permanence_and_old_handover(self):
        self._group_handover()
        self.permanence.permanence_date = timezone.localdate() - datetime.timedelta(days=3)
        self.permanence.save(update_fields=["permanence_date"])
        errors = StringIO()
        call_command("auto_validate_group_deliveries", stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertIn("handover delay not elapsed", errors.getvalue())
        handoff = PreparationSyncEvent.objects.get(purchase=self.purchase, operation="hand_to_group")
        received = PreparationSyncEvent.objects.get(purchase=self.purchase, operation="receive")
        old = timezone.now() - datetime.timedelta(days=3)
        PreparationSyncEvent.objects.filter(pk=received.pk).update(server_timestamp=old)
        PreparationSyncEvent.objects.filter(pk=handoff.pk).update(
            server_timestamp=old + datetime.timedelta(seconds=1)
        )
        call_command("auto_validate_group_deliveries", stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.VALIDATED)

    def test_missing_handover_or_receipt_is_reported_as_ambiguous(self):
        self._group_handover()
        PreparationSyncEvent.objects.filter(
            purchase=self.purchase, operation="receive"
        ).delete()
        errors = StringIO()
        call_command("auto_validate_group_deliveries", days=0, stderr=errors, stdout=StringIO())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.preparation_status, PreparationStatus.HANDED_TO_GROUP)
        self.assertIn("ambiguous handover or receipt", errors.getvalue())

    def test_expired_or_tampered_token_is_rejected(self):
        token = make_preparation_token(self.permanence.id)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        self.assertIsNone(resolve_preparation_token(tampered))
        self.assertIsNone(resolve_preparation_token(token, max_age=-1))

    def test_closed_permanence_rejects_token(self):
        token = make_preparation_token(self.permanence.id)
        self.permanence.status = SaleStatus.PLANNED
        self.permanence.save(update_fields=["status"])
        self.assertIsNone(resolve_preparation_token(token))

    def test_sync_apply_is_idempotent_by_uuid(self):
        event_uuid = str(uuid.uuid4())
        payload = {
            "uuid": event_uuid,
            "client_timestamp": timezone.now().isoformat(),
            "operation": "prepare",
            "purchase_id": self.purchase.id,
            "quantity": "3.0000",
        }
        first = apply_preparation_sync(self.permanence, payload)
        second = apply_preparation_sync(self.permanence, payload)

        self.assertEqual(first["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.assertTrue(second["idempotent"])
        self.purchase.refresh_from_db()
        self.assertEqual(str(self.purchase.quantity_prepared), "3.0000")
        self.assertEqual(
            self.purchase.preparation_status,
            PreparationStatus.PREPARED,
        )

    def test_obsolete_event_is_conflict(self):
        now = timezone.now()
        newer = {
            "uuid": str(uuid.uuid4()),
            "client_timestamp": now.isoformat(),
            "operation": "receive",
            "purchase_id": self.purchase.id,
            "quantity": "2.0000",
        }
        apply_preparation_sync(self.permanence, newer)

        older = {
            "uuid": str(uuid.uuid4()),
            "client_timestamp": (now - datetime.timedelta(minutes=5)).isoformat(),
            "operation": "prepare",
            "purchase_id": self.purchase.id,
            "quantity": "1.0000",
        }
        result = apply_preparation_sync(self.permanence, older)
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_CONFLICT)

    def test_snapshot_exposes_three_preparation_regimes(self):
        self.producer.invoice_by_basket = True
        self.producer.save(update_fields=["invoice_by_basket"])
        basket_snapshot = self.client.get(
            "/fr/repanier/permanence/{}/snapshot/".format(
                make_preparation_token(self.permanence.id)
            ),
            follow=True,
        )
        self.assertEqual(basket_snapshot.status_code, 200)
        basket_row = basket_snapshot.json()["purchases"][0]
        self.assertEqual(basket_row["regime"], "basket")

        self.producer.invoice_by_basket = False
        self.producer.save(update_fields=["invoice_by_basket"])
        self.offer_item.wrapped = True
        self.offer_item.save(update_fields=["wrapped"])
        wrapped_snapshot = self.client.get(
            "/fr/repanier/permanence/{}/snapshot/".format(
                make_preparation_token(self.permanence.id)
            ),
            follow=True,
        )
        wrapped_row = wrapped_snapshot.json()["purchases"][0]
        self.assertEqual(wrapped_row["regime"], "wrapped")

        self.offer_item.wrapped = False
        self.offer_item.save(update_fields=["wrapped"])
        standard_snapshot = self.client.get(
            "/fr/repanier/permanence/{}/snapshot/".format(
                make_preparation_token(self.permanence.id)
            ),
            follow=True,
        )
        standard_row = standard_snapshot.json()["purchases"][0]
        self.assertEqual(standard_row["regime"], "standard")

    def test_substitution_zeros_source_without_changing_quantity_ordered_or_invoiced(self):
        target_product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Substitution target",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("3.00"),
            customer_unit_price=Decimal("3.50"),
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
        )
        target_offer_item = OfferItem.objects.create(
            permanence=self.permanence,
            product=target_product,
            producer=self.producer,
            long_name_v2=target_product.long_name_v2,
            order_unit=target_product.order_unit,
            producer_unit_price=target_product.producer_unit_price,
            customer_unit_price=target_product.customer_unit_price,
            unit_deposit=target_product.unit_deposit,
        )

        old_ordered = self.purchase.quantity_ordered
        old_invoiced = self.purchase.quantity_invoiced
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "substitute",
                "purchase_id": self.purchase.id,
                "target_offer_item_id": target_offer_item.id,
                "quantity": "1.0000",
            },
        )

        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.purchase.refresh_from_db()
        target = Purchase.objects.get(id=result["target_purchase_id"])
        self.assertEqual(self.purchase.quantity_prepared, Decimal("0"))
        self.assertEqual(self.purchase.quantity_received, Decimal("0"))
        self.assertEqual(self.purchase.quantity_ordered, old_ordered)
        self.assertEqual(self.purchase.quantity_invoiced, old_invoiced)
        self.assertEqual(target.origin, PreparationOrigin.SUBSTITUTION)
        self.assertEqual(target.substitution_source_id, self.purchase.id)

    def test_express_request_has_zero_ordered_quantity(self):
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "express_request",
                "offer_item_id": self.offer_item.id,
                "customer_id": self.customer.id,
                "quantity": "2.0000",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_CONFLICT)
        self.assertEqual(result["reason"], "express_purchase_already_exists")

        new_offer_item = OfferItem.objects.create(
            permanence=self.permanence,
            product=Product.objects.create(
                producer=self.producer,
                long_name_v2="Express target",
                order_unit=OrderUnit.PC,
                producer_unit_price=Decimal("2.00"),
                customer_unit_price=Decimal("2.50"),
                vat_level=Vat.VAT_100,
                stock=Decimal("99"),
            ),
            producer=self.producer,
            long_name_v2="Express target",
            order_unit=OrderUnit.PC,
            producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
        )
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "express_request",
                "offer_item_id": new_offer_item.id,
                "customer_id": self.customer.id,
                "quantity": "2.0000",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_APPLIED)
        express = Purchase.objects.get(id=result["purchase_id"])
        self.assertEqual(express.quantity_ordered, Decimal("0"))
        self.assertEqual(express.origin, PreparationOrigin.EXPRESS_REQUEST)

    def test_deposit_receipt_calculates_credit_and_respects_disabled_flag(self):
        container = DepositContainerType.objects.create(
            code="CRATE",
            label="Crate",
            unit_credit=Decimal("1.25"),
        )
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
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

        from django.test.utils import override_settings
        from repanier import apps

        previous = apps.REPANIER_SETTINGS_USE_DEPOSITS
        apps.REPANIER_SETTINGS_USE_DEPOSITS = False
        try:
            disabled = apply_preparation_sync(
                self.permanence,
                {
                    "uuid": str(uuid.uuid4()),
                    "client_timestamp": timezone.now().isoformat(),
                    "operation": "deposit_receipt",
                    "container_type_id": container.id,
                    "customer_id": self.customer.id,
                    "returned_count": 1,
                    "missing_count": 0,
                },
            )
            self.assertEqual(
                disabled["status"],
                PreparationSyncEvent.STATUS_REJECTED,
            )
            self.assertEqual(disabled["reason"], "deposits_disabled")
        finally:
            apps.REPANIER_SETTINGS_USE_DEPOSITS = previous

    def test_invalid_quantity_returns_rejected(self):
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "prepare",
                "purchase_id": self.purchase.id,
                "quantity": "not-a-decimal",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "invalid_quantity")

    def test_mutations_are_rejected_once_the_permanence_left_the_closing_state(self):
        Status = SaleStatus

        container = DepositContainerType.objects.create(
            code="POSTINV", label="Post invoicing", unit_credit=Decimal("1.25"),
        )
        target_offer_item = OfferItem.objects.create(
            permanence=self.permanence,
            product=Product.objects.create(
                producer=self.producer, long_name_v2="Post-invoicing target",
                order_unit=OrderUnit.PC, producer_unit_price=Decimal("2.00"),
                customer_unit_price=Decimal("2.50"), vat_level=Vat.VAT_100,
                stock=Decimal("99"),
            ),
            producer=self.producer, long_name_v2="Post-invoicing target",
            order_unit=OrderUnit.PC, producer_unit_price=Decimal("2.00"),
            customer_unit_price=Decimal("2.50"),
        )
        payloads = {
            "substitute": {
                "purchase_id": self.purchase.id,
                "target_offer_item_id": target_offer_item.id,
                "quantity": "1.0000",
            },
            "express_request": {
                "offer_item_id": target_offer_item.id,
                "customer_id": self.customer.id,
                "quantity": "2.0000",
            },
            "deposit_receipt": {
                "container_type_id": container.id,
                "customer_id": self.customer.id,
                "returned_count": 3,
                "missing_count": 1,
            },
            "prepare": {"purchase_id": self.purchase.id, "quantity": "1.0000"},
            "validate": {"purchase_id": self.purchase.id},
        }
        for status in (Status.WAIT_FOR_INVOICED, Status.INVOICED):
            Permanence.objects.filter(pk=self.permanence.pk).update(status=status)
            self.permanence.refresh_from_db()
            purchases_before = Purchase.objects.count()
            for operation, extra in payloads.items():
                result = apply_preparation_sync(
                    self.permanence,
                    {
                        "uuid": str(uuid.uuid4()),
                        "client_timestamp": timezone.now().isoformat(),
                        "operation": operation,
                        **extra,
                    },
                )
                self.assertEqual(
                    result["status"], PreparationSyncEvent.STATUS_REJECTED,
                    (status, operation),
                )
                self.assertEqual(result["reason"], "permanence_closed")
            self.assertEqual(Purchase.objects.count(), purchases_before)
            self.assertFalse(DepositReceipt.objects.exists())
            self.purchase.refresh_from_db()
            self.assertEqual(self.purchase.preparation_status, PreparationStatus.ORDERED)

    def test_invalid_deposit_counts_are_rejected(self):
        container = DepositContainerType.objects.create(
            code="INVALID",
            label="Invalid",
            unit_credit=Decimal("1.25"),
        )
        result = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "deposit_receipt",
                "container_type_id": container.id,
                "customer_id": self.customer.id,
                "returned_count": "not-an-integer",
                "missing_count": 0,
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "invalid_deposit_count")

    def test_demo_rejects_accounting_operations(self):
        demo = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
            is_demo=True,
        )
        result = apply_preparation_sync(
            demo,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "express_request",
                "offer_item_id": self.offer_item.id,
                "customer_id": self.customer.id,
                "quantity": "1",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "demo_not_allowed")

    def test_demo_sync_does_not_link_real_accounting(self):
        demo = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
            is_demo=True,
        )
        result = apply_preparation_sync(
            demo,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "prepare",
                "purchase_id": self.purchase.id,
                "quantity": "1.0000",
            },
        )
        self.assertEqual(result["status"], PreparationSyncEvent.STATUS_REJECTED)
        self.assertEqual(result["reason"], "purchase_not_in_permanence")

    def test_four_preparation_states_are_isolated_from_sale_status(self):
        prepared = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": timezone.now().isoformat(),
                "operation": "prepare",
                "purchase_id": self.purchase.id,
                "quantity": "1.0000",
            },
        )
        handed = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": (timezone.now() + datetime.timedelta(seconds=1)).isoformat(),
                "operation": "hand_to_group",
                "purchase_id": self.purchase.id,
            },
        )
        validated = apply_preparation_sync(
            self.permanence,
            {
                "uuid": str(uuid.uuid4()),
                "client_timestamp": (timezone.now() + datetime.timedelta(seconds=2)).isoformat(),
                "operation": "validate",
                "purchase_id": self.purchase.id,
                "quantity": "1.0000",
            },
        )

        self.purchase.refresh_from_db()
        self.permanence.refresh_from_db()
        self.assertEqual(prepared["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.assertEqual(handed["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.assertEqual(validated["status"], PreparationSyncEvent.STATUS_APPLIED)
        self.assertEqual(
            self.purchase.preparation_status,
            PreparationStatus.VALIDATED,
        )
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
        self.assertEqual(str(self.purchase.quantity_invoiced), "1.0000")

    def test_offline_js_serializes_operation_specific_payload_fields(self):
        js_path = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "repanier"
            / "js"
            / "preparation-offline.js"
        )
        source = js_path.read_text(encoding="utf-8")
        for field in (
            "target_offer_item_id",
            "offer_item_id",
            "customer_id",
            "container_type_id",
            "returned_count",
            "missing_count",
            "disposition",
        ):
            self.assertIn(field, source)
        self.assertIn("function buildSyncPayload", source)
        self.assertIn("response.text()", source)
        self.assertIn("JSON.parse(text)", source)
        self.assertIn("saveConflict(event, eventResult)", source)
        self.assertIn("readLatestSnapshot()", source)
        self.assertIn("readConflicts()", source)
        self.assertIn("optionalFields", source)
        self.assertIn("payload[field]", source)
        self.assertIn("readLatestSnapshot()", source)
        self.assertIn("data-retry-conflict", source)
        self.assertIn("data-dismiss-conflict", source)
        self.assertIn("preparation-basket", source)
        self.assertIn("lost_in_transit", source)
        self.assertIn("not_in_bl", source)
        self.assertIn("wrapped-quantity", source)
        self.assertIn("purchase_ids", source)
        self.assertIn("readLatestSnapshot()", source)
        self.assertIn("cachedSnapshot", source)
        self.assertIn("producerFilter", source)
