# -*- coding: utf-8 -*-
from const import *
from tools import *
from django.db.models import F
from django.db.models import Sum
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
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


def close_orders_async_now():
	# now = datetime.datetime.utcnow().replace(tzinfo=utc)
	current_site_name = Site.objects.get_current().name
	something_to_close = False
	for permanence in Permanence.objects.filter(
		status=PERMANENCE_OPENED,
		automaticaly_closed=True):
		# automaticaly_closed_on__isnull = False,
		# automaticaly_closed_on__lte=now):
		permanence.status = PERMANENCE_WAIT_FOR_SEND
		permanence.save(update_fields=['status'])
		close_orders_async.delay(permanence.id, current_site_name)
		something_to_close = True
	return something_to_close


def email_offers_async(permanence_id, current_site_name):
	email_offers(permanence_id, current_site_name)


def email_orders_async(permanence_id, current_site_name):
	email_orders(permanence_id, current_site_name)


def email_invoices_async(permanence_id, current_site_name):
	email_invoices(permanence_id, current_site_name)

def open_offers_async(permanence_id, current_site_name):
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
			offer_item.save(update_fields=['is_active', 'automatically_added'])
		else:
			OfferItem.objects.create(
				permanence_id = permanence_id,
				product = product,
				automatically_added = product.automatically_added)

	# 3 - Activate all offer item having a preceding purchase even if not selectd in the admin
	# ## q = OfferItem.objects.all().permanence(permanence).values('product').distinct()
	# ## for product_id in Purchase.objects.all().permanence(permanence).exclude(order_quantity=0, product_in=q).values('product').distinct():
	# for purchase_dict in Purchase.objects.all().permanence(permanence_id).exclude(order_quantity=0).values('product').distinct():
	# 	offer_item_set= OfferItem.objects.all().product(
	# 		purchase_dict['product']).permanence(permanence_id).order_by()[:1]
	# 	if offer_item_set:
	# 		offer_item = offer_item_set[0]
	# 		if not offer_item.is_active:
	# 			offer_item.is_active=True
	# 			offer_item.automatically_added = ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
	# 			permanence.producers.add(offer_item.product.producer)
	# 			offer_item.save(update_fields=['is_active', 'automatically_added'])
	# 	else:
	# 		procduct_set = Product.objects.all().id(purchase_dict['product'])[:1]
	# 		if procduct_set:
	# 			product = procduct_set[0]
	# 			status = ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
	# 			if not product.is_active:
	# 				status = ADD_PRODUCT_DEACTIVATED_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN
	# 			OfferItem.objects.create(
	# 				permanence_id = permanence_id,
	# 				product = product,
	# 				automatically_added = status)
	# 			permanence.producers.add(product.producer)

	# 4 - Calculate the Purchase 'sum' for each customer
	recalculate_order_amount(permanence_id, send_to_producer=False)
	email_offers(permanence_id, current_site_name)
	menu_pool.clear()
	permanence.status=PERMANENCE_OPENED
	permanence.save(update_fields=['status'])


def close_orders_async(permanence_id, current_site_name):

	# Deposit
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added = ADD_PRODUCT_TO_CUSTOMER_BASKET_0).order_by():
		for customer in Customer.objects.filter(purchase__permanence_id=permanence_id).distinct().order_by():
			update_or_create_purchase(
				customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "0",
				close_orders = True
			)
	# Subscription
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added = ADD_PRODUCT_TO_CUSTOMER_BASKET).order_by():
		for customer in Customer.objects.all().active().may_order().not_the_buyinggroup().order_by():
			update_or_create_purchase(
				customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "1",
				close_orders = True
			)
	# Transport
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(automatically_added = ADD_PRODUCT_TO_GROUP_BASKET).order_by():
		for customer in Customer.objects.all().active().the_buyinggroup().order_by():
			update_or_create_purchase(
				customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "1",
				close_orders = True
			)
	recalculate_order_amount(permanence_id, send_to_producer=True)
	email_orders(permanence_id, current_site_name)
	menu_pool.clear()
	Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_SEND)

def done_async(permanence_id, permanence_distribution_date, current_site_name):
	now = datetime.datetime.utcnow().replace(tzinfo=utc)
	comment = _('Ok')
	validation_passed = True
	a_bank_amount = 0
	customer_buyinggroup_id = None
	producer_buyinggroup_id = None

	# Get customer and producer representing this buying group
	customer = None
	customer_set = Customer.objects.all().the_buyinggroup().order_by()[:1]
	if customer_set:
		customer = customer_set[0]
		customer_buyinggroup_id = customer.id
	if customer_buyinggroup_id == None:
		comment = _("At least one customer must represent the buying group.")	
		validation_passed = False
	else:
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
			date_balance=now,
			balance=customer.balance
		)

	if validation_passed:		
		producer = None
		producer_set = Producer.objects.all().the_buyinggroup().order_by()[:1]
		if producer_set:
			producer = producer_set[0]
			producer_buyinggroup_id = producer.id
		if producer_buyinggroup_id == None:
			comment = _("At least one producer must represent the buying group.")		
			validation_passed = False

	if validation_passed:
		# create invoices
		for customer in Customer.objects.filter(
			purchase__permanence=permanence_id).not_the_buyinggroup().order_by().distinct():
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
				total_price_with_tax=0,
				total_vat=0,
				total_compensation=0,
				total_deposit=0,
				bank_amount_in=0,
				bank_amount_out=0,
				date_balance=now,
				balance=producer.balance
			)
		# calculate new current balance
		for purchase in Purchase.objects.select_for_update().filter(
			permanence=permanence_id,
			).order_by():
			a_total_price_with_tax = purchase.price_with_tax
			a_total_vat = 0
			a_total_compensation = 0
			a_total_deposit = purchase.unit_deposit * purchase.quantity

			if purchase.invoiced_price_with_compensation:
				a_total_vat = 0
				a_total_compensation = a_total_price_with_tax - purchase.price_without_tax
			else:
				a_total_vat = a_total_price_with_tax - purchase.price_without_tax
				a_total_compensation = 0
			if purchase.is_recorded_on_customer_invoice == None:
				if purchase.producer.id == producer_buyinggroup_id:
					# When the producer represent the buying group, generate a compensation movement
					customerinvoice = CustomerInvoice.objects.get(
						customer=customer_buyinggroup_id,
						permanence=permanence_id,
					)
					customerinvoice.total_price_with_tax -= a_total_price_with_tax
					customerinvoice.total_vat -= a_total_vat
					customerinvoice.total_compensation -= a_total_compensation
					customerinvoice.balance += a_total_price_with_tax
					customerinvoice.total_deposit -= a_total_deposit
					customerinvoice.save()
					Customer.objects.filter(
						id=customer_buyinggroup_id
					).update(
						date_balance=now,
						balance=F('balance') + a_total_price_with_tax
					)
				customerinvoice = CustomerInvoice.objects.get(
					customer=purchase.customer,
					permanence=permanence_id,
				)
				customerinvoice.total_price_with_tax += a_total_price_with_tax
				customerinvoice.total_vat += a_total_vat
				customerinvoice.total_compensation += a_total_compensation
				customerinvoice.balance -= a_total_price_with_tax
				customerinvoice.total_deposit += a_total_deposit
				customerinvoice.save()
				Customer.objects.filter(
					id=purchase.customer_id
				).update(
					date_balance=now,
					balance=F('balance') - a_total_price_with_tax
				)
				purchase.is_recorded_on_customer_invoice_id = customerinvoice.id
			if  purchase.is_recorded_on_producer_invoice == None:
				producerinvoice = ProducerInvoice.objects.get(
					producer=purchase.producer,
					permanence=permanence_id,
				)
				if purchase.producer.id == producer_buyinggroup_id:
					# When the producer represent the buying group, generate a compensation movement
					producerinvoice.bank_amount_in = a_total_price_with_tax
					producerinvoice.bank_amount_out = a_total_price_with_tax
					producerinvoice.save()
				else:
					producerinvoice.total_price_with_tax += a_total_price_with_tax
					producerinvoice.total_vat += a_total_vat
					producerinvoice.total_compensation += a_total_compensation
					producerinvoice.balance += a_total_price_with_tax
					producerinvoice.total_deposit += a_total_deposit
					producerinvoice.save()
					Producer.objects.filter(
						id=purchase.producer_id
					).update(
						date_balance=now,
						balance=F('balance') - a_total_price_with_tax
					)
				purchase.is_recorded_on_producer_invoice_id = producerinvoice.id
			purchase.save()

		bank_account_set= BankAccount.objects.all().filter(
		customer = None,
		producer = None).order_by('-id')[:1]
		if bank_account_set:
			a_bank_amount = bank_account_set[0].bank_amount_in - bank_account_set[0].bank_amount_out
		for bank_account in BankAccount.objects.select_for_update().filter(
			is_recorded_on_customer_invoice__isnull=True, 
			customer__isnull=False,
			operation_date__lte=permanence_distribution_date).order_by():
			customerinvoice_set = CustomerInvoice.objects.filter(
				customer=bank_account.customer,
				permanence=permanence_id,
			).order_by()[:1]
			customerinvoice = None
			if customerinvoice_set:
				customerinvoice = customerinvoice_set[0]
			else:
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
					date_balance=now,
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
				date_balance=now,
				balance=F('balance') + bank_amount_in - bank_amount_out
			)
			bank_account.is_recorded_on_customer_invoice_id = customerinvoice.id
			bank_account.save()
		for bank_account in BankAccount.objects.select_for_update().filter(
			is_recorded_on_producer_invoice__isnull=True, 
			producer__isnull=False,
			operation_date__lte=permanence_distribution_date).order_by():
			producerinvoice_set = ProducerInvoice.objects.filter(
				producer=bank_account.producer,
				permanence=permanence_id,
			).order_by()[:1]
			producerinvoice = None
			if producerinvoice_set:
				producerinvoice = producerinvoice_set[0]
			else:
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
					date_balance=now,
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
				date_balance=now,
				balance=F('balance') - bank_amount_in + bank_amount_out
			)
			bank_account.is_recorded_on_producer_invoice_id = producerinvoice.id
			bank_account.save()

		sum_customers_balance = 0
		result_set = Customer.objects.filter(
			is_active=True).values(
			'is_active').annotate(
			sum_balance=Sum('balance')).values(
			'sum_balance').order_by()[:1]
		if result_set:
			sum_customers_balance = result_set[0].get('sum_balance')
			if sum_customers_balance == None:
				sum_customers_balance = 0
		sum_producers_balance = 0
		result_set = Producer.objects.filter(
			is_active=True).values(
			'is_active').annotate(
			sum_balance=Sum('balance')).values(
			'sum_balance').order_by()[:1]
		if result_set:
			sum_producers_balance = result_set[0].get('sum_balance')
			if sum_producers_balance == None:
				sum_producers_balance = 0

		if a_bank_amount == (sum_customers_balance + sum_producers_balance):
			validation_passed = False
			comment = _('Validation error. Should be :') +  number_format(sum_customers_balance + sum_producers_balance, 2)

	BankAccount.objects.create(
		producer = None,
		customer = None,
		operation_date = permanence_distribution_date,
		operation_comment = comment,
		bank_amount_in = a_bank_amount if a_bank_amount >= 0 else 0,
		bank_amount_out = -a_bank_amount if a_bank_amount < 0 else 0,
		is_recorded_on_customer_invoice = None,
		is_recorded_on_producer_invoice = None
	)
	if validation_passed:
		# email_invoices(permanence_id, current_site_name)
		menu_pool.clear()
		Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_DONE,is_done_on = now)
	else:
		Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_INVOICES_VALIDATION_FAILED)
