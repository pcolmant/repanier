# -*- coding: utf-8 -*-
from decimal import getcontext, ROUND_HALF_UP
# from django.utils.timezone import utc
import uuid
from django.contrib import messages
from django.contrib.sites.models import get_current_site
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool
from repanier.const import *
from repanier.models import BankAccount
from repanier.models import Customer
from repanier.models import CustomerInvoice
from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import Product
from repanier.models import ProducerInvoice
from repanier.models import Purchase
from repanier.task import task_producer
from repanier.tools import *
from repanier.email import email_invoice
import datetime
import thread


@transaction.atomic
def generate(request, permanence, payment_date, producers_to_be_paid_set):
    if RepanierSettings.invoice:
        validation_passed = True
        getcontext().rounding=ROUND_HALF_UP
        new_bank_latest_total = DECIMAL_ZERO
        bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
        if bank_account is None:
            # If not latest total exists, create it with operation date before all movements
            bank_account = BankAccount.objects.all().order_by("operation_date").first()
            if bank_account is None:
                bank_account = BankAccount.objects.create(operation_date = timezone.localtime(timezone.now()).date())
            if bank_account is not None:
                operation_date = bank_account.operation_date
                operation_date += datetime.timedelta(days=-1)
                bank_account.save()
        if bank_account is not None:
            new_bank_latest_total = bank_account.bank_amount_in - bank_account.bank_amount_out
            customer_buyinggroup = None

            # Get customer and producer representing this buying group
            producer_buyinggroup = Producer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
            if producer_buyinggroup is None:
                producer_buyinggroup = Producer.objects.create(
                    short_profile_name="z-%s" % RepanierSettings.group_name,
                    long_profile_name=RepanierSettings.group_name,
                    represent_this_buyinggroup=True
                )
            if producer_buyinggroup is not None:
                customer_buyinggroup = Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
                if customer_buyinggroup is None:
                    user = User.objects.create_user(
                        username="z-%s" % RepanierSettings.group_name, email=None, password=uuid.uuid1().hex,
                        first_name="", last_name=RepanierSettings.group_name)
                    customer_buyinggroup = Customer.objects.create(
                        user=user,
                        short_basket_name="z-%s" % RepanierSettings.group_name,
                        long_basket_name=RepanierSettings.group_name,
                        represent_this_buyinggroup=True
                    )

                if customer_buyinggroup is None:
                    # At least one customer must represent the buying group.
                    validation_passed = False
            else:
                # At least one producer must represent the buying group.
                validation_passed = False
        else:
            # At least one BANK_LATEST_TOTAL must exists.
            validation_passed = False

        if validation_passed:
            for customer_invoice in CustomerInvoice.objects.filter(
                    permanence_id=permanence.id):
                customer_invoice.date_previous_balance = customer_invoice.customer.date_balance
                customer_invoice.previous_balance = customer_invoice.customer.balance
                customer_invoice.total_price_with_tax = DECIMAL_ZERO
                customer_invoice.total_vat = DECIMAL_ZERO
                customer_invoice.total_compensation = DECIMAL_ZERO
                customer_invoice.total_deposit = DECIMAL_ZERO
                customer_invoice.bank_amount_in = DECIMAL_ZERO
                customer_invoice.bank_amount_out = DECIMAL_ZERO
                customer_invoice.date_balance = payment_date
                customer_invoice.balance = customer_invoice.customer.balance
                customer_invoice.save()
            for producer_invoice in ProducerInvoice.objects.filter(
                    permanence_id=permanence.id):
                producer_invoice.date_previous_balance = producer_invoice.producer.date_balance
                producer_invoice.previous_balance = producer_invoice.producer.balance
                producer_invoice.total_price_with_tax = DECIMAL_ZERO
                producer_invoice.total_vat = DECIMAL_ZERO
                producer_invoice.total_compensation = DECIMAL_ZERO
                producer_invoice.total_deposit = DECIMAL_ZERO
                producer_invoice.bank_amount_in = DECIMAL_ZERO
                producer_invoice.bank_amount_out = DECIMAL_ZERO
                producer_invoice.date_balance = payment_date
                producer_invoice.balance = producer_invoice.producer.balance
                producer_invoice.save()
            # Calculate new current balance : Purchases

            # Changed in Django 1.6.3:
            # It is now an error to execute a query with select_for_update() in autocommit mode. With earlier releases in the 1.6 series it was a no-op.

            for purchase in Purchase.objects.select_for_update().filter(
                    permanence=permanence.id,
            ).order_by():
                offer_item = purchase.offer_item
                deposit = offer_item.unit_deposit * purchase.quantity_invoiced
                if purchase.invoiced_price_with_compensation:
                    purchase_vat = DECIMAL_ZERO
                    selling_vat = DECIMAL_ZERO
                    compensation = offer_item.compensation * purchase.quantity_invoiced
                else:
                    purchase_vat = offer_item.producer_vat * purchase.quantity_invoiced
                    selling_vat = offer_item.customer_vat * purchase.quantity_invoiced
                    if selling_vat > purchase_vat:
                        # Bees Coop : The invoiced VAT is the VAT issued from the producer purchase price
                        selling_vat = purchase_vat
                    compensation = DECIMAL_ZERO
                selling_price = purchase.selling_price
                purchase_price = purchase.purchase_price
                if selling_price < purchase_price:
                    purchase_price = selling_price
                    purchase_vat = selling_vat
                customerinvoice = CustomerInvoice.objects.filter(
                    customer=purchase.customer,
                    permanence=permanence.id,
                ).order_by().first()
                if customerinvoice is None:
                    customerinvoice = CustomerInvoice.objects.create(
                        customer=purchase.customer,
                        permanence_id=permanence.id,
                        date_previous_balance=purchase.customer.date_balance,
                        previous_balance=purchase.customer.balance,
                        total_price_with_tax=DECIMAL_ZERO,
                        total_vat=DECIMAL_ZERO,
                        total_compensation=DECIMAL_ZERO,
                        bank_amount_in=DECIMAL_ZERO,
                        bank_amount_out=DECIMAL_ZERO,
                        date_balance=payment_date,
                        balance=purchase.customer.balance
                    )
                customerinvoice.total_price_with_tax += selling_price
                customerinvoice.total_vat += selling_vat
                customerinvoice.total_compensation += compensation
                customerinvoice.total_deposit += deposit
                customerinvoice.balance -= selling_price
                customerinvoice.save()
                Customer.objects.filter(
                    id=purchase.customer_id
                ).update(
                    date_balance=payment_date,
                    balance=F('balance') - selling_price
                )
                producerinvoice = ProducerInvoice.objects.filter(
                    producer=purchase.producer,
                    permanence=permanence.id,
                ).order_by().first()
                if producerinvoice is None:
                    producerinvoice = ProducerInvoice.objects.create(
                        producer=purchase.producer,
                        permanence_id=permanence.id,
                        date_previous_balance=purchase.producer.date_balance,
                        previous_balance=purchase.producer.balance,
                        total_price_with_tax=0,
                        total_vat=0,
                        total_compensation=0,
                        bank_amount_in=0,
                        bank_amount_out=0,
                        date_balance=payment_date,
                        balance=purchase.producer.balance
                    )
                producerinvoice.total_price_with_tax += purchase_price
                producerinvoice.total_vat += purchase_vat
                producerinvoice.total_compensation += compensation
                producerinvoice.total_deposit += deposit
                producerinvoice.balance += purchase_price
                producerinvoice.save()
                Producer.objects.filter(
                    id=purchase.producer_id
                ).update(
                    date_balance=payment_date,
                    balance=F('balance') + purchase_price
                )
            # Remove the stock and add the "add_2_stock" product and remove product taken from stock
            for offer_item in OfferItem.objects.filter(
                        is_active=True, manage_stock=True, permanence_id=permanence.id
                    ).order_by():
                qty, stock = offer_item.get_producer_qty_stock_invoiced()
                delta = qty - offer_item.quantity_invoiced + offer_item.add_2_stock
                if delta != DECIMAL_ZERO:
                    if offer_item.customer_unit_price < offer_item.producer_unit_price:
                        purchase_price = ((offer_item.customer_unit_price +
                            offer_item.unit_deposit) * delta).quantize(TWO_DECIMALS)
                        purchase_vat = offer_item.customer_vat * delta
                    else:
                        purchase_price = ((offer_item.producer_unit_price +
                            offer_item.unit_deposit) * delta).quantize(TWO_DECIMALS)
                        purchase_vat = offer_item.producer_vat * delta
                    deposit = offer_item.unit_deposit * delta
                    compensation = DECIMAL_ZERO
                    producerinvoice = ProducerInvoice.objects.get(
                        producer=offer_item.producer,
                        permanence=permanence,
                    )
                    producerinvoice.total_price_with_tax += purchase_price
                    producerinvoice.total_vat += purchase_vat
                    producerinvoice.total_compensation += compensation
                    producerinvoice.total_deposit += deposit
                    producerinvoice.balance += purchase_price
                    producerinvoice.save()
                    Producer.objects.filter(
                        id=offer_item.producer_id
                    ).update(
                        date_balance=payment_date,
                        balance=F('balance') + purchase_price
                    )
                    # // xslx_stock and task_invoice
                    offer_item.new_stock = offer_item.stock - stock + offer_item.add_2_stock
                    offer_item.previous_add_2_stock = offer_item.add_2_stock
                    offer_item.previous_producer_unit_price = offer_item.producer_unit_price
                    offer_item.previous_unit_deposit = offer_item.unit_deposit
                    Product.objects.filter(
                        id=offer_item.product_id, stock=offer_item.stock
                    ).update(stock=offer_item.new_stock)
                    offer_item.save()

            # Calculate if the customer representing the buying group has received/lost money
            # Either from initial negative customer balance or subscription
            result_set = Customer.objects.aggregate(Sum('balance'))
            customer_total_balance = result_set["balance__sum"]
            result_set = Producer.objects.aggregate(Sum('balance'))
            producer_total_balance = result_set["balance__sum"]
            delta_wrong_encoding = customer_total_balance + producer_total_balance - new_bank_latest_total
            # print("---------------------------------")
            # print("customer_total_balance : %f" % customer_total_balance)
            # print("producer_total_balance : %f" % producer_total_balance)
            # print("new_bank_latest_total : %f" % new_bank_latest_total)
            # print("delta_wrong_encoding : %f" % delta_wrong_encoding)
            if delta_wrong_encoding != DECIMAL_ZERO:
                previous_date_balance = customer_buyinggroup.date_balance
                previous_balance = customer_buyinggroup.balance
                Customer.objects.filter(
                    id=customer_buyinggroup.id
                ).update(
                    balance=F('balance') - delta_wrong_encoding,
                    date_balance=payment_date
                )
                customer_buyinggroup = Customer.objects.filter(is_active=True, represent_this_buyinggroup=True).order_by().first()
                customer_invoice = CustomerInvoice.objects.filter(
                    permanence_id=permanence.id, customer=customer_buyinggroup.id
                ).order_by().first()
                if customer_invoice is None:
                    CustomerInvoice.objects.create(
                        customer=customer_buyinggroup,
                        permanence_id=permanence.id,
                        date_previous_balance=previous_date_balance,
                        previous_balance=previous_balance,
                        total_price_with_tax=DECIMAL_ZERO,
                        total_vat=DECIMAL_ZERO,
                        total_compensation=DECIMAL_ZERO,
                        bank_amount_in=DECIMAL_ZERO,
                        bank_amount_out=DECIMAL_ZERO,
                        date_balance=payment_date,
                        balance=customer_buyinggroup.balance
                    )
                    customer_invoice = CustomerInvoice.objects.filter(
                        permanence_id=permanence.id, customer=customer_buyinggroup.id
                    ).order_by().first()
                else:
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id, customer=customer_buyinggroup.id
                    ).update(
                        balance=customer_buyinggroup.balance)
                BankAccount.objects.create(
                    permanence_id=permanence.id,
                    producer=None,
                    customer_id=customer_buyinggroup.id,
                    operation_date=payment_date,
                    operation_status=BANK_COMPENSATION,
                    operation_comment=_("Lost") if delta_wrong_encoding >= DECIMAL_ZERO else _("Profit"),
                    bank_amount_in=-delta_wrong_encoding if delta_wrong_encoding < DECIMAL_ZERO else DECIMAL_ZERO,
                    bank_amount_out=delta_wrong_encoding if delta_wrong_encoding >= DECIMAL_ZERO else DECIMAL_ZERO,
                    customer_invoice_id=customer_invoice.id,
                    producer_invoice=None
                )
                producer_invoice = ProducerInvoice.objects.filter(
                    permanence_id=permanence.id, producer=producer_buyinggroup.id
                ).order_by().first()
                if producer_invoice is None:
                    producer_invoice = ProducerInvoice.objects.create(
                        producer=producer_buyinggroup,
                        permanence_id=permanence.id,
                        date_previous_balance=producer_buyinggroup.date_balance,
                        previous_balance=producer_buyinggroup.balance,
                        total_price_with_tax=DECIMAL_ZERO,
                        total_vat=DECIMAL_ZERO,
                        total_compensation=DECIMAL_ZERO,
                        bank_amount_in=DECIMAL_ZERO,
                        bank_amount_out=DECIMAL_ZERO,
                        date_balance=payment_date,
                        balance=producer_buyinggroup.balance
                    )
                BankAccount.objects.create(
                    permanence_id=permanence.id,
                    producer_id=producer_buyinggroup.id,
                    customer=None,
                    operation_date=payment_date,
                    operation_status=BANK_COMPENSATION,
                    operation_comment=_("Compensation for lost") if delta_wrong_encoding >= DECIMAL_ZERO else _("Compensation for profit"),
                    bank_amount_in=delta_wrong_encoding if delta_wrong_encoding >= DECIMAL_ZERO else DECIMAL_ZERO,
                    bank_amount_out=-delta_wrong_encoding if delta_wrong_encoding < DECIMAL_ZERO else DECIMAL_ZERO,
                    customer_invoice=None,
                    producer_invoice_id=producer_invoice.id
                )

            # generate bank account movements
            task_producer.admin_generate_bank_account_movement(
                request, producers_to_be_paid_set, permanence=permanence, payment_date=payment_date)

            # Calculate new current balance : Bank
            for bank_account in BankAccount.objects.select_for_update().filter(
                    customer_invoice__isnull=True,
                    customer__isnull=False,
                    operation_date__lte=payment_date).order_by():

                customerinvoice = CustomerInvoice.objects.filter(
                    customer=bank_account.customer,
                    permanence=permanence.id,
                ).order_by().first()
                if customerinvoice is None:
                    customerinvoice = CustomerInvoice.objects.create(
                        customer=bank_account.customer,
                        permanence_id=permanence.id,
                        date_previous_balance=bank_account.customer.date_balance,
                        previous_balance=bank_account.customer.balance,
                        total_price_with_tax=DECIMAL_ZERO,
                        total_vat=DECIMAL_ZERO,
                        total_compensation=DECIMAL_ZERO,
                        bank_amount_in=DECIMAL_ZERO,
                        bank_amount_out=DECIMAL_ZERO,
                        date_balance=payment_date,
                        balance=bank_account.customer.balance
                    )
                bank_amount_in = bank_account.bank_amount_in
                new_bank_latest_total += bank_amount_in
                bank_amount_out = bank_account.bank_amount_out
                new_bank_latest_total -= bank_amount_out
                customerinvoice.bank_amount_in += bank_amount_in
                customerinvoice.bank_amount_out += bank_amount_out
                customerinvoice.balance += (bank_amount_in - bank_amount_out)
                customerinvoice.save()
                Customer.objects.filter(
                    id=bank_account.customer_id
                ).update(
                    date_balance=payment_date,
                    balance=F('balance') + bank_amount_in - bank_amount_out
                )
                bank_account.customer_invoice_id = customerinvoice.id
                bank_account.permanence_id = permanence.id
                bank_account.save()

            for bank_account in BankAccount.objects.select_for_update().filter(
                    producer_invoice__isnull=True,
                    producer__isnull=False,
                    operation_date__lte=payment_date).order_by():

                producerinvoice = ProducerInvoice.objects.filter(
                    producer=bank_account.producer,
                    permanence=permanence.id,
                ).order_by().first()
                if producerinvoice is None:
                    producerinvoice = ProducerInvoice.objects.create(
                        producer=bank_account.producer,
                        permanence_id=permanence.id,
                        date_previous_balance=bank_account.producer.date_balance,
                        previous_balance=bank_account.producer.balance,
                        total_price_with_tax=0,
                        total_vat=0,
                        total_compensation=0,
                        bank_amount_in=0,
                        bank_amount_out=0,
                        date_balance=payment_date,
                        balance=bank_account.producer.balance
                    )
                bank_amount_in = bank_account.bank_amount_in
                new_bank_latest_total += bank_amount_in
                bank_amount_out = bank_account.bank_amount_out
                new_bank_latest_total -= bank_amount_out
                producerinvoice.bank_amount_in += bank_amount_in
                producerinvoice.bank_amount_out += bank_amount_out
                producerinvoice.balance += (bank_amount_in - bank_amount_out)
                producerinvoice.save()
                Producer.objects.filter(
                    id=bank_account.producer_id
                ).update(
                    date_balance=payment_date,
                    balance=F('balance') + bank_amount_in - bank_amount_out
                )
                bank_account.permanence_id = permanence.id
                bank_account.producer_invoice_id = producerinvoice.id
                bank_account.save()

            BankAccount.objects.filter(
                operation_status=BANK_LATEST_TOTAL
            ).order_by().update(
                operation_status=BANK_NOT_LATEST_TOTAL
            )
            # Impotant : Create a new bank total for this permanence even if there is no bank movement
            bank_account = BankAccount.objects.create(
                permanence_id=permanence.id,
                producer=None,
                customer=None,
                operation_date=payment_date,
                operation_status=BANK_LATEST_TOTAL,
                operation_comment=cap(permanence, 100),
                bank_amount_in=new_bank_latest_total if new_bank_latest_total >= DECIMAL_ZERO else DECIMAL_ZERO,
                bank_amount_out=-new_bank_latest_total if new_bank_latest_total < DECIMAL_ZERO else DECIMAL_ZERO,
                customer_invoice=None,
                producer_invoice=None
            )
            ProducerInvoice.objects.filter(permanence_id=permanence.id).update(invoice_sort_order=bank_account.id)
            CustomerInvoice.objects.filter(permanence_id=permanence.id).update(invoice_sort_order=bank_account.id)

        if validation_passed:
            permanence.status = PERMANENCE_DONE
            if permanence.highest_status < PERMANENCE_DONE:
                permanence.highest_status = PERMANENCE_DONE
            permanence.payment_date=payment_date
            # Important : This also update the "update time" field of the permanence
            permanence.save()
        else:
            permanence.status = PERMANENCE_INVOICES_VALIDATION_FAILED
            if permanence.highest_status < PERMANENCE_INVOICES_VALIDATION_FAILED:
                permanence.highest_status = PERMANENCE_INVOICES_VALIDATION_FAILED
            # Important : This also update the "update time" field of the permanence
            permanence.save()
    else:
        permanence.status = PERMANENCE_ARCHIVED
        if permanence.highest_status < PERMANENCE_ARCHIVED:
            permanence.highest_status = PERMANENCE_ARCHIVED
        permanence.payment_date=payment_date
        # Important : This also update the "update time" field of the permanence
        permanence.save()
    menu_pool.clear()


@transaction.atomic
def cancel(permanence):
    if permanence.status >= PERMANENCE_INVOICES_VALIDATION_FAILED:
        last_bank_account_total = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL, permanence_id=permanence.id
        ).order_by().first()
        if last_bank_account_total is not None:
            # This is the last permanence invoiced
            getcontext().rounding=ROUND_HALF_UP
            for customer_invoice in CustomerInvoice.objects.filter(
                    permanence_id=permanence.id).order_by().distinct("id"):
                customer = customer_invoice.customer
                customer.balance = customer_invoice.previous_balance
                customer.date_balance = customer_invoice.date_previous_balance
                customer.save(update_fields=['balance', 'date_balance'])
                BankAccount.objects.all().filter(
                    customer_invoice_id=customer_invoice.id
                ).update(
                    customer_invoice=None
                )
            CustomerInvoice.objects.filter(
                permanence_id=permanence.id
            ).update(
                invoice_sort_order=None
            )
            for producer_invoice in ProducerInvoice.objects.filter(
                    permanence_id=permanence.id).order_by().distinct("id"):
                producer = producer_invoice.producer
                producer.balance = producer_invoice.previous_balance
                producer.date_balance = producer_invoice.date_previous_balance
                producer.save(update_fields=['balance', 'date_balance'])
                BankAccount.objects.all().filter(
                    producer_invoice_id=producer_invoice.id
                ).update(
                    producer_invoice=None
                )
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id
            ).update(
                invoice_sort_order=None
            )
            for offer_item in OfferItem.objects.filter(
                        is_active=True, manage_stock=True, permanence_id=permanence.id
                    ).order_by():
                Product.objects.filter(
                    id=offer_item.product_id, stock=offer_item.new_stock
                ).update(stock=offer_item.stock)
            last_bank_account_total.delete()
            bank_account = BankAccount.objects.filter(
                customer=None,
                producer=None).order_by('-id').first()
            if bank_account is not None:
                bank_account.operation_status = BANK_LATEST_TOTAL
                bank_account.save()
            # Delete also all payments recorded to producers
            BankAccount.objects.filter(
                permanence_id=permanence.id, producer__isnull=False,
                customer__isnull=True
            ).order_by().delete()
            # Delete also all compensation recorded to producers
            BankAccount.objects.filter(
                permanence_id=permanence.id,
                operation_status=BANK_COMPENSATION
            ).order_by().delete()
        permanence.status = PERMANENCE_SEND
        if permanence.highest_status < PERMANENCE_SEND:
            permanence.highest_status = PERMANENCE_SEND
        # Important : This also update the "update time" field of the permanence
        permanence.save()
        menu_pool.clear()


def admin_generate(request, producers_to_be_paid_set=Producer.objects.none(), permanence=None):
    user_message = _("You can only generate invoices when the permanence status is 'send'.")
    user_message_level = messages.WARNING
    if permanence is not None:
        if permanence.status == PERMANENCE_SEND:
            previous_permanence_not_invoiced = Permanence.objects.filter(
                status=PERMANENCE_SEND,
                permanence_date__lt=permanence.permanence_date).order_by("permanence_date").first()
            if previous_permanence_not_invoiced is not None:
                user_message = _("You must first invoice the %(permanence)s.") % {'permanence': previous_permanence_not_invoiced.__unicode__()}
                user_message_level = messages.WARNING
            else:
                next_permanence_not_invoiced = Permanence.objects.filter(
                    status=PERMANENCE_SEND,
                    permanence_date__gte=permanence.permanence_date)\
                    .exclude(id=permanence.id).order_by("permanence_date").first()
                if next_permanence_not_invoiced is not None:
                    payment_date = next_permanence_not_invoiced.payment_date
                    if payment_date is None or payment_date > timezone.localtime(timezone.now()).date():
                        payment_date = timezone.localtime(timezone.now()).date()
                else:
                    payment_date = timezone.localtime(timezone.now()).date()
                bank_account = BankAccount.objects.filter(
                    operation_status=BANK_LATEST_TOTAL)\
                    .only("operation_date").order_by("-id").first()
                if bank_account is not None:
                    if bank_account.operation_date > payment_date:
                        payment_date = bank_account.operation_date
                generate(request, permanence, payment_date, producers_to_be_paid_set)
                user_message = _("Action performed.")
                user_message_level = messages.INFO
        else:
            if permanence.status == PERMANENCE_INVOICES_VALIDATION_FAILED:
                user_message = _(
                    "The permanence status says there is an error. You must cancel the invoice then correct, before retrying.")
                user_message_level = messages.WARNING
    return user_message, user_message_level


def admin_send(request, queryset):
    if RepanierSettings.invoice:
        user_message = _("The status of this permanence prohibit you to send invoices.")
        user_message_level = messages.ERROR
        for permanence in queryset[:1]:
            if permanence.status == PERMANENCE_DONE:
                thread.start_new_thread(email_invoice.send, (permanence.id,))
                # email_invoice.send(permanence.id)
                user_message = _("Emails containing the invoices will be send to the customers and the producers.")
                user_message_level = messages.INFO
    else:
        user_message = _("This action is not activated for your group.")
        user_message_level = messages.ERROR
    return user_message, user_message_level


def admin_cancel(request, queryset):
    user_message = _("The status of this permanence prohibit you to cancel invoices.")
    user_message_level = messages.ERROR
    if RepanierSettings.invoice:
        latest_total = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL).only(
            "permanence"
        ).first()
        if latest_total is not None:
            last_permanence_invoiced_id = latest_total.permanence_id
            if last_permanence_invoiced_id is not None:
                permanence = queryset.first()
                if last_permanence_invoiced_id == permanence.id:
                    # This is well the latest closed permanence. The invoices can be cancelled without damages.
                    cancel(permanence)
                    user_message = _("The selected invoice has been canceled.")
                    user_message_level = messages.INFO
            else:
                user_message = _("The selected invoice is not the latest invoice.")
                user_message_level = messages.ERROR
        else:
            user_message = _("The selected invoice has been canceled.")
            user_message_level = messages.INFO
            permanence = queryset.first()
            permanence.status = PERMANENCE_SEND
            if permanence.highest_status < PERMANENCE_SEND:
                permanence.highest_status = PERMANENCE_SEND
            # Important : This also update the "update time" field of the permanence
            permanence.save()
            menu_pool.clear()
    else:
        permanence = queryset.first()
        if permanence.status == PERMANENCE_ARCHIVED:
            cancel(permanence)
            user_message = _("The selected invoice has been restored.")
            user_message_level = messages.INFO
    return user_message, user_message_level



