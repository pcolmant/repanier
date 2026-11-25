import datetime
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.distribution import DistributionEvent, Offer, PickupSlot
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.models.product_alias import ProductAlias, suggest_product_alias, suggest_product_aliases


class DistributionPickupTest(TestCase):
    def setUp(self):
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
        )
        self.producer = Producer.objects.create(
            short_profile_name="Distribution producer",
        )
        self.offer = Offer.objects.create(
            producer=self.producer,
            title="Distribution offer",
        )
        self.distribution = DistributionEvent.objects.create(
            permanence=self.permanence,
            offer=self.offer,
            distribution_date=self.permanence.permanence_date,
        )
        self.slot = PickupSlot.objects.create(
            distribution_event=self.distribution,
            location="Main hall",
            starts_at=timezone.now(),
            ends_at=timezone.now(),
        )

    def test_distribution_models_and_pickup_slot_are_linked(self):
        self.assertEqual(
            self.distribution.permanence_id,
            self.permanence.id,
        )
        self.assertEqual(self.slot.distribution_event_id, self.distribution.id)

    def test_distribution_models_are_registered_in_admin(self):
        from django.contrib import admin

        for model in (Offer, DistributionEvent, PickupSlot, ProductAlias):
            self.assertTrue(admin.site.is_registered(model), model.__name__)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_uncertain_arrival_is_visible_but_does_not_block_pickup(self):
        from repanier.preparation_sync import make_preparation_token

        self.offer.is_uncertain_arrival = True
        self.offer.save(update_fields=["is_uncertain_arrival"])
        self.assertTrue(self.distribution.has_uncertain_arrival)
        token = make_preparation_token(self.permanence.id)
        snapshot = self.client.get(reverse("repanier:preparation_snapshot", args=[token]))
        self.assertEqual(snapshot.status_code, 200)
        self.assertTrue(snapshot.json()["uncertain_arrival"])
        page = self.client.get(reverse("repanier:preparation_page", args=[token]))
        self.assertContains(page, 'data-uncertain-arrival')

        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        user = User.objects.create_user(username="uncertain-pickup")
        customer = Customer.objects.create(user=user, short_basket_name="Uncertain pickup")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED,
        )
        self.client.force_login(user)
        response = self.client.post(reverse("repanier:select_pickup_slot"), {
            "permanence": self.permanence.id, "pickup_slot": self.slot.id,
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, self.slot.id)
        fragment = invoice.get_html_my_order_confirmation(
            permanence=self.permanence, is_basket=True
        )["#span_btn_confirm_order"]
        self.assertIn("uncertain", str(fragment).lower())

    def test_customer_invoice_pickup_slot_is_permanence_scoped(self):
        user = User.objects.create_user(
            username="pickup-member",
            email="pickup@example.com",
            password="test-password",
        )
        customer = Customer.objects.create(
            user=user,
            short_basket_name="Pickup member",
        )
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence,
            customer=customer,
            customer_charged=customer,
            status=SaleStatus.SEND,
        )
        invoice.set_pickup_slot(self.slot)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, self.slot.id)

    def test_auto_validate_dry_run_does_not_change_status(self):
        out = StringIO()
        call_command(
            "auto_validate_group_deliveries",
            days=0,
            dry_run=True,
            stdout=out,
        )
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
        self.assertIn("candidate", out.getvalue())

    def test_product_alias_is_manual_and_linked(self):
        product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Canonical product",
        )
        alias = ProductAlias.objects.create(
            canonical_product=product,
            alias_label="Producer spelling",
            confidence="92.50",
            manually_validated=True,
        )
        suggestions = suggest_product_alias(
            "producer speling",
            [alias],
            threshold=50,
        )
        self.assertTrue(alias.manually_validated)
        self.assertEqual(alias.canonical_product_id, product.id)
        self.assertEqual(suggestions[0]["alias"].id, alias.id)

    def test_benchmark_command_runs_without_members(self):
        out = StringIO()
        call_command(
            "compute_producer_benchmarks",
            stdout=out,
        )
        self.assertIn("active members", out.getvalue())
        self.assertIn("Benchmarks unavailable", out.getvalue())

    def test_auto_validation_rejects_negative_delay(self):
        with self.assertRaisesMessage(CommandError, "non-negative"):
            call_command("auto_validate_group_deliveries", days=-1)

    def test_alias_batch_does_not_change_manual_validation(self):
        product = Product.objects.create(producer=self.producer, long_name_v2="Apple")
        alias = ProductAlias.objects.create(
            canonical_product=product, alias_label="Apple", confidence="95.00",
            manually_validated=True,
        )
        matches = suggest_product_aliases(["apple", "unknown"], [alias], threshold=80)
        self.assertEqual(matches["apple"][0]["alias"], alias)
        self.assertEqual(matches["unknown"], [])
        alias.refresh_from_db()
        self.assertTrue(alias.manually_validated)
        self.assertEqual(str(alias.confidence), "95.00")

    def test_alias_command_is_read_only_and_filters_producer(self):
        product = Product.objects.create(producer=self.producer, long_name_v2="Apple")
        alias = ProductAlias.objects.create(
            canonical_product=product, alias_label="Apple", confidence="95.00",
            manually_validated=True,
        )
        other = Producer.objects.create(short_profile_name="Other alias producer")
        other_product = Product.objects.create(producer=other, long_name_v2="Other apple")
        ProductAlias.objects.create(canonical_product=other_product, alias_label="Apple")
        out = StringIO()
        call_command(
            "suggest_product_aliases", "apple", "unknown", threshold=80,
            producer=self.producer.pk, stdout=out,
        )
        results = json.loads(out.getvalue())
        self.assertEqual(len(results[0]["matches"]), 1)
        self.assertEqual(results[0]["matches"][0]["alias_id"], alias.pk)
        self.assertTrue(results[0]["matches"][0]["manually_validated"])
        self.assertEqual(results[1]["matches"], [])
        alias.refresh_from_db()
        self.assertTrue(alias.manually_validated)
        self.assertEqual(str(alias.confidence), "95.00")
        with self.assertRaises(CommandError):
            call_command("suggest_product_aliases", "apple", threshold=101)

    def test_benchmarks_normalize_per_sale_and_exclude_demo(self):
        from repanier.management.commands.compute_producer_benchmarks import compute_benchmarks

        customers = [
            Customer.objects.create(
                user=User.objects.create_user(username=f"bench-{i}"),
                short_basket_name=f"Bench {i}",
            )
            for i in range(2)
        ]
        product = Product.objects.create(producer=self.producer, long_name_v2="Bench product")
        for quantity, demo in [(4, False), (8, False), (100, True)]:
            permanence = Permanence.objects.create(
                permanence_date=datetime.date.today(), status=SaleStatus.SEND, is_demo=demo
            )
            item = OfferItem.objects.create(
                permanence=permanence, product=product, producer=self.producer,
                long_name_v2="Bench product",
            )
            Purchase.objects.bulk_create([
                Purchase(
                    permanence=permanence, offer_item=item, producer=self.producer,
                    customer=customers[0], quantity_invoiced=quantity,
                )
            ])
        members, results = compute_benchmarks()
        self.assertEqual(members, 2)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["sales"], 2)
        self.assertEqual(results[0]["min"], Decimal("2"))
        self.assertEqual(results[0]["max"], Decimal("4"))
        self.assertEqual(results[0]["average"], Decimal("3"))

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_pickup_slot_post_is_scoped_to_invoice_permanence(self):
        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        user = User.objects.create_user(username="slot-post")
        customer = Customer.objects.create(user=user, short_basket_name="Slot post")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED,
        )
        self.client.force_login(user)
        url = reverse("repanier:select_pickup_slot")
        response = self.client.post(url, {
            "permanence": self.permanence.id, "pickup_slot": self.slot.id,
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, self.slot.id)
        other = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        event = DistributionEvent.objects.create(
            permanence=other, distribution_date=other.permanence_date
        )
        foreign_slot = PickupSlot.objects.create(
            distribution_event=event, location="Other", starts_at=timezone.now(),
            ends_at=timezone.now(),
        )
        response = self.client.post(url, {
            "permanence": self.permanence.id, "pickup_slot": foreign_slot.id,
        })
        self.assertEqual(response.status_code, 404)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, self.slot.id)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        response = csrf_client.post(url, {
            "permanence": self.permanence.id, "pickup_slot": self.slot.id,
        })
        self.assertEqual(response.status_code, 403)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_order_initialization_assigns_single_slot_and_renders_it(self):
        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        user = User.objects.create_user(username="slot-init")
        customer = Customer.objects.create(user=user, short_basket_name="Slot init")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("repanier:order_init_ajax"), {
            "pe": self.permanence.id, "ba": "true",
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, self.slot.id)
        self.assertIn('id="pickup_slot"', response.json()["#span_btn_confirm_order"])

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_order_initialization_does_not_choose_between_multiple_slots(self):
        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        PickupSlot.objects.create(
            distribution_event=self.distribution, location="Second",
            starts_at=timezone.now(), ends_at=timezone.now(),
        )
        user = User.objects.create_user(username="multiple-slots")
        customer = Customer.objects.create(user=user, short_basket_name="Multiple slots")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("repanier:order_init_ajax"), {
            "pe": self.permanence.id, "ba": "true",
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.pickup_slot_id)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_change_pickup_slot_cancels_confirmation_and_rejects_closed_order(self):
        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        second = PickupSlot.objects.create(
            distribution_event=self.distribution, location="Second",
            starts_at=timezone.now(), ends_at=timezone.now(),
        )
        user = User.objects.create_user(username="change-slot")
        customer = Customer.objects.create(user=user, short_basket_name="Change slot")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED, pickup_slot=self.slot, is_order_confirm_send=True,
        )
        self.client.force_login(user)
        url = reverse("repanier:select_pickup_slot")
        response = self.client.post(url, {
            "permanence": self.permanence.pk, "pickup_slot": second.pk,
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, second.pk)
        self.assertFalse(invoice.is_order_confirm_send)
        self.permanence.status = SaleStatus.SEND
        self.permanence.save(update_fields=["status"])
        response = self.client.post(url, {
            "permanence": self.permanence.pk, "pickup_slot": self.slot.pk,
        })
        self.assertEqual(response.status_code, 404)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pickup_slot_id, second.pk)

    def test_uncertainty_is_scoped_to_its_distribution(self):
        self.offer.is_uncertain_arrival = True
        self.offer.save(update_fields=["is_uncertain_arrival"])
        other = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.SEND,
        )
        event = DistributionEvent.objects.create(
            permanence=other, distribution_date=other.permanence_date,
        )
        self.assertTrue(self.distribution.has_uncertain_arrival)
        self.assertFalse(event.has_uncertain_arrival)
        self.assertFalse(DistributionEvent.objects.filter(
            permanence=other, offer__is_uncertain_arrival=True
        ).exists())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_invoiced_order_does_not_assign_or_change_pickup_slot(self):
        self.permanence.status = SaleStatus.INVOICED
        self.permanence.save(update_fields=["status"])
        user = User.objects.create_user(username="invoiced-pickup")
        customer = Customer.objects.create(user=user, short_basket_name="Invoiced pickup")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.INVOICED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("repanier:order_init_ajax"), {
            "pe": self.permanence.id, "ba": "true",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="pickup_slot"', response.json()["#span_btn_confirm_order"])
        response = self.client.post(reverse("repanier:select_pickup_slot"), {
            "permanence": self.permanence.pk, "pickup_slot": self.slot.pk,
        })
        self.assertEqual(response.status_code, 404)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.pickup_slot_id)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_selecting_same_slot_does_not_cancel_confirmation(self):
        self.permanence.status = SaleStatus.OPENED
        self.permanence.save(update_fields=["status"])
        user = User.objects.create_user(username="same-pickup")
        customer = Customer.objects.create(user=user, short_basket_name="Same pickup")
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence, customer=customer, customer_charged=customer,
            status=SaleStatus.OPENED, pickup_slot=self.slot, is_order_confirm_send=True,
        )
        self.client.force_login(user)
        response = self.client.post(reverse("repanier:select_pickup_slot"), {
            "permanence": self.permanence.pk, "pickup_slot": self.slot.pk,
        })
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertTrue(invoice.is_order_confirm_send)
