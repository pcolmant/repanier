# -*- coding: utf-8 -*-
import re
import uuid
import thread
try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl

from const import *
from tools import *
from django.conf import settings
from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core import urlresolvers
import datetime
from django.utils.timezone import utc
from django import forms

from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.utils.http import urlencode
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django import forms
from django.contrib.sites.models import get_current_site
from django.shortcuts import get_object_or_404

# from adminsortable.admin import SortableAdminMixin
from repanier.adminsortable import SortableAdminMixin

from repanier.models import LUT_ProductionMode
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_PermanenceRole

from repanier.models import Producer
from repanier.models import Permanence
from repanier.models import Customer
from repanier.models import Staff
from repanier.models import Product
from repanier.models import PermanenceBoard
from repanier.models import OfferItem
from repanier.models import CustomerOrder
from repanier.models import PermanenceInPreparation
from repanier.models import PermanenceDone
from repanier.models import Purchase
from repanier.models import BankAccount
from repanier.models import CustomerInvoice
from repanier.models import ProducerInvoice
from repanier.views import render_response

from repanier.admin_export_xlsx import export_permanence_planified_xlsx
from repanier.admin_export_xlsx import export_orders_xlsx
from repanier.admin_export_xlsx import export_product_xlsx
from repanier.admin_export_xlsx import export_permanence_done_xlsx
from repanier.admin_import_xlsx import import_product_xlsx
from repanier.admin_import_xlsx import import_permanence_done_xlsx
# from repanier.admin_export_docx import export_mymodel_docx
from repanier.admin_send_mail import send_alert_email

from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool

from repanier.tasks import open_offers_async
from repanier.tasks import close_orders_async
from repanier.tasks import done_async
from repanier.tasks import email_invoices_async

# Filters in the right sidebar of the change list page of the admin
from django.contrib.admin import SimpleListFilter

class ProductFilterByProducer(SimpleListFilter):
	# Human-readable title which will be displayed in the
	# right admin sidebar.
	title = _("producers")
	# Parameter for the filter that will be used in the URL query.
	parameter_name = 'producer'

	def lookups(self, request, model_admin):
		"""
		Returns a list of tuples. The first element in each
		tuple is the coded value for the option that will
		appear in the URL query. The second element is the
		human-readable name for the option that will appear
		in the right sidebar.
		"""
		# This list is a collection of producer.id, .name
		return [(c.id, c.short_profile_name) for c in 
			Producer.objects.all().active()
			]

	def queryset(self, request, queryset):
		"""
		Returns the filtered queryset based on the value
		provided in the query string and retrievable via
		`self.value()`.
		"""
		# This query set is a collection of products
		if self.value():
			return queryset.producer_is(self.value())
		else:
			return queryset

class ProductFilterByDepartmentForThisProducer(SimpleListFilter):
	title = _("departments for customer")
	parameter_name = 'department_for_customer'

	def lookups(self, request, model_admin):
		producer = request.GET.get('producer')
		if producer:
			inner_qs = Product.objects.all().active().producer_is(
				producer).order_by().distinct(
				'department_for_customer__id')
		else:
			inner_qs = Product.objects.all().active().order_by().distinct(
				'department_for_customer__id')

		return [(c.id, c.short_name) for c in 
			LUT_DepartmentForCustomer.objects.all().active().filter(product__in=inner_qs)
			]

	def queryset(self, request, queryset):
		# This query set is a collection of products
		if self.value():
			return queryset.department_for_customer_is(self.value())
		else:
			return queryset

class PurchaseFilterByCustomerForThisPermanence(SimpleListFilter):
	title = _("customer")
	parameter_name = 'customer'

	def lookups(self, request, model_admin):
		permanence = request.GET.get('permanence')
		if permanence:
			return [(c.id, c.short_basket_name) for c in 
				Customer.objects.filter(purchase__permanence_id=permanence).distinct()
				]
		else:
			return [(c.id, c.short_basket_name) for c in 
				Customer.objects.all().may_order()
				]

	def queryset(self, request, queryset):
		# This query set is a collection of permanence
		if self.value():
			return queryset.customer(self.value())
		else:
			return queryset

class PurchaseFilterByProducerForThisPermanence(SimpleListFilter):
	title = _("producer")
	parameter_name = 'producer'

	def lookups(self, request, model_admin):
		permanence = request.GET.get('permanence')
		if permanence:
			return [(c.id, c.short_profile_name) for c in 
				Producer.objects.filter(permanence=permanence).distinct()
				]
		else:
			return [(c.id, c.short_profile_name) for c in 
				Producer.objects.all().active()
				]

	def queryset(self, request, queryset):
		# This query set is a collection of permanence
		if self.value():
			return queryset.producer(self.value())
		else:
			return queryset

class PurchaseFilterByPermanence(SimpleListFilter):
	title = _("permanences")
	parameter_name = 'permanence'

	def lookups(self, request, model_admin):
		# This list is a collection of permanence.id, .name
		return [(c.id, c.__unicode__()) for c in 
			Permanence.objects.filter(status__in=[PERMANENCE_OPENED, PERMANENCE_SEND])
			]

	def queryset(self, request, queryset):
		# This query set is a collection of permanence
		if self.value():
			return queryset.permanence(self.value())
		else:
			return queryset


# LUT
class LUT_ProductionModeAdmin(admin.ModelAdmin):
	list_display = ('short_name', 'is_active')
	list_display_links = ('short_name',)
	list_max_show_all = True

admin.site.register(LUT_ProductionMode, LUT_ProductionModeAdmin)

class LUT_DepartmentForCustomerAdmin(admin.ModelAdmin):
	list_display = ('short_name', 'is_active')
	list_display_links = ('short_name',)
	list_max_show_all = True

admin.site.register(LUT_DepartmentForCustomer, LUT_DepartmentForCustomerAdmin)

class LUT_PermanenceRoleAdmin(admin.ModelAdmin):
	list_display = ('short_name', 'is_active')
	list_display_links = ('short_name',)
	list_max_show_all = True

admin.site.register(LUT_PermanenceRole, LUT_PermanenceRoleAdmin)

class ProducerAdmin(admin.ModelAdmin):
	fields = [ 
		('short_profile_name', 'long_profile_name'),
		('email', 'fax'),
		('phone1', 'phone2',), 
		'order_description',
		'invoice_description',
		('price_list_multiplier','vat_level'),
		('date_balance', 'balance'),
		'represent_this_buyinggroup', 
		'address',
		'is_active']
	readonly_fields = (
		'represent_this_buyinggroup',
		'date_balance', 
		'balance',
	)
	search_fields = ('short_profile_name', 'email')
	list_display = ('short_profile_name', 'get_products', 'get_balance', 'phone1', 'email', 'represent_this_buyinggroup',
		'is_active')
	list_max_show_all = True
	actions = [
		'export_xlsx',
		'import_xlsx',
	]

	def export_xlsx(self, request, queryset):
		return export_product_xlsx(request, queryset)
	export_xlsx.short_description = _("Export products of selected producer(s) as XSLX file")

	def import_xlsx(self, request, queryset):
		return import_product_xlsx(self, admin, request, queryset)
	import_xlsx.short_description = _("Import products of selected producer(s) from a XLSX file")

	# def get_producer_phone1(self, obj):
	# 	if obj.producer:
	# 		return '%s'%(obj.producer.phone1)
	# 	else:
	# 		return ''
	# get_producer_phone1.short_description = _("phone1") 

admin.site.register(Producer, ProducerAdmin)

# Custom User
class UserDataForm(forms.ModelForm):

	username = forms.CharField(label=_('Username'), max_length=30, 
			help_text=_(
				'Required. 30 characters or fewer. Letters, numbers and @/./+/-/_ characters'
			),
			validators=[
				validators.RegexValidator(re.compile('^[\w.@+-]+$'), _('Enter a valid username.'), 'invalid')
			])
	# password1 = forms.CharField(label=_('Password1'), max_length=128, required=False)
	# password2 = forms.CharField(label=_('Password2'), max_length=128, required=False)
	email = forms.EmailField(label=_('Email'))
	first_name = forms.CharField(label=_('First_name'), max_length=30)
	last_name = forms.CharField(label=_('Last_name'), max_length=30)

	def __init__(self, *args, **kwargs):
		super(UserDataForm, self).__init__(*args, **kwargs)
		self.user = None

	def error(self,field, msg):
		if field not in self._errors:
			self._errors[field]= self.error_class([msg])

	def clean(self, *args, **kwargs):
		# The Staff has no first_name or last_name because it's a function with login/pwd.
		# A Customer with a first_name and last_name is responsible of this funcition. 
		cleaned_data = super(UserDataForm, self).clean(*args, **kwargs)
		customer_form = 'short_basket_name' in self.fields
		if any(self.errors):
			if 'first_name' in self._errors:
				del self._errors['first_name']
			self.data['first_name'] = self.fields['first_name'].initial
			if 'last_name' in self._errors:
				del self._errors['last_name']
			self.data['last_name'] = self.fields['last_name'].initial
		username_field_name = 'username'
		initial_username  = None
		try:
			initial_username = self.instance.user.username
		except:
			pass
		if customer_form:
			# Customer
			username_field_name = 'short_basket_name'
		# initial_username = self.fields[username_field_name].initial
		username = self.cleaned_data.get(username_field_name)
		user_error1 = _('The given username must be set')
		user_error2 = _('The given username is used by another user')
		if customer_form:
			user_error1 = _('The given short_basket_name must be set')
			user_error2 = _('The given short_basket_name is used by another user')
			if 'username' in self._errors:
				del self._errors['username']
			self.data['username'] = username
		if not username:
			self.error(username_field_name ,user_error1)
		# Check that the email is set
		email = self.cleaned_data.get("email")
		if not email:
			self.error('email',_('The given email must be set'))
		# Check that the email is not already used
		user=None
		email = User.objects.normalize_email(email)
		if email:
			# Only if a email is given
			try:
				user = User.objects.get(email=email)
			except User.DoesNotExist:
				pass
		# Check that the username is not already used
		if user != None:
			if initial_username!=user.username:
				self.error('email',_('The given email is used by another user'))
		user=None
		try:
			user = User.objects.get(username=username)
		except User.DoesNotExist:
			pass
		if user != None:
			if initial_username!=user.username:
				self.error(username_field_name,user_error2)
		print self.errors
		return cleaned_data

	def save(self, *args, **kwargs):
		super(UserDataForm, self).save(*args, **kwargs)
		change = (self.instance.id != None)
		username = self.data['username']
		email = self.data['email']
		# password = self.data['password1']
		first_name = self.data['first_name']
		last_name = self.data['last_name']
		user = None
		if change:
			user=User.objects.get(id=self.instance.user_id)
			user.username = username
			user.email = email
			user.first_name = first_name
			user.last_name = last_name
			# if password:
			# 	user.set_password(password)
			user.save()
		else:
			user = User.objects.create_user(
				username=username, email=email, password=uuid.uuid1().hex,
				first_name=first_name, last_name=last_name)
		self.user = user
		return self.instance


# Customer
class CustomerWithUserDataForm(UserDataForm):

	class Meta:
		model = Customer

class CustomerWithUserDataAdmin(admin.ModelAdmin):
	form = CustomerWithUserDataForm
	fields = [
		('short_basket_name', 'long_basket_name'),
		('email','email2'), 
		('phone1', 'phone2'),
		'address', 'vat_id',
		('date_balance', 'balance'),
		('represent_this_buyinggroup', 'may_order','is_active')
	]
	readonly_fields = (
		'represent_this_buyinggroup',
		'date_balance', 
		'balance',
	)
	search_fields = ('short_basket_name', 'user__email', 'email2')
	list_display = ('__unicode__', 'get_balance', 'may_order', 'phone1', 'phone2', 'get_email', 'email2')
	list_max_show_all = True

	def get_email(self, obj):
		if obj.user:
			return '%s'%(obj.user.email)
		else:
			return ''
	get_email.short_description = _("email")

	def get_form(self,request, obj=None, **kwargs):
		form = super(CustomerWithUserDataAdmin,self).get_form(request, obj, **kwargs)
		username = form.base_fields['username']
		email = form.base_fields['email']
		first_name= form.base_fields['first_name']
		last_name= form.base_fields['last_name']

		if obj:
			user_model = get_user_model()
			user = user_model.objects.get(id=obj.user_id)
			username.initial = getattr(user, user_model.USERNAME_FIELD)
			# username.widget.attrs['readonly'] = True
			email.initial = user.email
			first_name.initial = user.first_name
			last_name.initial = user.last_name
		else:
			# Clean data displayed
			username.initial = ''
			# username.widget.attrs['readonly'] = False
			email.initial = ''
			first_name.initial = 'N/A'
			last_name.initial = 'N/A'
		return form

	def save_model(self, request, customer, form, change):
		customer.user = form.user
		form.user.is_staff = False
		form.user.is_active = customer.is_active
		form.user.save()
		super(CustomerWithUserDataAdmin,self).save_model(
			request, customer, form, change)

admin.site.register(Customer, CustomerWithUserDataAdmin)

# Staff
class StaffWithUserDataForm(UserDataForm):

	class Meta:
		model = Staff

class StaffWithUserDataAdmin(admin.ModelAdmin):
	form = StaffWithUserDataForm
	fields = ['username',
		# 'password1', 'password2',
		'email', 
		'is_reply_to_order_email', 'is_reply_to_invoice_email',
		'customer_responsible','long_name', 'function_description', 'is_active']
	list_display = ('__unicode__', 'customer_responsible', 'get_customer_phone1', 'is_active')
	list_max_show_all = True

	def get_form(self,request, obj=None, **kwargs):
		form = super(StaffWithUserDataAdmin,self).get_form(request, obj, **kwargs)
		username = form.base_fields['username']
		email = form.base_fields['email']
		first_name= form.base_fields['first_name']
		last_name= form.base_fields['last_name']
		customer_responsible = form.base_fields["customer_responsible"]
		customer_responsible.widget.can_add_related = False

		if obj:
			user_model = get_user_model()
			user = user_model.objects.get(id=obj.user_id)
			username.initial = getattr(user, user_model.USERNAME_FIELD)
			# username.widget.attrs['readonly'] = True
			email.initial = user.email
			first_name.initial = user.first_name
			last_name.initial = user.last_name
			customer_responsible.empty_label = None
			customer_responsible.initial = obj.customer_responsible
		else:
			# Clean data displayed
			username.initial = ''
			# username.widget.attrs['readonly'] = False
			email.initial = ''
			first_name.initial = 'N/A'
			last_name.initial = 'N/A'
		customer_responsible.queryset = Customer.objects.all(
			).active().order_by(
			"short_basket_name")
		return form

	def save_model(self, request, staff, form, change):
		# TODO Check there is not more that one is_reply_to_order_email set to True
		# TODO Check there is not more that one is_reply_to_invoice_email set to True
		staff.user = form.user
		form.user.is_staff = True
		form.user.is_active = staff.is_active
		form.user.save()
		super(StaffWithUserDataAdmin,self).save_model(
			request, staff, form, change)

admin.site.register(Staff, StaffWithUserDataAdmin)

class ProductAdmin(SortableAdminMixin, admin.ModelAdmin):
	list_display = ('producer',
		'is_into_offer',
		'long_name',
		'department_for_customer',
		'original_unit_price',
		'unit_deposit',
		'customer_alert_order_quantity',
		'is_active')
	list_display_links = ('long_name',)
	list_editable = ('original_unit_price',)
	readonly_fields = ('is_created_on', 
		'is_updated_on')
	fields = (
		('producer', 'long_name'),
		('original_unit_price', 'unit_deposit', 'order_average_weight'),
		'offer_description', 
	 	'usage_description', 
		('order_by_kg_pay_by_kg', 'order_by_piece_pay_by_piece', 'order_by_piece_pay_by_kg', 'producer_must_give_order_detail_per_customer'),
		('customer_minimum_order_quantity', 'customer_increment_order_quantity'),
		'customer_alert_order_quantity',
		('production_mode', 'picture'),
	 	('department_for_customer', 'placement'),
		('vat_level', 'automatically_added'),
		('is_into_offer', 'is_active', 'is_created_on', 'is_updated_on')
	)
	list_max_show_all = True
	# ordering = ('producer', 
	# 	'department_for_customer',
	# 	'long_name',)
	search_fields = ('long_name',)
	list_filter = ('is_active',
		'is_into_offer',
		ProductFilterByDepartmentForThisProducer,
		ProductFilterByProducer,)
	actions = ['flip_flop_select_for_offer_status', 'duplicate_product'	]

	def flip_flop_select_for_offer_status(self, request, queryset):
		for product in queryset.order_by():
			product.is_into_offer = not product.is_into_offer
			product.save(update_fields=['is_into_offer'])

	flip_flop_select_for_offer_status.short_description = _(
		'flip_flop_select_for_offer_status for offer')

	def duplicate_product(self, request, queryset):
		for product in queryset:
			super(ProductAdmin,self).move_for_duplicate(product)
			long_name_prefix = _("COPY_OF_")
			max_length = Product._meta.get_field('long_name').max_length
			product.long_name = cap(long_name_prefix + product.long_name, max_length)
			product.id = None
			product.save()

	duplicate_product.short_description = _('duplicate product')

	def get_form(self,request, obj=None, **kwargs):
		form = super(ProductAdmin,self).get_form(request, obj, **kwargs)
		# If we are coming from a list screen, use the filter to pre-fill the form

		producer = form.base_fields["producer"]
		department_for_customer = form.base_fields["department_for_customer"]
		production_mode = form.base_fields["production_mode"]

		producer.widget.can_add_related = False
		department_for_customer.widget.can_add_related = False
		production_mode.widget.can_add_related = False

		if obj:
			producer.empty_label = None
			producer.queryset = Producer.objects.all(
				).active()
			department_for_customer.empty_label = None
			department_for_customer.queryset = LUT_DepartmentForCustomer.objects.all(
				).active()
			production_mode.empty_label = None
		else:
			producer_id = None
			department_for_customer_id = None
			is_actif_value = None
			is_into_offer_value = None
			preserved_filters = request.GET.get('_changelist_filters', None)
			if preserved_filters:
				param = dict(parse_qsl(preserved_filters))
				if 'producer' in param:
					producer_id = param['producer']
				if 'department_for_customer' in param:
					department_for_customer_id = param['department_for_customer']
				if 'is_active__exact' in param:
					is_actif_value = param['is_active__exact']
				if 'is_into_offer__exact' in param:
					is_into_offer_value = param['is_into_offer__exact']
			is_active = form.base_fields["is_active"]
			is_into_offer = form.base_fields["is_into_offer"]
			vat_level = form.base_fields["vat_level"]
			if producer_id:
				vat_level.initial = get_object_or_404(Producer, id=producer_id).vat_level
				producer.empty_label = None
				producer.queryset = Producer.objects.all(
					).id(producer_id)
			else:
				producer.queryset = Producer.objects.all(
					).active()
			if department_for_customer_id:
				department_for_customer.empty_label = None
				department_for_customer.queryset = LUT_DepartmentForCustomer.objects.filter(
					id=department_for_customer_id
				)
			else:
				department_for_customer.queryset = LUT_DepartmentForCustomer.objects.all(
				).active()
			if is_actif_value:
				if is_actif_value == '0':
					is_active.initial = False
				else:
					is_active.initial = True
			if is_into_offer_value:
				if is_into_offer_value == '0':
					is_into_offer.initial = False
				else:
					is_into_offer.initial = True
		production_mode.queryset = LUT_ProductionMode.objects.all(
			).active()
		return form

admin.site.register(Product, ProductAdmin)

# Permanence
class PermanenceBoardInline(admin.TabularInline):
	model = PermanenceBoard
	fields = ['permanence_role', 'customer']
	extra = 1

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "customer":
			kwargs["queryset"] = Customer.objects.all(
				).active().not_the_buyinggroup()
		if db_field.name == "permanence_role":
			kwargs["queryset"] = LUT_PermanenceRole.objects.all(
				).active()
		return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

	# def save_formset(self, request, form, formset, change):
	# 	-> replaced by pre_save signal in model

class PermanenceDataForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super(PermanenceDataForm, self).__init__(*args, **kwargs)
		self.user = None

	def error(self,field, msg):
		if field not in self._errors:
			self._errors[field]= self.error_class([msg])

	def clean(self, *args, **kwargs):
		cleaned_data = super(PermanenceDataForm, self).clean(*args, **kwargs)
		initial_distribution_date = self.instance.distribution_date
		distribution_date = self.cleaned_data.get("distribution_date")
		initial_short_name = self.instance.short_name
		short_name = self.cleaned_data.get("short_name")
		if(initial_distribution_date != distribution_date or initial_short_name != short_name):
			permanence_already_exist = False
			try:
				Permanence.objects.get(distribution_date=distribution_date, short_name=short_name)
				permanence_already_exist = True
			except Permanence.DoesNotExist:
				pass
			if permanence_already_exist:
				self.error('short_name',_('A permanence with the same distribution date and the same short_name already exist. You must either change te distribution_date or the name.'))
			else:
				# Empty menu cache to eventually display the modified Permanence Label
				menu_pool.clear()
		return cleaned_data

	class Meta:
		model = Permanence

class PermanenceInPreparationAdmin(admin.ModelAdmin):
	form = PermanenceDataForm
	fields = (
 		'distribution_date',
 		'short_name', 
		# ('status', 'automaticaly_closed'), 
		'automaticaly_closed',
		'offer_description',
		'order_description', 
		'producers'
	)
	# readonly_fields = ('status', 'is_created_on', 'is_updated_on')
	exclude = ['invoice_description']
	list_max_show_all = True
	filter_horizontal = ('producers',)
	# inlines = [PermanenceBoardInline, OfferItemInline]
	inlines = [PermanenceBoardInline]
	date_hierarchy = 'distribution_date'
	list_display = ('__unicode__', 'get_producers', 'get_customers', 'get_board', 'status')
	ordering = ('distribution_date',)
	actions = [
		'download_planified', 
		'open_and_send_offers',
		'download_orders', 
		'close_and_send_orders',
		'delete_purchases', 
		'back_to_planified',
	]

	def get_readonly_fields(self, request, obj=None):
		if obj:
			status = obj.status
			if status>PERMANENCE_PLANIFIED:
				return('status', 'is_created_on', 'is_updated_on','producers')
		return ('status', 'is_created_on', 'is_updated_on')

	# def export_docx(self, request, queryset):
	# 	return export_mymodel_docx(request, queryset)
	# export_docx.short_description = _("Export DOCX")

	def download_planified(self, request, queryset):
		return export_permanence_planified_xlsx(request, queryset)
	download_planified.short_description = _("Export planified XLSX")


	def download_orders(self, request, queryset):
		for permanence in queryset[:1]:
			if permanence.status==PERMANENCE_OPENED:
				response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
				response['Content-Disposition'] = 'attachment; filename=' + unicode(_('Check')) + '.xlsx'
				wb = export_orders_xlsx(permanence)
				wb.save(response)
				return response
	download_orders.short_description = _("Export orders XLSX")

	def open_and_send_offers(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			current_site = get_current_site(request)
			user_message = _("The status of this permanence prohibit you to open and send offers.")
			user_message_level = messages.ERROR
			for permanence in queryset[:1]:
				if permanence.status==PERMANENCE_PLANIFIED:
					permanence.status = PERMANENCE_WAIT_FOR_OPEN
					permanence.save(update_fields=['status'])
					thread.start_new_thread( open_offers_async, (permanence.id, current_site.name) )
					user_message = _("The offers are being generated.")
					user_message_level = messages.INFO
				elif permanence.status==PERMANENCE_WAIT_FOR_OPEN:
					# On demand 15 minutes after the previous attempt, go back to previous status and send alert email
					now = datetime.datetime.utcnow().replace(tzinfo=utc)
					timediff = now - permanence.is_updated_on
					if timediff.total_seconds() > (15 * 60):
						send_alert_email(permanence, current_site.name)
						permanence.status = PERMANENCE_PLANIFIED
						permanence.save(update_fields=['status'])
						user_message = _("The action has been canceled by the system and an email send to the site administrator.")
						user_message_level = messages.INFO
					else:
						user_message = _("Action canceled by the system.")
						user_message_level = messages.WARNING
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : open and send offers"),
				'action' : 'open_and_send_offers',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None

	open_and_send_offers.short_description = _('open and send offers')

	def close_and_send_orders(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			user_message = _("The status of this permanence prohibit you to close it.")
			user_message_level = messages.ERROR
			current_site = get_current_site(request)
			for permanence in queryset[:1]:
				if permanence.status==PERMANENCE_OPENED:
					permanence.status = PERMANENCE_WAIT_FOR_SEND
					permanence.save(update_fields=['status'])
					thread.start_new_thread( close_orders_async, (permanence.id, current_site.name) )
					user_message = _("The orders are being closed.")
					user_message_level = messages.INFO
				elif permanence.status==PERMANENCE_WAIT_FOR_SEND:
					# On demand 30 minutes after the previous attempt, go back to previous status and send alert email
					now = datetime.datetime.utcnow().replace(tzinfo=utc)
					timediff = now - permanence.is_updated_on
					if timediff.total_seconds() > (30 * 60):
						send_alert_email(permanence, current_site.name)
						permanence.status = PERMANENCE_OPENED
						permanence.save(update_fields=['status'])
						user_message = _("The action has been canceled by the system and an email send to the site administrator.")
						user_message_level = messages.INFO
					else:
						user_message = _("Action canceled by the system.")
						user_message_level = messages.WARNING
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : close and send orders"),
				'action' : 'close_and_send_orders',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None


	close_and_send_orders.short_description = _('close and send orders')

	def back_to_planified(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			user_message = _("The status of this permanence prohibit you to go back to planified.")
			user_message_level = messages.ERROR
			for permanence in queryset[:1]:
				if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
					OfferItem.objects.all().permanence(permanence).update(is_active=False)
					permanence.status=PERMANENCE_PLANIFIED
					permanence.save(update_fields=['status'])
					menu_pool.clear()
					user_message = _("The permanence is back to planified.")
					user_message_level = messages.INFO
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : back to planified"),
				'action' : 'back_to_planified',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None

	back_to_planified.short_description = _('back to planified')

	def delete_purchases(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			user_message = _("The status of this permanence prohibit you to delete the purchases.")
			user_message_level = messages.ERROR
			is_something_deleted = False
			for permanence in queryset.filter(status=PERMANENCE_SEND)[:1]:
				Purchase.objects.all().permanence(permanence).delete()
				OfferItem.objects.all().permanence(permanence).delete()
				CustomerOrder.objects.filter(permanence=permanence).delete()
				user_message = _("The purchases of this permanence have been deleted. There is no way to restore them automaticaly.")
				user_message_level = messages.INFO
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : delete purchases. Be carefull : !!! THERE IS NO WAY TO RESTORE THEM AUTOMATICALY !!!!"),
				'action' : 'delete_purchases',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None

	delete_purchases.short_description = _('delete purchases')

	def get_actions(self, request):
		actions = super(PermanenceInPreparationAdmin, self).get_actions(request)
		if 'delete_selected' in actions:
			del actions['delete_selected']
		if not actions:
			try:
				self.list_display.remove('action_checkbox')
			except ValueError:
				pass
		return actions

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		if db_field.name == "producers":
			kwargs["queryset"] = Producer.objects.all().active(
				)
		return super(PermanenceInPreparationAdmin, self).formfield_for_manytomany(
			db_field, request, **kwargs)

	def queryset(self, request):
		qs = super(PermanenceInPreparationAdmin, self).queryset(request)
		return qs.filter(status__lte=PERMANENCE_SEND)

	# save_model() is called before the inlines are saved
	def save_model(self, request, permanence, form, change):
		if change and ('distribution_date' in form.changed_data):
			PermanenceBoard.objects.filter(permanence=permanence.id).update(distribution_date=permanence.distribution_date)
			Purchase.objects.filter(permanence=permanence.id).update(distribution_date=permanence.distribution_date)
		super(PermanenceInPreparationAdmin,self).save_model(
			request, permanence, form, change)

admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)

class PermanenceDoneAdmin(admin.ModelAdmin):
	fields = (
		'distribution_date',
		'short_name',
		'invoice_description',
		# 'status'
	)
	readonly_fields = ('status', 'is_created_on', 'is_updated_on', 'automaticaly_closed')
	exclude = ['offer_description', 'order_description']
	list_max_show_all = True
	# inlines = [PermanenceBoardInline, OfferItemInline]
	inlines = [PermanenceBoardInline]
	date_hierarchy = 'distribution_date'
	list_display = ('__unicode__', 'get_producers', 'get_customers', 'get_board', 'status')
	ordering = ('-distribution_date',)
	actions = [
		'export_xlsx',
		'import_xlsx',
		'generate_invoices',
		'send_invoices',
		'cancel_invoices',
	]

	def export_xlsx(self, request, queryset):
		return export_permanence_done_xlsx(request, queryset)
	export_xlsx.short_description = _("Export orders prepared as XSLX file")

	def import_xlsx(self, request, queryset):
		return import_permanence_done_xlsx(self, admin, request, queryset)
	import_xlsx.short_description = _("Import orders prepared from a XLSX file")

	# def get_urls(self):
	#         urls = super(PermanenceDoneAdmin, self).get_urls()
	#         my_urls = patterns('',
	#             (r'\d+/purchase/$', self.admin_site.admin_view(self.purchase)),
	#         )
	#         return my_urls + urls

	def generate_invoices(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			current_site = get_current_site(request)
			permanence_done_pending_set = Permanence.objects.filter(status__in= [PERMANENCE_WAIT_FOR_DONE, PERMANENCE_INVOICES_VALIDATION_FAILED]).order_by()[:1]
			user_message = _("The status of this permanence prohibit you to close invoices.")
			user_message_level = messages.ERROR
			if not permanence_done_pending_set:
				# Accept to close only one at the same time because the order of execution is important.
				for permanence in queryset[:1]:
					if permanence.status==PERMANENCE_SEND:
						permanence.status = PERMANENCE_WAIT_FOR_DONE
						permanence.save(update_fields=['status'])
						thread.start_new_thread( done_async, (permanence.id, permanence.distribution_date, current_site.name) )
						user_message = _("The invoices are being generated.")
						user_message_level = messages.INFO
			else:
				permanence_done_pending = permanence_done_pending_set[0]
				for permanence in queryset[:1]:
					if permanence_done_pending.id == permanence.id:
						if permanence_done_pending.status == PERMANENCE_INVOICES_VALIDATION_FAILED:
							self.cancel(permanence_done_pending.id)
							permanence_done_pending.status = PERMANENCE_WAIT_FOR_DONE
							permanence_done_pending.save(update_fields=['status'])
							thread.start_new_thread( permanence_done_pending_async, (permanence_done_pending.id, permanence_done_pending.distribution_date, current_site.name) )
							user_message = _("The invoices are being generated.")
							user_message_level = messages.INFO
						else:
							# On demand 30 minutes after the previous attempt, go back to previuos status and send alert email
							now = datetime.datetime.utcnow().replace(tzinfo=utc)
							timediff = now - permanence.is_updated_on
							if timediff.total_seconds() > (30 * 60):
								send_alert_email(permanence, current_site.name)
								permanence.status = PERMANENCE_DONE
								permanence.save(update_fields=['status'])
								self.cancel(permanence_done_pending.id)
								user_message = _("The action has been canceled by the system and an email send to the site administrator.")
								user_message_level = messages.INFO
							else:
								user_message = _("Action canceled by the system.")
								user_message_level = messages.WARNING
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : generate the invoices"),
				'action' : 'generate_invoices',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None

	generate_invoices.short_description = _('generate invoices')

	def send_invoices(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			current_site = get_current_site(request)
			for permanence in queryset[:1]:
				if permanence.status==PERMANENCE_DONE:
					thread.start_new_thread( email_invoices_async, (permanence.id, current_site.name) )
					user_message = _("Emails containing the invoices will be send to the customers and the producers.")
					user_message_level = messages.ERROR
				else:
					user_message = _("The status of this permanence prohibit you to send invoices.")
					user_message_level = messages.ERROR
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : send the invoices"),
				'action' : 'send_invoices',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None
	
	send_invoices.short_description = _('send invoices')

	def cancel_invoices(self, request, queryset):
		user_message = _("Action canceled by the user.")
		user_message_level = messages.WARNING
		if 'apply' in request.POST:
			latest_customer_invoice_set=CustomerInvoice.objects.order_by('-id')[:1]
			if latest_customer_invoice_set:
				user_message = _("The status of this permanence prohibit you to close invoices.")
				user_message_level = messages.ERROR
				for permanence in queryset[:1]:
					if permanence.status == PERMANENCE_DONE:
						if latest_customer_invoice_set[0].permanence.id == permanence.id:
							# This is well the latest closed permanence. The invoices can be cancelled without damages.
							self.cancel(permanence.id)
							user_message = _("The selected invoice has been canceled.")
							user_message_level = messages.INFO
						else:
							user_message = _("The selected invoice is not the latest invoice.")
							user_message_level = messages.ERROR
			# else:
			# 	for permanence in queryset:
			# 		if permanence.status == PERMANENCE_DONE:
			# 			self.cancel(permanence.id)
		elif 'cancel' not in request.POST:
			opts = self.model._meta
			app_label = opts.app_label
			return render_response(request, 'repanier/confirm_admin_action.html', {
				'title': _("Please, confirm the action : cancel the invoices"),
				'action' : 'cancel_invoices',
				'queryset': queryset[:1],
				"app_label": app_label,
				'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
			})
		self.message_user(request, user_message, user_message_level)
		return None

	cancel_invoices.short_description = _('cancel latest invoices')

	def cancel(self, permanence_id):

		for customer_invoice in CustomerInvoice.objects.filter(
			permanence_id=permanence_id).order_by().distinct():
			customer = Customer.objects.get(id=customer_invoice.customer_id)
			customer.balance = customer_invoice.previous_balance
			customer.date_balance = customer_invoice.date_previous_balance
			customer.save(update_fields=['balance', 'date_balance'])
			Purchase.objects.all().filter(
				is_recorded_on_customer_invoice_id=customer_invoice.id
				).update(
				is_recorded_on_customer_invoice=None
				)
			BankAccount.objects.all().filter(
				is_recorded_on_customer_invoice_id=customer_invoice.id
				).update(
				is_recorded_on_customer_invoice=None
				)
		for producer_invoice in ProducerInvoice.objects.filter(
			permanence_id=permanence_id).order_by().distinct():
			producer = Producer.objects.get(id=producer_invoice.producer_id)
			producer.balance = producer_invoice.previous_balance
			producer.date_balance = producer_invoice.date_previous_balance
			producer.save(update_fields=['balance', 'date_balance'])
			Purchase.objects.all().filter(
				is_recorded_on_producer_invoice_id=producer_invoice.id
				).update(
				is_recorded_on_producer_invoice=None
				)
			BankAccount.objects.all().filter(
				is_recorded_on_producer_invoice_id=producer_invoice.id
				).update(
				is_recorded_on_producer_invoice=None
				)
		CustomerInvoice.objects.filter(
			permanence_id=permanence_id).delete()
		ProducerInvoice.objects.filter(
			permanence_id=permanence_id).delete()
		bank_account_set= BankAccount.objects.all().filter(
		customer = None,
		producer = None).order_by('-id')[:1]
		if bank_account_set:
			a_bank_amount_id = bank_account_set[0].id
			BankAccount.objects.all().filter(id=a_bank_amount_id).order_by().delete()
		Permanence.objects.filter(id=permanence_id).update(status = PERMANENCE_SEND,is_done_on = None)
		menu_pool.clear()

	def has_add_permission(self, request):
		return False

	def get_actions(self, request):
		actions = super(PermanenceDoneAdmin, self).get_actions(request)
		if 'delete_selected' in actions:
			del actions['delete_selected']
		if not actions:
			try:
				self.list_display.remove('action_checkbox')
			except ValueError:
				pass
		return actions

	def queryset(self, request):
		qs = super(PermanenceDoneAdmin, self).queryset(request)
		return qs.filter(status__gte=PERMANENCE_SEND)

	def save_model(self, request, permanence, form, change):
		if change and ('distribution_date' in form.changed_data):
			PermanenceBoard.objects.filter(permanence=permanence.id).update(distribution_date=permanence.distribution_date)
			Purchase.objects.filter(permanence=permanence.id).update(distribution_date=permanence.distribution_date)
		super(PermanenceDoneAdmin,self).save_model(
			request, permanence, form, change)
admin.site.register(PermanenceDone, PermanenceDoneAdmin)

class PurchaseAdmin(admin.ModelAdmin):
	list_max_show_all = True
	exclude = ['offer_item']	
	list_display = [
		'permanence',
		'producer', 
		'long_name',
		'customer', 
		'quantity', 
		'original_unit_price',
		'unit_deposit',
		'original_price',
		'comment'
	]
	date_hierarchy = 'distribution_date'
	list_filter = (PurchaseFilterByPermanence,PurchaseFilterByCustomerForThisPermanence, PurchaseFilterByProducerForThisPermanence)
	list_display_links = ('long_name',)
	search_fields = ('customer__short_basket_name', 'long_name')
	fields = (
		'permanence',
		'customer',
		'product',
		'long_name',
		'quantity',
		'comment'
	)
	readonly_fields  = ('long_name',)
	actions = []

	# def get_readonly_fields(self, request, obj=None):
	# 	if obj:
	# 		status = obj.permanence.status
	# 		if status<PERMANENCE_SEND:
	# 			return('original_price',)


	def queryset(self, request):
		queryset = super(PurchaseAdmin, self).queryset(request)
		return queryset.exclude(producer__isnull=True)

	def get_form(self,request, obj=None, **kwargs):
		form = super(PurchaseAdmin,self).get_form(request, obj, **kwargs)
		# /purchase/add/?_changelist_filters=permanence%3D6%26customer%3D3
		# If we are coming from a list screen, use the filter to pre-fill the form
		permanence_id = None
		customer_id = None
		producer_id = None
		preserved_filters = request.GET.get('_changelist_filters', None)
		if preserved_filters:
			param = dict(parse_qsl(preserved_filters))
			if 'permanence' in param:
				permanence_id = param['permanence']
			if 'customer' in param:
				customer_id = param['customer']
			if 'producer' in param:
				producer_id = param['producer']
		permanence = form.base_fields["permanence"]
		customer = form.base_fields["customer"]
		product = form.base_fields["product"]
		permanence.widget.can_add_related = False
		customer.widget.can_add_related = False
		product.widget.can_add_related = False
		self.a_previous_total_price_with_tax = 0

		if obj:
			a_total_price_with_tax = obj.price_with_tax
			permanence.empty_label = None
			permanence.queryset = Permanence.objects.filter(
				id = obj.permanence_id)
			customer.empty_label = None
			customer.queryset = Customer.objects.filter(
				id = obj.customer_id)
			product.empty_label = None
			product.queryset = Product.objects.filter(
				id = obj.product_id)
		else:

			if permanence_id:
				permanence.empty_label = None
				permanence.queryset = Permanence.objects.all().filter(
					id = permanence_id,
					status__in=[PERMANENCE_OPENED, PERMANENCE_SEND]
				)
				if producer_id:
					product.queryset = Product.objects.filter(offeritem__permanence=permanence_id).producer(producer_id).active()
				else:
					product.queryset = Product.objects.filter(offeritem__permanence=permanence_id).active()
			else:
				permanence.queryset = Permanence.objects.all().filter(
					status__in=[PERMANENCE_OPENED, PERMANENCE_SEND]
				)
				if producer_id:
					product.queryset = Product.objects.all().producer(producer_id).active()
				else:
					product.queryset = Product.objects.all().active()
			if customer_id:
				customer.empty_label = None
				customer.queryset = Customer.objects.filter(id=customer_id).active().may_order()
			else:
				customer.queryset = Customer.objects.all().active().may_order()
		return form

	def save_model(self, request, purchase, form, change):
		# obj.preformed_by = request.user
		# obj.ip_address = utils.get_client_ip(request)
		if purchase.id == None:
			offer_item = None
			offer_item_set = OfferItem.objects.all().permanence(
				purchase.permanence).product(
				purchase.product).order_by()[:1]
			# if offer_item_set:
			# 	offer_item = offer_item_set[0]
			# else:
			# 	# Add the product to the OfferItem
			# 	if purchase.product.is_active:
			# 		offer_item = OfferItem.objects.create(
			# 			permanence = purchase.permanence,
			# 			product = purchase.product,
			# 			automatically_added = ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN )
			# 	else:
			# 		offer_item = OfferItem.objects.create(
			# 			permanence = purchase.permanence,
			# 			product = purchase.product,
			# 			automatically_added = ADD_PRODUCT_DEACTIVATED_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN )
			purchase.offert_item = offer_item

		if purchase.product:
			# TODO Make it worfs when puchase.product == None 
			# This happen when adding purchase of non existing products with the import feature
			purchase.producer = purchase.product.producer
			purchase.distribution_date = purchase.permanence.distribution_date
			purchase.is_to_be_prepared = (purchase.product.automatically_added == ADD_PORDUCT_MANUALY)
			purchase.long_name = purchase.product.long_name
			purchase.order_by_piece_pay_by_kg = purchase.product.order_by_piece_pay_by_kg
			purchase.order_by_kg_pay_by_kg = purchase.product.order_by_kg_pay_by_kg
			purchase.producer_must_give_order_detail_per_customer = purchase.product.producer_must_give_order_detail_per_customer
			purchase.product_order = purchase.product.product_order
			is_compensation = False
			if purchase.product.vat_level in [VAT_200, VAT_300] and purchase.customer.vat_id != None:
				is_compensation = True
			a_original_price = purchase.quantity * purchase.product.original_unit_price
			a_price_without_tax = purchase.quantity * purchase.product.unit_price_without_tax
			a_price_with_vat = purchase.quantity * purchase.product.unit_price_with_vat
			a_price_with_compensation = purchase.quantity * purchase.product.unit_price_with_compensation
			if purchase.product.order_by_piece_pay_by_kg:
				a_original_price *= purchase.product.order_average_weight
				a_price_without_tax *= purchase.product.order_average_weight
				a_price_with_vat *= purchase.product.order_average_weight
				a_price_with_compensation *= purchase.product.order_average_weight
			purchase.invoiced_price_with_compensation = is_compensation
			purchase.original_unit_price = purchase.product.original_unit_price
			purchase.original_price = a_original_price
			purchase.price_without_tax = a_price_without_tax
			purchase.price_with_vat = a_price_with_vat
			purchase.price_with_compensation = a_price_with_compensation
			a_total_price_with_tax = 0
			if is_compensation:
				a_total_price_with_tax = purchase.price_with_compensation
			else:
				a_total_price_with_tax = purchase.price_with_vat
			if purchase.permanence.status==PERMANENCE_OPENED:
				save_order_delta_amount(
					purchase.permanence.id,
					purchase.customer.id,
					self.a_previous_total_price_with_tax,
					a_total_price_with_tax
				)
			purchase.permanence.producers.add(purchase.producer)
			purchase.save()

	def get_actions(self, request):
		actions = super(PurchaseAdmin, self).get_actions(request)
		if 'delete_selected' in actions:
			del actions['delete_selected']
		if not actions:
			try:
				self.list_display.remove('action_checkbox')
			except ValueError:
				pass
		return actions

admin.site.register(Purchase, PurchaseAdmin)

# Accounting
class BankAccountAdmin(admin.ModelAdmin):
	list_max_show_all = True
	list_display = ['operation_date', 'get_producer' , 'get_customer',
	 'get_bank_amount_in', 'get_bank_amount_out', 'operation_comment'] 
	date_hierarchy = 'operation_date'
	ordering = ('-operation_date',)
	fields=('operation_date', 
		('producer', 'customer'), 'operation_comment', 'bank_amount_in',
		 'bank_amount_out', 
		 ('is_recorded_on_customer_invoice', 'is_recorded_on_producer_invoice'), 
		 ('is_created_on', 'is_updated_on') )
	search_fields = ('producer__short_profile_name', 'customer__short_basket_name', 'operation_comment')
	actions = []

	def get_readonly_fields(self, request, obj=None):
		if obj:
			readonly = ['operation_date',
				'bank_amount_in',
				'bank_amount_out',
				'is_created_on', 'is_updated_on',
				'is_recorded_on_customer_invoice', 'is_recorded_on_producer_invoice']
			if obj.customer==None:
				readonly.append('customer')
			if obj.producer==None:
				readonly.append('producer')
			if obj.customer==None and obj.producer==None:
				readonly.append('operation_comment')
			return readonly
		return ('is_created_on', 'is_updated_on',
			'is_recorded_on_customer_invoice', 'is_recorded_on_producer_invoice')

	def get_form(self,request, obj=None, **kwargs):
		form = super(BankAccountAdmin,self).get_form(request, obj, **kwargs)
		if obj:
			if obj.customer:
				customer = form.base_fields["customer"]
				customer.widget.can_add_related = False
				customer.empty_label = None
				customer.queryset = Customer.objects.id(
					obj.customer_id)
			if obj.producer:
				producer = form.base_fields["producer"]
				producer.widget.can_add_related = False
				producer.empty_label = None
				producer.queryset = Producer.objects.id(
					obj.producer_id)
		else:
			producer = form.base_fields["producer"]
			customer = form.base_fields["customer"]
			producer.widget.can_add_related = False
			customer.widget.can_add_related = False
			producer.queryset = Producer.objects.all(
				).not_the_buyinggroup().active().order_by(
				"short_profile_name")
			customer.queryset = Customer.objects.all(
				).not_the_buyinggroup().active().order_by(
				"short_basket_name")
		return form

	def get_actions(self, request):
		actions = super(BankAccountAdmin, self).get_actions(request)
		if 'delete_selected' in actions:
			del actions['delete_selected']
		if not actions:
			try:
				self.list_display.remove('action_checkbox')
			except ValueError:
				pass
		return actions

	def has_delete_permission(self, request, obj=None):
		return False

admin.site.register(BankAccount, BankAccountAdmin)