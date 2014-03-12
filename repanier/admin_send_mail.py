# -*- coding: utf-8 -*-
from const import *
from django.conf import settings

from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.core.mail import EmailMultiAlternatives
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from openpyxl.writer.excel import save_virtual_workbook

from repanier.tools import *
from repanier.models import Customer
from repanier.models import Producer
from repanier.models import Staff
from repanier.models import PermanenceBoard
from repanier.models import Purchase
from repanier.models import Product
from repanier.models import Permanence
from repanier.admin_export_xlsx import export_order_producer_xlsx
from repanier.admin_export_xlsx import export_order_customer_xlsx
from repanier.admin_export_xlsx import export_orders_xlsx
from repanier.admin_export_xlsx import export_invoices_xlsx

def send_test_email(request, queryset):
	try:
		send_mail('Test sujet', 'Test msg', settings.ALLOWED_HOSTS[0] + '@repanier.be', ['pcolmant@gmail.com'])
		# send_mail('Test sujet', 'Test msg', 'coordi@repanier.be', ['pcolmant@gmail.com'])
	except BadHeaderError:
		self.message_user(request, _("Invalid header found."))

# subject, from_email, to = 'Order Confirmation', 'admin@yourdomain.com', 'someone@somewhere.com'

# html_content = render_to_string('the_template.html', {'varname':'value'}) # ...
# <div style="display: none"><a onclick="javascript:pageTracker._trackPageview('/outgoing/wikiexback.com/');" href="http://wikiexback.com/" title="how to get your ex back">how to get your ex back</a></div>

# text_content = strip_tags(html_content) # this strips the html, so people will have the text as well.

# # create the email, and attach the HTML version as well.
# msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
# msg.attach_alternative(html_content, "text/html")
# msg.send()

def email_offers(permanence_id, current_site):
	permanence = Permanence.objects.get(id=permanence_id)
	sender_email = settings.DEFAULT_FROM_EMAIL
	for staff in Staff.objects.all().active().order_by():
		if staff.is_reply_to_order_email:
			sender_email = staff.user.email
	bcc_email = []
	for customer in Customer.objects.all().active().not_the_buyinggroup().may_order().order_by():
		bcc_email.append(customer.user.email)
	html_content = permanence.offer_description
	email = EmailMultiAlternatives(
		_("Orders opened") + " " + current_site.name + ", " + permanence.__unicode__(), 
		strip_tags(html_content),
		sender_email,
		# [sender_email],
		bcc=bcc_email
	)
	email.attach_alternative(html_content, "text/html")
	email.send()

def email_orders(permanence_id, current_site):
	permanence = Permanence.objects.get(id=permanence_id)
	sender_email = settings.DEFAULT_FROM_EMAIL
	cc_email_staff = []
	for staff in Staff.objects.all().active().order_by():
		cc_email_staff.append(staff.user.email)
		if staff.is_reply_to_order_email:
			sender_email = staff.user.email
	board_composition = ""
	board_message = ""
	first_board = True
	for permanenceboard in PermanenceBoard.objects.filter(
		permanence=permanence_id).order_by():
		r_part = ''
		m_part = ''
		r=permanenceboard.permanence_role
		if r:
			r_part = r.short_name + ', '
			m_part = '</br>' + r.description
		c_part = ''
		c=permanenceboard.customer
		if c:
			c_part = c.short_basket_name + ',' + c.phone1
		if first_board:
			board_composition += '<br/>'
		board_composition += r_part + c_part + '<br/>'
		board_message += r_part + c_part + '<br/>' + m_part
		first_board = False
# Order adressed to our producers, 
	producer_set = Producer.objects.filter(
		permanence=permanence_id).order_by()
	for producer in producer_set:
		wb = export_order_producer_xlsx(permanence=permanence, producer=producer, wb=None)
		html_content = producer.order_description
		email = EmailMultiAlternatives(
			current_site.name + ", " + permanence.__unicode__() + " - " + producer.short_profile_name, 
			strip_tags(html_content), 
			sender_email, 
			[producer.email], 
			bcc=['pcolmant@gmail.com'],
			cc=cc_email_staff
		)
		email.attach(permanence.__unicode__() + '.xlsx', 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		email.send()
	customer_set = Customer.objects.filter(
		purchase__permanence=permanence_id).order_by().distinct()
	for customer in customer_set:
		wb = export_order_customer_xlsx(permanence=permanence, customer=customer, wb=None)
		html_content = permanence.order_description + board_composition
		email = EmailMultiAlternatives(
			current_site.name + ", " + permanence.__unicode__() + " - " + customer.short_basket_name, 
			strip_tags(html_content),
			sender_email, 
			[customer.user.email], 
			bcc=['pcolmant@gmail.com']
		)
		email.attach(permanence.__unicode__() + '.xlsx', 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		email.send()
	wb = export_orders_xlsx(permanence=permanence, wb=None)
	to_email_board = []
	for permanenceboard in PermanenceBoard.objects.filter(
		permanence=permanence_id).order_by():
		to_email_board.append(permanenceboard.customer.user.email)
	html_content = permanence.order_description + board_message
	email = EmailMultiAlternatives(
		current_site.name + ", " + permanence.__unicode__() + " - " + unicode(_('permanence preparation list')), 
		strip_tags(html_content),
		sender_email, 
		to_email_board, 
		bcc=['pcolmant@gmail.com'],
		cc=cc_email_staff
	)
	email.attach(permanence.__unicode__() + '.xlsx', 
		save_virtual_workbook(wb), 
		'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	email.attach_alternative(html_content, "text/html")
	email.send()

def email_invoices(permanence_id, current_site):
	permanence = Permanence.objects.get(id=permanence_id)
	sender_email = settings.DEFAULT_FROM_EMAIL
	cc_email = []
	for staff in Staff.objects.all().active().order_by():
		cc_email.append(staff.user.email)
		if staff.is_reply_to_invoice_email:
			sender_email = staff.user.email
# Invoices adressed to our producers, 
	producer_set = Producer.objects.filter(
		permanence=permanence_id).order_by()
	for producer in producer_set:
		wb = export_invoices_xlsx(permanence=permanence, producer=producer, wb=None)
		html_content = producer.invoice_description
		email = EmailMultiAlternatives(
			current_site.name + ", " + permanence.__unicode__() + " - " + producer.short_profile_name, 
			strip_tags(html_content), 
			sender_email, 
			[producer.email], 
			bcc=['pcolmant@gmail.com'],
			cc=cc_email
		)
		email.attach(permanence.__unicode__() + '.xlsx', 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		email.send()
	customer_set = Customer.objects.filter(
		purchase__permanence=permanence_id).order_by().distinct()
	for customer in customer_set:
		wb = export_invoices_xlsx(permanence=permanence, customer=customer, wb=None)
		html_content = permanence.invoice_description
		email = EmailMultiAlternatives(
			current_site.name + ", " + permanence.__unicode__() + " - " + customer.short_basket_name, 
			strip_tags(html_content),
			sender_email, 
			[customer.user.email], 
			bcc=['pcolmant@gmail.com']
		)
		email.attach(permanence.__unicode__() + '.xlsx', 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		email.send()
	wb = export_invoices_xlsx(permanence=permanence, wb=None)
	for permanenceboard in PermanenceBoard.objects.filter(
		permanence=permanence_id).order_by():
		html_content = permanence.invoice_description
		email = EmailMultiAlternatives(
			current_site.name + ", " + permanence.__unicode__() + " - " + unicode(_('permanence preparation list')), 
			strip_tags(html_content),
			sender_email, 
			[customer.user.email], 
			bcc=['pcolmant@gmail.com'],
			cc=cc_email
		)
		email.attach(permanence.__unicode__() + '.xlsx', 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		email.send()
