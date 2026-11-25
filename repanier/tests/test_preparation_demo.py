import datetime

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from repanier import apps
from repanier.const import SaleStatus
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.preparation import DepositContainerType
from repanier.models.purchase import Purchase
from repanier.preparation_demo import create_demo_preparation, reset_demo_preparation
from repanier.xlsx.xlsx_invoice_bank import export_bank


@override_settings(
    REPANIER_SETTINGS_MANAGE_ACCOUNTING=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class MobilePreparationDemoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="demo-admin",
            email="demo-admin@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)
        previous = apps.REPANIER_SETTINGS_USE_MOBILE_PREPARATION
        apps.REPANIER_SETTINGS_USE_MOBILE_PREPARATION = True
        self.addCleanup(
            setattr,
            apps,
            "REPANIER_SETTINGS_USE_MOBILE_PREPARATION",
            previous,
        )

    def test_create_demo_has_three_products_one_group_and_one_deposit(self):
        result = create_demo_preparation()
        permanence = result["permanence"]

        self.assertTrue(permanence.is_demo)
        self.assertTrue(permanence.preparation_enabled)
        self.assertEqual(
            OfferItem.objects.filter(permanence=permanence).count(),
            3,
        )
        self.assertEqual(
            Purchase.objects.filter(permanence=permanence).count(),
            3,
        )
        self.assertEqual(result["group"].short_basket_name, "Group test")
        self.assertTrue(result["group"].is_group)
        self.assertEqual(
            DepositContainerType.objects.filter(code="DEMO-CONTAINER").count(),
            1,
        )

    def test_demo_snapshot_does_not_expose_real_reference_customers(self):
        real_user = User.objects.create_user(username="real-snapshot-member")
        real_customer = Customer.objects.create(
            user=real_user, short_basket_name="Real snapshot member",
        )
        real_container = DepositContainerType.objects.create(
            code="REAL", label="Real container", unit_credit=1,
        )
        result = create_demo_preparation()
        response = self.client.get(reverse(
            "repanier:preparation_snapshot", args=[result["token"]]
        ))
        self.assertEqual(response.status_code, 200)
        snapshot = response.json()
        self.assertNotIn(real_customer.pk, [customer["id"] for customer in snapshot["customers"]])
        self.assertEqual([c["id"] for c in snapshot["customers"]], [result["group"].pk])
        self.assertNotIn(real_container.pk, [c["id"] for c in snapshot["deposit_types"]])

    def test_demo_purchases_never_create_real_accounting_books(self):
        result = create_demo_preparation()
        permanence = result["permanence"]

        purchases = Purchase.objects.filter(permanence=permanence)
        self.assertEqual(purchases.count(), 3)
        self.assertFalse(
            purchases.exclude(customer_invoice=None).exists()
        )
        self.assertFalse(
            purchases.exclude(producer_invoice=None).exists()
        )
        self.assertFalse(
            purchases.exclude(customer_producer_invoice=None).exists()
        )
        self.assertFalse(CustomerInvoice.objects.filter(permanence=permanence).exists())
        self.assertFalse(ProducerInvoice.objects.filter(permanence=permanence).exists())
        self.assertFalse(
            CustomerProducerInvoice.objects.filter(permanence=permanence).exists()
        )

    def test_reset_restores_initial_demo_state_only(self):
        result = create_demo_preparation()
        permanence = result["permanence"]
        Purchase.objects.filter(permanence=permanence).update(quantity_prepared=1)

        reset_permanence = reset_demo_preparation(permanence.id)

        self.assertIsNotNone(reset_permanence)
        self.assertEqual(
            Purchase.objects.filter(permanence=permanence).count(),
            3,
        )
        self.assertFalse(
            Purchase.objects.filter(
                permanence=permanence,
                quantity_prepared__gt=0,
            ).exists()
        )
        self.assertFalse(
            Permanence.objects.filter(is_demo=False, id=permanence.id).exists()
        )

    def test_export_is_explicitly_test_data_and_rejects_real_permanence(self):
        result = create_demo_preparation()
        demo = result["permanence"]
        url = "/fr/repanier/demo/mobile-preparation/{}/export/".format(demo.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("TEST-data", response["Content-Disposition"])
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        real = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            is_demo=False,
        )
        real_url = "/fr/repanier/demo/mobile-preparation/{}/export/".format(real.id)
        self.assertEqual(self.client.get(real_url).status_code, 404)

    def test_demo_actions_require_permission_and_replay_reset_demonstration(self):
        normal_user = User.objects.create_user(
            username="normal",
            email="normal@example.com",
            password="test-password",
        )
        self.client.force_login(normal_user)

        self.assertEqual(
            self.client.get(
                "/fr/repanier/demo/mobile-preparation/create/"
            ).status_code,
            405,
        )

        self.client.force_login(self.user)
        create_response = self.client.post(
            "/fr/repanier/demo/mobile-preparation/create/"
        )
        self.assertEqual(create_response.status_code, 200)
        permanence_id = create_response.json()["permanence_id"]

        replay_url = "/fr/repanier/demo/mobile-preparation/{}/replay/".format(permanence_id)
        reset_url = "/fr/repanier/demo/mobile-preparation/{}/reset/".format(permanence_id)
        self.assertEqual(self.client.post(replay_url).status_code, 200)
        self.assertEqual(self.client.post(reset_url).status_code, 200)

    def test_demo_bank_export_and_closure_are_blocked(self):
        from repanier.accounting_closing import ClosingBalance

        result = create_demo_preparation()
        demo = result["permanence"]

        self.assertIsNone(export_bank(demo))
        closing = ClosingBalance(demo)
        closing.check()
        self.assertFalse(closing.is_valid)
        self.assertEqual(closing.blocking[0]["code"], "DEMO")
