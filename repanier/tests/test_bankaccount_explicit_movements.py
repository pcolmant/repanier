import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from repanier.admin.bankaccount import BankAccountDataForm, BankAccountResource
from repanier.const import BankMovement, SaleStatus
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer

D = Decimal


class ExplicitBankMovementTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="account-member",
            email="account-member@example.com",
            password="password",
        )
        self.customer = Customer.objects.create(
            user=user,
            short_basket_name="Account member",
        )
        self.producer = Producer.objects.create(short_profile_name="Account producer")
        self.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.INVOICED,
        )

    def create_movement(self, **kwargs):
        defaults = {
            "operation_date": datetime.date.today(),
            "operation_status": BankMovement.NOT_LATEST_TOTAL,
            "operation_comment": "Test movement",
        }
        defaults.update(kwargs)
        return BankAccount.objects.create(**defaults)

    def test_producer_draw_accepts_out_only(self):
        BankAccount.validate_explicit_movement(
            operation_status=BankMovement.PRODUCER_DRAW,
            producer=self.producer,
            bank_amount_out=D("10.00"),
        )

    def test_negative_and_simultaneous_amounts_are_rejected(self):
        with self.assertRaises(ValidationError):
            BankAccount.validate_explicit_movement(
                operation_status=BankMovement.PAYMENT_RECEIVED,
                customer=self.customer,
                bank_amount_in=D("-10.00"),
            )
        with self.assertRaises(ValidationError):
            BankAccount.validate_explicit_movement(
                operation_status=BankMovement.GROUP_EXPENSE,
                bank_amount_in=D("10.00"),
                bank_amount_out=D("10.00"),
            )

    def test_producer_draw_rejects_in_only_and_both_directions(self):
        for bank_amount_in, bank_amount_out in (
            (D("10.00"), D("0")),
            (D("10.00"), D("10.00")),
        ):
            with self.subTest(bank_amount_in=bank_amount_in):
                with self.assertRaises(ValidationError):
                    BankAccount.validate_explicit_movement(
                        operation_status=BankMovement.PRODUCER_DRAW,
                        producer=self.producer,
                        bank_amount_in=bank_amount_in,
                        bank_amount_out=bank_amount_out,
                    )

    def test_producer_draw_requires_a_producer(self):
        with self.assertRaises(ValidationError):
            BankAccount.validate_explicit_movement(
                operation_status=BankMovement.PRODUCER_DRAW,
                bank_amount_out=D("10.00"),
            )

    def test_payment_received_never_accepts_a_zero_invoice(self):
        invoice = CustomerInvoice.objects.create(
            permanence=self.permanence,
            customer=self.customer,
            customer_charged=self.customer,
            total_price_with_tax=D("0"),
        )
        with self.assertRaises(ValidationError):
            BankAccount.validate_explicit_movement(
                operation_status=BankMovement.PAYMENT_RECEIVED,
                customer=self.customer,
                bank_amount_in=D("10.00"),
                customer_invoice=invoice,
            )

    def test_payment_received_accepts_customer_cash_in_without_invoice(self):
        BankAccount.validate_explicit_movement(
            operation_status=BankMovement.PAYMENT_RECEIVED,
            customer=self.customer,
            bank_amount_in=D("10.00"),
        )

    def test_group_expense_rejects_customers_and_producers(self):
        with self.assertRaises(ValidationError):
            BankAccount.validate_explicit_movement(
                operation_status=BankMovement.GROUP_EXPENSE,
                customer=self.customer,
                bank_amount_out=D("10.00"),
            )
        BankAccount.validate_explicit_movement(
            operation_status=BankMovement.GROUP_EXPENSE,
            bank_amount_out=D("10.00"),
        )

    def test_waiver_and_claimed_accept_normal_out_direction(self):
        for status in (
            BankMovement.PRODUCER_WAIVER,
            BankMovement.PRODUCER_CLAIMED_AMOUNT,
        ):
            self.assertFalse(
                BankAccount.validate_explicit_movement(
                    operation_status=status,
                    producer=self.producer,
                    bank_amount_out=D("10.00"),
                )
            )

    def test_unusual_in_direction_requires_confirmation(self):
        for status in (
            BankMovement.PRODUCER_WAIVER,
            BankMovement.PRODUCER_CLAIMED_AMOUNT,
        ):
            with self.assertRaises(ValidationError):
                BankAccount.validate_explicit_movement(
                    operation_status=status,
                    producer=self.producer,
                    bank_amount_in=D("10.00"),
                )
            unusual = BankAccount.validate_explicit_movement(
                operation_status=status,
                producer=self.producer,
                bank_amount_in=D("10.00"),
                allow_unusual_direction=True,
            )
            self.assertTrue(unusual)

    def test_admin_form_requires_confirmation_and_comment_for_unusual_direction(self):
        data = {
            "operation_date": datetime.date.today(),
            "operation_status": BankMovement.PRODUCER_WAIVER,
            "operation_comment": "Reverse adjustment",
            "bank_amount_in": D("10.00"),
            "bank_amount_out": D("0"),
            "producer": self.producer.pk,
            "customer": "",
        }
        form = BankAccountDataForm(data=data)
        self.assertFalse(form.is_valid())

        data["confirm_unusual_direction"] = True
        form = BankAccountDataForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_form_rejects_unconfirmed_comment_only_direction(self):
        data = {
            "operation_date": datetime.date.today(),
            "operation_status": BankMovement.PRODUCER_CLAIMED_AMOUNT,
            "operation_comment": "",
            "bank_amount_in": D("10.00"),
            "bank_amount_out": D("0"),
            "producer": self.producer.pk,
            "customer": "",
            "confirm_unusual_direction": True,
        }
        form = BankAccountDataForm(data=data)
        self.assertFalse(form.is_valid())

    def test_import_rejects_unusual_direction_without_option(self):
        instance = BankAccount(
            operation_date=datetime.date.today(),
            operation_status=BankMovement.PRODUCER_WAIVER,
            operation_comment="Reverse adjustment",
            producer=self.producer,
            bank_amount_in=D("10.00"),
            bank_amount_out=D("0"),
        )
        resource = BankAccountResource()
        with self.assertRaises(ValidationError):
            resource.before_save_instance(instance, {})

    def test_explicit_import_does_not_infer_a_target_from_the_amount(self):
        instance = BankAccount(
            operation_date=datetime.date.today(),
            operation_status=BankMovement.PRODUCER_DRAW,
            operation_comment="Cash draw",
            bank_amount_in=D("0"),
            bank_amount_out=D("10.00"),
        )
        resource = BankAccountResource()
        with self.assertRaises(ValidationError):
            resource.before_save_instance(instance, {})

    def test_import_accepts_unusual_direction_with_option_and_comment(self):
        instance = BankAccount(
            operation_date=datetime.date.today(),
            operation_status=BankMovement.PRODUCER_CLAIMED_AMOUNT,
            operation_comment="Reverse adjustment",
            producer=self.producer,
            bank_amount_in=D("10.00"),
            bank_amount_out=D("0"),
        )
        resource = BankAccountResource(allow_unusual_amount_direction=True)
        resource.before_save_instance(instance, {})
        self.assertIn(
            BankAccount.UNUSUAL_DIRECTION_CONFIRMED_MARKER,
            instance.operation_comment,
        )

    def test_import_rejects_unusual_direction_without_comment(self):
        instance = BankAccount(
            operation_date=datetime.date.today(),
            operation_status=BankMovement.PRODUCER_CLAIMED_AMOUNT,
            operation_comment="",
            producer=self.producer,
            bank_amount_in=D("10.00"),
            bank_amount_out=D("0"),
        )
        resource = BankAccountResource(allow_unusual_amount_direction=True)
        with self.assertRaises(ValueError):
            resource.before_save_instance(instance, {})

    def test_cancel_invoice_preserves_independent_and_other_permanence_movements(self):
        independent_payment = self.create_movement(
            permanence=None,
            operation_status=BankMovement.PAYMENT_RECEIVED,
            customer=self.customer,
            bank_amount_in=D("20.00"),
        )
        independent_expense = self.create_movement(
            permanence=None,
            operation_status=BankMovement.GROUP_EXPENSE,
            bank_amount_out=D("5.00"),
        )
        other_permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.INVOICED,
        )
        other_payment = self.create_movement(
            permanence=other_permanence,
            operation_status=BankMovement.PAYMENT_RECEIVED,
            customer=self.customer,
            bank_amount_in=D("30.00"),
        )

        BankAccount.invoice_cancel_movements(self.permanence.pk).delete()

        self.assertTrue(BankAccount.objects.filter(pk=independent_payment.pk).exists())
        self.assertTrue(BankAccount.objects.filter(pk=independent_expense.pk).exists())
        self.assertTrue(BankAccount.objects.filter(pk=other_payment.pk).exists())
