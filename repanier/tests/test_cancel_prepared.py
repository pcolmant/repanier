"""Tests of the "cancel this permanence" action of the preparation screen.

Groups create permanences by mistake and never run the three step manual
chain to get rid of them. The red button runs it in one action: open the
orders without sending any email, close them without sending any email,
cancel the delivery. Everything stays reversible.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from repanier.const import OrderUnit, SaleStatus, Vat
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.offeritem import OfferItem
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
        # The group charges a 10.00 membership fee valid 12 months
        Configuration.objects.update(
            membership_fee=D("10.00"), membership_fee_duration=D("12")
        )
        configuration = Configuration.objects.first()
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

    def test_an_empty_planned_permanence_is_deleted_for_good(self):
        self.build_permanence(with_order=False)
        self.permanence.cancel_prepared()
        # Nothing was ever ordered: no shell stays in any list
        self.assertFalse(Permanence.objects.filter(id=self.permanence.id).exists())

    def test_an_empty_opened_permanence_is_deleted_for_good(self):
        self.build_permanence(with_order=False)
        task_order.open_order(self.permanence.id, send_mail=False)
        # Opening created the offer items: they leave with the shell
        self.assertTrue(
            OfferItem.objects.filter(permanence_id=self.permanence.id).exists()
        )
        self.permanence.refresh_from_db()
        self.permanence.cancel_prepared()
        self.assertFalse(Permanence.objects.filter(id=self.permanence.id).exists())
        self.assertFalse(
            OfferItem.objects.filter(permanence_id=self.permanence.id).exists()
        )

    def test_an_opened_permanence_with_orders_is_cancelled_and_reversible(self):
        self.build_permanence(with_order=True)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.OPENED)

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
    def build_and_login(self):
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
            permanence_date=utc_today(), status=SaleStatus.PLANNED
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
        # The cancellation chain is not announced for a shell
        self.assertNotIn("restaurer la livraison", content)
        self.assertNotIn("Cette permanence contient", content)

    def test_applying_deletes_the_empty_planned_permanence(self):
        url = self.build_and_login()
        response = self.client.post(url, {"apply": "apply"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Permanence.objects.filter(id=self.permanence.id).exists())

    def test_the_screen_shows_the_orders_counter_of_an_opened_permanence(self):
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
        response = self.client.get(url, follow=True)
        content = response.content.decode("utf-8")
        # One order was placed: the screen shows the counter so that the
        # staff member can spot a real permanence before cancelling
        self.assertIn("Cette permanence contient", content)

    def test_refusing_cancels_nothing(self):
        url = self.build_and_login()
        response = self.client.post(url, {"cancel": "cancel"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.PLANNED)

    def test_a_closed_permanence_is_refused(self):
        url = self.build_and_login()
        self.permanence.status = SaleStatus.SEND
        self.permanence.save()
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        # Refused with an explicit status message; the permanence stays
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.status, SaleStatus.SEND)
