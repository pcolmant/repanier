"""Tests of the membership fee renewal date over the cancel flows.

close_order() forces the membership fee onto outdated members and extends
their renewal date. Global rule, applied by these tests: whatever cancels
the delivery or the invoices restores the previous renewal date, and
whatever re-applies the invoices (restore_delivery, a re-invoicing)
re-extends it.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from repanier.const import BankMovement, OrderUnit, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal
OTHER_MEMBERSHIP_START = datetime.date(2010, 1, 1)


def utc_today():
    """The clock close_order() runs on: timezone.now().date(), always UTC.

    The membership assertions must run on this clock, never on
    datetime.date.today() (the OS local date): from 23:00 to 00:00 UTC the
    two clocks disagree for a Europe/Brussels-style timezone and the test
    becomes flaky.
    """
    return timezone.now().date()


class MembershipFeeCancelRestoreTest(TestCase):
    def build_home_run(self, valid_until):
        """A member buys one product, the group forces the fee at close."""
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The group charges a 10.00 membership fee valid 12 months
        Configuration.objects.update(
            membership_fee=D("10.00"), membership_fee_duration=D("12")
        )
        # Re-trigger the post_save signal so the settings are refreshed
        configuration = Configuration.objects.first()
        configuration.save()
        # The bank anchor required by Permanence.invoice()
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Account opening",
        )
        user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        customer = Customer.objects.create(
            user=user,
            short_basket_name="Client",
            may_order=True,
            membership_fee_valid_until=valid_until,
        )
        producer = Producer.objects.create(short_profile_name="Ferme")
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        permanence.producers.add(producer)
        product = Product.objects.create(
            producer=producer,
            long_name_v2="Produit",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        product.is_into_offer = True
        product.save()
        task_order.open_order(permanence.id, send_mail=False)
        offer_item = Product.objects.get(id=product.id).offeritem_set.get(
            permanence=permanence
        )
        CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id, customer_id=customer.id, status=SaleStatus.OPENED
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        self.assertTrue(updated)
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )
        permanence.refresh_from_db()
        return customer, producer, permanence

    # --------------------------------------------------------- the delivery

    def test_cancel_delivery_restores_the_previous_validity(self):
        customer, producer, permanence = self.build_home_run(
            OTHER_MEMBERSHIP_START
        )
        # The close forced the fee and extended the renewal date
        customer.refresh_from_db()
        self.assertGreaterEqual(customer.membership_fee_valid_until, utc_today())
        invoice = CustomerInvoice.objects.get(
            permanence_id=permanence.id, customer_id=customer.id
        )
        self.assertEqual(
            invoice.membership_fee_valid_until_save, OTHER_MEMBERSHIP_START
        )

        permanence.cancel_delivery()
        self.assertEqual(permanence.status, SaleStatus.CANCELLED)
        # A cancelled delivery never pays the fee: the renewal date the
        # member had before the close is restored
        customer.refresh_from_db()
        self.assertEqual(
            customer.membership_fee_valid_until, OTHER_MEMBERSHIP_START
        )

    def test_restore_delivery_reextends_the_validity(self):
        customer, producer, permanence = self.build_home_run(
            OTHER_MEMBERSHIP_START
        )
        permanence.cancel_delivery()
        permanence.restore_delivery()
        self.assertEqual(permanence.status, SaleStatus.SEND)
        # The cancellation of the cancellation re-applies the extension
        customer.refresh_from_db()
        self.assertGreaterEqual(customer.membership_fee_valid_until, utc_today())

    def test_cancel_delivery_does_not_touch_up_to_date_members(self):
        # An up to date member is never charged, so nothing is restored
        still_valid = utc_today() + datetime.timedelta(days=30)
        customer, producer, permanence = self.build_home_run(still_valid)
        self.assertFalse(
            CustomerInvoice.objects.filter(
                permanence_id=permanence.id,
                membership_fee_valid_until_save__isnull=False,
            ).exists()
        )
        permanence.cancel_delivery()
        customer.refresh_from_db()
        self.assertEqual(customer.membership_fee_valid_until, still_valid)

    # -------------------------------------------------------- the invoicing

    def invoice_the_permanence(self, producer, permanence):
        ProducerInvoice.objects.filter(
            permanence_id=permanence.id, producer_id=producer.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("2.50"))
        permanence.invoice(payment_date=datetime.date(2026, 12, 31))
        permanence.refresh_from_db()
        self.assertEqual(permanence.status, SaleStatus.INVOICED)

    def test_cancel_invoicing_restores_the_previous_validity(self):
        customer, producer, permanence = self.build_home_run(
            OTHER_MEMBERSHIP_START
        )
        self.invoice_the_permanence(producer, permanence)
        # The invoicing kept the extension computed at close time
        customer.refresh_from_db()
        self.assertGreaterEqual(customer.membership_fee_valid_until, utc_today())

        anchor = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL, permanence_id=permanence.id
        )
        permanence.cancel_invoice(anchor)
        permanence.refresh_from_db()
        # Cancelling the invoices unwinds the forced fee too
        customer.refresh_from_db()
        self.assertEqual(
            customer.membership_fee_valid_until, OTHER_MEMBERSHIP_START
        )

    def test_reinvoicing_reextends_the_validity(self):
        customer, producer, permanence = self.build_home_run(
            OTHER_MEMBERSHIP_START
        )
        self.invoice_the_permanence(producer, permanence)
        anchor = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL, permanence_id=permanence.id
        )
        permanence.cancel_invoice(anchor)
        # The treasurer fixes the mistake and invoices again
        self.invoice_the_permanence(producer, permanence)
        customer.refresh_from_db()
        self.assertGreaterEqual(customer.membership_fee_valid_until, utc_today())
        self.assertLessEqual(
            customer.membership_fee_valid_until,
            utc_today() + datetime.timedelta(days=367),
        )
