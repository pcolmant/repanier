# -*- coding: utf-8 -*-
from repanier.const import *
import cStringIO

from django.http import HttpResponse
from django.core.mail import send_mail, BadHeaderError
from django.core.mail import EmailMessage
from django.utils.translation import ugettext_lazy as _
# Alternative to openpyxl : XlsxWriter
from openpyxl.workbook import Workbook
from openpyxl.cell import get_column_letter
from openpyxl.style import Border
from openpyxl.style import NumberFormat
from openpyxl.writer.excel import save_virtual_workbook

from repanier.tools import *
from repanier.models import Customer
from repanier.models import Producer
from repanier.models import Purchase
from repanier.models import Product
from repanier.models import BankAccount


ROW_TITLE = 0
ROW_WIDTH = 1
ROW_VALUE = 2
ROW_FORMAT = 3
ROW_BOX = 4

def worksheet_setup_portait_a4(worksheet, title):
	worksheet.title = unicode(title)
	worksheet.page_setup.orientation = worksheet.ORIENTATION_PORTRAIT 
	worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
	worksheet.page_setup.fitToPage = True
	worksheet.page_setup.fitToHeight = 0
	worksheet.page_setup.fitToWidth = 1
	worksheet.print_gridlines = True

def worksheet_setup_landscape_a4(worksheet, title):
	worksheet.title = unicode(title)
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
		worksheet.column_dimensions[get_column_letter(col_num+1)].width = header[col_num][ ROW_WIDTH ]

def export_orders_xlsx(permanence, wb = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()

# Customer info
	ws = wb.get_active_sheet()
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

	if permanence.status == PERMANENCE_SEND:
# Customer label
		ws = wb.create_sheet()
		worksheet_setup_portait_a4(ws, _('Label'))
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
		ws.column_dimensions[get_column_letter(1)].width = 120

	if permanence.status == PERMANENCE_SEND:
# Basket check list, by customer
		ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, _('Customer check'))

		row_num = 0
		page_break = 40
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False).order_by(
			"customer__short_basket_name", 
			"-is_to_be_prepared",
			"producer__short_profile_name", 
			"product__placement", 
			"product__long_name"
		)
		customer_save = None
		for purchase in purchase_set:
			qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
			if (qty != 0 or not purchase.is_to_be_prepared):
				row = [
					(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Placement")), 15, purchase.product.get_placement_display(), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Separated")), 5, unicode(_("separated_yes")) if purchase.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.product.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.product.order_by_piece_pay_by_kg else False),
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

	if permanence.status == PERMANENCE_SEND:

# Preparation list, for those working by producer

		ws = wb.create_sheet()
		worksheet_setup_landscape_a4(ws, _('Preparation List'))

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
			"product__long_name",
			"prepared_quantity",
			"order_quantity"
		)

		product_save = None
		for purchase in purchase_set:
			qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
			previous_product_qty_sum += qty
			previous_product_counter += 1
			if (qty != 0 or not purchase.is_to_be_prepared):
				row = [
					(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Placement")), 15, purchase.product.get_placement_display(), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("#")), 4, "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
					(unicode(_(u"Σ")), 10, "", '#,##0.???', False),
					(unicode(_("Separated")), 5, unicode(_("separated_yes")) if purchase.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.product.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.product.order_by_piece_pay_by_kg else False),
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
					if product_save!= purchase.product.id:
						# Display the product in bold when changing
						if col_num == 3: 
							c.style.font.bold = True
						c.style.borders.top.border_style = Border.BORDER_THIN
				if product_save!= purchase.product.id:
					if product_save != None:
						c = ws.cell(row=previous_product_row_num, column=8)
						c.value = previous_product_qty_sum - qty
					previous_product_qty = qty
					previous_product_qty_sum = qty
					previous_product_counter = 1
					product_save = purchase.product.id
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

	if permanence.status == PERMANENCE_SEND:
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
		response['Content-Disposition'] = 'attachment; filename=' + permanence.__unicode__() + '.xlsx'
		worksheet_setup_landscape_a4(ws, _('Order choices'))
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
					(unicode(_("Unit Price")), 10, product.producer_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
					(unicode(_("Separated")), 5, unicode(_("separated_yes")) if product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Added")), 15, product.get_automatically_added_display(), NumberFormat.FORMAT_TEXT, False),
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
					(unicode(_("Unit Price")), 10, offer_item.product.producer_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
					(unicode(_("Separated")), 5, unicode(_("separated_yes")) if offer_item.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Added")), 15, offer_item.product.get_automatically_added_display(), NumberFormat.FORMAT_TEXT, False),
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
	previous_product_counter = 0
	previous_product_qty = 0
	previous_product_qty_sum = 0
	previous_product_total_price_sum = 0
	previous_product_producer_must_give_order_detail_per_customer = None

	page_break = 40
	purchase_set = Purchase.objects.filter(
		permanence_id=permanence.id, producer_id=producer.id).order_by(
		"product__product_order",
		"prepared_quantity",
		"order_quantity"
	)

	producer_must_give_order_detail_per_customer_later = False
	product_save = None
	for purchase in purchase_set:
		qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
		previous_product_qty_sum += qty
		previous_product_counter += 1
		if (qty != 0):
			producer_must_give_order_detail_per_customer_later |= purchase.product.producer_must_give_order_detail_per_customer
			price = purchase.product.producer_unit_price if permanence.status < PERMANENCE_SEND else purchase.prepared_unit_price
			total_price = 0 if purchase.product.order_by_piece_pay_by_kg else price * qty
			previous_product_total_price_sum += total_price
			row = [
				(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
				(unicode(_("#")), 4, "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
				(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
				(unicode(_(u"Σ")), 10, "", '#,##0.???', False),
				(unicode(_("Basket")), 15, purchase.customer.short_basket_name if purchase.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.product.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.product.order_by_piece_pay_by_kg else False),
				(unicode(_("Unit Price")), 10, price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("Total Price")), 10, total_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_(u"Σ")), 10, "", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
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
				if product_save!= purchase.product.id:
					# Display the product in bold when changing
					if col_num == 1: 
						c.style.font.bold = True
					c.style.borders.top.border_style = Border.BORDER_THIN
			row_increment = 0

			if product_save!= purchase.product.id:
				if product_save != None:
					if not previous_product_producer_must_give_order_detail_per_customer:
						c = ws.cell(row=previous_product_row_num, column=2)
						c.value = previous_product_qty_sum - qty
						c = ws.cell(row=previous_product_row_num, column=9)
						c.value = previous_product_total_price_sum - total_price
					else:
						c = ws.cell(row=previous_product_row_num, column=5)
						c.value = previous_product_qty_sum - qty
					c = ws.cell(row=previous_product_row_num, column=10)
					c.value = previous_product_total_price_sum - total_price
				previous_product_qty = qty
				previous_product_qty_sum = qty
				previous_product_total_price_sum = total_price
				previous_product_counter = 1
				product_save = purchase.product.id
				row_increment = 1
			else:
				if purchase.product.producer_must_give_order_detail_per_customer:
					row_increment = 1
				if previous_product_qty != qty:
					previous_product_counter = 1
			previous_product_row_num += row_increment
			previous_product_qty = qty
			if purchase.product.producer_must_give_order_detail_per_customer and previous_product_counter > 1:
				c = ws.cell(row=previous_product_row_num, column=1)
				c.value = u"("+str(previous_product_counter)+")"
			row_num += row_increment
			previous_product_producer_must_give_order_detail_per_customer = purchase.product.producer_must_give_order_detail_per_customer

	if product_save != None:
		if not previous_product_producer_must_give_order_detail_per_customer:
			c = ws.cell(row=previous_product_row_num, column=2)
			c.value = previous_product_qty_sum - qty
			for col_num in xrange(10):
				c = ws.cell(row=row_num, column=col_num)
				c.value = ""
			c = ws.cell(row=previous_product_row_num, column=9)
			c.value = previous_product_total_price_sum - total_price
		else:
			c = ws.cell(row=previous_product_row_num, column=5)
			c.value = previous_product_qty_sum - qty
		c = ws.cell(row=previous_product_row_num, column=10)
		c.value = previous_product_total_price_sum - total_price

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
			"product__product_order",
		)
		customer_save = None
		for purchase in purchase_set:
			qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
			if (qty != 0):
				if purchase.product.producer_must_give_order_detail_per_customer:
					price = purchase.product.producer_unit_price if permanence.status < PERMANENCE_SEND else purchase.prepared_unit_price
					total_price = 0 if purchase.product.order_by_piece_pay_by_kg else price * qty
					row = [
						(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
						(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
						(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
						(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.product.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.product.order_by_piece_pay_by_kg else False),
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
		"producer__short_profile_name", 
		"product__placement", 
		"product__long_name"
	)
	customer_save = None
	for purchase in purchase_set:
		qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
		if (qty != 0 or not purchase.is_to_be_prepared):
			row = [
				(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
				(unicode(_("Placement")), 15, purchase.product.get_placement_display(), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
				(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Separated")), 5, unicode(_("separated_yes")) if purchase.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
				(unicode(_("Weigh")), 20, unicode(_(u"€ or Kg :")) if purchase.product.order_by_piece_pay_by_kg else "", NumberFormat.FORMAT_TEXT, True if purchase.product.order_by_piece_pay_by_kg else False),
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


def export_invoices_xlsx(permanence, customer = None, producer = None, wb = None):

	ws=None
	if wb==None:
		wb = Workbook()
		ws = wb.get_active_sheet()
	else:
		ws = wb.create_sheet()
# Detail of what has been prepared
		
	worksheet_setup_landscape_a4(ws, unicode(_('Account')))
	row_num = 0
	page_break = 44

# Detail of what has been prepared
	purchase_set = Purchase.objects.none()
	if customer == None and producer == None:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False, customer__isnull=False).order_by(
			"producer__short_profile_name",
			"product__product_order", 
			"customer__short_basket_name"
		)
	elif customer != None:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer__isnull=False, customer=customer).order_by(
			"producer__short_profile_name",
			"product__product_order", 
			"customer__short_basket_name"
		)
	else:
		purchase_set = Purchase.objects.filter(
			permanence_id=permanence.id, producer=producer, customer__isnull=False).order_by(
			"producer__short_profile_name",
			"product__product_order", 
			"customer__short_basket_name"
		)

	for purchase in purchase_set:
		qty = purchase.order_quantity if permanence.status<PERMANENCE_SEND else purchase.prepared_quantity
		if (qty != 0):
			if purchase.product:
				# Product purchased
				row = [
					(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Department")), 15, purchase.product.department_for_producer.short_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, purchase.product.long_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Separated")), 5, unicode(_("separated_yes")) if purchase.product.producer_must_give_order_detail_per_customer else "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', True if purchase.product.order_by_piece_pay_by_kg else False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")) if qty < 2 and (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else (unicode(_("/ pieces")) if (purchase.product.order_by_piece_pay_by_piece or purchase.product.order_by_piece_pay_by_kg) else unicode(_("/ Kg"))), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit Price")), 10, purchase.product.producer_unit_price if permanence.status < PERMANENCE_SEND else purchase.prepared_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
					(unicode(_("Total Price")), 10, "=G"+str(row_num+1)+"*I"+str(row_num+1) if row_num % page_break else  "=G"+str(row_num+2)+"*I"+str(row_num+2) , u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False)
				]
			else:
				# Prodcut added for invoice purpose
				row = [
					(unicode(_("Date")), 7, purchase.distribution_date, NumberFormat.FORMAT_DATE_XLSX16, False),
					(unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Department")), 15, unicode(_("N/A")), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Product")), 60, unicode(_("N/A")), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Basket")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Separated")), 5, "", NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Quantity")), 10, qty, '#,##0.???', False),
					(unicode(_("Unit")), 10, unicode(_("/ piece")), NumberFormat.FORMAT_TEXT, False),
					(unicode(_("Unit Price")), 10, purchase.prepared_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
					(unicode(_("Total Price")), 10, "=G"+str(row_num+1)+"*I"+str(row_num+1) if row_num % page_break else  "=G"+str(row_num+2)+"*I"+str(row_num+2) , u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False)
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

	return wb


def export_product_xlsx(request, queryset):

	wb = Workbook()
	ws = wb.get_active_sheet()
	response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = 'attachment; filename=' + unicode(_("products")) + '.xlsx'

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
				(unicode(_("long_name")), 60, product.long_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("department_for_customer")), 15, product.department_for_customer.short_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("department_for_producer")), 15, product.department_for_producer.short_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_by_kg_pay_by_kg")), 7, unicode(_("Yes")) if product.order_by_kg_pay_by_kg else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_by_piece_pay_by_kg")), 7,  unicode(_("Yes")) if product.order_by_piece_pay_by_kg else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("order_average_weight")), 10, product.order_average_weight, '#,##0.???', False),
				(unicode(_("order_by_piece_pay_by_piece")), 7,  unicode(_("Yes")) if product.order_by_piece_pay_by_piece else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("producer_must_give_order_detail_per_customer")), 7,  unicode(_("Yes")) if product.producer_must_give_order_detail_per_customer else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("producer_unit_price")), 10, product.producer_original_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("customer_minimum_order_quantity")), 10, product.customer_minimum_order_quantity, '#,##0.???', False),
				(unicode(_("customer_increment_order_quantity")), 10, product.customer_increment_order_quantity, '#,##0.???', False),
				(unicode(_("customer_alert_order_quantity")), 10, product.customer_alert_order_quantity, '#,##0.???', False),
				(unicode(_("producer_must_give_order_detail_per_customer")), 7,  unicode(_("Yes")) if product.producer_must_give_order_detail_per_customer else None, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("is_into_offer")), 7,  unicode(_("Yes")) if product.is_into_offer else None, NumberFormat.FORMAT_TEXT, False),
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
				if product_save!= product.department_for_producer.id:
					c.style.borders.top.border_style = Border.BORDER_THIN
			if product_save!= product.department_for_producer.id:
				product_save = product.department_for_producer.id
			row_num += 1
		if row_num==0:
			#  For helping the user encoding new movement, add a header if
			#  there is no previous movement.
			row = [
				(unicode(_("long_name")), 60, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("department_for_customer")), 15, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("department_for_producer")), 15, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("order_by_kg_pay_by_kg")), 7, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("order_by_piece_pay_by_kg")), 7, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("order_average_weight")), 10, u"", '#,##0.???'),
				(unicode(_("order_by_piece_pay_by_piece")), 7, u"",  NumberFormat.FORMAT_TEXT),
				(unicode(_("producer_must_give_order_detail_per_customer")), 7, u"", NumberFormat.FORMAT_TEXT),
				(unicode(_("producer_unit_price")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
				(unicode(_("customer_minimum_order_quantity")), 10, u"", '#,##0.???'),
				(unicode(_("customer_increment_order_quantity")), 10, u"", '#,##0.???'),
				(unicode(_("customer_alert_order_quantity")), 10, u"", '#,##0.???'),
				(unicode(_("producer_must_give_order_detail_per_customer")), 7, u"",  NumberFormat.FORMAT_TEXT),
				(unicode(_("is_into_offer")), 7, u"", NumberFormat.FORMAT_TEXT),
			]
			worksheet_set_header(ws, row_num, row)
			row_num +=1
			for col_num in xrange(len(row)):
				c = ws.cell(row=row_num, column=col_num)
				c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]

		# if row_num > 0:
		# Let's create a new sheet for the next producer
		ws = None
	wb.save(response)
	return response

def export_permanence_done_xlsx(request, queryset):

	wb = Workbook()
	ws = wb.get_active_sheet()
	response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = 'attachment; filename=' + unicode(_("orders prepared")) + '.xlsx'

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
			"product__product_order",
			"customer"
		)
		for purchase in purchase_set:
			row = [
				(unicode(_("producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("customer")), 15, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
				(unicode(_("product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, True if purchase.order_by_piece_pay_by_kg else False),
				(unicode(_("prepared_quantity")), 10, purchase.prepared_quantity, '#,##0.???', False),
				(unicode(_("prepared_unit_price")), 10, purchase.prepared_unit_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("prepared_amount")), 10, purchase.prepared_amount, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
				(unicode(_("vat or compensation")), 10, purchase.get_vat_level_display(), NumberFormat.FORMAT_TEXT, False),
				(unicode(_("comment")), 30, purchase.comment, NumberFormat.FORMAT_TEXT, False),
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
		if row_num > 0:
			ws = None
	if ws == None:
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
			(unicode(_("Who")), 15, bank_account.customer.short_basket_name if bank_account.customer else bank_account.producer.short_profile_name, NumberFormat.FORMAT_TEXT, True if bank_account.producer else False),
			(unicode(_("Bank_amount_in")), 10, bank_account.bank_amount_in, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
			(unicode(_("Bank_amount_out")), 10, bank_account.bank_amount_out, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
			(unicode(_("Operation_comment")), 30, bank_account.operation_comment, NumberFormat.FORMAT_TEXT, False),
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

		row_num += 1
	if row_num==0:
		#  For helping the user encoding new movement, add a header if
		#  there is no previous movement.
		row = [
			(unicode(_("Id")), 10, u"", '#,##0'),
			(unicode(_("Operation_date")), 8, u"", NumberFormat.FORMAT_DATE_XLSX16),
			(unicode(_("Who")), 15, u"", NumberFormat.FORMAT_TEXT),
			(unicode(_("Bank_amount_in")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("Bank_amount_out")), 10, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
			(unicode(_("Operation_comment")), 30, u"", NumberFormat.FORMAT_TEXT),
		]
		worksheet_set_header(ws, row_num, row)
		row_num +=1
		for col_num in xrange(len(row)):
			c = ws.cell(row=row_num, column=col_num)
			c.style.number_format.format_code = row[col_num][ ROW_FORMAT ]
	wb.save(response)
	return response

