# -*- coding: utf-8 -*-
# from django.utils.timezone import utc
from django.contrib import messages
from django.contrib.sites.models import get_current_site
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool
from repanier.const import *
from repanier.models import BankAccount
from repanier.models import Customer
from repanier.models import CustomerInvoice
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import ProducerInvoice
from repanier.models import Purchase
from repanier.task import task_producer
from repanier.tools import *
from repanier.email import email_invoice
import datetime
import thread


@transaction.atomic
def generate(request, permanence_id, permanence_distribution_date, permanence_unicode, current_site_name,
             producers_to_be_paid_set):
    validation_passed = True
    bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
    if bank_account:
        # try:
        a_bank_amount = bank_account.bank_amount_in - bank_account.bank_amount_out

        comment = _('Intermediate balance')
        customer_buyinggroup_id = None
        producer_buyinggroup_id = None

        # Get customer and producer representing this buying group
        producer = Producer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
        if producer:
            producer_buyinggroup_id = producer.id
        else:
            comment = _("At least one producer must represent the buying group.")
            validation_passed = False

        if validation_passed:
            customer = Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
            if customer:
                customer_buyinggroup_id = customer.id
                CustomerInvoice.objects.create(
                    customer=customer,
                    permanence_id=permanence_id,
                    date_previous_balance=customer.date_balance,
                    previous_balance=customer.balance,
                    total_price_with_tax=0,
                    total_vat=0,
                    total_compensation=0,
                    total_deposit=0,
                    bank_amount_in=0,
                    bank_amount_out=0,
                    date_balance=permanence_distribution_date,
                    balance=customer.balance
                )
            else:
                comment = _("At least one customer must represent the buying group.")
                validation_passed = False

        if validation_passed:
            # create invoices
            for customer in Customer.objects.filter(
                    purchase__permanence=permanence_id, represent_this_buyinggroup=False).order_by().distinct():
                CustomerInvoice.objects.create(
                    customer=customer,
                    permanence_id=permanence_id,
                    date_previous_balance=customer.date_balance,
                    previous_balance=customer.balance,
                    total_price_with_tax=0,
                    total_vat=0,
                    total_compensation=0,
                    total_deposit=0,
                    bank_amount_in=0,
                    bank_amount_out=0,
                    date_balance=permanence_distribution_date,
                    balance=customer.balance
                )
            # for producer in Producer.objects.filter(
            # permanence=permanence_id).order_by():
            # ^^^ 	if we add a producer to a permanence, order some products then remove it
            # ^^^	this query won't return this producer.
            for purchase in Purchase.objects.filter(
                    permanence=permanence_id).order_by().distinct("producer"):
                # On PostgreSQL only, you can pass positional arguments (*fields) in order to specify
                # the names of fields to which the DISTINCT should apply. This translates to a
                # SELECT DISTINCT ON SQL query. Here’s the difference. For a normal distinct() call,
                # the database compares each field in each row when determining which rows are distinct.
                # For a distinct() call with specified field names, the database will only compare the
                # specified field names.
                ProducerInvoice.objects.create(
                    producer=purchase.producer,
                    permanence_id=permanence_id,
                    date_previous_balance=purchase.producer.date_balance,
                    previous_balance=purchase.producer.balance,
                    total_price_with_tax=0,
                    total_vat=0,
                    total_compensation=0,
                    total_deposit=0,
                    bank_amount_in=0,
                    bank_amount_out=0,
                    date_balance=permanence_distribution_date,
                    balance=purchase.producer.balance
                )
            # Calculate new current balance : Purchases

            # Changed in Django 1.6.3:
            # It is now an error to execute a query with select_for_update() in autocommit mode. With earlier releases in the 1.6 series it was a no-op.

            for purchase in Purchase.objects.select_for_update().filter(
                    permanence=permanence_id,
            ).order_by():

                a_total_deposit = purchase.unit_deposit * purchase.quantity_deposit
                if purchase.invoiced_price_with_compensation:
                    a_total_price = purchase.price_with_compensation + a_total_deposit
                    a_total_vat = 0
                    a_total_compensation = purchase.price_with_compensation - purchase.price_with_vat
                else:
                    a_total_price = purchase.price_with_vat + a_total_deposit
                    a_total_vat = 0
                    if purchase.vat_level == VAT_400:
                        a_total_vat = (purchase.price_with_vat * DECIMAL_0_06).quantize(THREE_DECIMALS)
                    elif purchase.vat_level == VAT_500:
                        a_total_vat = (purchase.price_with_vat * DECIMAL_0_12).quantize(THREE_DECIMALS)
                    elif purchase.vat_level == VAT_600:
                        a_total_vat = (purchase.price_with_vat * DECIMAL_0_21).quantize(THREE_DECIMALS)
                    a_total_compensation = 0

                if purchase.is_recorded_on_customer_invoice is None:
                    if purchase.producer.id == producer_buyinggroup_id:
                        # When the producer represent the buying group, generate a compensation movement
                        customerinvoice = CustomerInvoice.objects.get(
                            customer=customer_buyinggroup_id,
                            permanence=permanence_id,
                        )
                        customerinvoice.total_price_with_tax -= a_total_price
                        customerinvoice.total_vat -= a_total_vat
                        customerinvoice.total_compensation -= a_total_compensation
                        customerinvoice.balance += a_total_price
                        customerinvoice.total_deposit -= a_total_deposit
                        customerinvoice.save()
                        Customer.objects.filter(
                            id=customer_buyinggroup_id
                        ).update(
                            date_balance=permanence_distribution_date,
                            balance=F('balance') + a_total_price
                        )
                    customerinvoice = CustomerInvoice.objects.get(
                        customer=purchase.customer,
                        permanence=permanence_id,
                    )
                    customerinvoice.total_price_with_tax += a_total_price
                    customerinvoice.total_vat += a_total_vat
                    customerinvoice.total_compensation += a_total_compensation
                    customerinvoice.balance -= a_total_price
                    customerinvoice.total_deposit += a_total_deposit
                    customerinvoice.save()
                    Customer.objects.filter(
                        id=purchase.customer_id
                    ).update(
                        date_balance=permanence_distribution_date,
                        balance=F('balance') - a_total_price
                    )
                    purchase.is_recorded_on_customer_invoice_id = customerinvoice.id
                if purchase.is_recorded_on_producer_invoice is None:
                    producerinvoice = ProducerInvoice.objects.get(
                        producer=purchase.producer,
                        permanence=permanence_id,
                    )
                    if purchase.producer.id == producer_buyinggroup_id:
                        # When the producer represent the buying group, generate a compensation movement
                        producerinvoice.bank_amount_in = a_total_price
                        producerinvoice.bank_amount_out = a_total_price
                        producerinvoice.save()
                    else:
                        producerinvoice.total_price_with_tax += a_total_price
                        producerinvoice.total_vat += a_total_vat
                        producerinvoice.total_compensation += a_total_compensation
                        producerinvoice.total_deposit += a_total_deposit
                        producerinvoice.balance += a_total_price
                        producerinvoice.save()
                        Producer.objects.filter(
                            id=purchase.producer_id
                        ).update(
                            date_balance=permanence_distribution_date,
                            balance=F('balance') + a_total_price
                        )
                    purchase.is_recorded_on_producer_invoice_id = producerinvoice.id
                purchase.save()

            # generate bank account movements
            user_message, user_message_level = task_producer.admin_generate_bank_account_movement(request,
                                                                                                  producers_to_be_paid_set,
                                                                                                  permanence_distribution_date=permanence_distribution_date)

            # Calculate new current balance : Bank

            for bank_account in BankAccount.objects.select_for_update().filter(
                    # for bank_account in BankAccount.objects.all().filter(
                    is_recorded_on_customer_invoice__isnull=True,
                    customer__isnull=False,
                    operation_date__lte=permanence_distribution_date).order_by():

                customerinvoice = CustomerInvoice.objects.filter(
                    customer=bank_account.customer,
                    permanence=permanence_id,
                ).order_by().first()
                if customerinvoice is None:
                    customerinvoice = CustomerInvoice.objects.create(
                        customer=bank_account.customer,
                        permanence_id=permanence_id,
                        date_previous_balance=bank_account.customer.date_balance,
                        previous_balance=bank_account.customer.balance,
                        total_price_with_tax=0,
                        total_vat=0,
                        total_compensation=0,
                        bank_amount_in=0,
                        bank_amount_out=0,
                        date_balance=permanence_distribution_date,
                        balance=bank_account.customer.balance
                    )
                bank_amount_in = bank_account.bank_amount_in
                a_bank_amount += bank_amount_in
                bank_amount_out = bank_account.bank_amount_out
                a_bank_amount -= bank_amount_out
                customerinvoice.bank_amount_in += bank_amount_in
                customerinvoice.bank_amount_out += bank_amount_out
                customerinvoice.balance += (bank_amount_in - bank_amount_out)
                customerinvoice.save()
                Customer.objects.filter(
                    id=bank_account.customer_id
                ).update(
                    date_balance=permanence_distribution_date,
                    balance=F('balance') + bank_amount_in - bank_amount_out
                )
                bank_account.is_recorded_on_customer_invoice_id = customerinvoice.id
                bank_account.permanence_id = permanence_id
                bank_account.save()

            for bank_account in BankAccount.objects.select_for_update().filter(
                    # for bank_account in BankAccount.objects.all().filter(
                    is_recorded_on_producer_invoice__isnull=True,
                    producer__isnull=False,
                    operation_date__lte=permanence_distribution_date).order_by():

                producerinvoice = ProducerInvoice.objects.filter(
                    producer=bank_account.producer,
                    permanence=permanence_id,
                ).order_by().first()
                if producerinvoice is None:
                    producerinvoice = ProducerInvoice.objects.create(
                        producer=bank_account.producer,
                        permanence_id=permanence_id,
                        date_previous_balance=bank_account.producer.date_balance,
                        previous_balance=bank_account.producer.balance,
                        total_price_with_tax=0,
                        total_vat=0,
                        total_compensation=0,
                        bank_amount_in=0,
                        bank_amount_out=0,
                        date_balance=permanence_distribution_date,
                        balance=bank_account.producer.balance
                    )
                bank_amount_in = bank_account.bank_amount_in
                a_bank_amount += bank_amount_in
                bank_amount_out = bank_account.bank_amount_out
                a_bank_amount -= bank_amount_out
                producerinvoice.bank_amount_in += bank_amount_in
                producerinvoice.bank_amount_out += bank_amount_out
                producerinvoice.balance += (bank_amount_in - bank_amount_out)
                producerinvoice.save()
                Producer.objects.filter(
                    id=bank_account.producer_id
                ).update(
                    date_balance=permanence_distribution_date,
                    balance=F('balance') + bank_amount_in - bank_amount_out
                )
                bank_account.permanence_id = permanence_id
                bank_account.is_recorded_on_producer_invoice_id = producerinvoice.id
                bank_account.save()

            BankAccount.objects.filter(
                operation_status=BANK_LATEST_TOTAL
            ).order_by().update(
                operation_status=BANK_NOT_LATEST_TOTAL
            )
            # Impotant : Create a new bank total for this permanence even if there is no bank movement
            BankAccount.objects.create(
                permanence_id=permanence_id,
                producer=None,
                customer=None,
                operation_date=permanence_distribution_date,
                operation_status=BANK_LATEST_TOTAL,
                operation_comment=comment,
                bank_amount_in=a_bank_amount if a_bank_amount >= 0 else 0,
                bank_amount_out=-a_bank_amount if a_bank_amount < 0 else 0,
                is_recorded_on_customer_invoice=None,
                is_recorded_on_producer_invoice=None
            )
            # except Exception, e:
    # validation_passed = False

    if validation_passed:
        # now = datetime.datetime.utcnow().replace(tzinfo=utc)
        now = timezone.localtime(timezone.now())
        menu_pool.clear()
        Permanence.objects.filter(id=permanence_id).update(status=PERMANENCE_DONE, is_done_on=now)
    else:
        Permanence.objects.filter(id=permanence_id).update(status=PERMANENCE_INVOICES_VALIDATION_FAILED)


@transaction.atomic
def cancel(permanence_id):
    for customer_invoice in CustomerInvoice.objects.filter(
            permanence_id=permanence_id).order_by().distinct():
        customer = Customer.objects.get(id=customer_invoice.customer_id)
        customer.balance = customer_invoice.previous_balance
        customer.date_balance = customer_invoice.date_previous_balance
        customer.save(update_fields=['balance', 'date_balance'])
        Purchase.objects.all().filter(
            is_recorded_on_customer_invoice_id=customer_invoice.id
        ).update(
            is_recorded_on_customer_invoice=None
        )
        BankAccount.objects.all().filter(
            is_recorded_on_customer_invoice_id=customer_invoice.id
        ).update(
            is_recorded_on_customer_invoice=None
        )
    for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=permanence_id).order_by().distinct():
        producer = Producer.objects.get(id=producer_invoice.producer_id)
        producer.balance = producer_invoice.previous_balance
        producer.date_balance = producer_invoice.date_previous_balance
        producer.save(update_fields=['balance', 'date_balance'])
        Purchase.objects.all().filter(
            is_recorded_on_producer_invoice_id=producer_invoice.id
        ).update(
            is_recorded_on_producer_invoice=None
        )
        BankAccount.objects.all().filter(
            is_recorded_on_producer_invoice_id=producer_invoice.id
        ).update(
            is_recorded_on_producer_invoice=None
        )
    CustomerInvoice.objects.filter(
        permanence_id=permanence_id).order_by().delete()
    ProducerInvoice.objects.filter(
        permanence_id=permanence_id).order_by().delete()
    BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().delete()
    bank_account = BankAccount.objects.filter(
        customer=None,
        producer=None).order_by('-id').first()
    if bank_account:
        bank_account.operation_status = BANK_LATEST_TOTAL
        bank_account.save(update_fields=[
            'operation_status'
        ])
        # Delete also all payments recoreded to producers
        BankAccount.objects.filter(id__gt=bank_account.id, producer__isnull=False,
                                   customer__isnull=True).order_by().delete()
    else:
        # Delete also all payments recoreded to producers
        BankAccount.objects.filter(producer__isnull=False, customer__isnull=True).order_by().delete()
    Permanence.objects.filter(id=permanence_id).update(status=PERMANENCE_SEND, is_done_on=None)
    menu_pool.clear()


def admin_generate(request, producers_to_be_paid_set=Producer.objects.none(), permanence_id=None):
    user_message = _("You can only generate invoices when the permanence status is 'send'.")
    user_message_level = messages.WARNING
    permanence = Permanence.objects.filter(id=permanence_id).order_by().first()
    if permanence is not None:
        current_site = get_current_site(request)
        if permanence.status == PERMANENCE_SEND:
            generate(request, permanence.id, permanence.distribution_date, permanence.__unicode__(), current_site.name,
                     producers_to_be_paid_set)
            user_message = _("Action performed.")
            user_message_level = messages.INFO
        else:
            if permanence.status == PERMANENCE_INVOICES_VALIDATION_FAILED:
                user_message = _(
                    "The permanence status says there is an error. You must cancel the invoice then correct, before retrying.")
                user_message_level = messages.WARNING
    return user_message, user_message_level


def admin_send(request, queryset):
    current_site = get_current_site(request)
    for permanence in queryset[:1]:
        if permanence.status == PERMANENCE_DONE:
            thread.start_new_thread(email_invoice.send, (permanence.id, current_site.name))
            user_message = _("Emails containing the invoices will be send to the customers and the producers.")
            user_message_level = messages.INFO
        else:
            user_message = _("The status of this permanence prohibit you to send invoices.")
            user_message_level = messages.ERROR
    return user_message, user_message_level


def admin_cancel(request, queryset):
    # TODO : Use the bank account total record
    user_message = _("The status of this permanence prohibit you to close invoices.")
    user_message_level = messages.ERROR
    latest_customer_invoice = CustomerInvoice.objects.order_by('-id').first()
    if latest_customer_invoice:
        for permanence in queryset[:1]:
            if permanence.status in [PERMANENCE_WAIT_FOR_DONE, PERMANENCE_INVOICES_VALIDATION_FAILED, PERMANENCE_DONE]:
                if latest_customer_invoice.permanence.id == permanence.id:
                    # This is well the latest closed permanence. The invoices can be cancelled without damages.
                    cancel(permanence.id)
                    user_message = _("The selected invoice has been canceled.")
                    user_message_level = messages.INFO
                else:
                    user_message = _("The selected invoice is not the latest invoice.")
                    user_message_level = messages.ERROR
    return user_message, user_message_level



