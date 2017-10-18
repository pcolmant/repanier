# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
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
        _("Operation comment"), max_length=100, null=True, blank=True)
    operation_status = models.CharField(
        max_length=3,
        choices=LUT_BANK_TOTAL,
        default=BANK_NOT_LATEST_TOTAL,
        verbose_name=_("Bank balance status"),
        db_index=True
    )
    bank_amount_in = ModelMoneyField(
        _("Bank amount in"), help_text=_('Payment on the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)])
    bank_amount_out = ModelMoneyField(
        _("Bank amount out"), help_text=_('Payment from the account'),
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

    def get_bank_amount_in(self):
        if self.operation_status in [BANK_PROFIT, BANK_TAX]:
            return "<i>%s</i>" % (self.bank_amount_in if self.bank_amount_in.amount != DECIMAL_ZERO else EMPTY_STRING)
        else:
            return self.bank_amount_in if self.bank_amount_in.amount != DECIMAL_ZERO else EMPTY_STRING

    get_bank_amount_in.short_description = (_("Bank amount in"))
    get_bank_amount_in.allow_tags = True
    get_bank_amount_in.admin_order_field = 'bank_amount_in'

    def get_bank_amount_out(self):
        if self.operation_status in [BANK_PROFIT, BANK_TAX]:
            return "<i>%s</i>" % (self.bank_amount_out if self.bank_amount_out.amount != DECIMAL_ZERO else EMPTY_STRING)
        else:
            return self.bank_amount_out if self.bank_amount_out.amount != DECIMAL_ZERO else EMPTY_STRING

    get_bank_amount_out.short_description = (_("Bank amount out"))
    get_bank_amount_out.allow_tags = True
    get_bank_amount_out.admin_order_field = 'bank_amount_out'

    def get_producer(self):
        if self.producer is not None:
            return self.producer.short_profile_name
        else:
            if self.customer is None:
                # This is a total, show it
                from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
                if self.operation_status == BANK_LATEST_TOTAL:
                    return "<b>%s</b>" % "=== %s" % REPANIER_SETTINGS_GROUP_NAME
                else:
                    return "<b>%s</b>" % "--- %s" % REPANIER_SETTINGS_GROUP_NAME
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
                        return "<b>%s</b>" % REPANIER_SETTINGS_BANK_ACCOUNT
                    else:
                        return "<b>%s</b>" % "=============="
                else:
                    if REPANIER_SETTINGS_BANK_ACCOUNT is not None:
                        return "<b>%s</b>" % REPANIER_SETTINGS_BANK_ACCOUNT
                    else:
                        return "<b>%s</b>" % "--------------"
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


@receiver(pre_save, sender=BankAccount)
def bank_account_pre_save(sender, **kwargs):
    bank_account = kwargs["instance"]
    if bank_account.producer is None and bank_account.customer is None:
        initial_balance = BankAccount.objects.filter(
            producer__isnull=True, customer__isnull=True).order_by('?').first()
        if initial_balance is None:
            bank_account.operation_status = BANK_LATEST_TOTAL
            bank_account.permanence = None
            bank_account.operation_comment = _("Initial balance")
            bank_account.producer_invoice = None
            bank_account.customer_invoice = None
