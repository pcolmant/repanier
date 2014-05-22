# -*- coding: utf-8 -*-
import thread

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
from django.utils import timezone
from django.utils.timezone import utc
from django.utils import translation
from django.db import transaction

from repanier.admin_send_mail import email_offers
from repanier.admin_send_mail import email_orders
from repanier.admin_send_mail import email_invoices

@transaction.atomic
def close_orders_now():
	# now = timezone.localtime(timezone.now())
	current_site_name = Site.objects.get_current().name
	translation.activate("fr")
	something_to_close = False
	for permanence in Permanence.objects.filter(
		# status=PERMANENCE_WAIT_FOR_SEND,
		status=PERMANENCE_OPENED,
		automaticaly_closed=True):
		permanence.status = PERMANENCE_WAIT_FOR_SEND
		permanence.save(update_fields=['status'])
		# close_orders.delay(permanence.id, current_site_name)
		close_orders(permanence.id, current_site_name)
		something_to_close = True
	return something_to_close

@transaction.atomic
def open_offers(permanence_id, current_site_name):
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
			# offer_item.automatically_added = product.automatically_added
			offer_item.save(update_fields=['is_active'])
		else:
			OfferItem.objects.create(
				permanence_id = permanence_id,
				product = product)
				# automatically_added = product.automatically_added)

	# 4 - Calculate the Purchase 'sum' for each customer
	recalculate_order_amount(permanence_id, send_to_producer=False)
	email_offers(permanence_id, current_site_name)
	menu_pool.clear()
	permanence.status=PERMANENCE_OPENED
	permanence.save(update_fields=['status'])

@transaction.atomic
def close_orders(permanence_id, current_site_name):

	# Deposit
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(product__order_unit = PRODUCT_ORDER_UNIT_DEPOSIT).order_by():
		for customer in Customer.objects.filter(purchase__permanence_id=permanence_id).distinct().order_by():
			update_or_create_purchase(
				customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "0",
				close_orders = True
			)
	# Subscription
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(product__order_unit = PRODUCT_ORDER_UNIT_SUBSCRIPTION).order_by():
		for customer in Customer.objects.all().active().may_order().not_the_buyinggroup().order_by():
			update_or_create_purchase(
				customer=customer, 
				p_offer_item_id=offer_item.id, 
				p_value_id = "1",
				close_orders = True
			)
	# Transport
	for offer_item in OfferItem.objects.all().permanence(permanence_id).active().filter(product__order_unit = PRODUCT_ORDER_UNIT_TRANSPORTATION).order_by():
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

@transaction.atomic
def done(permanence_id, permanence_distribution_date, current_site_name):

	validation_passed = True
	something_to_put_into_the_invoice = False

	try:
		bank_account_set= BankAccount.objects.filter(
			operation_status=BANK_LATEST_TOTAL).order_by()[:1]
		if bank_account_set:
			bank_account = bank_account_set[0]
			a_bank_amount = bank_account.bank_amount_in - bank_account.bank_amount_out

			comment = _('Intermediate balance')
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
					date_balance=permanence_distribution_date,
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
						date_balance=permanence_distribution_date,
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
						date_balance=permanence_distribution_date,
						balance=producer.balance
					)
				# Calculate new current balance : Purchases

				# Changed in Django 1.6.3:
				# 	It is now an error to execute a query with select_for_update() in autocommit mode. With earlier releases in the 1.6 series it was a no-op.

				for purchase in Purchase.objects.select_for_update().filter(
					permanence=permanence_id,
					).order_by():

					a_total_price = 0
					a_total_vat = 0
					a_total_compensation = 0
					a_total_deposit = purchase.unit_deposit * purchase.quantity
					if purchase.invoiced_price_with_compensation:
						a_total_price = purchase.price_with_compensation
						a_total_vat = 0
						a_total_compensation = purchase.price_with_compensation - purchase.price_with_vat
					else:
						a_total_price = purchase.price_with_vat
						a_total_vat = 0
						a_total_without_deposit = a_total_price - a_total_deposit
						if purchase.vat_level == VAT_400:
							a_total_vat = (a_total_without_deposit * Decimal(0.06)).quantize(DECIMAL_0_001, rounding=ROUND_HALF_UP)
						elif purchase.vat_level == VAT_500:
							a_total_vat = (a_total_without_deposit * Decimal(0.12)).quantize(DECIMAL_0_001, rounding=ROUND_HALF_UP)
						elif purchase.vat_level == VAT_600:
							a_total_vat = (a_total_without_deposit * Decimal(0.21)).quantize(DECIMAL_0_001, rounding=ROUND_HALF_UP)
						a_total_compensation = 0

					if purchase.is_recorded_on_customer_invoice == None:
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
					if  purchase.is_recorded_on_producer_invoice == None:
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

				# Calculate new current balance : Bank
				
				for bank_account in BankAccount.objects.select_for_update().filter(
				# for bank_account in BankAccount.objects.all().filter(
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
					permanence_id = permanence_id,
					producer = None,
					customer = None,
					operation_date = permanence_distribution_date,
					operation_status = BANK_LATEST_TOTAL,
					operation_comment = comment,
					bank_amount_in = a_bank_amount if a_bank_amount >= 0 else 0,
					bank_amount_out = -a_bank_amount if a_bank_amount < 0 else 0,
					is_recorded_on_customer_invoice = None,
					is_recorded_on_producer_invoice = None
				)
	except Exception, e:
			validation_passed = False

	if validation_passed:
		# now = datetime.datetime.utcnow().replace(tzinfo=utc)
		now = timezone.localtime(timezone.now())
		# email_invoices(permanence_id, current_site_name)
		menu_pool.clear()
		Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_DONE,is_done_on = now)
	else:
		Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_INVOICES_VALIDATION_FAILED)
