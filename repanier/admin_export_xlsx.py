# -*- coding: utf-8 -*-
from repanier.const import *
from tools import *

from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
# Alternative to openpyxl : XlsxWriter
from openpyxl.workbook import Workbook
from openpyxl.cell import get_column_letter
from openpyxl.style import Border
from openpyxl.style import NumberFormat
from openpyxl.writer.excel import save_virtual_workbook
from openpyxl.datavalidation import DataValidation, ValidationType, ValidationOperator

from repanier.tools import *
from repanier.models import Customer
from repanier.models import Producer
from repanier.models import Purchase
from repanier.models import Product
from repanier.models import BankAccount
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_ProductionMode


ROW_TITLE = 0
ROW_WIDTH = 1
ROW_VALUE = 2
ROW_FORMAT = 3
ROW_BOX = 4

def worksheet_setup_portait_a4(worksheet, title):
	worksheet.title = unicode(cap(title,31), "utf8")
	worksheet.page_setup.orientation = worksheet.ORIENTATION_PORTRAIT 
	worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
	worksheet.page_setup.fitToPage = True
	worksheet.page_setup.fitToHeight = 0
	worksheet.page_setup.fitToWidth = 1
	worksheet.print_gridlines = True

def worksheet_setup_landscape_a4(worksheet, title):
	worksheet.title = unicode(cap(title,31), "utf8")
	worksheet.page_setup.orientation = worksheet.ORIENTATION_LANDSCAPE 
	worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
	worksheet.page_setup.fitToPage = True
	worksheet.page_setup.fitToHeight = 0
	worksheet.page_setup.fitToWidth = 1
	worksheet.print_gridlines = True

def worksheet_set_header(worksheet, row_num, header):
	for col_num in xrange(len(header)):
		c = worksheet.cell(row=row_num, column=col_num)
		c.value = header[col_num][ ROW_TITLE ]
		c.style.font.bold = True
		c.style.alignment.wrap_text = True
		worksheet.column_dimensions[get_column_letter(col_num+1)].width = header[col_num][ ROW_WIDTH ]
		if header[col_num][ ROW_TITLE ] == unicode(_("Id")):
			worksheet.column_dimensions[get_column_letter(col_num+1)].visible = False

def export_orders_xlsx(permanence, wb = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()

# Customer info
	worksheet_setup_portait_a4(ws, unicode(permanence))

	header = [
		(unicode(_("Basket")), 20),
		(unicode(_('Family')), 35),
		(unicode(_('Phone1')), 15),
		(unicode(_('Phone2')), 15),
	]
	row_num = 0
	worksheet_set_header(ws, row_num, header)
	row_num += 1
	customer_set = Customer.objects.filter(
		purchase__permanence_id=permanence.id).distinct()
	for customer in customer_set:
		row = [
			customer.short_basket_name,
			customer.long_basket_name,
			customer.phone1,
			customer.phone2
		]
		for col_num in xrange(len(row)):
			c = ws.cell(row=row_num, column=col_num)
			c.value = row[col_num]
			c.style.alignment.wrap_text = True
		row_num += 1

	if permanence.status == PERMANENCE_WAIT_FOR_SEND:
# Customer label
		ws = wb.create_sheet()
		worksheet_setup_portait_a4(ws, unicode(_('Label')))
		row_num = 0
		customer_set = Customer.objects.filter(
			purchase__permanence_id=permanence.id).distinct()
		for customer in customer_set:
			c = ws.cell(row=row_num, column=0)
			c.value = customer.short_basket_name
			c.style.font.size = 36
			c.style.font.bold = False
			c.style.alignment.wrap_text = False
			c.style.borders.top.border_style = Border.BORDER_THIN
			c.style.borders.bottom.border_style = Border.BORDER_THIN
			c.style.borders.left.border_style = Border.BORDER_THIN
			c.style.borders.right.border_style = Border.BORDER_THIN
			c.style.alignment.vertical = 'center'
			c.style.alignment.horizontal = 'center'
			row_num += 1
			ws.row_dimensions[row_num].height = 60
		if row_num > 0:
			ws.column_dimensions[get_column_letter(1)].width = 120

	if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
# Basket check list, by customer
		ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, unicode(_('Customer check')))

		row_num = 0
		page_break = 40
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False).order_by(
			"customer__short_basket_name", 
			"-is_to_be_prepared",
			"product__placement", 
			"producer__short_profile_name", 
			"product__long_name"
		)
		customer_save = None
		for purchase in purchase_set:
			qty = purchase.quantity
			if (qty != 0 or not purchase.is_to_be_prepared):
				row = [
					(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Placement")), 15, purchase.product.get_placement_display() if purchase.product != None else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				]
				if not(row_num % page_break):
					if row_num > 1:
						ws.page_breaks.append(row_num)
					worksheet_set_header(ws, row_num, row)
					row_num += 1
				for col_num in xrange(len(row)):
					c = ws.cell(row=row_num, column=col_num)
					c.value = row[col_num][ ROW_VALUE ]
					c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
					if row[col_num][ ROW_BOX ]:
						c.style.borders.top.border_style = Border.BORDER_THIN   
						c.style.borders.bottom.border_style = Border.BORDER_THIN   
						c.style.borders.left.border_style = Border.BORDER_THIN   
						c.style.borders.right.border_style = Border.BORDER_THIN   							
					else:
						c.style.borders.bottom.border_style = Border.BORDER_HAIR    
					if customer_save!= purchase.customer.id:
						# Display the customer in bold when changing
						if col_num == 7: 
							c.style.font.bold = True
						c.style.borders.top.border_style = Border.BORDER_THIN
				if customer_save!= purchase.customer.id:
					customer_save = purchase.customer.id
				row_num += 1

	if PERMANENCE_WAIT_FOR_SEND <= permanence.status <= PERMANENCE_SEND:

# Preparation list

		ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, unicode(_('Preparation List')))

		row_num = 0
		previous_product_row_num = row_num
		previous_product_counter = 0
		previous_product_qty = 0
		previous_product_qty_sum = 0
		page_break = 40
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False).order_by(
			"-is_to_be_prepared",
			"producer__short_profile_name", 
			"product__placement", 
			"long_name",
			"quantity"
		)

		product_save = None
		producer_save = None
		for purchase in purchase_set:
			qty = purchase.quantity
			previous_product_qty_sum += qty
			previous_product_counter += 1
			if (qty != 0 or not purchase.is_to_be_prepared):
				row = [
					(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Placement")), 15, purchase.product.get_placement_display() if purchase.product != None else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("#")), 4, "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
					(unicode(_(u"Σ")), 10, "", '#,##0.???', False),
					(unicode(_("producer_must_give_order_detail_per_customer")), 5, unicode(_("Yes")) if purchase.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
				]
				if not(row_num % page_break):
					if row_num > 1:
						ws.page_breaks.append(row_num)
					worksheet_set_header(ws, row_num, row)
					row_num += 1
				for col_num in xrange(len(row)):
					c = ws.cell(row=row_num, column=col_num)
					c.value = row[col_num][ ROW_VALUE ]
					c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
					if row[col_num][ ROW_BOX ]:
						c.style.borders.top.border_style = Border.BORDER_THIN   
						c.style.borders.bottom.border_style = Border.BORDER_THIN   
						c.style.borders.left.border_style = Border.BORDER_THIN   
						c.style.borders.right.border_style = Border.BORDER_THIN   							
					else:
						c.style.borders.bottom.border_style = Border.BORDER_HAIR
					if product_save != purchase.long_name:
						# Display the product in bold when changing
						if col_num == 3: 
							c.style.font.bold = True
						c.style.borders.top.border_style = Border.BORDER_THIN
						if col_num == 2: 
							if producer_save != purchase.producer.id:
								c.style.font.bold = True
				if product_save!= purchase.long_name:
					if product_save != None:
						c = ws.cell(row=previous_product_row_num, column=8)
						c.value = previous_product_qty_sum - qty
					previous_product_qty = qty
					previous_product_qty_sum = qty
					previous_product_counter = 1
					product_save = purchase.long_name
					producer_save = purchase.producer.id
				else:
					if previous_product_qty != qty:
						previous_product_counter = 1
				previous_product_row_num = row_num
				previous_product_qty = qty
				if previous_product_counter > 1:
					c = ws.cell(row=previous_product_row_num, column=4)
					c.value = u"("+str(previous_product_counter)+")"
				row_num += 1

		if product_save != None:
			c = ws.cell(row=previous_product_row_num, column=8)
			c.value = previous_product_qty_sum

	if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
# Order adressed to our producers, 
		producer_set = Producer.objects.filter(permanence=permanence).order_by("short_profile_name")
		for producer in producer_set:

			export_order_producer_xlsx(permanence=permanence, producer=producer, wb=wb)

	return wb

def export_permanence_planified_xlsx(request, queryset):

	wb = Workbook()
	ws = wb.get_active_sheet()

	for permanence in queryset[:1]:

# Product selected in a planified permanence
		response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		response['Content-Disposition'] = 'attachment; filename=' + unicode(_('Preview')) + '.xlsx'
		worksheet_setup_landscape_a4(ws, permanence.__unicode__())
		row_num = 0
		page_break = 44

		if permanence.status == PERMANENCE_PLANIFIED:

			producers_in_this_permanence = Producer.objects.filter(
				permanence=permanence).active()

			for product in Product.objects.filter(
				producer__in = producers_in_this_permanence
				).active().is_selected_for_offer().order_by(
				"producer__short_profile_name",
				"product_order"):
				row = [
					(unicode(_("Producer")), 15, product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Department")), 15, product.department_for_customer.short_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, product.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit Price")), 10, product.original_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				]
				if row_num == 0:
					worksheet_set_header(ws, row_num, row)
					row_num += 1
				for col_num in xrange(len(row)):
					c = ws.cell(row=row_num, column=col_num)
					c.value = row[col_num][ ROW_VALUE ]
					c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
					if row[col_num][ ROW_BOX ]:
						c.style.borders.top.border_style = Border.BORDER_THIN   
						c.style.borders.bottom.border_style = Border.BORDER_THIN   
						c.style.borders.left.border_style = Border.BORDER_THIN   
						c.style.borders.right.border_style = Border.BORDER_THIN   							
					else:
						c.style.borders.bottom.border_style = Border.BORDER_HAIR


				col_num = len(row)
				q_min = product.customer_minimum_order_quantity
				q_alert = product.customer_alert_order_quantity
				q_step = product.customer_increment_order_quantity
				# The q_min cannot be 0. In this case try to replace q_min by q_step.
				# In last ressort by q_alert.
				if q_step <= 0:
					q_step = q_min
				if q_min <= 0:
					q_min = q_step
				if q_min <= 0:
					q_min = q_alert
					q_step = q_alert
				c = ws.cell(row=row_num, column=col_num)
				c.value = unicode('---')
				ws.column_dimensions[get_column_letter(col_num+1)].width = 2.3
				c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
				col_num += 1
				q_valid = q_min
				q_counter = 0 # Limit to avoid too long selection list
				while q_valid <= q_alert and q_counter <= 20:
					q_counter += 1
					c = ws.cell(row=row_num, column=col_num)
					c.value = get_qty_display(
						q_valid,
					 	product.order_average_weight,
						product.order_by_kg_pay_by_kg,
					 	product.order_by_piece_pay_by_kg
					)
					ws.column_dimensions[get_column_letter(col_num+1)].width = 15
					c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
					col_num += 1
					q_valid = q_valid + q_step

				row_num += 1

		if permanence.status > PERMANENCE_PLANIFIED:

			for offer_item in OfferItem.objects.all().permanence(permanence).active().order_by(
				'product__producer__short_profile_name', 
				'product__department_for_customer__short_name', 'product__long_name'):
				row = [
					(unicode(_("Producer")), 15, offer_item.product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Department")), 15, offer_item.product.department_for_customer.short_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, offer_item.product.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit Price")), 10, offer_item.product.original_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				]
				if row_num == 0:
					worksheet_set_header(ws, row_num, row)
					row_num += 1
				for col_num in xrange(len(row)):
					c = ws.cell(row=row_num, column=col_num)
					c.value = row[col_num][ ROW_VALUE ]
					c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
					if row[col_num][ ROW_BOX ]:
						c.style.borders.top.border_style = Border.BORDER_THIN   
						c.style.borders.bottom.border_style = Border.BORDER_THIN   
						c.style.borders.left.border_style = Border.BORDER_THIN   
						c.style.borders.right.border_style = Border.BORDER_THIN   							
					else:
						c.style.borders.bottom.border_style = Border.BORDER_HAIR


				col_num = len(row)
				q_min = offer_item.product.customer_minimum_order_quantity
				q_alert = offer_item.product.customer_alert_order_quantity
				q_step = offer_item.product.customer_increment_order_quantity
				# The q_min cannot be 0. In this case try to replace q_min by q_step.
				# In last ressort by q_alert.
				if q_step <= 0:
					q_step = q_min
				if q_min <= 0:
					q_min = q_step
				if q_min <= 0:
					q_min = q_alert
					q_step = q_alert
				c = ws.cell(row=row_num, column=col_num)
				c.value = unicode('---')
				ws.column_dimensions[get_column_letter(col_num+1)].width = 2.3
				c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
				col_num += 1
				q_valid = q_min
				q_counter = 0 # Limit to avoid too long selection list
				while q_valid <= q_alert and q_counter <= 20:
					q_counter += 1
					c = ws.cell(row=row_num, column=col_num)
					c.value = get_qty_display(
						q_valid,
					 	offer_item.product.order_average_weight,
						offer_item.product.order_by_kg_pay_by_kg,
					 	offer_item.product.order_by_piece_pay_by_kg
					)
					ws.column_dimensions[get_column_letter(col_num+1)].width = 15
					c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
					col_num += 1
					q_valid = q_valid + q_step

				row_num += 1


	wb.save(response)
	return response

def export_order_producer_xlsx(permanence, producer, wb = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()
	worksheet_setup_landscape_a4(ws, producer.short_profile_name)
	row_num = 0
	previous_product_row_num = row_num
	previous_product_qty = 0
	previous_product_qty_sum = 0
	previous_product_producer_must_give_order_detail_per_customer = None

	page_break = 40
	purchase_set = Purchase.objects.filter(
		permanence_id=permanence.id, producer_id=producer.id).order_by(
		"product_order",
		"long_name",
		"quantity"
	)

	producer_must_give_order_detail_per_customer_later = False
	product_save = None
	for purchase in purchase_set:
		qty = purchase.quantity
		previous_product_qty_sum += qty
		if (qty != 0):
			producer_must_give_order_detail_per_customer_later |= purchase.producer_must_give_order_detail_per_customer
			price = purchase.original_unit_price
			row = [
				(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
				(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
				(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Basket")), 15, purchase.customer.short_basket_name if purchase.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
				(unicode(_("Unit Price")), 10, price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
			]
			if not(row_num % page_break):
				if row_num > 1:
					ws.page_breaks.append(row_num)
				worksheet_set_header(ws, row_num, row)
				row_num += 1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.value = row[col_num][ ROW_VALUE ]
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
				if row[col_num][ ROW_BOX ]:
					c.style.borders.top.border_style = Border.BORDER_THIN   
					c.style.borders.bottom.border_style = Border.BORDER_THIN   
					c.style.borders.left.border_style = Border.BORDER_THIN   
					c.style.borders.right.border_style = Border.BORDER_THIN   							
				else:
					if product_save!= purchase.long_name:
						# Display the product in bold when changing
						c.style.borders.top.border_style = Border.BORDER_THIN
					else:
						c.style.borders.bottom.border_style = Border.BORDER_HAIR
				if col_num == 1: 
					c.style.font.bold = True

			row_increment = 0

			if product_save!= purchase.long_name:
				if product_save != None:
					if not previous_product_producer_must_give_order_detail_per_customer:
						qty_ok = previous_product_qty_sum - qty
						c = ws.cell(row=previous_product_row_num, column=1)
						c.value = qty_ok
						c = ws.cell(row=previous_product_row_num, column=2)
						if qty_ok > 1 and c.value==unicode(_("/ piece")):
							c.value = unicode(_("/ pieces"))
				previous_product_qty = qty
				previous_product_qty_sum = qty
				product_save = purchase.long_name
				row_increment = 1
			else:
				if purchase.producer_must_give_order_detail_per_customer:
					row_increment = 1
			previous_product_row_num += row_increment
			previous_product_qty = qty
			row_num += row_increment
			previous_product_producer_must_give_order_detail_per_customer = purchase.producer_must_give_order_detail_per_customer

	if product_save != None:
		if not previous_product_producer_must_give_order_detail_per_customer:
			qty_ok = previous_product_qty_sum - qty
			c = ws.cell(row=previous_product_row_num, column=1)
			c.value = qty_ok
			c = ws.cell(row=previous_product_row_num, column=2)
			if qty_ok > 1 and c.value==unicode(_("/ piece")):
				c.value = unicode(_("/ pieces"))
			for col_num in xrange(10):
				c = ws.cell(row=row_num, column=col_num)
				c.value = ""

	if producer_must_give_order_detail_per_customer_later:

# Order adressed to our producers, by customer for product "producer_must_give_order_detail_per_customer"

		ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, producer.short_profile_name + unicode(_(" Detail")))

		producer_must_give_order_detail_per_customer_later = False
		row_num = 0
		page_break = 40
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer_id=producer.id).order_by(
			"customer__short_basket_name",
			"product_order",
		)
		customer_save = None
		for purchase in purchase_set:
			qty = purchase.quantity
			if (qty != 0):
				if purchase.producer_must_give_order_detail_per_customer:
					price = purchase.original_unit_price
					total_price = 0 if purchase.order_by_piece_pay_by_kg else price * qty
					row = [
						(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
						(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
						(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
						(unicode(_("Unit Price")), 10, price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
						(unicode(_("Total Price")), 10, total_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False)
					]
					if not(row_num % page_break):
						if row_num > 1:
							ws.page_breaks.append(row_num)
						worksheet_set_header(ws, row_num, row)
						row_num += 1
					for col_num in xrange(len(row)):
						c = ws.cell(row=row_num, column=col_num)
						c.value = row[col_num][ ROW_VALUE ]
						c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
						if row[col_num][ ROW_BOX ]:
							c.style.borders.top.border_style = Border.BORDER_THIN   
							c.style.borders.bottom.border_style = Border.BORDER_THIN   
							c.style.borders.left.border_style = Border.BORDER_THIN   
							c.style.borders.right.border_style = Border.BORDER_THIN   							
						else:
							c.style.borders.bottom.border_style = Border.BORDER_HAIR 
						if customer_save!= purchase.customer.id:
							# Display the customer in bold when changing
							if col_num == 1: 
								c.style.font.bold = True
							c.style.borders.top.border_style = Border.BORDER_THIN
					if customer_save!= purchase.customer.id:
						customer_save = purchase.customer.id   
					row_num += 1
	return wb

def export_order_customer_xlsx(permanence, customer, wb = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()
	worksheet_setup_landscape_a4(ws, _('Customer check'))

	row_num = 0
	page_break = 40
	purchase_set = Purchase.objects.filter(
		permanence_id=permanence.id, customer_id=customer.id, producer__isnull=False).order_by(
		"customer__short_basket_name", 
		"-is_to_be_prepared",
		"product__placement", 
		"producer__short_profile_name", 
		"long_name"
	)
	customer_save = None
	for purchase in purchase_set:
		qty = purchase.quantity
		if (qty != 0 or not purchase.is_to_be_prepared):
			row = [
				(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
				(unicode(_("Placement")), 15, purchase.product.get_placement_display() if purchase.product != None else "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
				(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
			]
			if not(row_num % page_break):
				if row_num > 1:
					ws.page_breaks.append(row_num)
				worksheet_set_header(ws, row_num, row)
				row_num += 1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.value = row[col_num][ ROW_VALUE ]
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
				if row[col_num][ ROW_BOX ]:
					c.style.borders.top.border_style = Border.BORDER_THIN   
					c.style.borders.bottom.border_style = Border.BORDER_THIN   
					c.style.borders.left.border_style = Border.BORDER_THIN   
					c.style.borders.right.border_style = Border.BORDER_THIN   							
				else:
					c.style.borders.bottom.border_style = Border.BORDER_HAIR    
				if customer_save!= purchase.customer.id:
					# Display the customer in bold when changing
					if col_num == 4: 
						c.style.font.bold = True
					c.style.borders.top.border_style = Border.BORDER_THIN
			if customer_save!= purchase.customer.id:
				customer_save = purchase.customer.id
			row_num += 1
	return wb


def export_invoices_xlsx(permanence, customer = None, producer = None, wb = None, sheet_name = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()

# Detail of what has been prepared
	purchase_set = Purchase.objects.none()
	if customer == None and producer == None:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False, customer__isnull=False).order_by(
			"producer__short_profile_name",
			"product_order", 
			"customer__short_basket_name"
		)
	elif customer != None:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False, customer=customer).order_by(
			"producer__short_profile_name",
			"product_order", 
			"customer__short_basket_name"
		)
	else:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer=producer, customer__isnull=False).order_by(
			"producer__short_profile_name",
			"product_order", 
			"customer__short_basket_name"
		)
	if sheet_name:
		worksheet_setup_landscape_a4(ws, unicode(sheet_name))
	else:	
		worksheet_setup_landscape_a4(ws, unicode(_('Account')))
	row_num = 0
	page_break = 44

	for purchase in purchase_set:
		qty = purchase.quantity
		if (qty != 0):
			a_total_price_with_tax = purchase.price_with_tax
			a_total_vat = 0
			a_total_compensation = 0
			if purchase.invoiced_price_with_compensation:
				a_total_vat = 0
				a_total_compensation = purchase.price_with_tax - purchase.price_without_tax
			else:
				a_total_vat = purchase.price_with_tax - purchase.price_without_tax
				a_total_compensation = 0
			a_unit_price_with_tax = a_total_price_with_tax / qty
			row = [
				(unicode(_("Date")), 8, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
				(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Department")), 15, purchase.product.department_for_customer.short_name if purchase.product != None else "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Quantity")), 10, qty, '#,##0.???', True if purchase.order_by_piece_pay_by_kg else False),
				(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (not purchase.order_by_kg_pay_by_kg) else (unicode(_("/ pieces")) if (not purchase.order_by_kg_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Unit Invoided Price")), 10, a_unit_price_with_tax, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("Total Invoiced Price")), 10, a_total_price_with_tax , u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("Vat")), 10, a_total_vat , u'_ € * #,##0.000_ ;_ € * -#,##0.000_ ;_ € * "-"??_ ;_ @_ ', False)
			]
			if customer==None:
				row.append((unicode(_("Compensation")), 10, a_total_compensation, u'_ € * #,##0.000_ ;_ € * -#,##0.000_ ;_ € * "-"??_ ;_ @_ ', False))
			if customer!=None and customer.vat_id!=None:
				row.append((unicode(_("Compensation")), 10, a_total_compensation, u'_ € * #,##0.000_ ;_ € * -#,##0.000_ ;_ € * "-"??_ ;_ @_ ', False))
			if row_num == 0:
				worksheet_set_header(ws, row_num, row)
				row_num += 1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.value = row[col_num][ ROW_VALUE ]
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
				if row[col_num][ ROW_BOX ]:
					c.style.borders.top.border_style = Border.BORDER_THIN   
					c.style.borders.bottom.border_style = Border.BORDER_THIN   
					c.style.borders.left.border_style = Border.BORDER_THIN   
					c.style.borders.right.border_style = Border.BORDER_THIN   							
				else:
					c.style.borders.bottom.border_style = Border.BORDER_HAIR    
			row_num += 1

	return wb


def export_product_xlsx(request, queryset):

	wb = Workbook()
	ws = wb.get_active_sheet()
	response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = 'attachment; filename=' + unicode(_("products")) + '.xlsx'
	# list of Departement for customer
	valid_values=[]
	department_for_customer_set = LUT_DepartmentForCustomer.objects.all().active().order_by()
	for department_for_customer in department_for_customer_set:
		valid_values.append(department_for_customer.short_name)
	valid_values.sort()
	department_for_customer_list = get_list(wb=wb, valid_values=valid_values)
	# List of Production mode
	valid_values=[]
	production_mode_set = LUT_ProductionMode.objects.all().active().order_by()
	for production_mode in production_mode_set:
		valid_values.append(production_mode.short_name)
	valid_values.sort()
	production_mode_list = get_list(wb=wb, valid_values=valid_values)
	# List of Yes/ 
	valid_values=[unicode(_('Yes')),]
	yes_list = get_list(wb=wb, valid_values=valid_values)
	# List of Vat or Compensation
	valid_values=[]
	for record in LUT_VAT:
		valid_values.append(unicode(record[1]))
	vat_list = get_list(wb=wb, valid_values=valid_values)

	queryset = queryset.order_by("-short_profile_name")
	for producer in queryset:

		row_num = 0
		product_set = Product.objects.filter(
			producer_id=producer.id, is_active=True
		)
		product_save = None
		if ws == None:
			ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, producer.short_profile_name)
		for product in product_set:
			row = [
				(unicode(_("Id")), 10, product.id, '#,##0', False),
				(unicode(_("department_for_customer")), 15, product.department_for_customer.short_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("production mode")), 15, product.production_mode.short_name if product.production_mode != None else u"", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("is_into_offer")), 7,  unicode(_("Yes")) if product.is_into_offer else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("long_name")), 60, product.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_by_kg_pay_by_kg")), 7, unicode(_("Yes")) if product.order_by_kg_pay_by_kg else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_by_piece_pay_by_kg")), 7,  unicode(_("Yes")) if product.order_by_piece_pay_by_kg else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_average_weight")), 10, product.order_average_weight, '#,##0.???', False),
				(unicode(_("order_by_piece_pay_by_piece")), 7,  unicode(_("Yes")) if product.order_by_piece_pay_by_piece else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("producer_must_give_order_detail_per_customer")), 7,  unicode(_("Yes")) if product.producer_must_give_order_detail_per_customer else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("original_unit_price")), 10, product.original_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("deposit")), 10, product.unit_deposit, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("vat or compensation")), 10, product.get_vat_level_display(), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("customer_minimum_order_quantity")), 10, product.customer_minimum_order_quantity, '#,##0.???', False),
				(unicode(_("customer_increment_order_quantity")), 10, product.customer_increment_order_quantity, '#,##0.???', False),
				(unicode(_("customer_alert_order_quantity")), 10, product.customer_alert_order_quantity, '#,##0.???', False),
			]
			if row_num==0:
				worksheet_set_header(ws, row_num, row)
				row_num += 1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.value = row[col_num][ ROW_VALUE ]
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
				if row[col_num][ ROW_BOX ]:
					c.style.borders.top.border_style = Border.BORDER_THIN   
					c.style.borders.bottom.border_style = Border.BORDER_THIN   
					c.style.borders.left.border_style = Border.BORDER_THIN   
					c.style.borders.right.border_style = Border.BORDER_THIN   							
				else:
					c.style.borders.bottom.border_style = Border.BORDER_HAIR    
				if product_save!= product.department_for_customer.id:
					c.style.borders.top.border_style = Border.BORDER_THIN
			if product_save!= product.department_for_customer.id:
				product_save = product.department_for_customer.id
			row_num += 1
		#  Now, for helping the user encoding new purchases
		row = [
			(unicode(_("Id")), 10, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("department_for_customer")), 15, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("production mode")), 15, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("is_into_offer")), 7, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("long_name")), 60, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("order_by_kg_pay_by_kg")), 7, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("order_by_piece_pay_by_kg")), 7, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("order_average_weight")), 10, u"", '#,##0.???'),
			(unicode(_("order_by_piece_pay_by_piece")), 7, u"",  NumberFormat.FORMAT_TEXT),
			(unicode(_("producer_must_give_order_detail_per_customer")), 7, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("original_unit_price")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("deposit")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("vat or compensation")), 10, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("customer_minimum_order_quantity")), 10, u"", '#,##0.???'),
			(unicode(_("customer_increment_order_quantity")), 10, u"", '#,##0.???'),
			(unicode(_("customer_alert_order_quantity")), 10, u"", '#,##0.???'),
		]

		if row_num==0:
			#  add a header if there is no previous movement.
			worksheet_set_header(ws, row_num, row)
			row_num +=1

		# Data validation Id
		dv = DataValidation(ValidationType.WHOLE,
			ValidationOperator.EQUAL,
			0)
		ws.add_data_validation(dv)
		dv.ranges.append('A%s:A5000' % (row_num+1))
		# Data validation Departement for customer
		dv = DataValidation(ValidationType.LIST, formula1=department_for_customer_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('B2:B5000')
		# Data validation Production mode
		dv = DataValidation(ValidationType.LIST, formula1=production_mode_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('C2:C5000')
		# Data validation Yes/ 
		dv = DataValidation(ValidationType.LIST, formula1=yes_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('D2:D5000')
		dv = DataValidation(ValidationType.LIST, formula1=yes_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('F2:G5000')
		dv = DataValidation(ValidationType.LIST, formula1=yes_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('I2:J5000')
		# Data validation qty / weight
		dv = DataValidation(ValidationType.DECIMAL,
			ValidationOperator.GREATER_THAN_OR_EQUAL,
			0)
		ws.add_data_validation(dv)
		dv.ranges.append('H2:H5000')
		dv = DataValidation(ValidationType.DECIMAL,
			ValidationOperator.GREATER_THAN_OR_EQUAL,
			0)
		ws.add_data_validation(dv)
		dv.ranges.append('L2:L5000')
		dv = DataValidation(ValidationType.DECIMAL,
			ValidationOperator.GREATER_THAN_OR_EQUAL,
			0)
		ws.add_data_validation(dv)
		dv.ranges.append('N2:P5000')
		# Data validation Vat or Compensation
		dv = DataValidation(ValidationType.LIST, formula1=vat_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('M2:M5000')
		# End of data validation

		#  Add formating for empty cells.
		for row_num in xrange(row_num,row_num+30):
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]

		# if row_num > 0:
		# Let's create a new sheet for the next producer
		ws = None
	wb.worksheets.reverse()
	wb.save(response)
	return response

def export_permanence_done_xlsx(request, queryset):

	wb = Workbook()
	ws = wb.get_active_sheet()
	response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = 'attachment; filename=' + unicode(_("invoices")) + '.xlsx'
	# list of Customer
	valid_values=[]
	customer_set = Customer.objects.all().active().order_by()
	for customer in customer_set:
		valid_values.append(customer.short_basket_name)
	valid_values.sort()
	customer_list = get_list(wb=wb, valid_values=valid_values)
	# List of Producer
	valid_values=[]
	producer_set = Producer.objects.all().active().order_by()
	for producer in producer_set:
		valid_values.append(producer.short_profile_name)
	valid_values.sort()
	producer_list = get_list(wb=wb, valid_values=valid_values)
	# List of Vat or Compensation
	valid_values=[]
	for record in LUT_VAT:
		valid_values.append(unicode(record[1]))
	vat_list = get_list(wb=wb, valid_values=valid_values)

	for permanence in queryset:

		if ws == None:
			ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, permanence.__unicode__())

		row_num = 0
		page_break = 40
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id
		).order_by(
			"producer",
			"product_order",
			"customer"
		)
		for purchase in purchase_set:
			row = [
				(unicode(_("Id")), 10, purchase.id, '#,##0', False),
				(unicode(_("producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("customer")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("quantity")), 10, purchase.quantity, '#,##0.???', True if purchase.order_by_piece_pay_by_kg else False),
				(unicode(_("original unit price")), 10, purchase.original_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("deposit")), 10, purchase.unit_deposit, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("original price")), 10, purchase.original_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("comment")), 30, purchase.comment, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("vat or compensation")), 10, purchase.get_vat_level_display(), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("price_list_multiplier")), 10, u"" if purchase.price_list_multiplier == DECIMAL_ONE else purchase.price_list_multiplier , '#,##0.???', False),
			]
			if row_num == 0:
				worksheet_set_header(ws, row_num, row)
				row_num += 1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.value = row[col_num][ ROW_VALUE ]
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
				if row[col_num][ ROW_BOX ]:
					c.style.borders.top.border_style = Border.BORDER_THIN   
					c.style.borders.bottom.border_style = Border.BORDER_THIN   
					c.style.borders.left.border_style = Border.BORDER_THIN   
					c.style.borders.right.border_style = Border.BORDER_THIN   							
				else:
					c.style.borders.bottom.border_style = Border.BORDER_HAIR    

			row_num += 1

		#  Now, for helping the user encoding new purchases
		row = [
			(unicode(_("Id")), 10, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("producer")), 15, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("customer")), 15, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("product")), 60, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("quantity")), 10, u"", '#,##0.???'),
			(unicode(_("original unit price")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("deposit")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("original price")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("comment")), 30, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("vat or compensation")), 10, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("price_list_multiplier")), 10, u"", '#,##0.???'),
		]
		if row_num==0:
			#  add a header if there is no previous movement.
			worksheet_set_header(ws, row_num, row)
			row_num +=1

		# Data validation Id
		dv = DataValidation(ValidationType.WHOLE,
			ValidationOperator.EQUAL,
			0)
		ws.add_data_validation(dv)
		dv.ranges.append('A%s:A5000' % (row_num+1))
		# Data validation Producer
		dv = DataValidation(ValidationType.LIST, formula1=producer_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('B2:B5000')
		# Data validation Customer
		dv = DataValidation(ValidationType.LIST, formula1=customer_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('C2:C5000')
		# Data validation Vat or Compensation
		dv = DataValidation(ValidationType.LIST, formula1=vat_list, allow_blank=True)
		ws.add_data_validation(dv)
		dv.ranges.append('J2:J5000')
		# End of data validation

		#  Add formating for empty cells.
		for row_num in xrange(row_num,row_num+30):
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]

		# use a new ws if needed for another permanence
		ws = None

	ws = wb.create_sheet()
	worksheet_setup_landscape_a4(ws, unicode(_("bank movements")))
	row_num = 0
	page_break = 40
	bank_account_set = BankAccount.objects.filter(
		is_recorded_on_customer_invoice__isnull=True,
		is_recorded_on_producer_invoice__isnull=True
	).order_by(
		"operation_date"
	)
	for bank_account in bank_account_set:
		row = [
			(unicode(_("Id")), 10, bank_account.id, '#,##0', False),
			(unicode(_("Operation_date")), 8, bank_account.operation_date, NumberFormat.FORMAT_DATE_XLSX16, False),
			(unicode(_("Who")), 15, bank_account.customer.short_basket_name if bank_account.customer else bank_account.producer.short_profile_name if bank_account.producer else unicode(_("N/A")), NumberFormat.FORMAT_TEXT, True if bank_account.producer else False),
			(unicode(_("Bank_amount_in")), 10, bank_account.bank_amount_in, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
			(unicode(_("Bank_amount_out")), 10, bank_account.bank_amount_out, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
			(unicode(_("Operation_comment")), 30, bank_account.operation_comment, NumberFormat.FORMAT_TEXT, False),
		]

		if row_num == 0:
			worksheet_set_header(ws, row_num, row)
			row_num += 1

		for col_num in xrange(len(row)):
			c = ws.cell(row=row_num, column=col_num)
			c.value = row[col_num][ ROW_VALUE ]
			c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
			if row[col_num][ ROW_BOX ]:
				c.style.borders.top.border_style = Border.BORDER_THIN   
				c.style.borders.bottom.border_style = Border.BORDER_THIN   
				c.style.borders.left.border_style = Border.BORDER_THIN   
				c.style.borders.right.border_style = Border.BORDER_THIN   							
			else:
				c.style.borders.bottom.border_style = Border.BORDER_HAIR    

		row_num += 1
	#  Now, for helping the user encoding new movement
	row = [
		(unicode(_("Id")), 10, u"", '#,##0'),
		(unicode(_("Operation_date")), 8, u"", NumberFormat.FORMAT_DATE_XLSX16),
		(unicode(_("Who")), 15, u"", NumberFormat.FORMAT_TEXT),
		(unicode(_("Bank_amount_in")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
		(unicode(_("Bank_amount_out")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
		(unicode(_("Operation_comment")), 30, u"", NumberFormat.FORMAT_TEXT),
	]
	if row_num==0:
		#  add a header if there is no previous movement.
		worksheet_set_header(ws, row_num, row)
		row_num +=1

	# Data validation Id
	dv = DataValidation(ValidationType.WHOLE,
		ValidationOperator.EQUAL,
		0)
	ws.add_data_validation(dv)
	dv.ranges.append('A%s:A500' % (row_num+1))
	# Data validation Operation_date
	dv = DataValidation(ValidationType.DATE,
		ValidationOperator.GREATER_THAN_OR_EQUAL,
		0)
	ws.add_data_validation(dv)
	dv.ranges.append('B2:B500')
	# Data validation Who
	valid_values=[]
	customer_set = Customer.objects.all().active().order_by()
	for customer in customer_set:
		valid_values.append(customer.short_basket_name)
	producer_set = Producer.objects.all().active().order_by()
	for producer in producer_set:
		valid_values.append(producer.short_profile_name)
	valid_values.sort()
	who_list = get_list(wb=wb, valid_values=valid_values)
	dv = DataValidation(ValidationType.LIST, formula1=who_list, allow_blank=True)
	ws.add_data_validation(dv)
	dv.ranges.append('C2:C500')
	# Data validation Bank_amount_in and Bank_amount_out
	dv = DataValidation(ValidationType.DECIMAL,
		ValidationOperator.GREATER_THAN_OR_EQUAL,
		0)
	ws.add_data_validation(dv)
	dv.ranges.append('D2:E500')
	# End of data validation

	#  Add formating for empty cells.
	for row_num in xrange(row_num,row_num+30):
		for col_num in xrange(len(row)):
			c = ws.cell(row=row_num, column=col_num)
			c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]

	wb.worksheets.reverse()
	wb.save(response)
	return response

def get_worksheet_and_col_for_data_validation(wb=None):
	ws_dv_name = cap(unicode(_("data validation")),31)
	ws = wb.get_sheet_by_name(ws_dv_name)
	if ws==None:
		ws = wb.create_sheet(index=0)
		worksheet_setup_landscape_a4(ws, ws_dv_name)
	col_num = 0
	c = ws.cell(row=0, column=col_num)
	while (c.value!=None ) and (col_num < 20):
		col_num+=1
		c = ws.cell(row=0, column=col_num)
	return ws, ws_dv_name, col_num, get_column_letter(col_num + 1)

def get_list(wb=None, valid_values=None):
	if valid_values:
		ws_dv, ws_dv_name, col_dv, col_letter_dv = get_worksheet_and_col_for_data_validation(wb=wb)
		row_num = 0
		for v in valid_values:
			c = ws_dv.cell(row=row_num, column=col_dv)
			c.value = v
			c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
			row_num +=1
		formula1 = "'%s'!$%s$1:$%s$%s" % (ws_dv_name, col_letter_dv, col_letter_dv, row_num + 1)
		return formula1