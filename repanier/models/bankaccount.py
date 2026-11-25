from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.db import models
from repanier.const import BankMovement, DECIMAL_ZERO, EMPTY_STRING
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField


class BankAccount(models.Model):
    UNUSUAL_DIRECTION_CONFIRMED_MARKER = "UNUSUAL_DIRECTION_CONFIRMED"

    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=_("Sale"),
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    producer = models.ForeignKey(
        "Producer",
        verbose_name=_("Producer"),
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    operation_date = models.DateField(_("Operation date"), db_index=True)
    operation_comment = models.CharField(
        _("Operation comment"), max_length=100, blank=True, default=EMPTY_STRING
    )
    operation_status = models.CharField(
        max_length=3,
        choices=BankMovement.choices,
        default=BankMovement.NOT_LATEST_TOTAL,
        verbose_name=_("Account balance status"),
        db_index=True,
    )
    bank_amount_in = ModelRepanierMoneyField(
        _("Cash in"),
        help_text=_("Payment on the account"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)],
    )
    bank_amount_out = ModelRepanierMoneyField(
        _("Cash out"),
        help_text=_("Payment from the account"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)],
    )
    producer_invoice = models.ForeignKey(
        "ProducerInvoice",
        verbose_name=_("Accounting entry"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        db_index=True,
    )
    customer_invoice = models.ForeignKey(
        "CustomerInvoice",
        verbose_name=_("Accounting entry"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        db_index=True,
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True)

    INVOICE_CANCEL_OPERATION_STATUSES = (
        BankMovement.CALCULATED_INVOICE,
        BankMovement.PROFIT,
        BankMovement.TAX,
        BankMovement.MEMBERSHIP_FEE,
        BankMovement.COMPENSATION,
    )

    @classmethod
    def invoice_cancel_movements(cls, permanence_id):
        """Movements historically generated and owned by a permanence invoice."""
        return cls.objects.filter(
            permanence_id=permanence_id,
            operation_status__in=cls.INVOICE_CANCEL_OPERATION_STATUSES,
        )

    @classmethod
    def validate_explicit_movement(
        cls,
        *,
        operation_status,
        producer=None,
        customer=None,
        bank_amount_in=DECIMAL_ZERO,
        bank_amount_out=DECIMAL_ZERO,
        customer_invoice=None,
        producer_invoice=None,
        allow_unusual_direction=False,
    ):
        """Validate accounting movements used by manual entry and imports."""
        explicit_statuses = {
            BankMovement.PAYMENT_RECEIVED,
            BankMovement.PRODUCER_WAIVER,
            BankMovement.PRODUCER_CLAIMED_AMOUNT,
            BankMovement.GROUP_EXPENSE,
            BankMovement.PRODUCER_DRAW,
        }
        if operation_status not in explicit_statuses:
            return False

        amount_in = getattr(bank_amount_in, "amount", bank_amount_in)
        amount_out = getattr(bank_amount_out, "amount", bank_amount_out)
        amount_in = DECIMAL_ZERO if amount_in is None else amount_in
        amount_out = DECIMAL_ZERO if amount_out is None else amount_out

        if amount_in < DECIMAL_ZERO or amount_out < DECIMAL_ZERO:
            raise ValidationError(_("Bank movements cannot have negative amounts."))
        if amount_in != DECIMAL_ZERO and amount_out != DECIMAL_ZERO:
            raise ValidationError(
                _("A bank movement cannot have cash in and cash out at the same time.")
            )

        unusual_direction = False

        if operation_status == BankMovement.PAYMENT_RECEIVED:
            if customer is None or producer is not None:
                raise ValidationError(
                    _("A payment received must be assigned to a customer.")
                )
            if amount_in <= DECIMAL_ZERO or amount_out != DECIMAL_ZERO:
                raise ValidationError(
                    _("A payment received requires a positive cash-in amount.")
                )
            if producer_invoice is not None:
                raise ValidationError(
                    _("A payment received cannot use a producer invoice.")
                )
            if customer_invoice is not None:
                invoice_total = getattr(
                    customer_invoice, "get_total_price_with_tax", lambda: DECIMAL_ZERO
                )()
                invoice_total = getattr(invoice_total, "amount", invoice_total)
                if invoice_total == DECIMAL_ZERO:
                    raise ValidationError(
                        _("A payment received must not use a zero-total invoice.")
                    )

        elif operation_status == BankMovement.PRODUCER_DRAW:
            if producer is None or customer is not None:
                raise ValidationError(
                    _("A producer draw must be assigned to a producer.")
                )
            if amount_out <= DECIMAL_ZERO or amount_in != DECIMAL_ZERO:
                raise ValidationError(
                    _("A producer draw requires cash-out only.")
                )

        elif operation_status == BankMovement.GROUP_EXPENSE:
            if customer is not None or producer is not None:
                raise ValidationError(
                    _("A group expense must not be assigned to a customer or producer.")
                )
            if amount_out <= DECIMAL_ZERO or amount_in != DECIMAL_ZERO:
                raise ValidationError(
                    _("A group expense requires cash-out only.")
                )
            if customer_invoice is not None or producer_invoice is not None:
                raise ValidationError(
                    _("A group expense must not use a business invoice.")
                )

        elif operation_status in (
            BankMovement.PRODUCER_WAIVER,
            BankMovement.PRODUCER_CLAIMED_AMOUNT,
        ):
            if producer is None or customer is not None:
                raise ValidationError(
                    _("This producer operation must be assigned to a producer.")
                )
            if amount_in == DECIMAL_ZERO and amount_out == DECIMAL_ZERO:
                raise ValidationError(
                    _("This producer operation requires a positive amount.")
                )
            if amount_out > DECIMAL_ZERO:
                unusual_direction = False
            elif amount_in > DECIMAL_ZERO:
                unusual_direction = True
            if unusual_direction and not allow_unusual_direction:
                raise ValidationError(
                    _("This unusual amount direction requires confirmation.")
                )

        return unusual_direction

    def clean(self):
        super().clean()
        confirmed_unusual_direction = (
            self.UNUSUAL_DIRECTION_CONFIRMED_MARKER in (self.operation_comment or "")
        )
        self.validate_explicit_movement(
            operation_status=self.operation_status,
            producer=self.producer,
            customer=self.customer,
            bank_amount_in=self.bank_amount_in,
            bank_amount_out=self.bank_amount_out,
            customer_invoice=self.customer_invoice,
            producer_invoice=self.producer_invoice,
            allow_unusual_direction=confirmed_unusual_direction,
        )

    def save(self, *args, allow_unusual_amount_direction=False, **kwargs):
        if self.UNUSUAL_DIRECTION_CONFIRMED_MARKER in (self.operation_comment or ""):
            allow_unusual_amount_direction = True
        self.validate_explicit_movement(
            operation_status=self.operation_status,
            producer=self.producer,
            customer=self.customer,
            bank_amount_in=self.bank_amount_in,
            bank_amount_out=self.bank_amount_out,
            customer_invoice=self.customer_invoice,
            producer_invoice=self.producer_invoice,
            allow_unusual_direction=allow_unusual_amount_direction,
        )
        super().save(*args, **kwargs)

    @classmethod
    def open_account(cls, customer_buyinggroup, very_first_customer):
        bank_account = BankAccount.objects.filter()
        if not bank_account.exists():
            BankAccount.objects.create(
                operation_status=BankMovement.LATEST_TOTAL,
                operation_date=timezone.now().date(),
                operation_comment=_("Account opening"),
            )
            # Create this also prevent the deletion of the customer representing the buying group
            BankAccount.objects.create(
                operation_date=timezone.now().date(),
                customer=customer_buyinggroup,
                operation_comment=_("Initial balance"),
            )
            # Create this also prevent the deletion of the very first customer
            BankAccount.objects.create(
                operation_date=timezone.now().date(),
                customer=very_first_customer,
                operation_comment=_("Initial balance"),
            )

    @classmethod
    def get_closest_to(cls, target):
        # https://stackoverflow.com/questions/15855715/filter-on-datetime-closest-to-the-given-datetime
        # https://www.vinta.com.br/blog/2017/advanced-django-querying-sorting-events-date/
        # Get closest bank_account (sub-)total from target date
        qs = cls.objects.filter(producer__isnull=True, customer__isnull=True)
        closest_greater_qs = qs.filter(operation_date__gt=target).order_by(
            "operation_date"
        )
        closest_less_qs = qs.filter(operation_date__lt=target).order_by(
            "-operation_date"
        )

        closest_greater = closest_greater_qs.first()
        if closest_greater is None:
            closest_greater = closest_less_qs.first()

        closest_less = closest_less_qs.first()
        if closest_less is None:
            closest_less = closest_greater_qs.first()

        if closest_greater is not None and closest_less is not None:
            if (
                closest_greater.operation_date - target
                > target - closest_less.operation_date
            ):
                return closest_less
            else:
                return closest_greater

    @classmethod
    def get_latest_total(cls):
        return BankAccount.objects.filter(
            operation_status=BankMovement.LATEST_TOTAL
        ).first()

    def get_bank_amount_in(self):
        if self.operation_status in [BankMovement.PROFIT, BankMovement.TAX]:
            return format_html(
                "<i>{}</i>",
                self.bank_amount_in
                if self.bank_amount_in.amount != DECIMAL_ZERO
                else EMPTY_STRING,
            )
        else:
            return (
                self.bank_amount_in
                if self.bank_amount_in.amount != DECIMAL_ZERO
                else EMPTY_STRING
            )

    get_bank_amount_in.short_description = _("Cash in")
    get_bank_amount_in.admin_order_field = "bank_amount_in"

    def get_bank_amount_out(self):
        if self.operation_status in [BankMovement.PROFIT, BankMovement.TAX]:
            return format_html(
                "<i>{}</i>",
                self.bank_amount_out
                if self.bank_amount_out.amount != DECIMAL_ZERO
                else EMPTY_STRING,
            )
        else:
            return (
                self.bank_amount_out
                if self.bank_amount_out.amount != DECIMAL_ZERO
                else EMPTY_STRING
            )

    get_bank_amount_out.short_description = _("Cash out")
    get_bank_amount_out.admin_order_field = "bank_amount_out"

    def get_producer(self):
        if self.producer is not None:
            return self.producer.short_profile_name
        else:
            if self.customer is None:
                # This is a total, show it
                if self.operation_status == BankMovement.LATEST_TOTAL:
                    return format_html(
                        "<b>=== {}</b>", settings.REPANIER_SETTINGS_GROUP_NAME
                    )
                else:
                    return format_html(
                        "<b>--- {}</b>", settings.REPANIER_SETTINGS_GROUP_NAME
                    )
            return EMPTY_STRING

    get_producer.short_description = _("Producer")
    get_producer.admin_order_field = "producer"

    def get_customer(self):
        if self.customer is not None:
            return self.customer.short_basket_name
        else:
            if self.producer is None:
                # This is a total, show it
                from repanier.apps import REPANIER_SETTINGS_BANK_ACCOUNT

                if self.operation_status == BankMovement.LATEST_TOTAL:

                    if REPANIER_SETTINGS_BANK_ACCOUNT is not None:
                        return format_html("<b>{}</b>", REPANIER_SETTINGS_BANK_ACCOUNT)
                    else:
                        return format_html("<b>{}</b>", "==============")
                else:
                    if REPANIER_SETTINGS_BANK_ACCOUNT is not None:
                        return format_html("<b>{}</b>", REPANIER_SETTINGS_BANK_ACCOUNT)
                    else:
                        return format_html("<b>{}</b>", "--------------")
            return EMPTY_STRING

    get_customer.short_description = _("Customer")
    get_customer.admin_order_field = "customer"

    def __str__(self):
        return format_html("{} ({})", _("Banking transaction number"), self.id)

    class Meta:
        verbose_name = _("Bank account transaction")
        verbose_name_plural = _("Bank account transactions")
        ordering = ("-operation_date", "-id")
        indexes = [
            models.Index(
                fields=["operation_date", "id"], name="repanier_bankaccount_idx01"
            ),
            models.Index(
                fields=["customer_invoice", "operation_date", "id"],
                name="repanier_bankaccount_idx02",
            ),
            models.Index(
                fields=["producer_invoice", "operation_date", "operation_date", "id"],
                name="repanier_bankaccount_idx03",
            ),
            models.Index(
                fields=["permanence", "customer", "producer", "operation_date", "id"],
                name="repanier_bankaccount_idx04",
            ),
        ]
