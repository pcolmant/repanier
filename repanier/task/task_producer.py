# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.models import get_current_site
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.models import BankAccount
from repanier.models import ProducerInvoice
from repanier.tools import cap


def admin_generate_bank_account_movement(request, queryset, permanence=None, payment_date=None):
    if permanence is not None and payment_date is not None:
        current_site = get_current_site(request)
        bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).only("id").order_by().first()
        if bank_account is not None:
            counter = 0
            counter_max = 0
            for producer in queryset:
                counter_max += 1
                if producer.balance > DECIMAL_ZERO:
                    counter += 1
                    bank_amount_in = DECIMAL_ZERO
                    bank_amount_out = DECIMAL_ZERO
                    for bank_account in BankAccount.objects.filter(producer_id=producer.id,
                                                                   operation_date__lte=payment_date,
                                                                   producer_invoice__isnull=True).order_by():
                        bank_amount_in += bank_account.bank_amount_in
                        bank_amount_out += bank_account.bank_amount_out
                    bank_balance = bank_amount_out - bank_amount_in
                    delta = DECIMAL_ZERO
                    if producer.balance >= bank_balance:
                        delta = (producer.balance - bank_balance).quantize(TWO_DECIMALS)
                    if delta > DECIMAL_ZERO:
                        current_producer_invoice = ProducerInvoice.objects.filter(
                            producer_id=producer.id, permanence_id=permanence.id).first()
                        if current_producer_invoice is not None:
                            if current_producer_invoice.total_price_with_tax == delta:
                                operation_comment = _("Delivery %(current_site)s - %(permanence)s. Thanks!") \
                                    % {
                                        'current_site': current_site.name,
                                        'permanence': permanence.__unicode__()
                                    }
                            else:
                                operation_comment = _("Deliveries %(current_site)s - up to the %(permanence)s (included). Thanks!") \
                                    % {
                                        'current_site': current_site.name,
                                        'permanence': permanence.__unicode__()
                                    }
                        else:
                            operation_comment = _("Deliveries %(current_site)s - up to %(payment_date)s (included). Thanks!") \
                                % {
                                    'current_site': current_site.name,
                                    'payment_date': payment_date.strftime('%d-%m-%Y')
                                }
                        BankAccount.objects.create(
                            permanence_id=None,
                            producer_id=producer.id,
                            customer=None,
                            operation_date=payment_date,
                            operation_status=BANK_NOT_LATEST_TOTAL,
                            operation_comment=cap(operation_comment, 100),
                            bank_amount_in=0,
                            bank_amount_out=delta,
                            customer_invoice=None,
                            producer_invoice=None
                        )
    return
