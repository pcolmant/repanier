# -*- coding: utf-8 -*-

from django.conf import settings
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
from repanier.const import *
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import ProducerInvoice
from repanier.tools import cap


def admin_generate_bank_account_movement(
        permanence, payment_date,
        customer_buyinggroup):

    for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=permanence.id,
            invoice_sort_order__isnull=True,
            to_be_paid=True
    ).select_related("producer"):
        # We have to pay something
        producer=producer_invoice.producer
        result_set = BankAccount.objects.filter(
            producer_id=producer.id, producer_invoice__isnull=True
        ).order_by('?').aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
        if result_set["bank_amount_in__sum"] is not None:
            bank_in = RepanierMoney(result_set["bank_amount_in__sum"])
        else:
            bank_in = REPANIER_MONEY_ZERO
        if result_set["bank_amount_out__sum"] is not None:
            bank_out = RepanierMoney(result_set["bank_amount_out__sum"])
        else:
            bank_out = REPANIER_MONEY_ZERO
        bank_not_invoiced = bank_out - bank_in

        if producer.balance.amount != DECIMAL_ZERO or producer_invoice.to_be_invoiced_balance.amount != DECIMAL_ZERO or bank_not_invoiced != DECIMAL_ZERO:

            delta = (producer_invoice.to_be_invoiced_balance.amount - bank_not_invoiced.amount).quantize(TWO_DECIMALS)
            if delta > DECIMAL_ZERO:

                if producer_invoice.invoice_reference:
                    operation_comment = producer_invoice.invoice_reference
                else:
                    if producer.represent_this_buyinggroup:
                        operation_comment = permanence.get_permanence_display()
                    else:
                        if producer_invoice is not None:
                            if producer_invoice.total_price_with_tax.amount == delta:
                                operation_comment = _("Delivery %(current_site)s - %(permanence)s. Thanks!") \
                                                    % {
                                                        'current_site': REPANIER_SETTINGS_GROUP_NAME,
                                                        'permanence'  : permanence.get_permanence_display()
                                                    }
                            else:
                                operation_comment = _(
                                    "Deliveries %(current_site)s - up to the %(permanence)s (included). Thanks!") \
                                                    % {
                                                        'current_site': REPANIER_SETTINGS_GROUP_NAME,
                                                        'permanence'  : permanence.get_permanence_display()
                                                    }
                        else:
                            operation_comment = _(
                                "Deliveries %(current_site)s - up to %(payment_date)s (included). Thanks!") \
                                                % {
                                                    'current_site': REPANIER_SETTINGS_GROUP_NAME,
                                                    'payment_date': payment_date.strftime(
                                                        settings.DJANGO_SETTINGS_DATE)
                                                }

                BankAccount.objects.create(
                    permanence_id=None,
                    producer_id=producer.id,
                    customer=None,
                    operation_date=payment_date,
                    operation_status=BANK_CALCULATED_INVOICE,
                    operation_comment=cap(operation_comment, 100),
                    bank_amount_out=delta,
                    customer_invoice=None,
                    producer_invoice=None
                )

        delta = (producer.balance.amount - producer_invoice.to_be_invoiced_balance.amount).quantize(TWO_DECIMALS)
        if delta != DECIMAL_ZERO:
            # Profit or loss for the group
            operation_comment = _("Correction %(producer)s") \
                                % {
                                    'producer': producer.short_profile_name
                                }
            BankAccount.objects.create(
                permanence_id=permanence.id,
                producer=None,
                customer_id=customer_buyinggroup.id,
                operation_date=payment_date,
                operation_status=BANK_PROFIT,
                operation_comment=cap(operation_comment, 100),
                bank_amount_in=delta if delta > DECIMAL_ZERO else DECIMAL_ZERO,
                bank_amount_out=-delta if delta < DECIMAL_ZERO else DECIMAL_ZERO,
                customer_invoice_id=None,
                producer_invoice=None
            )
        producer_invoice.balance.amount -= delta
        producer_invoice.save(update_fields=['balance'])
        producer.balance.amount -= delta
        producer.save(update_fields=['balance'])


    return
