# -*- coding: utf-8 -*-
from const import *
from tools import *
from decimal import *
from django import forms
from django.http import HttpResponseRedirect
from django.db.models import F
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from views import render_response
from openpyxl import load_workbook
from repanier.views import render_response

import datetime
from django.utils.timezone import utc

from repanier.models import Producer
from repanier.models import Product
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_ProductionMode
from repanier.models import OfferItem
from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import BankAccount
from repanier.models import Permanence

class ImportXlsxForm(forms.Form):
	_selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
	file_to_import = forms.FileField(
		label=_('File to import'), 
		allow_empty_file=False
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
			row[col_header] = None if c.data_type == c.TYPE_FORMULA else c.value
		if last_row:
			row = {}
	return row

def import_producer_products(worksheet, producer = None, product_reorder=0, db_write=False,
		department_for_customer_2_id_dict = None,
		production_mode_2_id_dict = None
	):
	vat_level_dict = dict(LUT_VAT_REVERSE)
	error = False
	error_msg = None
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			try:
				row_id = None
				if row[_('Id')] != None:
					row_id = Decimal(row[_('Id')])
				product_reorder += 1

				department_for_customer_id = None
				if row[_('department_for_customer')] in department_for_customer_2_id_dict:
					department_for_customer_id = department_for_customer_2_id_dict[row[_('department_for_customer')]]
				else:
					error = True
					error_msg = _("Row %(row_num)d : No valid departement for customer") % {'row_num': row_num + 1}
					break

				production_mode_id = None
				if row[_('production mode')] in production_mode_2_id_dict:
					production_mode_id = production_mode_2_id_dict[row[_('production mode')]]
				else:
					error = True
					error_msg = _("Row %(row_num)d : No valid production mode") % {'row_num': row_num + 1}
					break

				original_unit_price = None if row[_('original_unit_price')] == None else Decimal(row[_('original_unit_price')])
				unit_deposit = None if row[_('deposit')] == None else Decimal(row[_('deposit')])
				order_average_weight = None if row[_('order_average_weight')] == None else Decimal(row[_('order_average_weight')])
				customer_minimum_order_quantity = None if row[_('customer_minimum_order_quantity')] == None else Decimal(row[_('customer_minimum_order_quantity')])
				customer_increment_order_quantity = None if row[_('customer_increment_order_quantity')] == None else Decimal(row[_('customer_increment_order_quantity')])
				customer_alert_order_quantity = None if row[_('customer_alert_order_quantity')] == None else Decimal(row[_('customer_alert_order_quantity')])
				order_by_piece_pay_by_kg = ( row[_('order_by_piece_pay_by_kg')] != None )
				order_by_piece_pay_by_piece = ( row[_('order_by_piece_pay_by_piece')] != None )
				order_by_kg_pay_by_kg = ( row[_('order_by_kg_pay_by_kg')] != None )
				long_name = cap(row[_('long_name')], 100)
				product_set = Product.objects.filter(
					producer_id = producer.id,
					long_name = long_name
				).order_by()[:1]
				# print(long_name.encode('utf8'))
				if product_set:
					product = product_set[0]
					if row_id == product.id:
						# Detect VAT LEVEL. Fall back on product.
						vat_level = None
						if row[_("vat or compensation")] in vat_level_dict:
							vat_level = vat_level_dict[row[_("vat or compensation")]]
						elif product != None:
							vat_level = product.vat_level
						else:
							vat_level = producer.vat_level
						# Let only update if the given id is the same as the product found id
						product.producer_id = producer.id
						product.long_name = long_name
						product.production_mode_id = production_mode_id
						product.department_for_customer_id = department_for_customer_id
						product.order_by_kg_pay_by_kg = order_by_kg_pay_by_kg
						product.order_by_piece_pay_by_kg = order_by_piece_pay_by_kg
						if order_average_weight != None:
							product.order_average_weight = order_average_weight
						product.order_by_piece_pay_by_piece = order_by_piece_pay_by_piece
						product.producer_must_give_order_detail_per_customer = ( row[_('producer_must_give_order_detail_per_customer')] != None )
						if original_unit_price != None:
							product.original_unit_price = original_unit_price
						if unit_deposit != None:
							product.unit_deposit = unit_deposit
						if customer_minimum_order_quantity != None:
							product.customer_minimum_order_quantity = customer_minimum_order_quantity
						if customer_increment_order_quantity != None:
							product.customer_increment_order_quantity = customer_increment_order_quantity
						if customer_alert_order_quantity != None:
							product.customer_alert_order_quantity = customer_alert_order_quantity
						product.is_into_offer = ( row[_('is_into_offer')] != None )
						product.vat_level = vat_level
						product.is_active = True
						product.product_reorder = product_reorder
						if db_write:
							product.save()
					else:
						error = True
						if row[_('Id')]==None:
							error_msg = _("Row %(row_num)d : No id given, or the product %(producer)s - %(product)s already exist.") % {'row_num': row_num + 1, 'producer': producer.short_profile_name, 'product': row[_('long_name')]}
						else:
							error_msg = _("Row %(row_num)d : The given id %(record_id)s is not the id of %(producer)s - %(product)s.") % {'row_num': row_num + 1, 'record_id':row[_('Id')], 'producer': producer.short_profile_name, 'product': row[_('long_name')]}
						break
				else:
					if row_id == None:
						# Let only create product if non id in the row
						if db_write:
							# Detect VAT LEVEL. Can't fall back on product.
							vat_level = None
							if row[_("vat or compensation")] in vat_level_dict:
								vat_level = vat_level_dict[row[_("vat or compensation")]]
							else:
								vat_level = producer.vat_level

							if order_average_weight == None:
								order_average_weight = 0
							if original_unit_price == None:
								original_unit_price = 0
							if unit_deposit == None:
								unit_deposit = 0
							if customer_minimum_order_quantity == None:
								customer_minimum_order_quantity = 0
							if customer_increment_order_quantity == None:
								customer_increment_order_quantity = 0
							if customer_alert_order_quantity == None:
								customer_alert_order_quantity = 0
							Product.objects.create(
								producer = producer,
								long_name = long_name,
								production_mode_id = production_mode_id,
								department_for_customer_id = department_for_customer_id,
								order_by_kg_pay_by_kg = order_by_kg_pay_by_kg,
								order_by_piece_pay_by_kg = order_by_piece_pay_by_kg,
								order_average_weight = order_average_weight,
								order_by_piece_pay_by_piece = order_by_piece_pay_by_piece,
								producer_must_give_order_detail_per_customer = ( row[_('producer_must_give_order_detail_per_customer')] != None ),
								original_unit_price = original_unit_price,
								unit_deposit = unit_deposit,
								customer_minimum_order_quantity = customer_minimum_order_quantity,
								customer_increment_order_quantity = customer_increment_order_quantity,
								customer_alert_order_quantity = customer_alert_order_quantity,
								is_into_offer = ( row[_('is_into_offer')] != None ),
								is_active = True,
								product_reorder = product_reorder
							)
					else:
						error = True
						error_msg = _("Row %(row_num)d : The given id %(record_id)s is not the id of %(producer)s - %(product)s.") % {'row_num': row_num + 1, 'record_id':row[_('Id')], 'producer': producer.short_profile_name, 'product': row[_('long_name')]}
						break

				row_num += 1
				row = get_row(worksheet, header, row_num)
			except KeyError, e:
				# Missing field
				error = True
				error_msg = _("Row %(row_num)d : A required column is missing.") % {'row_num': row_num + 1}
			except Exception, e:
				error = True
				error_msg = _("Row %(row_num)d : %(error_msg)s.") % {'row_num': row_num + 1, 'error_msg':str(e)}
	return error, error_msg

def handle_product_uploaded_file(request, queryset, file_to_import):
	error = False
	error_msg = None
	wb = load_workbook(file_to_import)
	# dict for performance optimisation purpose : read the DB only once
	department_for_customer_2_id_dict=get_department_for_customer_2_id_dict()
	production_mode_2_id_dict=get_production_mode_2_id_dict()
	product_reorder = 0
	for producer in queryset:
		error, error_msg = import_producer_products(wb.get_sheet_by_name(unicode(cap(producer.short_profile_name,31))), producer=producer, product_reorder=product_reorder, db_write=False,
				department_for_customer_2_id_dict=department_for_customer_2_id_dict,
				production_mode_2_id_dict=production_mode_2_id_dict
			)
		if error:
			error_msg = producer.short_profile_name + " > " + error_msg
			break
	if not error:
		Product.objects.all().update(product_reorder=F('product_order') + 100000)
		product_reorder = 0
		for producer in queryset:
			error_flag, error_msg  = import_producer_products(wb.get_sheet_by_name(unicode(cap(producer.short_profile_name,31))), producer=producer, product_reorder=product_reorder, db_write=True,
					department_for_customer_2_id_dict=department_for_customer_2_id_dict,
					production_mode_2_id_dict=production_mode_2_id_dict
				)
			if error:
				error_msg = producer.short_profile_name + " > " + error_msg
				break
		order = 0
		for obj in Product.objects.all().order_by('producer__short_profile_name', 'product_reorder'):
			order += 1
			obj.product_order = order
			obj.save(update_fields=['product_order'])
		for permanence in Permanence.objects.filter(status=PERMANENCE_OPENED):
			recalculate_order_amount(permanence.id)
	return error, error_msg

def import_product_xlsx(producer, admin, request, queryset):
	form = None
	error_msg = None
	if 'apply' in request.POST:
		form = ImportXlsxForm(request.POST, request.FILES)
		if form.is_valid():
			file_to_import = request.FILES['file_to_import']
			if('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
				error, error_msg = handle_product_uploaded_file(request, queryset, file_to_import)
				if error:
					if error_msg == None:
						producer.message_user(request, 
							_("Error when importing %s : Content not valid") % (file_to_import.name),
							level=messages.WARNING
						)
					else:
						producer.message_user(request, 
							_("Error when importing %(file_name)s : %(error_msg)s") % {'file_name': file_to_import.name, 'error_msg':error_msg},
							level=messages.ERROR
						)
				else:
					producer.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
			else:
				producer.message_user(request, 
					_("Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (file_to_import.name),
					level=messages.ERROR
				)
		else:
			producer.message_user(request, _("No file to import."),level=messages.WARNING)
		return HttpResponseRedirect(request.get_full_path())
	elif 'cancel' in request.POST:
		producer.message_user(request, _("Action canceled by the user."),level=messages.WARNING)
		return HttpResponseRedirect(request.get_full_path())
	form = ImportXlsxForm(
		initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
	)
	return render_response(request, 'repanier/import_xlsx.html', {
		'title': _("Import products"),
		'objects': queryset,
		'import_xlsx_form': form,
	})

def import_bank_movements(worksheet, db_write = False,
		customer_2_id_dict=None,
		producer_2_id_dict=None
	):
	error = False
	error_msg = None
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			try:
				if row[_('Id')] == None:
					# Only for a new movement
					producer_id = None
					customer_id = None
					if row[_('Who')] != None:
						if row[_('Who')] in producer_2_id_dict:
							producer_id = producer_2_id_dict[row[_('Who')]]
						if producer_id == None:
							if row[_('Who')] in customer_2_id_dict:
								customer_id = customer_2_id_dict[row[_('Who')]]
					bank_amount_in = 0 if row[_('bank_amount_in')] == None else Decimal(row[_('bank_amount_in')])
					bank_amount_out = 0 if row[_('bank_amount_out')] == None else Decimal(row[_('bank_amount_out')])
					if bank_amount_in < 0 or bank_amount_out < 0:
						error = True
						error_msg = _("Row %(row_num)d : A bank amount is lower than 0") % {'row_num': row_num + 1}
					operation_date = None
					if row[_('Operation_date')] != None:
						operation_date = row[_('Operation_date')]
					if operation_date == None:
						error = True
						error_msg = _("Row %(row_num)d : The date is missing") % {'row_num': row_num + 1}
						break
					if operation_date < datetime.datetime(2000, 01, 01):
						# Do not record anything if the date is abnormal
						producer_id = None
						customer_id = None
					if producer_id:
						bank_account_set = BankAccount.objects.filter(
							producer_id = producer_id,
							customer = None,
							operation_date = operation_date,
							operation_comment = cap(row[_('Operation_comment')], 100)
						).order_by()[:1]
						if bank_account_set:
							error = True
							error_msg = _("Row %(row_num)d : A this date and for this producer, a bank movement already exist with the same comment") % {'row_num': row_num + 1}
							break
						if db_write:
							BankAccount.objects.create(
								producer_id = producer_id,
								customer = None,
								operation_date = operation_date,
								operation_comment = cap(row[_('Operation_comment')], 100),
								bank_amount_in = bank_amount_in,
								bank_amount_out = bank_amount_out,
								is_recorded_on_customer_invoice = None,
								is_recorded_on_producer_invoice = None
							)
					elif customer_id:
						bank_account_set = BankAccount.objects.filter(
							producer = None,
							customer_id = customer_id,
							operation_date = operation_date,
							operation_comment = cap(row[_('Operation_comment')], 100)
						).order_by()[:1]
						if bank_account_set:
							error = True
							error_msg = _("Row %(row_num)d : A this date and for this customer, a bank movement already exist with the same comment") % {'row_num': row_num + 1}
							break
						if db_write:
							BankAccount.objects.create(
								producer = None,
								customer_id = customer_id,
								operation_date = operation_date,
								operation_comment = cap(row[_('Operation_comment')], 100),
								bank_amount_in = bank_amount_in,
								bank_amount_out = bank_amount_out,
								is_recorded_on_customer_invoice = None,
								is_recorded_on_producer_invoice = None
							)
					elif row[_('Who')] != None:
						error = True
						error_msg = _("Row %(row_num)d : %(user_name)s is neither a customer nor a producer.") % {'row_num': row_num + 1, 'user_name':row[_('Who')]}
						break

				row_num += 1
				row = get_row(worksheet, header, row_num)
			except KeyError, e:
				# Missing field
				error = True
				error_msg = _("Row %(row_num)d : A required column is missing.") % {'row_num': row_num + 1}
			except Exception, e:
				error = True
				error_msg = _("Row %(row_num)d : %(error_msg)s.") % {'row_num': row_num + 1, 'error_msg':str(e)}
	return error, error_msg


def import_permanence_purchases(worksheet, permanence = None, db_write = False,
		customer_2_id_dict=None,
		id_2_customer_vat_id_dict=None,
		producer_2_id_dict=None,
		id_2_producer_vat_level_dict=None,
		customer_buyinggroup_id=None,
		producer_buyinggroup_id=None
	):
	vat_level_dict = dict(LUT_VAT_REVERSE)
	error = False
	error_msg = None
	header = get_header(worksheet)
	if header:
		row_num = 1
		row = get_row(worksheet, header, row_num)
		while row and not error:
			# try:
			row_id = None
			if row[_('Id')] != None:
				row_id = Decimal(row[_('Id')])
			producer_id = None
			product = None
			offer_item = None
			long_name = cap(row[_('product')], 100)
			comment = cap(row[_('comment')], 100)
			if row[_('producer')] in producer_2_id_dict:
				producer_id = producer_2_id_dict[row[_('producer')]]
				if long_name != None:
					product_set = Product.objects.filter(
						producer_id = producer_id,
						long_name = long_name).order_by()[:1]
					if product_set:
						product = product_set[0]
						offer_item_set = OfferItem.objects.filter(
							permanence_id = permanence.id,
							product_id = product.id
							).order_by()[:1]
						if offer_item_set:
							offer_item = offer_item_set[0]
			if producer_id == None:
				error = True
				error_msg = _("Row %(row_num)d : No valid producer") % {'row_num': row_num + 1}
				break

			customer_id = None
			if row[_('customer')] in customer_2_id_dict:
				customer_id = customer_2_id_dict[row[_('customer')]]
			if customer_id == None:
				error = True
				error_msg = _("Row %(row_num)d : No valid customer") % {'row_num': row_num + 1}
				break

			if customer_buyinggroup_id == customer_id and producer_buyinggroup_id == producer_id:
				error = True
				error_msg = _("Row %(row_num)d : The buying group sell to himself. But this kind of technical movements are automatically generated at invoicing.") % {'row_num': row_num + 1}
				break

			vat_level = None
			if row[_("vat or compensation")] in vat_level_dict:
				vat_level = vat_level_dict[row[_("vat or compensation")]]
			elif product != None:
				vat_level = product.vat_level
			elif producer_id in id_2_producer_vat_level_dict:
					vat_level = id_2_producer_vat_level_dict[producer_id]
			else:
				vat_level = VAT_400

			purchase = None
			if product != None:
				purchase_set = Purchase.objects.filter(
					permanence = permanence,
					product = product,
					customer = customer_id).order_by()[:1]
			else:
				purchase_set = Purchase.objects.filter(
					permanence = permanence,
					producer_id = producer_id,
					long_name = long_name,
					customer = customer_id).order_by()[:1]
			if purchase_set:
				purchase = purchase_set[0]

			quantity = None if row[_('quantity')] == None else Decimal(row[_('quantity')])
			original_unit_price = None if row[_('original unit price')] == None else Decimal(row[_('original unit price')])
			unit_deposit = 0 if row[_('deposit')] == None else Decimal(row[_('deposit')])
			if unit_deposit == None:
				unit_deposit = product.unit_deposit
			original_price = None if row[_('original price')] == None  else Decimal(row[_('original price')])

			if quantity == None:
				if original_price == None:
					error = True
					error_msg = _("Row %(row_num)d : No quantity given.") % {'row_num': row_num + 1}
				elif original_unit_price == None:
					quantity = Decimal('1')
					original_unit_price = original_price + unit_deposit
				else:
					divided_by = original_unit_price + unit_deposit
					if divided_by.is_zero():
						error = True
						error_msg = _("Row %(row_num)d : No quantity given.") % {'row_num': row_num + 1}
					else:
						quantity = original_price / divided_by
			else:
				if original_unit_price == None:
					if original_price == None:
						if product == None:
							error = True
							error_msg = _("Row %(row_num)d : No price given and product not known.") % {'row_num': row_num + 1}
						else:
							original_unit_price = product.original_unit_price + product.unit_deposit
							original_price = quantity * original_unit_price
					else:
						if quantity.is_zero() or ( original_unit_price.is_zero() and unit_deposit.is_zero() ) :
							error = True
							error_msg = _("Row %(row_num)d : No price or quantity given.") % {'row_num': row_num + 1}
						else:
							original_unit_price = ( original_price / quantity ) - unit_deposit
							# To avoid rouding errors
							quantity = original_price / ( original_unit_price + unit_deposit )
				else:
					if original_price == None:
						original_price = quantity * ( original_unit_price + unit_deposit )
					else:
						check_quantize = (quantity * ( original_unit_price + unit_deposit )).quantize(Decimal('.0001'), rounding=ROUND_UP)
						original_price_quantize = original_price.quantize(Decimal('.0001'), rounding=ROUND_UP)
						if abs(check_quantize - original_price_quantize) > 0.01:
							error = True
							error_msg = _("Row %(row_num)d : Price validation error. Calculated quantity * original unit price = %(check)f and given total price is %(total)f.") % {'row_num': row_num + 1, 'check':check_quantize, 'total': original_price_quantize}
			if error:
				break
			price_list_multiplier = DECIMAL_ONE if row[_("price_list_multiplier")] == None else Decimal(row[_("price_list_multiplier")])
			price_with_vat = original_price * price_list_multiplier if price_list_multiplier > DECIMAL_ZERO else original_price
			price_without_tax = price_with_vat
			if vat_level == VAT_400:
				price_without_tax /= Decimal(1.06)
			elif vat_level == VAT_500:
				price_without_tax /= Decimal(1.12)
			elif vat_level == VAT_600:
				price_without_tax /= Decimal(1.21)
			price_with_compensation = price_with_vat
			if vat_level == VAT_200:
				price_with_compensation *= Decimal(1.02)
			elif vat_level == VAT_300:
				price_with_compensation *= Decimal(1.06)
			else:
				# Important, has impact on order form and on invoice generation
				price_with_compensation = price_with_vat
			is_compensation = False
			price_with_tax = 0
			if (vat_level in [VAT_200, VAT_300]) and (id_2_customer_vat_id_dict[customer_id] != None):
				is_compensation = True
				price_with_tax = price_with_compensation
			else:
				price_with_tax = price_with_vat

			if purchase:
				if row_id == purchase.id:
					# Let only update if the given id is the same as the product found id
					purchase.original_unit_price = original_unit_price
					purchase.unit_deposit = unit_deposit
					purchase.original_price = original_price
					purchase.price_without_tax = price_without_tax
					purchase.price_with_tax =price_with_tax
					purchase.invoiced_price_with_compensation = is_compensation
					purchase.vat_level = vat_level
					purchase.price_list_multiplier = price_list_multiplier
					purchase.comment = comment
					if db_write:
						purchase.save(update_fields=[
							'quantity', 
							'original_unit_price', 
							'original_price',
							'price_without_tax',
							'price_with_tax',
							'invoiced_price_with_compensation',
							'vat_level',
							'price_list_multiplier',
							'comment', 
						])
				else:
					error = True
					if row[_('Id')]==None:
						error_msg = _("Row %(row_num)d : No id given, or a corresponding purchase already exist.") % {'row_num': row_num + 1}
					else:
						error_msg = _("Row %(row_num)d : The given id %(record_id)s is not the id of the purchase.") % {'row_num': row_num + 1, 'record_id':row[_('Id')]}
					break

			else:
				if row_id == None:
					# Let only create product if non id in the row
					if db_write:
						purchase = Purchase.objects.create(
							permanence_id = permanence.id,
							distribution_date = permanence.distribution_date,
							product = product,
							offer_item = offer_item,
							producer_id = producer_id,
							customer_id = customer_id,
							quantity = quantity,
							long_name = long_name,
							order_by_kg_pay_by_kg = False,
							order_by_piece_pay_by_kg = False,
							original_unit_price = original_unit_price,
							unit_deposit = unit_deposit,
							original_price = original_price,
							price_without_tax= price_without_tax,
							price_with_tax= price_with_tax,
							invoiced_price_with_compensation= is_compensation,
							vat_level = vat_level,
							price_list_multiplier=price_list_multiplier,
							comment = comment,
							is_recorded_on_customer_invoice = None,
							is_recorded_on_producer_invoice = None
						)
						purchase.permanence.producers.add(producer_id)
				else:
					error = True
					error_msg = _("Row %(row_num)d : The given id %(record_id)s is not the id of the purchase.") % {'row_num': row_num + 1, 'record_id':row[_('Id')]}
					break
			
			row_num += 1
			row = get_row(worksheet, header, row_num)
			# except KeyError, e:
			# 	# Missing field
			# 	error = True
			# 	error_msg = _("Row %(row_num)d : A required column is missing.") % {'row_num': row_num + 1}
			# except Exception, e:
			# 	error = True
			# 	error_msg = _("Row %(row_num)d : %(error_msg)s.") % {'row_num': row_num + 1, 'error_msg': str(e)}
	return error, error_msg


def handle_permanence_done_uploaded_file(request, queryset, file_to_import):
	error = False
	error_msg = None
	wb = load_workbook(file_to_import)
	# dict for performance optimisation purpose : read the DB only once
	customer_buyinggroup_id, customer_2_id_dict = get_customer_2_id_dict()
	id_2_customer_vat_id_dict=get_customer_2_vat_id_dict()
	producer_buyinggroup_id, producer_2_id_dict = get_producer_2_id_dict()
	id_2_producer_vat_level_dict = get_id_2_producer_vat_level_dict()
	if customer_buyinggroup_id == None:
		error=True
		error_msg = _("At least one customer must represent the buying group.")	
	else:
		if producer_buyinggroup_id == None:
			error=True
			error_msg = _("At least one producer must represent the buying group.")	
	if not error:
		for permanence in queryset:
			if permanence.status == PERMANENCE_SEND:
				ws = wb.get_sheet_by_name(unicode(cap(permanence.__unicode__(),31)))
				if ws:
					error, error_msg = import_permanence_purchases(ws, permanence=permanence, db_write=False,
						customer_2_id_dict=customer_2_id_dict,
						id_2_customer_vat_id_dict=id_2_customer_vat_id_dict,
						producer_2_id_dict=producer_2_id_dict,
						id_2_producer_vat_level_dict=id_2_producer_vat_level_dict,
						customer_buyinggroup_id=customer_buyinggroup_id,
						producer_buyinggroup_id=producer_buyinggroup_id
					)
					if error:
						error_msg = cap(permanence.__unicode__(),31) + " > " + error_msg
						break
			else:
				error=True
				error_msg = _("At least one of the permanences has already been invoiced.")
				break;
	if not error:
		ws = wb.get_sheet_by_name(cap(unicode(_("bank movements")),31))
		if ws:
			error, error_msg = import_bank_movements(ws, db_write=False,
				customer_2_id_dict=customer_2_id_dict,
				producer_2_id_dict=producer_2_id_dict
				)
			if error:
				error_msg = cap(unicode(_("bank movements")),31) + " > " + error_msg
	if not error:
		for permanence in queryset:
			ws = wb.get_sheet_by_name(cap(permanence.__unicode__(),31))
			if ws:
				error, error_msg  = import_permanence_purchases(ws, permanence=permanence, db_write=True,
					customer_2_id_dict=customer_2_id_dict,
					id_2_customer_vat_id_dict=id_2_customer_vat_id_dict,
					producer_2_id_dict=producer_2_id_dict,
					id_2_producer_vat_level_dict=id_2_producer_vat_level_dict,
					customer_buyinggroup_id=customer_buyinggroup_id,
					producer_buyinggroup_id=producer_buyinggroup_id
				)
				if error:
					error_msg = cap(permanence.__unicode__(),31) + " > " + error_msg
					break
		if not error:
			ws = wb.get_sheet_by_name(cap(unicode(_("bank movements")),31))
			if ws:
				error, error_msg  = import_bank_movements(ws, db_write=True,
					customer_2_id_dict=customer_2_id_dict,
					producer_2_id_dict=producer_2_id_dict
					)
				if error:
					error_msg = cap(unicode(_("bank movements")),31) + " > " + error_msg
	return error, error_msg

def import_permanence_done_xlsx(permanence, admin, request, queryset):
	form = None
	if 'apply' in request.POST:
		form = ImportXlsxForm(request.POST, request.FILES)
		if form.is_valid():
			file_to_import = request.FILES['file_to_import']
			if('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
				error, error_msg = handle_permanence_done_uploaded_file(request, queryset, file_to_import)
				if error:
					if error_msg == None:
						permanence.message_user(request, 
							_("Error when importing %s : Content not valid") % (file_to_import.name),
							level=messages.WARNING
						)
					else:
						permanence.message_user(request, 
							_("Error when importing %(file_name)s : %(error_msg)s") % {'file_name': file_to_import.name, 'error_msg':error_msg},
							level=messages.ERROR
						)
				else:
					permanence.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
			else:
				permanence.message_user(request, 
					_("Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (file_to_import.name),
					level=messages.ERROR
				)
		else:
			permanence.message_user(request, _("No file to import."), level=messages.WARNING)
		return HttpResponseRedirect(request.get_full_path())
	elif 'cancel' in request.POST:
		permanence.message_user(request, _("Action canceled by the user."),level=messages.WARNING)
		return HttpResponseRedirect(request.get_full_path())
	form = ImportXlsxForm(
		initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
	)
	return render_response(request, 'repanier/import_xlsx.html', {
		'title': _("Import purchases"),
		'objects': queryset,
		'import_xlsx_form': form,
	})
