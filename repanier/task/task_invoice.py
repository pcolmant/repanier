# -*- coding: utf-8 -*-
import threading

from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.models import DeliveryBoard
from repanier.email import email_invoice
from repanier.models import BankAccount
from repanier.models import Customer
from repanier.models import CustomerInvoice
from repanier.models import OfferItem
from repanier.models import CustomerProducerInvoice
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import ProducerInvoice
from repanier.models import Product
from repanier.models import Purchase
from repanier.task import task_producer
from repanier.tools import *


@transaction.atomic
def generate_invoice(permanence, payment_date):
    getcontext().rounding = ROUND_HALF_UP
    from repanier.apps import REPANIER_SETTINGS_MEMBERSHIP_FEE, REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION
    today = timezone.now().date()
    bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by('?').first()
    producer_buyinggroup = Producer.objects.filter(represent_this_buyinggroup=True).order_by('?').first()
    customer_buyinggroup = Customer.objects.filter(represent_this_buyinggroup=True).order_by('?').first()
    if bank_account is None or producer_buyinggroup is None or customer_buyinggroup is None:
        return
    customer_invoice_buyinggroup = CustomerInvoice.objects.filter(
        customer_id=customer_buyinggroup.id,
        permanence_id=permanence.id,
    ).order_by('?').first()
    if customer_invoice_buyinggroup is None:
        customer_invoice_buyinggroup = CustomerInvoice.objects.create(
            customer_id=customer_buyinggroup.id,
            permanence_id=permanence.id,
            date_previous_balance=customer_buyinggroup.date_balance,
            previous_balance=customer_buyinggroup.balance,
            date_balance=payment_date,
            balance=customer_buyinggroup.balance,
            customer_charged_id=customer_buyinggroup.id,
            transport=repanier.apps.REPANIER_SETTINGS_TRANSPORT,
            min_transport=repanier.apps.REPANIER_SETTINGS_MIN_TRANSPORT,
            price_list_multiplier=DECIMAL_ONE
        )
    old_bank_latest_total = bank_account.bank_amount_in.amount - bank_account.bank_amount_out.amount
    permanence_partially_invoiced = ProducerInvoice.objects.filter(
        permanence_id=permanence.id,
        invoice_sort_order__isnull=True,
        to_be_paid=False
    ).order_by('?').exists()
    if permanence_partially_invoiced:
        # Move the producers not invoiced into a new permanence
        producers_to_move = list(ProducerInvoice.objects.filter(
            permanence_id=permanence.id,
            invoice_sort_order__isnull=True,
            to_be_paid=False
        ).values_list('producer_id', flat=True).order_by("producer_id"))

        new_permanence = permanence.create_child(PERMANENCE_SEND)

        ProducerInvoice.objects.filter(
            permanence_id=permanence.id,
            producer_id__in=producers_to_move
        ).order_by('?').update(
            permanence_id=new_permanence.id
        )
        CustomerProducerInvoice.objects.filter(
            permanence_id=permanence.id,
            producer_id__in=producers_to_move
        ).order_by('?').update(
            permanence_id=new_permanence.id
        )
        OfferItem.objects.filter(
            permanence_id=permanence.id,
            producer_id__in=producers_to_move
        ).order_by('?').update(
            permanence_id=new_permanence.id
        )

        for purchase in Purchase.objects.filter(
            permanence_id=permanence.id,
            producer_id__in=producers_to_move
        ).order_by().distinct('customer_invoice'):
            customer_invoice = CustomerInvoice.objects.filter(
                id=purchase.customer_invoice_id
            ).order_by('?').first()
            new_customer_invoice = customer_invoice.create_child(new_permanence=new_permanence)
            # Important : The customer_charged is null. This is required for calculate_and_save_delta_buyinggroup
            new_customer_invoice.calculate_and_save_delta_buyinggroup()
            new_customer_invoice.set_delivery(customer_invoice.delivery)
            new_customer_invoice.save()
            Purchase.objects.filter(
                customer_invoice_id=customer_invoice.id,
                producer_id__in=producers_to_move
            ).order_by('?').update(
                permanence_id=new_permanence.id,
                customer_invoice_id=new_customer_invoice.id,
                customer_charged_id=new_customer_invoice.customer_charged_id
            )

    # Important : linked to task_invoice.cancel
    # First pass, set customer_charged
    for customer_invoice in CustomerInvoice.objects.filter(
        permanence_id=permanence.id
    ).order_by('?'):
        # In case of changed delivery conditions
        customer_invoice.set_delivery(customer_invoice.delivery)
        customer_invoice.save()
        Purchase.objects.filter(
            customer_invoice_id=customer_invoice.id
        ).order_by('?').update(
            customer_charged_id=customer_invoice.customer_charged_id
        )
    # Second pass, calculate invoices of charged customers
    for customer_invoice in CustomerInvoice.objects.filter(
            permanence_id=permanence.id
    ).order_by('?'):
        # Need to calculate delta_price_with_tax, delta_vat and delta_transport
        customer_invoice.calculate_and_save_delta_buyinggroup()
        customer_invoice.save()

    if REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION > 0 and REPANIER_SETTINGS_MEMBERSHIP_FEE > 0:
        membership_fee_product = Product.objects.filter(
            order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
            is_active=True
        ).order_by('?').first()
        membership_fee_product.producer_unit_price = REPANIER_SETTINGS_MEMBERSHIP_FEE
        # Update the prices
        membership_fee_product.save()

        for customer_invoice in CustomerInvoice.objects.filter(
            permanence_id=permanence.id,
            customer_charged_id=F('customer_id')
        ).select_related("customer").order_by('?'):
            # 4 - Add Membership fee Subscription
            customer = customer_invoice.customer
            if not customer.represent_this_buyinggroup:
                # There is a membership fee
                if customer.membership_fee_valid_until < today:
                    membership_fee_offer_item = get_or_create_offer_item(
                        permanence,
                        membership_fee_product.id,
                        membership_fee_product.producer_id
                    )
                    permanence.producers.add(membership_fee_offer_item.producer_id)
                    create_or_update_one_purchase(
                        customer.id,
                        membership_fee_offer_item,
                        q_order=1,
                        permanence_date=permanence.permanence_date,
                        batch_job=True,
                        is_box_content=False
                    )
                    customer.membership_fee_valid_until = add_months(
                        customer.membership_fee_valid_until,
                        REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION
                    )
                    customer.save(update_fields=['membership_fee_valid_until', ])



    for customer_invoice in CustomerInvoice.objects.filter(
        permanence_id=permanence.id
    ):
        customer_invoice.balance = customer_invoice.previous_balance = customer_invoice.customer.balance
        customer_invoice.date_previous_balance = customer_invoice.customer.date_balance
        customer_invoice.date_balance = payment_date

        if customer_invoice.customer_id == customer_invoice.customer_charged_id:
            # ajuster sa balance
            # il a droit aux réductions
            total_price_with_tax = customer_invoice.get_total_price_with_tax().amount
            customer_invoice.balance.amount -= total_price_with_tax
            Customer.objects.filter(
                id=customer_invoice.customer_id
            ).update(
                date_balance=payment_date,
                balance=F('balance') - total_price_with_tax
            )
        else:
            # ne pas modifier sa balance
            # ajuster la balance de celui qui paye
            # celui qui paye a droit aux réductions
            Customer.objects.filter(
                id=customer_invoice.customer_id
            ).update(
                date_balance=payment_date,
            )
        customer_invoice.save()

    # Claculate new stock
    for offer_item in OfferItem.objects.filter(
            is_active=True, manage_replenishment=True, permanence_id=permanence.id
    ).order_by('?'):
        invoiced_qty, taken_from_stock, customer_qty = offer_item.get_producer_qty_stock_invoiced()
        if taken_from_stock != DECIMAL_ZERO:
            if offer_item.price_list_multiplier < DECIMAL_ONE: # or offer_item.is_resale_price_fixed:
                unit_price = offer_item.customer_unit_price.amount
                unit_vat = offer_item.customer_vat.amount
            else:
                unit_price = offer_item.producer_unit_price.amount
                unit_vat = offer_item.producer_vat.amount
            delta_price_with_tax = ((unit_price +
                               offer_item.unit_deposit.amount) * taken_from_stock).quantize(TWO_DECIMALS)
            delta_vat = unit_vat * taken_from_stock
            delta_deposit = offer_item.unit_deposit.amount * taken_from_stock
            producer_invoice = ProducerInvoice.objects.get(
                producer=offer_item.producer,
                permanence=permanence,
            )
            producer_invoice.delta_stock_with_tax.amount -= delta_price_with_tax
            producer_invoice.delta_stock_vat.amount -= delta_vat
            producer_invoice.delta_stock_deposit.amount -= delta_deposit
            producer_invoice.save(update_fields=[
                'delta_stock_with_tax',
                'delta_stock_vat',
                'delta_stock_deposit'
            ])

        # Update new_stock even if no order
        # // xslx_stock and task_invoice
        offer_item.new_stock = offer_item.stock - taken_from_stock + offer_item.add_2_stock
        if offer_item.new_stock < DECIMAL_ZERO:
            offer_item.new_stock = DECIMAL_ZERO
        offer_item.previous_add_2_stock = offer_item.add_2_stock
        offer_item.previous_producer_unit_price = offer_item.producer_unit_price
        offer_item.previous_unit_deposit = offer_item.unit_deposit
        if permanence.highest_status <= PERMANENCE_SEND:
            # Asked by Bees-Coop : Do not update stock when canceling
            new_stock = offer_item.stock if offer_item.stock > DECIMAL_ZERO else DECIMAL_ZERO
            Product.objects.filter(
                id=offer_item.product_id, stock=new_stock
            ).update(stock=offer_item.new_stock)
        offer_item.save()

    for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=permanence.id):
        producer_invoice.balance = producer_invoice.previous_balance = producer_invoice.producer.balance
        producer_invoice.date_previous_balance = producer_invoice.producer.date_balance
        producer_invoice.date_balance = payment_date
        total_price_with_tax = producer_invoice.get_total_price_with_tax().amount
        producer_invoice.balance.amount += total_price_with_tax
        producer_invoice.save()
        Producer.objects.filter(
            id=producer_invoice.producer_id
        ).update(
            date_balance=payment_date,
            balance=F('balance') + total_price_with_tax
        )
        producer_invoice.save()

    result_set = Purchase.objects.filter(
        permanence_id=permanence.id,
        is_box_content=False,
        offer_item__price_list_multiplier__gte=DECIMAL_ONE,
        producer__represent_this_buyinggroup=False
    ).order_by('?').aggregate(
        Sum('purchase_price'),
        Sum('selling_price'),
        Sum('producer_vat'),
        Sum('customer_vat'),
    )
    if result_set["purchase_price__sum"] is not None:
        sum_purchase_price = result_set["purchase_price__sum"]
    else:
        sum_purchase_price = DECIMAL_ZERO
    if result_set["selling_price__sum"] is not None:
        sum_selling_price = result_set["selling_price__sum"]
    else:
        sum_selling_price = DECIMAL_ZERO
    if result_set["producer_vat__sum"] is not None:
        sum_producer_vat = result_set["producer_vat__sum"]
    else:
        sum_producer_vat = DECIMAL_ZERO
    if result_set["customer_vat__sum"] is not None:
        sum_customer_vat = result_set["customer_vat__sum"]
    else:
        sum_customer_vat = DECIMAL_ZERO
    purchases_delta_vat = sum_customer_vat - sum_producer_vat
    purchases_delta_price_with_tax = sum_selling_price - sum_purchase_price

    purchases_delta_price_wo_tax = purchases_delta_price_with_tax - purchases_delta_vat

    if purchases_delta_price_wo_tax != DECIMAL_ZERO:
        BankAccount.objects.create(
            permanence_id=permanence.id,
            producer=None,
            customer_id=customer_buyinggroup.id,
            operation_date=payment_date,
            operation_status=BANK_PROFIT,
            operation_comment=_("Profit") if purchases_delta_price_wo_tax >= DECIMAL_ZERO else _("Lost"),
            bank_amount_out=-purchases_delta_price_wo_tax if purchases_delta_price_wo_tax < DECIMAL_ZERO else DECIMAL_ZERO,
            bank_amount_in=purchases_delta_price_wo_tax if purchases_delta_price_wo_tax > DECIMAL_ZERO else DECIMAL_ZERO,
            customer_invoice_id=None,
            producer_invoice=None
        )
    if purchases_delta_vat != DECIMAL_ZERO:
        BankAccount.objects.create(
            permanence_id=permanence.id,
            producer=None,
            customer_id=customer_buyinggroup.id,
            operation_date=payment_date,
            operation_status=BANK_TAX,
            operation_comment=_("VAT to pay to the tax authorities") if purchases_delta_vat >= DECIMAL_ZERO else
            _("VAT to receive from the tax authorities"),
            bank_amount_out=-purchases_delta_vat if purchases_delta_vat < DECIMAL_ZERO else DECIMAL_ZERO,
            bank_amount_in=purchases_delta_vat if purchases_delta_vat > DECIMAL_ZERO else DECIMAL_ZERO,
            customer_invoice_id=None,
            producer_invoice=None
        )

    for customer_invoice in CustomerInvoice.objects.filter(
        permanence_id=permanence.id,
    ).exclude(
        customer_id=customer_buyinggroup.id,
        delta_transport=DECIMAL_ZERO
    ):
        if customer_invoice.delta_transport != DECIMAL_ZERO:
            # --> This bank movement is not a real entry
            # customer_invoice_id=customer_invoice_buyinggroup.id
            # making this, it will not be counted into the customer_buyinggroup movements twice
            # because Repanier will see it has already been counted into the customer_buyinggroup movements
            BankAccount.objects.create(
                permanence_id=permanence.id,
                producer=None,
                customer_id=customer_buyinggroup.id,
                operation_date=payment_date,
                operation_status=BANK_PROFIT,
                operation_comment="%s : %s" % (_("Transport"), customer_invoice.customer.short_basket_name),
                bank_amount_in=customer_invoice.delta_transport,
                bank_amount_out=DECIMAL_ZERO,
                customer_invoice_id=customer_invoice_buyinggroup.id,
                producer_invoice=None
            )

    # generate bank account movements
    task_producer.admin_generate_bank_account_movement(
        permanence=permanence, payment_date=payment_date,
        customer_buyinggroup=customer_buyinggroup
    )

    new_bank_latest_total = old_bank_latest_total

    # Calculate new current balance : Bank
    for bank_account in BankAccount.objects.select_for_update().filter(

        customer_invoice__isnull=True,
        producer_invoice__isnull=True,
        operation_status__in=[BANK_PROFIT, BANK_TAX],
        customer_id=customer_buyinggroup.id,
        operation_date__lte=payment_date
    ).order_by('?'):

        # --> This bank movement is not a real entry
        # It will not be counted into the customer_buyinggroup bank movements twice
        Customer.objects.filter(
            id=bank_account.customer_id
        ).update(
            date_balance=payment_date,
            balance=F('balance') + bank_account.bank_amount_in.amount - bank_account.bank_amount_out.amount
        )
        CustomerInvoice.objects.filter(
            customer_id=bank_account.customer_id,
            permanence_id=permanence.id,
        ).update(
            date_balance=payment_date,
            balance=F('balance') + bank_account.bank_amount_in.amount - bank_account.bank_amount_out.amount
        )
        bank_account.customer_invoice_id = customer_invoice_buyinggroup.id
        bank_account.save(update_fields=['customer_invoice'])

    for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            customer__isnull=False,
            operation_date__lte=payment_date).order_by('?'):

        customer_invoice = CustomerInvoice.objects.filter(
            customer_id=bank_account.customer_id,
            permanence_id=permanence.id,
        ).order_by('?').first()
        if customer_invoice is None:
            customer_invoice = CustomerInvoice.objects.create(
                customer_id=bank_account.customer_id,
                permanence_id=permanence.id,
                date_previous_balance=bank_account.customer.date_balance,
                previous_balance=bank_account.customer.balance,
                date_balance=payment_date,
                balance=bank_account.customer.balance,
                customer_charged_id=bank_account.customer_id,
                transport=repanier.apps.REPANIER_SETTINGS_TRANSPORT,
                min_transport=repanier.apps.REPANIER_SETTINGS_MIN_TRANSPORT
            )
        bank_amount_in = bank_account.bank_amount_in.amount
        new_bank_latest_total += bank_amount_in
        bank_amount_out = bank_account.bank_amount_out.amount
        new_bank_latest_total -= bank_amount_out
        customer_invoice.date_balance = payment_date
        customer_invoice.bank_amount_in.amount += bank_amount_in
        customer_invoice.bank_amount_out.amount += bank_amount_out
        customer_invoice.balance.amount += (bank_amount_in - bank_amount_out)

        customer_invoice.save()
        Customer.objects.filter(
            id=bank_account.customer_id
        ).update(
            date_balance=payment_date,
            balance=F('balance') + bank_amount_in - bank_amount_out
        )
        bank_account.customer_invoice_id = customer_invoice.id
        bank_account.permanence_id = permanence.id
        bank_account.save()

    for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            producer__isnull=False,
            operation_date__lte=payment_date).order_by('?'):

        producer_invoice = ProducerInvoice.objects.filter(
            producer_id=bank_account.producer_id,
            permanence_id=permanence.id,
        ).order_by('?').first()
        if producer_invoice is None:
            producer_invoice = ProducerInvoice.objects.create(
                producer=bank_account.producer,
                permanence_id=permanence.id,
                date_previous_balance=bank_account.producer.date_balance,
                previous_balance=bank_account.producer.balance,
                date_balance=payment_date,
                balance=bank_account.producer.balance
            )
        bank_amount_in = bank_account.bank_amount_in.amount
        new_bank_latest_total += bank_amount_in
        bank_amount_out = bank_account.bank_amount_out.amount
        new_bank_latest_total -= bank_amount_out
        producer_invoice.date_balance = payment_date
        producer_invoice.bank_amount_in.amount += bank_amount_in
        producer_invoice.bank_amount_out.amount += bank_amount_out
        producer_invoice.balance.amount += (bank_amount_in - bank_amount_out)
        producer_invoice.save()
        Producer.objects.filter(
            id=bank_account.producer_id
        ).update(
            date_balance=payment_date,
            balance=F('balance') + bank_amount_in - bank_amount_out
        )
        bank_account.permanence_id = permanence.id
        bank_account.producer_invoice_id = producer_invoice.id
        bank_account.save()

    BankAccount.objects.filter(
        operation_status=BANK_LATEST_TOTAL
    ).order_by('?').update(
        operation_status=BANK_NOT_LATEST_TOTAL
    )
    # Important : Create a new bank total for this permanence even if there is no bank movement
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

    new_status = PERMANENCE_INVOICED if repanier.apps.REPANIER_SETTINGS_INVOICE else PERMANENCE_ARCHIVED
    permanence.set_status(new_status, update_payment_date=True, payment_date=payment_date)

    ProducerInvoice.objects.filter(
        permanence_id=permanence.id
    ).update(invoice_sort_order=bank_account.id)
    CustomerInvoice.objects.filter(
        permanence_id=permanence.id
    ).update(invoice_sort_order=bank_account.id)
    Permanence.objects.filter(
        id=permanence.id
    ).update(invoice_sort_order=bank_account.id)


@transaction.atomic
def generate_archive(permanence):
    permanence.set_status(PERMANENCE_ARCHIVED)


@transaction.atomic
def cancel_delivery(permanence):
    permanence.set_status(PERMANENCE_CANCELLED)

@transaction.atomic
def cancel_invoice(permanence):
    if permanence.status in [PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
        last_bank_account_total = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL, permanence_id=permanence.id
        ).order_by('?').first()
        if last_bank_account_total is not None:
            # This is the last permanence invoiced
            getcontext().rounding = ROUND_HALF_UP
            # Historical : bo compatibility
            # permanence_id is not NULL and t.customer_id is NULL and t.producer_invoice_id is NULL
            BankAccount.objects.filter(
                operation_status='100',
                permanence__isnull=False,
                customer__isnull=True,
                producer_invoice__isnull=True,
                producer__isnull=False
            ).delete()
            # Historical : eo compatibility
            CustomerInvoice.objects.filter(
                permanence_id=permanence.id,
            ).update(
                bank_amount_in=DECIMAL_ZERO,
                bank_amount_out=DECIMAL_ZERO,
                balance=F('previous_balance'),
                date_balance=F('date_previous_balance'),
                invoice_sort_order=None
            )
            # # Important : linked to task_invoice.generate
            # First pass, set customer_charged
            CustomerInvoice.objects.filter(
                    permanence_id=permanence.id
            ).order_by('?').update(customer_charged=None)
            # Second pass, calculate invoices of charged customers
            for customer_invoice in CustomerInvoice.objects.filter(
                    permanence_id=permanence.id
            ).order_by('?'):
                # Need to calculate delta_price_with_tax, delta_vat and delta_transport
                customer_invoice.calculate_and_save_delta_buyinggroup()
                customer_invoice.save()

            for customer_invoice in CustomerInvoice.objects.filter(
                    permanence_id=permanence.id).order_by():
                customer = customer_invoice.customer
                customer.balance = customer_invoice.previous_balance
                customer.date_balance = customer_invoice.date_previous_balance
                customer.save(update_fields=['balance', 'date_balance'])
                BankAccount.objects.all().filter(
                    customer_invoice_id=customer_invoice.id
                ).update(
                    customer_invoice=None
                )
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id
            ).exclude(
                producer__represent_this_buyinggroup=True
            ).update(
                bank_amount_in=DECIMAL_ZERO,
                bank_amount_out=DECIMAL_ZERO,
                delta_price_with_tax=DECIMAL_ZERO,
                delta_vat=DECIMAL_ZERO,
                delta_transport=DECIMAL_ZERO,
                delta_deposit=DECIMAL_ZERO,
                delta_stock_with_tax=DECIMAL_ZERO,
                delta_stock_vat=DECIMAL_ZERO,
                delta_stock_deposit=DECIMAL_ZERO,
                balance=F('previous_balance'),
                date_balance=F('date_previous_balance'),
                invoice_sort_order=None
            )
            # Important : Restore delta from delivery points added into invoice.confirm_order()
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id,
                producer__represent_this_buyinggroup=True
            ).update(
                bank_amount_in=DECIMAL_ZERO,
                bank_amount_out=DECIMAL_ZERO,
                delta_stock_with_tax=DECIMAL_ZERO,
                delta_stock_vat=DECIMAL_ZERO,
                delta_stock_deposit=DECIMAL_ZERO,
                balance=F('previous_balance'),
                date_balance=F('date_previous_balance'),
                invoice_sort_order=None
            )


            for producer_invoice in ProducerInvoice.objects.filter(
                    permanence_id=permanence.id
            ).order_by('?'): # .distinct("id"):
                producer = producer_invoice.producer
                producer.balance = producer_invoice.previous_balance
                producer.date_balance = producer_invoice.date_previous_balance
                producer.save(update_fields=['balance', 'date_balance'])
                BankAccount.objects.all().filter(
                    producer_invoice_id=producer_invoice.id
                ).update(
                    producer_invoice=None
                )
            # IMPORTANT : Do not update stock when canceling
            last_bank_account_total.delete()
            bank_account = BankAccount.objects.filter(
                customer=None,
                producer=None).order_by('-id').first()
            if bank_account is not None:
                bank_account.operation_status = BANK_LATEST_TOTAL
                bank_account.save()
            # Delete also all payments recorded to producers, bank profit, bank tax
            # Delete also all compensation recorded to producers
            BankAccount.objects.filter(
                permanence_id=permanence.id,
                operation_status__in=[
                    BANK_CALCULATED_INVOICE,
                    BANK_PROFIT,
                    BANK_TAX,
                    BANK_MEMBERSHIP_FEE,
                    BANK_COMPENSATION # BANK_COMPENSATION may occurs in previous release of Repanier
                ]
            ).order_by('?').delete()
        Permanence.objects.filter(
            id=permanence.id
        ).update(invoice_sort_order=None)
        permanence.set_status(PERMANENCE_SEND)


@transaction.atomic
def cancel_archive(permanence):
    if BankAccount.objects.filter(
        operation_status=BANK_LATEST_TOTAL, permanence_id=permanence.id
    ).order_by('?').exists():
        # old archive
        cancel_invoice(permanence)
    else:
        permanence.set_status(PERMANENCE_SEND, allow_downgrade=True)


def admin_cancel(permanence):
    if permanence.status == PERMANENCE_INVOICED:
        latest_total = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL).only(
            "permanence"
        ).first()
        if latest_total is not None:
            last_permanence_invoiced_id = latest_total.permanence_id
            if last_permanence_invoiced_id is not None:
                if last_permanence_invoiced_id == permanence.id:
                    # This is well the latest closed permanence. The invoices can be cancelled without damages.
                    cancel_invoice(permanence)
                    user_message = _("The selected invoice has been canceled.")
                    user_message_level = messages.INFO
                else:
                    user_message = _("The selected invoice is not the latest invoice.")
                    user_message_level = messages.ERROR
            else:
                user_message = _("The selected invoice is not the latest invoice.")
                user_message_level = messages.ERROR
        else:
            user_message = _("The selected invoice has been canceled.")
            user_message_level = messages.INFO
            permanence.set_status(PERMANENCE_SEND)
    elif permanence.status in [PERMANENCE_ARCHIVED, PERMANENCE_CANCELLED]:
            cancel_archive(permanence)
            user_message = _("The selected invoice has been restored.")
            user_message_level = messages.INFO
    else:
        user_message = _("The status of %(permanence)s prohibit you to cancel invoices.") % {
            'permanence': permanence}
        user_message_level = messages.ERROR

    return user_message, user_message_level


def admin_send(permanence):
    if permanence.status == PERMANENCE_INVOICED:
        # thread.start_new_thread(email_invoice.send_invoice, (permanence.id,))
        t = threading.Thread(target=email_invoice.send_invoice, args=(permanence.id,))
        t.start()
        user_message = _("Emails containing the invoices will be send to the customers and the producers.")
        user_message_level = messages.INFO
    else:
        user_message = _("The status of %(permanence)s prohibit you to send invoices.") % {
            'permanence': permanence}
        user_message_level = messages.ERROR

    return user_message, user_message_level