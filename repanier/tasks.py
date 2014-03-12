# -*- coding: utf-8 -*-
from celery import shared_task
from celery import task
from const import *
from tools import *
from django.db.models import F
from django.contrib.sites.models import Site
from menus.menu_pool import menu_pool
from repanier.models import Producer
from repanier.models import Product
from repanier.models import Customer
from repanier.models import Purchase
from repanier.models import BankAccount
from repanier.models import CustomerInvoice
from repanier.models import ProducerInvoice
from repanier.models import Permanence
from repanier.models import OfferItem
from repanier.models import Purchase
import datetime
from django.utils.timezone import utc

from repanier.admin_send_mail import email_offers
from repanier.admin_send_mail import email_orders
from repanier.admin_send_mail import email_invoices

# cd v1
# source bin/activate
# cd ptidej
# celery -A ptidej worker -B -l info
# celery -A ptidej worker -B --loglevel=INFO --concurrency=1 -n ptidej

@task
def close_orders_async_now():
	now = datetime.datetime.utcnow().replace(tzinfo=utc)
	current_site = Site.objects.get_current()
	for permanence in Permanence.objects.filter(
		status=PERMANENCE_OPENED,
		automaticaly_closed_on__isnull = False, 
		automaticaly_closed_on__lte=now):
		permanence.status = PERMANENCE_WAIT_FOR_SEND
		permanence.save()
		close_orders_async.delay(permanence.id, current_site)

@task
def email_offers_async(permanence_id, current_site):
	email_offers(permanence_id, current_site)

@task
def email_orders_async(permanence_id, current_site):
	email_orders(permanence_id, current_site)

@task
def email_invoices_async(permanence_id, current_site):
	email_invoices(permanence_id, current_site)

@task
def open_offers_async(permanence_id, current_site):
	permanence = Permanence.objects.get(id=permanence_id)
	# 1- Deactivate all offer item of this permanence
	# Not needed, already done in 'back_to_previous_status'

	# 2 - Activate all offer item depending on selection in the admin
	producers_in_this_permanence = Producer.objects.filter(
		permanence=permanence_id).active()

	for product in Product.objects.filter(
		producer__in = producers_in_this_permanence
		).active().is_selected_for_offer():
		offer_item_set= OfferItem.objects.all().product(
			product).permanence(permanence_id).order_by()[:1]
		if offer_item_set:
			offer_item = offer_item_set[0]
			offer_item.is_active=True
			offer_item.automatically_added = product.automatically_added
			offer_item.save()
		else:
			OfferItem.objects.create(
				permanence_id = permanence_id,
				product = product,
				automatically_added = product.automatically_added)

	# 3 - Activate all offer item having a preceding purchase even if not selectd in the admin
	# ## q = OfferItem.objects.all().permanence(permanence).values('product').distinct()
	# ## for product_id in Purchase.objects.all().permanence(permanence).exclude(order_quantity=0, product_in=q).values('product').distinct():
	for purchase_dict in Purchase.objects.all().permanence(permanence_id).exclude(order_quantity=0).values('product').distinct():
		offer_item_set= OfferItem.objects.all().product(
			purchase_dict['product']).permanence(permanence_id).order_by()[:1]
		if offer_item_set:
			offer_item = offer_item_set[0]
			if not offer_item.is_active:
				offer_item.is_active=True
				offer_item.automatically_added = ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
				permanence.producers.add(offer_item.product.producer)
				offer_item.save()
		else:
			procduct_set = Product.objects.all().id(purchase_dict['product'])[:1]
			if procduct_set:
				product = procduct_set[0]
				status = ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
				if not product.is_active:
					status = ADD_PRODUCT_DEACTIVATED_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
				OfferItem.objects.create(
					permanence_id = permanence_id,
					product = product,
					automatically_added = status)
				permanence.producers.add(product.producer)

	# 4 - Calculate the Purchase 'sum' for each customer
	recalculate_order_amount(permanence_id)
	email_offers(permanence_id, current_site)
	menu_pool.clear()
	permanence.status=PERMANENCE_OPENED
	permanence.save()


@task
def close_orders_async(permanence_id, current_site):

	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added__in = [ADD_PRODUCT_TO_CUSTOMER_BASKET_0]).order_by():
		for purchase_dict in Purchase.objects.all().permanence(permanence_id).exclude(order_quantity=0).values('customer').order_by().distinct():
			update_or_create_purchase(customer_id=purchase_dict['customer'], 
				p_offer_item_id=offer_item.id, 
				p_value_id = "0"
			)
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added__in = [ADD_PRODUCT_TO_CUSTOMER_BASKET]).order_by():
		for customer in Customer.objects.all().active().not_the_buyinggroup().order_by():
			update_or_create_purchase(customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "1"
			)
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added__in = [ADD_PRODUCT_TO_GROUP_BASKET]).order_by():
		for customer in Customer.objects.all().active().the_buyinggroup().order_by():
			update_or_create_purchase(customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "1"
			)
	for purchase in Purchase.objects.all().permanence(permanence_id).order_by():
		purchase.vat_level = purchase.product.vat_level
		purchase.long_name = purchase.product.long_name
		purchase.order_by_piece_pay_by_kg = purchase.product.order_by_piece_pay_by_kg
		purchase.prepared_unit_price = purchase.product.producer_unit_price
		if purchase.prepared_quantity == 0:
			purchase.prepared_quantity = purchase.order_quantity
		purchase.order_amount = purchase.prepared_quantity * purchase.product.producer_unit_price
		purchase.prepared_amount = purchase.order_amount
		purchase.save()
	recalculate_order_amount(permanence_id)
	email_orders(permanence_id, current_site)
	menu_pool.clear()
	Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_SEND)

@task
def done_async(permanence_id, current_site):
	now = datetime.datetime.utcnow().replace(tzinfo=utc)
	# create invoices
	for customer in Customer.objects.filter(
		purchase__permanence=permanence_id).order_by().distinct():
		CustomerInvoice.objects.create(
			customer=customer,
			permanence_id=permanence_id,
			date_previous_balance=customer.date_balance,
			previous_balance=customer.balance,
			purchase_amount=0,
			bank_amount_in=0,
			bank_amount_out=0,
			date_balance=now,
			balance=customer.balance
		)
	for producer in Producer.objects.filter(
		permanence=permanence_id).order_by():
		ProducerInvoice.objects.create(
			producer=producer,
			permanence_id=permanence_id,
			date_previous_balance=producer.date_balance,
			previous_balance=producer.balance,
			purchase_amount=0,
			bank_amount_in=0,
			bank_amount_out=0,
			date_balance=now,
			balance=producer.balance
		)
	# calculate new current balance
	for purchase in Purchase.objects.select_for_update().filter(
		permanence=permanence_id,
		).order_by():
		prepared_amount = purchase.prepared_amount
		if purchase.is_recorded_on_customer_invoice == None:
			customerinvoice = CustomerInvoice.objects.get(
				customer=purchase.customer,
				permanence=permanence_id,
			)
			customerinvoice.purchase_amount+=prepared_amount
			customerinvoice.balance -= prepared_amount
			customerinvoice.save()
			Customer.objects.filter(
				id=purchase.customer_id
			).update(
				date_balance=now,
				balance=F('balance') - prepared_amount
			)
			purchase.is_recorded_on_customer_invoice_id = customerinvoice.id
		if  purchase.is_recorded_on_producer_invoice == None:
			producerinvoice = ProducerInvoice.objects.get(
				producer=purchase.producer,
				permanence=permanence_id,
			)
			producerinvoice.purchase_amount+=prepared_amount
			producerinvoice.balance += prepared_amount
			producerinvoice.save()
			Producer.objects.filter(
				id=purchase.producer_id
			).update(
				date_balance=now,
				balance=F('balance') + prepared_amount
			)
			purchase.is_recorded_on_producer_invoice_id = producerinvoice.id
		purchase.save()
	for bank_account in BankAccount.objects.select_for_update().filter(
		is_recorded_on_customer_invoice__isnull=True, 
		customer__isnull=False,
		operation_date__lte=now).order_by():
		customerinvoice = CustomerInvoice.objects.get(
			customer=bank_account.customer,
			permanence=permanence_id,
		)
		bank_amount_in = bank_account.bank_amount_in
		bank_amount_out = bank_account.bank_amount_out
		customerinvoice.bank_amount_in += bank_amount_in
		customerinvoice.bank_amount_out += bank_amount_out
		customerinvoice.balance += (bank_amount_in - bank_amount_out)
		customerinvoice.save()
		Customer.objects.filter(
			id=bank_account.customer_id
		).update(
			date_balance=now,
			balance=F('balance') + bank_amount_in - bank_amount_out
		)
		bank_account.is_recorded_on_customer_invoice_id = customerinvoice.id
		bank_account.save()
	for bank_account in BankAccount.objects.select_for_update().filter(
		is_recorded_on_producer_invoice__isnull=True, 
		producer__isnull=False,
		operation_date__lte=now).order_by():
		producerinvoice = ProducerInvoice.objects.get(
			producer=bank_account.producer,
			permanence=permanence_id,
		)
		bank_amount_in = bank_account.bank_amount_in
		bank_amount_out = bank_account.bank_amount_out
		producerinvoice.bank_amount_in += bank_amount_in
		producerinvoice.bank_amount_out += bank_amount_out
		producerinvoice.balance += (bank_amount_out - bank_amount_in)
		producerinvoice.save()
		Producer.objects.filter(
			id=bank_account.producer_id
		).update(
			date_balance=now,
			balance=F('balance') - bank_amount_in + bank_amount_out
		)
		bank_account.is_recorded_on_producer_invoice_id = producerinvoice.id
		bank_account.save()
	email_invoices(permanence_id, current_site)
	menu_pool.clear()
	Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_DONE,is_done_on = now)
