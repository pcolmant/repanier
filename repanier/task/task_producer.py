# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.sites.models import get_current_site
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.models import BankAccount
from repanier.models import ProducerInvoice
from repanier.settings import *


def admin_generate_bank_account_movement(request, queryset, permanence_distribution_date=None):
    user_message = _("Action canceled by the system. No latest bank total has been set.")
    user_message_level = messages.ERROR
    current_site = get_current_site(request)
    # operation_date = timezone.localtime(timezone.now()).date() if permanence_distribution_date == None else permanence_distribution_date
    operation_date = timezone.localtime(timezone.now()).date()
    bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by("-id").first()
    bank_latest_total_id = None
    if bank_account:
        if bank_account.operation_date > operation_date:
            operation_date = bank_account.operation_date
        bank_latest_total_id = bank_account.id
    if bank_latest_total_id is not None:
        counter = 0
        counter_max = 0
        for producer in queryset:
            counter_max += 1
            if producer.balance > 0:
                counter += 1
                bank_amount_in = 0
                bank_amount_out = 0
                for bank_account in BankAccount.objects.filter(producer_id=producer.id,
                                                               operation_date__lte=operation_date,
                                                               is_recorded_on_producer_invoice__isnull=True).order_by():
                    bank_amount_in += bank_account.bank_amount_in
                    bank_amount_out += bank_account.bank_amount_out
                bank_balance = bank_amount_out - bank_amount_in
                delta = 0
                if producer.balance >= bank_balance:
                    delta = (producer.balance - bank_balance).quantize(TWO_DECIMALS)
                if delta > 0:
                    producer_last_invoice = ProducerInvoice.objects.filter(producer_id=producer.id).order_by(
                        "-id").first()
                    msg = unicode(_('Delivery')) + " " + current_site.name + " - " + unicode(
                        REPANIER_PERMANENCE_ON_NAME) + permanence_distribution_date.strftime('%d-%m-%Y') + ". " + unicode(
                        _('Thanks!'))
                    if producer_last_invoice:
                        if producer_last_invoice.total_price_with_tax == delta:
                            msg = unicode(_('Delivery')) + " " + current_site.name + " - " + unicode(
                                REPANIER_PERMANENCE_ON_NAME) + producer_last_invoice.date_balance.strftime(
                                '%d-%m-%Y') + ". " + unicode(_('Thanks!'))
                        else:
                            msg = unicode(_('Delivery')) + " " + current_site.name + " - " + unicode(
                                _('up to')) + " " + permanence_distribution_date.strftime('%d-%m-%Y') + " " + unicode(
                                _('(included)')) + ". " + unicode(_('Thanks!'))
                    bank_account = BankAccount.objects.filter(producer_id=producer.id, operation_date=operation_date,
                                                              operation_comment=msg).order_by("-id").first()
                    if bank_account:
                        if bank_account.is_recorded_on_producer_invoice is None:
                            bank_account.bank_amount_in = 0
                            bank_account.bank_amount_out += delta
                            bank_account.operation_comment = msg
                            bank_account.save()
                        else:
                            BankAccount.objects.create(
                                permanence_id=None,
                                producer_id=producer.id,
                                customer=None,
                                operation_date=operation_date,
                                operation_status=BANK_NOT_LATEST_TOTAL,
                                operation_comment=msg,
                                bank_amount_in=0,
                                bank_amount_out=delta,
                                is_recorded_on_customer_invoice=None,
                                is_recorded_on_producer_invoice=None
                            )
                    else:
                        BankAccount.objects.create(
                            permanence_id=None,
                            producer_id=producer.id,
                            customer=None,
                            operation_date=operation_date,
                            operation_status=BANK_NOT_LATEST_TOTAL,
                            operation_comment=msg,
                            bank_amount_in=0,
                            bank_amount_out=delta,
                            is_recorded_on_customer_invoice=None,
                            is_recorded_on_producer_invoice=None
                        )
        if counter == 0:
            user_message = _("No bank account movement generated because there was nothing to pay.")
            user_message_level = messages.INFO
        elif counter == 1:
            if counter == counter_max:
                user_message = _("The bank account movement has been generated.")
                user_message_level = messages.INFO
            else:
                user_message = _(
                    "At least one bank account movement has not been generated because there was nothing to pay or there is a conflit with the latest bank total.")
                user_message_level = messages.WARNING
        else:
            if counter == counter_max:
                user_message = _("The bank account movement have been generated.")
                user_message_level = messages.INFO
            else:
                user_message = _(
                    "At least one bank account movement has not been generated because there was nothing to pay or there is a conflit with the latest bank total.")
                user_message_level = messages.WARNING
    return user_message, user_message_level
