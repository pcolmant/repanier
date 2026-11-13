"""Tests of the "cancel this permanence" action of the preparation screen.

Groups create permanences by mistake and pollute the preparation screen
with empty shells. The red button deletes a scheduled permanence in one
action. A permanence whose orders were opened is not handled here:
getting rid of it passes through closing the orders - or going back to
scheduled - and cancelling the delivery from the payment screen, where
everything stays reversible.
"""
import datetime
from decimal import Decimal
from html import escape

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from django.contrib.admin import site as default_admin_site

from repanier.admin.permanence_in_preparation import (
    PermanenceInPreparationAdmin,
)
from repanier.admin.permanence_done import PermanenceDoneAdmin
from repanier.const import BankMovement, OrderUnit, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal
OTHER_MEMBERSHIP_START = datetime.date(2010, 1, 1)


def utc_today():
    """The clock close_order() runs on: timezone.now().date(), always UTC."""
    return timezone.now().date()


class CancelPreparedTest(TestCase):
    def build_permanence(self, with_order):
        """A member may have ordered before the group notices the mistake."""
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        # The group charges a 10.00 membership fee valid 12 months.
        # save() reloads the settings caches: close_order reads them
        # from there, not from the row alone.
        configuration = Configuration.objects.first()
        configuration.membership_fee = D("10.00")
        configuration.membership_fee_duration = D("12")
        configuration.save()
        user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Client",
            may_order=True,
            membership_fee_valid_until=OTHER_MEMBERSHIP_START,
        )
        self.producer = Producer.objects.create(short_profile_name="Ferme")
        self.permanence = Permanence.objects.create(
            permanence_date=utc_today(), status=SaleStatus.PLANNED
        )
        self.permanence.producers.add(self.producer)
        product = Product.objects.create(
            producer=self.producer,
            long_name_v2="Produit",
            order_unit=OrderUnit.PC,
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        product.is_into_offer = True
        product.save()
        if with_order:
            task_order.open_order(self.permanence.id, send_mail=False)
            offer_item = Product.objects.get(id=product.id).offeritem_set.get(
                permanence=self.permanence
            )
            CustomerInvoice.get_or_create_invoice(
                permanence_id=self.permanence.id,
                customer_id=self.customer.id,
                status=SaleStatus.OPENED,
            )
            purchase, updated = create_or_update_one_cart_item(
                customer=self.customer,
                offer_item_id=offer_item.id,
                q_order=D("1"),
                comment="",
            )
            self.assertTrue(updated)
            return purchase
        return None

    def test_a_scheduled_permanence_without_order_is_deleted_for_good(self):
        self.build_permanence(with_order=False)
        # Opening creates the offer items even without any order: they
        # leave with the shell
        task_order.open_order(self.permanence.id, send_mail=False)
        self.permanence.refresh_from_db()
        task_order.back_to_scheduled(self.permanence)
        self.assertTrue(
            OfferItem.objects.filter(permanence_id=self.permanence.id).exists()
        )
        self.permanence.cancel_prepared()
        # Nothing was ever ordered: no shell stays in any list
        self.assertFalse(Permanence.objects.filter(id=self.permanence.id).exists())
        self.assertFalse(
            OfferItem.objects.filter(permanence_id=self.permanence.id).exists()
        )
        self.assertFalse(
            CustomerInvoice.objects.filter(permanence_id=self.permanence.id).exists()
        )

    def test_a_scheduled_permanence_with_orders_is_cancelled_and_reversible(self):
        # Orders placed while the permanence was opened survive its
        # return to scheduled: they are never deleted to get rid of a
        # mistake, the cancellation goes through the status machinery.
        self.build_permanence(with_order=True)
        task_order.back_to_scheduled(self.permanence)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)

        self.permanence.cancel_prepared()
        self.assertEqual(self.permanence.status, SaleStatus.CANCELLED)

        # The purchases are preserved, cancelled with the permanence
        purchase = Purchase.objects.get(
            permanence_id=self.permanence.id,
            customer_id=self.customer.id,
            offer_item__order_unit=OrderUnit.PC,
        )
        self.assertEqual(purchase.status, SaleStatus.CANCELLED)
        # The forced membership fee went with them: the renewal date
        # restored to the one the member had before the closure
        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.membership_fee_valid_until, OTHER_MEMBERSHIP_START
        )

        # The cancellation stays reversible, as on the payment screen
        self.permanence.restore_delivery()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, SaleStatus.SEND)
        self.customer.refresh_from_db()
        self.assertGreaterEqual(
            self.customer.membership_fee_valid_until, utc_today()
        )


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CancelPreparedViewTest(TestCase):
    def build_and_login(self, status=SaleStatus.PLANNED):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        self.user = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        self.client.force_login(user=self.user)
        self.permanence = Permanence.objects.create(
            permanence_date=utc_today(), status=status
        )
        return reverse("admin:permanence-cancel-prepared", args=[self.permanence.id])

    def test_the_confirmation_screen_announces_the_deletion_of_a_shell(self):
        url = self.build_and_login()
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn(
            str(
                gettext(
                    "No order was placed: the permanence is an empty shell, it will be deleted for good."
                )
            ),
            content,
        )
        # The cancellation chain is announced only when orders were
        # placed, not for an empty shell
        self.assertNotIn("restaurer la livraison", content)
        self.assertNotIn("Cette permanence contient", content)

    def test_applying_deletes_the_scheduled_permanence(self):
        url = self.build_and_login()
        response = self.client.post(url, {"apply": "apply"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Permanence.objects.filter(id=self.permanence.id).exists())

    def test_the_screen_shows_the_orders_counter_of_a_scheduled_permanence(self):
        url = self.build_and_login()
        producer = Producer.objects.create(short_profile_name="Ferme")
        self.permanence.producers.add(producer)
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
        task_order.open_order(self.permanence.id, send_mail=False)
        offer_item = Product.objects.get(id=product.id).offeritem_set.get(
            permanence=self.permanence
        )
        user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        customer = Customer.objects.create(
            user=user, short_basket_name="Client", may_order=True
        )
        CustomerInvoice.get_or_create_invoice(
            permanence_id=self.permanence.id,
            customer_id=customer.id,
            status=SaleStatus.OPENED,
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        self.assertTrue(updated)
        # Orders survive the return to scheduled: the screen must
        # still show the counter before the confirmation
        task_order.back_to_scheduled(self.permanence)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)
        response = self.client.get(url, follow=True)
        content = response.content.decode("utf-8")
        self.assertIn("Cette permanence contient", content)

    def test_refusing_cancels_nothing(self):
        url = self.build_and_login()
        response = self.client.post(url, {"cancel": "cancel"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)

    def test_an_opened_permanence_is_refused(self):
        url = self.build_and_login()
        producer = Producer.objects.create(short_profile_name="Ferme")
        self.permanence.producers.add(producer)
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
        task_order.open_order(self.permanence.id, send_mail=False)
        response = self.client.post(url, {"apply": "apply"}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Refused: the staff closes the orders or goes back to scheduled
        self.assertTrue(Permanence.objects.filter(id=self.permanence.id).exists())
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.OPENED)

    def test_a_closed_permanence_is_refused(self):
        url = self.build_and_login()
        self.permanence.status = SaleStatus.SEND
        self.permanence.save()
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Permanence.objects.filter(id=self.permanence.id).exists())


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CancelPreparedRowActionsTest(TestCase):
    """The buttons offered by the preparation screen, per status."""

    def build_and_login(self, status=SaleStatus.PLANNED):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        self.user = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        self.client.force_login(user=self.user)
        self.permanence = Permanence.objects.create(
            permanence_date=utc_today(), status=status, highest_status=status
        )
        self.row_actions = PermanenceInPreparationAdmin(
            Permanence, default_admin_site
        ).get_row_actions

    def test_a_scheduled_permanence_offers_the_cancel_button(self):
        self.build_and_login(status=SaleStatus.PLANNED)
        row = self.row_actions(self.permanence)
        self.assertIn("/cancel-prepared/", row)
        # Every button carries the one sentence help shown in the
        # tooltip, translated like any other message.
        self.assertEqual(row.count("data-repanier-help="), 3)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "A permanence without any order is deleted for good. A "
                        "permanence already containing orders is only cancelled and "
                        "the cancellation can be reverted."
                    )
                )
            ),
            row,
        )

    def test_an_opened_permanence_offers_no_cancel_button(self):
        self.build_and_login(status=SaleStatus.OPENED)
        row = self.row_actions(self.permanence)
        self.assertIn("/close-order/", row)
        self.assertNotIn("/cancel-prepared/", row)
        self.assertEqual(row.count("data-repanier-help="), 2)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "The members can not order anymore. The next screen "
                        "confirms the closing, with or without the order emails."
                    )
                )
            ),
            row,
        )

    def test_a_closed_permanence_offers_the_cancel_delivery_of_the_payment_screen(self):
        self.build_and_login(status=SaleStatus.SEND)
        row = self.row_actions(self.permanence)
        # The very same action as the payment screen, reversible from
        # there with restore_delivery
        self.assertIn("/cancel-delivery/", row)
        self.assertNotIn("/cancel-prepared/", row)
        self.assertEqual(row.count("data-repanier-help="), 1)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "Purchases and invoices are kept and the cancellation can "
                        "be reverted."
                    )
                )
            ),
            row,
        )


class PermanenceDoneRowActionsTest(TestCase):
    """The buttons of the payment and archive screens carry the same help."""

    def build(self, status, latest_total=False):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )
        self.user = User.objects.create_superuser(
            username="staff@example.com", email="staff@example.com", password="x"
        )
        self.client.force_login(user=self.user)
        self.permanence = Permanence.objects.create(
            permanence_date=utc_today(),
            status=status,
            highest_status=status,
        )
        if latest_total:
            BankAccount.objects.create(
                permanence=self.permanence,
                operation_status=BankMovement.LATEST_TOTAL,
                operation_date=utc_today(),
            )
        self.row_actions = PermanenceDoneAdmin(
            Permanence, default_admin_site
        ).get_row_actions

    def test_the_payment_screen_buttons_carry_their_help(self):
        self.build(status=SaleStatus.SEND)
        row = self.row_actions(self.permanence)
        self.assertEqual(row.count("data-repanier-help="), 4)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "Register this permanence in the accounting of the group: "
                        "the customers pay, the producers get paid."
                    )
                )
            ),
            row,
        )

    def test_an_invoiced_permanence_with_latest_total_offers_the_cancel_booking(self):
        self.build(status=SaleStatus.INVOICED, latest_total=True)
        row = self.row_actions(self.permanence)
        self.assertEqual(row.count("data-repanier-help="), 2)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "Cancel the accounting entries of this permanence, when a "
                        "correction is needed."
                    )
                )
            ),
            row,
        )

    def test_an_archived_permanence_only_offers_the_restore(self):
        self.build(status=SaleStatus.ARCHIVED)
        row = self.row_actions(self.permanence)
        self.assertEqual(row.count("data-repanier-help="), 1)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "Take this permanence out of the archive to correct or "
                        "rebook it."
                    )
                )
            ),
            row,
        )

    def test_a_cancelled_delivery_offers_the_uncancel(self):
        self.build(status=SaleStatus.CANCELLED)
        row = self.row_actions(self.permanence)
        self.assertEqual(row.count("data-repanier-help="), 1)
        self.assertIn(
            escape(
                str(
                    gettext(
                        "Uncancel this delivery: the permanence is back to the "
                        "payment screen, with all its purchases."
                    )
                )
            ),
            row,
        )
