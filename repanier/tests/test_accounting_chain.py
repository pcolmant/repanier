"""Accounting chain tests: the balances, the bank and the site accounts
stay square across a full invoicing.

The chain locks the accounting identities of a permanence invoicing:

- each payer balance: previous + payments - purchases charged to him;
- each producer: fully paid -> balance back to zero (claimed amount,
  including the profit correction when the group keeps a discount);
- the site CONSUMER account (represent_this_buyinggroup) receives the
  profit corrections; the site PRODUCER account sells the membership fee;
- the bank anchor: each invoicing produces exactly one LATEST_TOTAL,
  the previous one is demoted, every invoice is stamped with it, and the
  anchor net equals the payments attached during the round (the profit
  corrections are not real bank entries and do not move the anchor).
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from repanier.const import BankMovement, SaleStatus, Vat
from repanier.models.bankaccount import BankAccount
from repanier.models.configuration import Configuration
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.lut import LUT_DeliveryPoint
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.task import task_order
from repanier.tools import create_or_update_one_cart_item

D = Decimal
PAYMENT_DATE = datetime.date(2026, 12, 24)


class AccountingJourneyMixin:
    """Build a full invoiced permanence with both charging models.

    - Legumes producer: Cerises at 2.50 + 0.20 deposit,
      bought by Alice (3) and by the two members of a group (2 + 1);
    - Viande producer: Saucisses at 4.00, bought by Bob (2);
    - the accounting staff pre-records a 10.00 payment for Alice;
    - both producers are to be paid: Legumes for its calculated amount
      (16.20), Viande for a claimed amount of 7.50 (the group keeps a
      0.50 discount -> profit correction on the site consumer account).
    """

    @classmethod
    def build_invoiced_permanence(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",  # PermanenceName.PERMANENCE
            bank_account="BE99 9999 9999 9999",
            currency="100",  # Currency.EUR
        )
        # The bank anchor required by Permanence.invoice()
        BankAccount.objects.create(
            operation_status=BankMovement.LATEST_TOTAL,
            operation_date=datetime.date.today(),
            operation_comment="Account opening",
        )
        cls.opening_anchor = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL
        )
        cls.site_customer = Customer.get_or_create_group()
        cls.site_producer = Producer.get_or_create_group()

        # A group is a customer bound to a delivery point
        group_user = User.objects.create_user(
            username="group@example.com", email="group@example.com", password="x"
        )
        cls.group = Customer.objects.create(
            user=group_user,
            short_basket_name="MonGroupe",
            may_order=True,
            is_group=True,
        )
        cls.delivery_point = LUT_DeliveryPoint.objects.create(
            short_name_v2="PointGroupe", group=cls.group
        )
        # The delivery point of the individual customers of this permanence
        cls.individual_point = LUT_DeliveryPoint.objects.create(
            short_name_v2="PointCommun"
        )
        cls.legumes = Producer.objects.create(short_profile_name="Legumes")
        cls.viande = Producer.objects.create(short_profile_name="Viande")
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.PLANNED,
            with_delivery_point=True,
        )
        cls.permanence.producers.add(cls.legumes, cls.viande)
        cls.group_board = DeliveryBoard.objects.create(
            permanence=cls.permanence, delivery_point=cls.delivery_point
        )
        cls.individual_board = DeliveryBoard.objects.create(
            permanence=cls.permanence, delivery_point=cls.individual_point
        )
        cls.cerise = Product.objects.create(
            producer=cls.legumes,
            long_name_v2="Cerises",
            order_unit="100",  # PC
            producer_unit_price=D("2.50"),
            unit_deposit=D("0.20"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.cerise.is_into_offer = True
        cls.cerise.save()
        cls.saucisse = Product.objects.create(
            producer=cls.viande,
            long_name_v2="Saucisses",
            order_unit="100",  # PC
            producer_unit_price=D("4.00"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        cls.saucisse.is_into_offer = True
        cls.saucisse.save()
        task_order.open_order(cls.permanence.id, send_mail=False)
        cls.cerise_offer = cls.cerise.offeritem_set.get(permanence=cls.permanence)
        cls.saucisse_offer = cls.saucisse.offeritem_set.get(permanence=cls.permanence)

        def new_customer(n, name, group_id=None):
            user = User.objects.create_user(
                username="%s@example.com" % name.lower(),
                email="%s@example.com" % name.lower(),
                password="x",
            )
            customer = Customer.objects.create(
                user=user,
                short_basket_name=name,
                may_order=True,
                group_id=group_id,
            )
            invoice = CustomerInvoice.get_or_create_invoice(
                permanence_id=cls.permanence.id,
                customer_id=customer.id,
                status=SaleStatus.OPENED,
            )
            if group_id is None:
                # Individual customers are attached to their delivery point
                # (set_order_delivery does not save, exactly like the view
                # delivery_ajax does it)
                invoice.set_order_delivery(cls.individual_board)
                invoice.save()
            return customer

        # Individual customers, and the members of the group
        cls.alice = new_customer(0, "Alice")
        cls.bob = new_customer(1, "Bob")
        cls.member1 = new_customer(2, "Membre1", group_id=cls.group.id)
        cls.member2 = new_customer(3, "Membre2", group_id=cls.group.id)

        orders = [
            (cls.alice, cls.cerise_offer, D("3")),
            (cls.bob, cls.saucisse_offer, D("2")),
            (cls.member1, cls.cerise_offer, D("2")),
            (cls.member2, cls.cerise_offer, D("1")),
        ]
        for customer, offer_item, quantity in orders:
            purchase, updated = create_or_update_one_cart_item(
                customer=customer, offer_item_id=offer_item.id, q_order=quantity, comment=""
            )
            assert updated and purchase is not None

        task_order.close_order(
            cls.permanence.id,
            everything=True,
            deliveries_id=(cls.group_board.id, cls.individual_board.id),
            send_mail=False,
        )
        cls.permanence.refresh_from_db()
        assert cls.permanence.status == SaleStatus.SEND

        # Accounting staff: a payment from Alice, claimed producer amounts
        BankAccount.objects.create(
            customer_id=cls.alice.id,
            operation_date=datetime.date.today(),
            operation_comment="Payment Alice",
            bank_amount_in=D("10.00"),
        )
        ProducerInvoice.objects.filter(
            permanence_id=cls.permanence.id, producer_id=cls.legumes.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("16.20"))
        ProducerInvoice.objects.filter(
            permanence_id=cls.permanence.id, producer_id=cls.viande.id
        ).update(to_be_paid=True, to_be_invoiced_balance=D("7.50"))

        cls.permanence.invoice(payment_date=PAYMENT_DATE)
        cls.permanence.refresh_from_db()
        assert cls.permanence.status == SaleStatus.INVOICED


class SquareBalancesTest(AccountingJourneyMixin, TestCase):
    """Identity: balance = previous + payments - purchases charged."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def test_every_payer_balance_identity(self):
        # Alice: 10.00 paid - 8.10 charged (3 x 2.70)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.balance.amount, D("1.90"))
        alice_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.alice.id
        )
        self.assertEqual(alice_invoice.balance.amount, D("1.90"))
        self.assertEqual(alice_invoice.bank_amount_in.amount, D("10.00"))
        self.assertEqual(alice_invoice.get_total_price_with_tax().amount, D("8.10"))

        # Bob: -8.00 charged (2 x 4.00), no payment
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.balance.amount, D("-8.00"))
        bob_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.bob.id
        )
        self.assertEqual(bob_invoice.bank_amount_in.amount, D("0"))
        self.assertEqual(bob_invoice.balance.amount, D("-8.00"))

    def test_the_group_is_charged_and_not_its_members(self):
        # Members: order without paying
        for member in (self.member1, self.member2):
            member.refresh_from_db()
            self.assertEqual(member.balance.amount, D("0"))
            member_invoice = CustomerInvoice.objects.get(
                permanence_id=self.permanence.id, customer_id=member.id
            )
            self.assertEqual(member_invoice.customer_charged_id, self.group.id)
            self.assertEqual(member_invoice.balance.amount, D("0"))
        # Group: 8.10 charged (3 x 2.70)
        self.group.refresh_from_db()
        self.assertEqual(self.group.balance.amount, D("-8.10"))
        group_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.group.id
        )
        self.assertTrue(group_invoice.is_group)
        self.assertEqual(group_invoice.get_total_price_with_tax().amount, D("8.10"))
        self.assertEqual(group_invoice.balance.amount, D("-8.10"))

    def test_fully_paid_producers_end_with_a_zero_balance(self):
        # Legumes: calculated 16.20, claimed 16.20, paid 16.20
        self.legumes.refresh_from_db()
        self.assertEqual(self.legumes.balance.amount, D("0"))
        legumes_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.legumes.id
        )
        self.assertEqual(legumes_invoice.get_total_price_with_tax().amount, D("16.20"))
        self.assertEqual(legumes_invoice.bank_amount_out.amount, D("16.20"))
        self.assertEqual(legumes_invoice.bank_amount_in.amount, D("0"))
        self.assertEqual(legumes_invoice.balance.amount, D("0"))

        # Viande: calculated 8.00, claimed 7.50 (0.50 kept by the group)
        self.viande.refresh_from_db()
        self.assertEqual(self.viande.balance.amount, D("0"))
        viande_invoice = ProducerInvoice.objects.get(
            permanence_id=self.permanence.id, producer_id=self.viande.id
        )
        self.assertEqual(viande_invoice.to_be_invoiced_balance.amount, D("7.50"))
        self.assertEqual(viande_invoice.bank_amount_out.amount, D("7.50"))
        self.assertEqual(viande_invoice.balance.amount, D("0"))

    def test_the_discount_books_as_a_profit_on_the_site_consumer_account(self):
        # The difference between the calculated producer amount (8.00)
        # and the claimed amount (7.50) is a profit for the group, booked
        # on the site consumer account.
        profit = BankAccount.objects.get(operation_status=BankMovement.PROFIT)
        self.assertEqual(profit.customer_id, self.site_customer.id)
        self.assertEqual(profit.bank_amount_in.amount, D("0.50"))
        self.assertEqual(profit.bank_amount_out.amount, D("0"))
        self.assertEqual(profit.permanence_id, self.permanence.id)

        self.site_customer.refresh_from_db()
        self.assertEqual(self.site_customer.balance.amount, D("0.50"))
        site_invoice = CustomerInvoice.objects.get(
            permanence_id=self.permanence.id, customer_id=self.site_customer.id
        )
        # The profit is attached to the site invoice: not counted as a
        # bank entry anywhere else
        self.assertEqual(profit.customer_invoice_id, site_invoice.id)


class SquareBankTest(AccountingJourneyMixin, TestCase):
    """Identity: the bank anchor chains from invoicing to invoicing."""

    @classmethod
    def setUpTestData(cls):
        cls.build_invoiced_permanence()

    def test_one_single_latest_total_and_the_previous_one_is_demoted(self):
        self.assertFalse(
            BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL,
                permanence_id__isnull=True,
            ).exists()
        )
        self.opening_anchor.refresh_from_db()
        self.assertEqual(
            self.opening_anchor.operation_status, BankMovement.NOT_LATEST_TOTAL
        )
        latest_total = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL,
            permanence_id=self.permanence.id,
        )
        self.assertEqual(latest_total.operation_date, PAYMENT_DATE)

    def test_the_anchor_net_equals_the_movements_of_the_round(self):
        latest_total = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL,
            permanence_id=self.permanence.id,
        )
        # The payments attached during the round: Alice 10.00 in,
        # the producers paid out: 16.20 + 7.50. The profit correction is
        # not a real bank entry: it does not move the anchor.
        expected_net = D("10.00") - D("16.20") - D("7.50")
        self.assertEqual(
            latest_total.bank_amount_in.amount
            - latest_total.bank_amount_out.amount,
            expected_net,
        )
        self.assertEqual(latest_total.bank_amount_in.amount, D("0"))
        self.assertEqual(latest_total.bank_amount_out.amount, D("13.70"))

    def test_every_invoice_is_stamped_with_the_anchor(self):
        latest_total = BankAccount.objects.get(
            operation_status=BankMovement.LATEST_TOTAL,
            permanence_id=self.permanence.id,
        )
        for invoice in CustomerInvoice.objects.filter(permanence_id=self.permanence.id):
            self.assertEqual(invoice.invoice_sort_order, latest_total.id)
        for invoice in ProducerInvoice.objects.filter(permanence_id=self.permanence.id):
            self.assertEqual(invoice.invoice_sort_order, latest_total.id)
        self.permanence.refresh_from_db()
        self.assertEqual(self.permanence.invoice_sort_order, latest_total.id)


class SiteAccountsTest(TestCase):
    """The site consumer / producer accounts and the membership fee."""

    @classmethod
    def setUpTestData(cls):
        Configuration.objects.create(
            group_name="Test Group",
            name="100",
            bank_account="BE99 9999 9999 9999",
            currency="100",
        )

    def test_the_site_accounts_are_singletons(self):
        site_customer, site_producer = (
            Customer.get_or_create_group(),
            Producer.get_or_create_group(),
        )
        self.assertTrue(site_customer.represent_this_buyinggroup)
        self.assertTrue(site_producer.represent_this_buyinggroup)
        # Idempotent
        self.assertEqual(Customer.get_or_create_group().id, site_customer.id)
        self.assertEqual(Producer.get_or_create_group().id, site_producer.id)

    def test_the_membership_fee_product_belongs_to_the_site_producer(self):
        site_producer = Producer.get_or_create_group()
        membership = Product.objects.get(order_unit="400")  # OrderUnit.MEMBERSHIP_FEE
        self.assertEqual(membership.producer_id, site_producer.id)

    def test_a_forced_membership_is_invoiced_on_the_site_producer_account(self):
        # Out of date member, group charging a 10.00 membership fee
        user = User.objects.create_user(
            username="member@example.com", email="member@example.com", password="x"
        )
        customer = Customer.objects.create(
            user=user,
            short_basket_name="Member",
            may_order=True,
            membership_fee_valid_until=datetime.date(2010, 1, 1),
        )
        producer = Producer.objects.create(short_profile_name="Ferme")
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.PLANNED
        )
        permanence.producers.add(producer)
        product = Product.objects.create(
            producer=producer,
            long_name_v2="Produit",
            order_unit="100",
            producer_unit_price=D("2.50"),
            vat_level=Vat.VAT_100,
            stock=D("99"),
        )
        product.is_into_offer = True
        product.save()
        task_order.open_order(permanence.id, send_mail=False)
        offer_item = product.offeritem_set.get(permanence=permanence)
        CustomerInvoice.get_or_create_invoice(
            permanence_id=permanence.id,
            customer_id=customer.id,
            status=SaleStatus.OPENED,
        )
        purchase, updated = create_or_update_one_cart_item(
            customer=customer, offer_item_id=offer_item.id, q_order=D("1"), comment=""
        )
        assert updated
        Configuration.objects.update(
            membership_fee=D("10.00"), membership_fee_duration=D("12")
        )
        # Re-trigger the post_save signal so the settings are refreshed
        Configuration.objects.first().save()
        task_order.close_order(
            permanence.id, everything=True, deliveries_id=(), send_mail=False
        )

        membership_purchase = Purchase.objects.get(
            permanence_id=permanence.id,
            customer_id=customer.id,
            offer_item__order_unit="400",
        )
        self.assertEqual(membership_purchase.producer_id, self.site_producer_id)
        self.assertEqual(membership_purchase.selling_price.amount, D("10.00"))

    @property
    def site_producer_id(self):
        return Producer.get_or_create_group().id
