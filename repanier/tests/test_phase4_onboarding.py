import datetime

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from repanier.accounting_policy import AccountingPolicy
from repanier.const import AccountingMode, SaleStatus
from repanier.models.configuration import Configuration
from repanier.models.permanence import Permanence
from repanier.models.preparation import PermanencePreparationAccess
from repanier.preparation_sync import (
    make_preparation_token,
    resolve_preparation_token,
    revoke_preparation_access,
)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class Phase4OnboardingTest(TestCase):
    def setUp(self):
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.SEND,
            preparation_enabled=True,
        )

    def test_simple_orders_rejects_invoice_by_basket(self):
        configuration = Configuration(
            accounting_mode=AccountingMode.SIMPLE_ORDERS,
            use_invoice_by_basket=True,
        )
        with self.assertRaises(Exception):
            configuration.clean()

    def test_simple_orders_rejects_mobile_preparation(self):
        configuration = Configuration(
            accounting_mode=AccountingMode.SIMPLE_ORDERS,
            use_mobile_preparation=True,
        )
        with self.assertRaises(Exception):
            configuration.clean()

    def test_token_generation_resolution_and_revocation(self):
        token = make_preparation_token(self.permanence.id)
        resolved = resolve_preparation_token(token)

        self.assertEqual(resolved.id, self.permanence.id)
        access = PermanencePreparationAccess.objects.get(
            permanence=self.permanence,
        )
        self.assertTrue(access.is_valid())

        revoke_preparation_access(self.permanence.id)
        access.refresh_from_db()
        self.assertFalse(access.is_valid())
        self.assertIsNone(resolve_preparation_token(token))

    def test_demo_permanence_never_gets_real_mobile_token(self):
        self.permanence.is_demo = True
        self.permanence.save(update_fields=["is_demo"])

        access_count = PermanencePreparationAccess.objects.filter(
            permanence=self.permanence,
        ).count()
        self.assertEqual(access_count, 0)
