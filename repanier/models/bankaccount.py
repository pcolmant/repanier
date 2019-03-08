# -*- coding: utf-8

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField


class BankAccount(models.Model):
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, blank=True, null=True)
    producer = models.ForeignKey(
        'Producer', verbose_name=_("Producer"),
        on_delete=models.PROTECT, blank=True, null=True)
    customer = models.ForeignKey(
        'Customer', verbose_name=_("Customer"),
        on_delete=models.PROTECT, blank=True, null=True)
    operation_date = models.DateField(_("Operation date"),
                                      db_index=True)
    operation_comment = models.CharField(
        _("Operation comment"), max_length=100, blank=True, default=EMPTY_STRING)
    operation_status = models.CharField(
        max_length=3,
        choices=LUT_BANK_TOTAL,
        default=BANK_NOT_LATEST_TOTAL,
        verbose_name=_("Account balance status"),
        db_index=True
    )
    bank_amount_in = ModelMoneyField(
        _("Cash in"), help_text=_('Payment on the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)])
    bank_amount_out = ModelMoneyField(
        _("Cash out"), help_text=_('Payment from the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)])
    producer_invoice = models.ForeignKey(
        'ProducerInvoice', verbose_name=_("Producer invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    customer_invoice = models.ForeignKey(
        'CustomerInvoice', verbose_name=_("Customer invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    is_updated_on = models.DateTimeField(
        _("Updated on"), auto_now=True)

    @classmethod
    def open_account(cls, customer_buyinggroup, very_first_customer):
        bank_account = BankAccount.objects.filter().order_by('?')
        if not bank_account.exists():
            BankAccount.objects.create(
                operation_status=BANK_LATEST_TOTAL,
                operation_date=timezone.now().date(),
                operation_comment=_("Account opening")
            )
            # Create this also prevent the deletion of the customer representing the buying group
            BankAccount.objects.create(
                operation_date=timezone.now().date(),
                customer=customer_buyinggroup,
                operation_comment=_("Initial balance")
            )
            # Create this also prevent the deletion of the very first customer
            BankAccount.objects.create(
                operation_date=timezone.now().date(),
                customer=very_first_customer,
                operation_comment=_("Initial balance")
            )

    @classmethod
    def get_closest_to(cls, target):
        # https://stackoverflow.com/questions/15855715/filter-on-datetime-closest-to-the-given-datetime
        # https://www.vinta.com.br/blog/2017/advanced-django-querying-sorting-events-date/
        # Get closest bank_account (sub-)total from target date
        qs = cls.objects.filter(producer__isnull=True, customer__isnull=True).order_by('?')
        closest_greater_qs = qs.filter(operation_date__gt=target).order_by('operation_date')
        closest_less_qs = qs.filter(operation_date__lt=target).order_by('-operation_date')

        closest_greater = closest_greater_qs.first()
        if closest_greater is None:
            closest_greater = closest_less_qs.first()

        closest_less = closest_less_qs.first()
        if closest_less is None:
            closest_less = closest_greater_qs.first()

        if closest_greater is not None and closest_less is not None:
            if closest_greater.operation_date - target > target - closest_less.operation_date:
                return closest_less
            else:
                return closest_greater

    def get_bank_amount_in(self):
        if self.operation_status in [BANK_PROFIT, BANK_TAX]:
            return mark_safe(
                "<i>{}</i>".format(self.bank_amount_in if self.bank_amount_in.amount != DECIMAL_ZERO else EMPTY_STRING))
        else:
            return self.bank_amount_in if self.bank_amount_in.amount != DECIMAL_ZERO else EMPTY_STRING

    get_bank_amount_in.short_description = (_("Cash in"))
    get_bank_amount_in.admin_order_field = 'bank_amount_in'

    def get_bank_amount_out(self):
        if self.operation_status in [BANK_PROFIT, BANK_TAX]:
            return mark_safe("<i>{}</i>".format(
                self.bank_amount_out if self.bank_amount_out.amount != DECIMAL_ZERO else EMPTY_STRING))
        else:
            return self.bank_amount_out if self.bank_amount_out.amount != DECIMAL_ZERO else EMPTY_STRING

    get_bank_amount_out.short_description = (_("Cash out"))
    get_bank_amount_out.admin_order_field = 'bank_amount_out'

    def get_producer(self):
        if self.producer is not None:
            return self.producer.short_profile_name
        else:
            if self.customer is None:
                # This is a total, show it
                if self.operation_status == BANK_LATEST_TOTAL:
                    return "<b>=== {}</b>".format(settings.REPANIER_SETTINGS_GROUP_NAME)
                else:
                    return "<b>--- {}</b>".format(settings.REPANIER_SETTINGS_GROUP_NAME)
            return EMPTY_STRING

    get_producer.short_description = (_("Producer"))
    get_producer.allow_tags = True
    get_producer.admin_order_field = 'producer'

    def get_customer(self):
        if self.customer is not None:
            return self.customer.short_basket_name
        else:
            if self.producer is None:
                # This is a total, show it
                from repanier.apps import REPANIER_SETTINGS_BANK_ACCOUNT
                if self.operation_status == BANK_LATEST_TOTAL:

                    if REPANIER_SETTINGS_BANK_ACCOUNT is not None:
                        return "<b>{}</b>".format(REPANIER_SETTINGS_BANK_ACCOUNT)
                    else:
                        return "<b>{}</b>".format("==============")
                else:
                    if REPANIER_SETTINGS_BANK_ACCOUNT is not None:
                        return "<b>{}</b>".format(REPANIER_SETTINGS_BANK_ACCOUNT)
                    else:
                        return "<b>{}</b>".format("--------------")
            return EMPTY_STRING

    get_customer.short_description = (_("Customer"))
    get_customer.allow_tags = True
    get_customer.admin_order_field = 'customer'

    class Meta:
        verbose_name = _("Bank account transaction")
        verbose_name_plural = _("Bank account transactions")
        ordering = ('-operation_date', '-id')
        index_together = [
            ['operation_date', 'id'],
            ['customer_invoice', 'operation_date', 'id'],
            ['producer_invoice', 'operation_date', 'operation_date', 'id'],
            ['permanence', 'customer', 'producer', 'operation_date', 'id'],
        ]
