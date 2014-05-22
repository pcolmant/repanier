# -*- coding: utf-8 -*-
from const import *
from django.conf import settings

from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.core import urlresolvers
from django.core.mail import EmailMultiAlternatives
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

def send_alert_email(permanence, current_site_name):
	try:
		send_mail('Alert - ' + " - " + unicode(permanence) + " - " + current_site_name, permanence.get_status_display(), settings.ALLOWED_HOSTS[0] + '@repanier.be', [v for k,v in settings.ADMINS])
	except:
		pass

# subject, from_email, to = 'Order Confirmation', 'admin@yourdomain.com', 'someone@somewhere.com'

# html_content = render_to_string('the_template.html', {'varname':'value'}) # ...
# <div style="display: none"><a onclick="javascript:pageTracker._trackPageview('/outgoing/wikiexback.com/');" href="http://wikiexback.com/" title="how to get your ex back">how to get your ex back</a></div>

# text_content = strip_tags(html_content) # this strips the html, so people will have the text as well.

# # create the email, and attach the HTML version as well.
# msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
# msg.attach_alternative(html_content, "text/html")
# msg.send()

def email_offers(permanence_id, current_site_name):
	permanence = Permanence.objects.get(id=permanence_id)
	sender_email = settings.DEFAULT_FROM_EMAIL
	sender_function = ""
	signature = ""
	cc_email_staff = []
	for staff in Staff.objects.all().active().order_by():
		cc_email_staff.append(staff.user.email)
		if staff.is_reply_to_order_email:
			sender_email = staff.user.username + '@repanier.be'
			sender_function = staff.long_name
			r = staff.customer_responsible
			if r:
				if r.long_basket_name:
					signature = r.long_basket_name + " - " + r.phone1
				else:
					signature = r.short_basket_name + " - " + r.phone1
				if r.phone2:
					signature += " / " + r.phone2

	for customer in Customer.objects.all().active().not_the_buyinggroup().may_order().order_by():
		cc_email_staff.append(customer.user.email)
	long_basket_name = customer.long_basket_name if customer.long_basket_name != None else customer.short_baskrt_name
	html_content = unicode(_('Hello')) + ",<br/><br/>" + unicode(_('The order of')) + \
		" " + unicode(permanence) + " " + unicode(_("are now opened.")) + "<br/>" + permanence.offer_description + \
		"<br/>" + current_site_name + \
		"<br/>" + sender_function + \
		"<br/>" + signature
	email = EmailMultiAlternatives(
		unicode(_("Opening of orders")) + " - " + unicode(permanence) + " - " + current_site_name, 
		strip_tags(html_content),
		sender_email,
		# [sender_email],
		bcc=cc_email_staff
	)
	email.attach_alternative(html_content, "text/html")
	if not settings.DEBUG:
		email.send()
	else:
		email.to = [v for k,v in settings.ADMINS]
		email.cc = []
		email.bcc = []
		# email.send()

def email_orders(permanence_id, current_site_name):
	permanence = Permanence.objects.get(id=permanence_id)
	filename = (unicode(_("Order")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1', errors='ignore')
	sender_email = settings.DEFAULT_FROM_EMAIL
	sender_function = ""
	signature = ""
	cc_email_staff = []

	for staff in Staff.objects.all().active():
		cc_email_staff.append(staff.user.email)
		if staff.is_reply_to_order_email:
			sender_email = staff.user.username + '@repanier.be'
			sender_function = staff.long_name
			r = staff.customer_responsible
			if r:
				if r.long_basket_name:
					signature = r.long_basket_name + " - " + r.phone1
				else:
					signature = r.short_basket_name + " - " + r.phone1
				if r.phone2:
					signature += " / " + r.phone2

	board_composition = ""
	board_message = ""
	first_board = True
	for permanenceboard in PermanenceBoard.objects.filter(
		permanence=permanence_id):
		r_part = ''
		m_part = ''
		r=permanenceboard.permanence_role
		if r:
			r_part = r.short_name + ', '
			m_part = '</br>' + r.description
		c_part = ''
		c=permanenceboard.customer
		if c:
			if c.phone2:
				c_part = c.long_basket_name + ',<b>' + c.phone1 + ',' + c.phone2 + '</b>'
			else:
				c_part = c.long_basket_name + ',<b>' + c.phone1 + '</b>'
			if first_board:
				board_composition += '<br/>'
			board_composition += c_part + '<br/>'
		board_message += r_part + c_part + '<br/>' + m_part
		first_board = False
# Order adressed to our producers, 
	producer_set = Producer.objects.filter(
		permanence=permanence_id).order_by()
	for producer in producer_set:
		if producer.email.upper().find("NO-SPAM.WS") < 0:
			wb = export_order_producer_xlsx(permanence=permanence, producer=producer, wb=None)
			if wb != None:
				long_profile_name = producer.long_profile_name if producer.long_profile_name != None else producer.short_profile_name
				html_content = unicode(_('Dear')) + " " +long_profile_name + ",<br/><br/>" + unicode(_('In attachment, you will find the detail of our order for the')) + \
					" " + unicode(permanence) + ".<br/><br/>" + unicode(_('In case of impediment for delivering the order, please advertise the preparation team :')) + \
					"<br/>" + board_composition + \
					"<br/><br/>" + current_site_name + \
					"<br/>" + sender_function + \
					"<br/>" + signature
				email = EmailMultiAlternatives(
					unicode(_("Order")) + " - " + unicode(permanence) + " - " + current_site_name + " - " + long_profile_name, 
					strip_tags(html_content), 
					sender_email, 
					[producer.email],
					cc=cc_email_staff
				)
				email.attach(filename, 
					save_virtual_workbook(wb), 
					'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
				email.attach_alternative(html_content, "text/html")
				if not settings.DEBUG:
					email.send()
				else:
					email.to = [v for k,v in settings.ADMINS]
					email.cc = []
					email.bcc = []
					# email.send()

	customer_set = Customer.objects.filter(
		purchase__permanence=permanence_id).not_the_buyinggroup().order_by().distinct()
	for customer in customer_set:
		wb = export_order_customer_xlsx(permanence=permanence, customer=customer, wb=None)
		if wb != None:
			long_basket_name = customer.long_basket_name if customer.long_basket_name != None else customer.short_baskrt_name
			html_content = unicode(_('Dear')) + " " + long_basket_name + ",<br/><br/>" + unicode(_('In attachment, you will find the detail of your order for the')) + \
				" " + unicode(permanence) + ".<br/><br/>" + unicode(_('In case of impediment for keeping your basket, please advertise the preparation team :')) + \
				"<br/><br/>" + board_composition + \
				"<br/><br/>" + current_site_name + \
				"<br/>" + sender_function + \
				"<br/>" + signature
			email = EmailMultiAlternatives(
				unicode(_("Order")) + " - " + unicode(permanence) + " - " + current_site_name + " - " + long_basket_name, 
				strip_tags(html_content),
				sender_email, 
				[customer.user.email]
			)
			email.attach(filename, 
				save_virtual_workbook(wb), 
				'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
			email.attach_alternative(html_content, "text/html")
			if not settings.DEBUG:
				email.send()
			else:
				email.to = [v for k,v in settings.ADMINS]
				email.cc = []
				email.bcc = []
				# email.send()

	wb = export_orders_xlsx(permanence=permanence, wb=None)
	if wb != None:
		to_email_board = []
		for permanenceboard in PermanenceBoard.objects.filter(
			permanence=permanence_id).order_by():
			if permanenceboard.customer:
				to_email_board.append(permanenceboard.customer.user.email)
		html_content = unicode(_('Dear preparation team member')) + ",<br/><br/>" + unicode(_('In attachment, you will find the preparation lists for the')) + \
			" " + unicode(permanence) + ".<br/><br/>" + unicode(_('In case of impediment, please advertise the other member of the preparation team :')) + \
			"<br/><br/>" + board_message + \
			"<br/><br/>" + current_site_name + \
			"<br/>" + sender_function + \
			"<br/>" + signature

			# unicode(_('Or, at default a member of the staff team :')) + \
			# "<br/>" + staff_composition + \

		email = EmailMultiAlternatives(
			unicode(_('Permanence preparation list')) + " - " + unicode(permanence) + " - " + current_site_name, 
			strip_tags(html_content),
			sender_email, 
			to_email_board,
			cc=cc_email_staff
		)
		email.attach(filename, 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		if not settings.DEBUG:
			email.send()
		else:
			email.to = [v for k,v in settings.ADMINS]
			email.cc = []
			email.bcc = []
			# email.send()

def email_invoices(permanence_id, current_site_name):
	permanence = Permanence.objects.get(id=permanence_id)
	filename = (unicode(_("Invoice")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1', errors='ignore')
	sender_email = settings.DEFAULT_FROM_EMAIL
	sender_function = ""
	signature = ""
	cc_email_staff = []
	staff_composition = ""
	first_staff = True
	for staff in Staff.objects.all().active():
		cc_email_staff.append(staff.user.email)
		if staff.is_reply_to_invoice_email:
			sender_email = staff.user.username + '@repanier.be'
			sender_function = staff.long_name
			r = staff.customer_responsible
			if r:
				if r.long_basket_name:
					signature = r.long_basket_name + " - " + r.phone1
				else:
					signature = r.short_basket_name + " - " + r.phone1
				if r.phone2:
					signature += " / " + r.phone2
		s_part = staff.long_name + ', '
		c_part = ''
		c=staff.customer_responsible
		if c:
			if c.phone2:
				c_part = c.long_basket_name + ',<b>' + c.phone1 + ',' + c.phone2 + '</b>'
			else:
				c_part = c.long_basket_name + ',<b>' + c.phone1 + '</b>'
		if first_staff:
			staff_composition += '<br/>'
		staff_composition += s_part + c_part + '<br/>'
		first_staff = False

# Invoices adressed to our producers, 
	producer_set = Producer.objects.filter(
		permanence=permanence_id).order_by()
	for producer in producer_set:
		if producer.email.upper().find("NO-SPAM.WS") < 0:
			long_profile_name = producer.long_profile_name if producer.long_profile_name != None else producer.short_profile_name
			wb = export_invoices_xlsx(permanence=permanence, producer=producer, wb=None, sheet_name=long_profile_name)
			if wb != None:
				invoices_url = 'http://' + settings.ALLOWED_HOSTS[0] + urlresolvers.reverse(
					'invoicep_uuid_view', 
					args=(0, producer.uuid )
				)
				html_content = unicode(_('Dear')) + " " + long_profile_name + ",<br/><br/>" + unicode(_('In attachment, you will find the detail of our payment for the')) + \
					' <a href="' + invoices_url + '">' + unicode(permanence) + \
					"</a>.<br/><br/>" + unicode(_('In case of discordance, please advertise the staff team :')) + \
					"<br/>" + staff_composition + \
					"<br/><br/>" + current_site_name + \
					"<br/>" + sender_function + \
					"<br/>" + signature
				email = EmailMultiAlternatives(
					unicode(_('Invoice')) + " - " + unicode(permanence) + " - " + current_site_name + " - " + long_profile_name,
					strip_tags(html_content), 
					sender_email, 
					[producer.email], 
					cc=[sender_email]
				)
				email.attach(filename, 
					save_virtual_workbook(wb), 
					'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
				email.attach_alternative(html_content, "text/html")
				if not settings.DEBUG:
					email.send()
				else:
					email.to = [v for k,v in settings.ADMINS]
					email.cc = []
					email.bcc = []
					# email.send()

	customer_set = Customer.objects.filter(
		purchase__permanence=permanence_id).not_the_buyinggroup().order_by().distinct()
	for customer in customer_set:
		long_basket_name = customer.long_basket_name if customer.long_basket_name != None else customer.short_baskrt_name
		wb = export_invoices_xlsx(permanence=permanence, customer=customer, wb=None, sheet_name=long_basket_name)
		if wb != None:
			html_content = unicode(_('Dear')) + " " + long_basket_name + ",<br/><br/>" + unicode(_('Your invoice of')) + \
				" " + unicode(permanence) + " " + unicode(_("is now available in attachment")) + ".<br/>" + permanence.invoice_description + \
				"<br/>" + current_site_name + \
				"<br/>" + sender_function + \
				"<br/>" + signature
			email = EmailMultiAlternatives(
				unicode(_('Invoice')) + " - " + unicode(permanence) + " - " + current_site_name + " - " + long_basket_name,
				strip_tags(html_content),
				sender_email, 
				[customer.user.email]
			)
			email.attach(filename, 
				save_virtual_workbook(wb), 
				'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
			email.attach_alternative(html_content, "text/html")
			if not settings.DEBUG:
				email.send()
			else:
				email.to = [v for k,v in settings.ADMINS]
				email.cc = []
				email.bcc = []
				# email.send()

	wb = export_invoices_xlsx(permanence=permanence, wb=None, sheet_name=current_site_name)
	if wb != None:
		html_content = unicode(_('Dear staff member')) + ",<br/><br/>" + unicode(_('The invoices of')) + \
				" " + unicode(permanence) + " " + unicode(_("are now available in attachment")) + ".<br/>" + permanence.invoice_description + \
				"<br/>" + current_site_name + \
				"<br/>" + sender_function + \
				"<br/>" + signature
		email = EmailMultiAlternatives(
			unicode(_('Invoice')) + " - " + unicode(permanence) + " - " + current_site_name,
			strip_tags(html_content),
			sender_email, 
			cc_email_staff
		)
		email.attach(filename, 
			save_virtual_workbook(wb), 
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
		email.attach_alternative(html_content, "text/html")
		if not settings.DEBUG:
			email.send()
		else:
			email.to = [v for k,v in settings.ADMINS]
			email.cc = []
			email.bcc = []
			# email.send()
