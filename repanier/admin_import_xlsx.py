# -*- coding: utf-8 -*-
from const import *
from tools import *
from decimal import *
from django import forms
from django.http import HttpResponseRedirect
from django.db.models import F
from django.utils.translation import ugettext_lazy as _
from views import render_response
from openpyxl import load_workbook
from repanier.views import render_response

import datetime
from django.utils.timezone import utc

from repanier.models import Producer
from repanier.models import Product
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_DepartmentForProducer
from repanier.models import OfferItem
from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import BankAccount
from repanier.models import Permanence

class ImportXlsxForm(forms.Form):
	_selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
	file_to_import = forms.FileField(
		label=_('File to import'), allow_empty_file=False
	)

def get_header(worksheet):
	header = []
	if worksheet:
		row_num = 0
		col_num = 0
		c = worksheet.cell(row=row_num, column=col_num)
		while (c.value!=None ) and (col_num < 50):
			header.append(c.value)
			col_num+=1
			c = worksheet.cell(row=row_num, column=col_num)
	return header

def get_row(worksheet, header, row_num):
	row = {}
	if worksheet:
		# last_row is a row with all cells empty
		last_row = True
		for col_num, col_header in enumerate(header):
			c = worksheet.cell(row=row_num, column=col_num)
			if c.value:
				last_row = False
			row[col_header]=c.value
		if last_row:
			row = {}
	return row

def import_producer_products(worksheet, producer = None, product_reorder=0):
	error = False
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			try:
				product_reorder += 1
				department_for_customer_id = None
				if row[_('department_for_customer')] != None:
					department_for_customer_set = LUT_DepartmentForCustomer.objects.filter(
					short_name = row[_('department_for_customer')])[:1]
					if department_for_customer_set:
						department_for_customer_id = department_for_customer_set[0].id
					else:
						department_for_customer = LUT_DepartmentForCustomer.objects.create(
							short_name = row[_('department_for_customer')],
							is_active = True)
						if department_for_customer!= None:
							department_for_customer_id = department_for_customer.id 

				department_for_producer_id = None
				if row[_('department_for_producer')] != None:
					department_for_producer_set = LUT_DepartmentForProducer.objects.filter(
					short_name = row[_('department_for_producer')])[:1]
					if department_for_producer_set:
						department_for_producer_id = department_for_producer_set[0].id
					else:
						department_for_producer = LUT_DepartmentForProducer.objects.create(
							short_name = row[_('department_for_producer')],
							is_active = True)
						if department_for_producer!= None:
							department_for_producer_id = department_for_producer.id 

				producer_unit_price = Decimal(row[_('producer_unit_price')]) if row[_('producer_unit_price')] != None else 0
				order_average_weight = Decimal(row[_('order_average_weight')]) if row[_('order_average_weight')] != None else 0
				customer_minimum_order_quantity = Decimal(row[_('customer_minimum_order_quantity')]) if row[_('customer_minimum_order_quantity')] != None else 0
				customer_increment_order_quantity = Decimal(row[_('customer_increment_order_quantity')]) if row[_('customer_increment_order_quantity')] != None else 0
				customer_alert_order_quantity = Decimal(row[_('customer_alert_order_quantity')]) if row[_('customer_alert_order_quantity')] != None else 0
				order_by_piece_pay_by_kg = ( row[_('order_by_piece_pay_by_kg')] != None )
				order_by_piece_pay_by_piece = ( row[_('order_by_piece_pay_by_piece')] != None )
				order_by_kg_pay_by_kg = ( row[_('order_by_kg_pay_by_kg')] != None )
				if order_by_piece_pay_by_kg:
					order_by_kg_pay_by_kg = False
					order_by_piece_pay_by_piece = False
					if order_average_weight <= 0:
						order_average_weight = 1
				elif order_by_kg_pay_by_kg:
					order_by_piece_pay_by_kg = False
					order_by_piece_pay_by_piece = False
					order_average_weight = 0
				else:
					order_by_kg_pay_by_kg = False
					order_by_piece_pay_by_kg = False
					order_average_weight = 0

				producer_unit_price = producer_unit_price * producer.price_list_multiplier if producer.price_list_multiplier > 0 else producer_unit_price
				producer_original_unit_price = producer_unit_price
				product_set = Product.objects.filter(
					producer_id = producer.id,
					long_name = row[_('long_name')]
				)[:1]
				if product_set:
					product = product_set[0]
					product.producer_id = producer.id
					product.long_name = row[_('long_name')]
					product.department_for_customer_id = department_for_customer_id
					product.department_for_producer_id = department_for_producer_id
					product.order_by_kg_pay_by_kg = order_by_kg_pay_by_kg
					product.order_by_piece_pay_by_kg = order_by_piece_pay_by_kg
					product.order_average_weight = order_average_weight
					product.order_by_piece_pay_by_piece = order_by_piece_pay_by_piece
					product.producer_must_give_order_detail_per_customer = ( row[_('producer_must_give_order_detail_per_customer')] != None )
					product.producer_unit_price = producer_unit_price
					product.producer_original_unit_price = producer_original_unit_price
					product.customer_minimum_order_quantity = customer_minimum_order_quantity
					product.customer_increment_order_quantity = customer_increment_order_quantity
					product.customer_alert_order_quantity = customer_alert_order_quantity
					product.is_into_offer = ( row[_('is_into_offer')] != None )
					product.is_active = True
					product.product_reorder = product_reorder
					product.save()
				else:
					product = Product.objects.create(
						producer = producer.id,
						long_name = row[_('long_name')],
						department_for_customer_id = department_for_customer_id,
						department_for_producer_id = department_for_producer_id,
						order_by_kg_pay_by_kg = order_by_kg_pay_by_kg,
						order_by_piece_pay_by_kg = order_by_piece_pay_by_kg,
						order_average_weight = order_average_weight,
						order_by_piece_pay_by_piece = order_by_piece_pay_by_piece,
						producer_must_give_order_detail_per_customer = ( row[_('producer_must_give_order_detail_per_customer')] != None ),
						producer_unit_price = producer_unit_price,
						producer_original_unit_price = producer_original_unit_price,
						customer_minimum_order_quantity = customer_minimum_order_quantity,
						customer_increment_order_quantity = customer_increment_order_quantity,
						customer_alert_order_quantity = customer_alert_order_quantity,
						is_into_offer = ( row[_('is_into_offer')] != None ),
						is_active = True,
						product_reorder = product_reorder
					)
				
				row_num += 1
				row = get_row(worksheet, header, row_num)
			except KeyError:
				# Missing field
				error = True
			except:
				raise
	return error

def handle_product_uploaded_file(request, queryset, file_to_import):
	error = False
	wb = load_workbook(file_to_import)
	Product.objects.all().update(product_reorder=F('product_order') + 100000)
	product_reorder = 0
	for producer in queryset:
		error |= import_producer_products(wb.get_sheet_by_name(producer.short_profile_name), producer=producer, product_reorder=product_reorder)
	order = 0
	for obj in Product.objects.all().order_by('product_reorder'):
		order += 1
		obj.product_order = order
		obj.save()
	for permanence in Permanence.objects.filter(status=PERMANENCE_OPENED):
		recalculate_order_amount(permanence.id)
	return error

def import_product_xlsx(producer, admin, request, queryset):
	form = None
	if 'apply' in request.POST:
		form = ImportXlsxForm(request.POST, request.FILES)
		if form.is_valid():
			print("ICICICICICI")
			file_to_import = request.FILES['file_to_import']
			if('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
				error = handle_product_uploaded_file(request, queryset, file_to_import)
				if error:
					producer.message_user(request, 
						_("Error when importing %s : Content not valid") % (file_to_import.name)
					)
				else:
					producer.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
			else:
				producer.message_user(request, 
					_("Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (file_to_import.name)
				)
		else:
			producer.message_user(request, _("No file to import."))
		return HttpResponseRedirect(request.get_full_path())
	if not form:
		form = ImportXlsxForm(
			initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
		)
	return render_response(request, 'repanier/import_xlsx.html', {
			'objects': queryset,
			'import_xlsx_form': form,
	})

def import_bank_movements(worksheet):
	error = False
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			try:
				if row[_('Id')] == None:
					# Only for a new movement
					producer = None
					customer = None
					if row[_('Who')] != None:
						producer_set = Producer.objects.filter(
							short_profile_name = row[_('Who')])[:1]
						if producer_set:
							producer = producer_set[0]
							if producer.is_active==False or producer.represent_this_buyinggroup:
								producer = None
						if producer == None:
							customer_set = Customer.objects.filter(
								short_basket_name = row[_('Who')])[:1]
							if customer_set:
								customer = customer_set[0]
							if customer.is_active==False or customer.represent_this_buyinggroup:
								customer = None
					bank_amount_in = Decimal(row[_('Bank_amount_in')]) if row[_('Bank_amount_in')] != None else 0
					bank_amount_out = Decimal(row[_('Bank_amount_out')]) if row[_('Bank_amount_out')] != None else 0
					operation_date = row[_('Operation_date')] if row[_('Operation_date')] != None else datetime.datetime.utcnow().replace(tzinfo=utc)
					if operation_date < datetime.datetime(2000, 01, 01):
						# Do not record anything if the date is abnormal
						producer = None
						customer = None
					if producer:
						BankAccount.objects.create(
							producer_id = producer.id,
							customer = None,
							operation_date = operation_date,
							operation_comment = row[_('Operation_comment')],
							bank_amount_in = bank_amount_in,
							bank_amount_out = bank_amount_out,
							is_recorded_on_customer_invoice = None,
							is_recorded_on_producer_invoice = None
						)
					if customer:
						BankAccount.objects.create(
							producer = None,
							customer_id = customer.id,
							operation_date = operation_date,
							operation_comment = row[_('Operation_comment')],
							bank_amount_in = bank_amount_in,
							bank_amount_out = bank_amount_out,
							is_recorded_on_customer_invoice = None,
							is_recorded_on_producer_invoice = None
						)

				row_num += 1
				row = get_row(worksheet, header, row_num)
			except KeyError:
				# Missing field
				error = True
			except:
				raise
	return error


def import_permanence_purchases(worksheet, permanence = None):
	vat_level_dict = dict(LUT_VAT_REVERSE)
	error = False
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			try:
				producer = None
				product = None
				offer_item = None
				if row[_('producer')] != None:
					producer_set = Producer.objects.filter(
						short_profile_name = row[_('producer')])[:1]
					if producer_set:
						producer = producer_set[0]
						if row[_('product')] != None:
							product_set = Product.objects.filter(
								producer_id = producer.id,
								long_name = row[_('product')])[:1]
							if product_set:
								product = product_set[0]
								offer_item_set = OfferItem.objects.filter(
									permanence_id = permanence.id,
									product_id = product.id
									)[:1]
								if offer_item_set:
									offer_item = offer_item_set[0]
				vat_level = None
				if row[_("vat or compensation")] in vat_level_dict:
					vat_level = vat_level_dict[row[_("vat or compensation")]]
				else:
					vat_level = VAT_400

				customer = None
				if row[_('customer')] != None:
					customer_set = Customer.objects.filter(
						short_basket_name = row[_('customer')])[:1]
					if customer_set:
						customer = customer_set[0]

				purchase = None
				if product and customer:
					purchase_set = Purchase.objects.filter(
						permanence = permanence,
						product = product,
						customer = customer)[:1]
					if purchase_set:
						purchase = purchase_set[0]
				prepared_quantity = Decimal(row[_('prepared_quantity')]) if row[_('prepared_quantity')] != None else 0
				repared_unit_price = Decimal(row[_('prepared_unit_price')]) if row[_('prepared_unit_price')] != None else 0
				prepared_amount = Decimal(row[_('prepared_amount')]) if row[_('prepared_amount')] != None else 0
				if purchase:
					purchase.prepared_quantity = prepared_quantity
					purchase.prepared_unit_price = repared_unit_price
					purchase.prepared_amount = prepared_amount
					purchase.comment = row[_('comment')]
					vat_level = vat_level
					purchase.save()
				else:
					purchase = Purchase.objects.create(
						permanence_id = permanence.id,
						distribution_date = permanence.distribution_date,
						product = product,
						offer_item = offer_item,
						producer = producer,
						customer = customer,
						order_quantity = 0,
						order_by_piece_pay_by_kg = False,
						prepared_long_name = row[_('product')],
						prepared_quantity = prepared_quantity,
						prepared_unit_price = repared_unit_price,
						prepared_amount = prepared_amount,
						vat_level = vat_level,
						comment = row[_('comment')],
						is_recorded_on_customer_on = None,
						is_recorded_on_producer_on = None
					)
				
				row_num += 1
				row = get_row(worksheet, header, row_num)
			except KeyError:
				# Missing field
				error = True
			except:
				raise
	return error


def handle_permanence_done_uploaded_file(request, queryset, file_to_import):
	error = False
	wb = load_workbook(file_to_import)
	for permanence in queryset:
		ws = wb.get_sheet_by_name(permanence.__unicode__())
		if ws:
			error |= import_permanence_purchases(ws, permanence=permanence)
	ws = wb.get_sheet_by_name(_("bank movements"))
	if ws:
		error |= import_bank_movements(ws)
	return error

def import_permanence_done_xlsx(permanence, admin, request, queryset):
	form = None
	if 'apply' in request.POST:
		form = ImportXlsxForm(request.POST, request.FILES)
		if form.is_valid():
			file_to_import = request.FILES['file_to_import']
			if('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
				error = handle_permanence_done_uploaded_file(request, queryset, file_to_import)
				if error:
					permanence.message_user(request, 
						_("Error when importing %s : Content not valid") % (file_to_import.name)
					)
				else:
					permanence.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
			else:
				permanence.message_user(request, 
					_("Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (file_to_import.name)
				)
		else:
			permanence.message_user(request, _("No file to import."))
		return HttpResponseRedirect(request.get_full_path())
	if not form:
		form = ImportXlsxForm(
			initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
		)
	return render_response(request, 'repanier/import_xlsx.html', {
			'objects': queryset,
			'import_xlsx_form': form,
	})
