# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.db import models
from django.db.models.query import QuerySet
from django.db.models import Q, F

from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from djangocms_text_ckeditor.fields import HTMLField
from django.utils.translation import ugettext_lazy as _
from filer.fields.image import FilerImageField
from filer.fields.file import FilerFileField
from django.core import urlresolvers

import datetime

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], 
    	['^djangocms_text_ckeditor\.fields\.HTMLField'])
except ImportError:
    pass

# Create your models here.
class LUTQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

class LUTManager(models.Manager):
    def get_queryset(self):
        return LUTQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

class LUT(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	short_name = models.CharField(_("short_name"), max_length=40)
	description = HTMLField(_("description"), blank=True)
	is_active = models.BooleanField(_("is_active"), default=True)
	objects = LUTManager()
	objects_without_filter = models.Manager()

	def __unicode__(self):
		return self.short_name

	class Meta:
		abstract = True

class LUT_ProductionMode(LUT):

	class Meta:
		verbose_name = _("production mode")
		verbose_name_plural = _("production modes")
		ordering = ("short_name",)
		unique_together = ("site", "short_name",)
		index_together = [
			["site", "short_name"],
			["short_name"],
		]

class LUT_DepartmentForCustomer(LUT):

	class Meta:
		verbose_name = _("department for customer")
		verbose_name_plural = _("departments for customer")
		ordering = ("short_name",)
		unique_together = ("site", "short_name",)
		index_together = [
			["site", "short_name"],
			["short_name"],
		]

class LUT_DepartmentForProducer(LUT):

	class Meta:
		verbose_name = _("department for producer")
		verbose_name_plural = _("departments for producer")
		ordering = ("short_name",)
		unique_together = ("site", "short_name",)
		index_together = [
			["site", "short_name"],
			["short_name"],
		]

class LUT_PermanenceRole(LUT):

	class Meta:
		verbose_name = _("permanence role")
		verbose_name_plural = _("permanences roles")
		ordering = ("short_name",)
		unique_together = ("site", "short_name",)
		index_together = [
			["site", "short_name"],
			["short_name"],
		]

class ProducerQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def id(self, id):
		return self.filter(id = id)

class ProducerManager(models.Manager):
    def get_queryset(self):
        return ProducerQuerySet(self.model, using=self._db)

    def id(self, id):
        return self.get_queryset().id(id)

    def not_producer_of_the_buyinggroup(self):
    	# Don't allow to add the same producer twice
        return self.get_queryset(
        	).active().filter(~Q(siteproducer__site=settings.SITE_ID))

class Producer(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL)
	phone1 = models.CharField(
		_("phone1"), max_length=20,null=True)
	phone2 = models.CharField(
		_("phone2"), max_length=20,null=True, blank=True)
	fax = models.CharField(
		_("fax"), max_length=100,null=True, blank=True)
	bank_account = models.CharField(
		_("bank_account"), max_length=100,null=True, blank=True)
	address = models.TextField(_("address"), null=True, blank=True)
	is_active = models.BooleanField(_("is_active"), default=True)
	objects = ProducerManager()

	def __unicode__(self):
		return getattr(self.user, get_user_model().USERNAME_FIELD)
	
	class Meta:
		verbose_name = _("producer")
		verbose_name_plural = _("producers")
		ordering = ("user__" + get_user_model().USERNAME_FIELD,)

@receiver(post_save, sender=Producer)
def producer_post_save(sender, **kwargs):
	# give access to the producer to private documents for the site "SITE_ID_PRODUCER"
	producer = kwargs['instance']
	site = Site.objects.get(id=SITE_ID_PRODUCER) 
	group = Group.objects.get(name=site.domain) 
	group.user_set.add(producer.user)

@receiver(post_delete, sender=Producer)
def producer_post_delete(sender, **kwargs):
	# remove access to the producer to private documents for the site "SITE_ID_PRODUCER"
	producer = kwargs['instance']
	site = Site.objects.get(id=SITE_ID_PRODUCER) 
	group = Group.objects.get(name=site.domain) 
	group.user_set.remove(producer.user)

class SiteProducerQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def id(self, id):
		return self.filter(id=id)

	def with_login(self):
		return self.filter(producer__isnull=False)

	def not_the_buyinggroup(self):
		return self.filter(represent_this_buyinggroup=False)

class SiteProducerManager(models.Manager):
    def get_queryset(self):
        return SiteProducerQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

    def id(self, id):
        return self.get_queryset().id(id)

class SiteProducer(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	producer = models.ForeignKey(
		Producer, verbose_name=_("producer"),
		blank=True, null=True,
		on_delete=models.PROTECT)
	short_profile_name = models.CharField(
		_("short_profile_name"), max_length=25,null=False)
	long_profile_name = models.CharField(
		_("long_profile_name"), max_length=100,null=True)
	memo = HTMLField(
		_("memo"),blank=True)
	date_previous_balance = models.DateField(
		_("date_previous_balance"),	default=datetime.date.today)
	previous_balance = models.DecimalField(
		_("previous_balance"), max_digits=8, decimal_places=2, default = 0)
	amount_in = models.DecimalField(
		_("amount_in"), max_digits=8, decimal_places=2, default = 0)
	amount_out = models.DecimalField(
		_("amount_out"), max_digits=8, decimal_places=2, default = 0)
	represent_this_buyinggroup = models.BooleanField(
		_("represent_this_buyinggroup"), default = False)
	is_active = models.BooleanField(_("is_active"), default=True)
	objects = SiteProducerManager()
	objects_without_filter = models.Manager()

	def get_products(self):
		link = ''
		if self.id:
			# changeproducer_url = urlresolvers.reverse(
			# 	'admin:repanier_producer_change', args=(self.id,)
			# )
			# link = u'<a href="' + changeproducer_url + '">  ' + unicode(self) + '</a>'
			if self.producer:
				# This producer may have product's list
				changeproductslist_url = urlresolvers.reverse(
					'admin:repanier_product_changelist', 
				)
				# &&& is used to hide the site_producer filter
				link = u'<a href="' + changeproductslist_url + \
					'?is_active__exact=1&department_for_this_producer=all&site_producer=' + \
					str(self.id) + '">  ' + \
					unicode(_("his_products")) + '</a>'
		return link
	get_products.short_description=(_("link to his products"))
	get_products.allow_tags = True

	def __unicode__(self):
		return self.short_profile_name
	
	class Meta:
		verbose_name = _("site producer")
		verbose_name_plural = _("site producers")
		ordering = ("short_profile_name",)
		unique_together = ("site", "producer",)
		index_together = [
			["site", "producer"],
			["site", "short_profile_name"],
			["short_profile_name"],
		]

@receiver(post_save, sender=SiteProducer)
def site_producer_post_save(sender, **kwargs):
	# give access to the producer to private documents for the site
	site_producer = kwargs['instance']
	if site_producer.producer:
		site = Site.objects.get(id=settings.SITE_ID) 
		group = Group.objects.get(name=site.domain) 
		group.user_set.add(site_producer.producer.user)

@receiver(post_delete, sender=SiteProducer)
def site_producer_post_delete(sender, **kwargs):
	# remove access to the producer to private documents for the site
	site_producer = kwargs['instance']
	if site_producer.producer:
		site = Site.objects.get(id=settings.SITE_ID) 
		group = Group.objects.get(name=site.domain) 
		group.user_set.remove(site_producer.producer.user)

class CustomerQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def id(self, id):
		return self.filter(id=id)

class CustomerManager(models.Manager):
    def get_queryset(self):
        return CustomerQuerySet(self.model, using=self._db)

    def id(self, id):
        return self.get_queryset().id(id)

    def not_customer_of_the_buyinggroup(self):
    	# Don't allow to add the same customer twice
        return self.get_queryset(
        	).active().filter(~Q(sitecustomer__site=settings.SITE_ID))

class Customer(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL)
	phone1 = models.CharField(
		_("phone1"), max_length=25,null=True)
	phone2 = models.CharField(
		_("phone2"), max_length=25,null=True, blank=True)
	address = models.TextField(
		_("address"), null=True, blank=True)
	is_active = models.BooleanField(
		_("is_active"), default=True)
	objects = CustomerManager()
	objects_without_filter = models.Manager()

	def __unicode__(self):
		return getattr(self.user, get_user_model().USERNAME_FIELD)

	class Meta:
		verbose_name = _("customer")
		verbose_name_plural = _("customers")
		ordering = ("user__" + get_user_model().USERNAME_FIELD,)


class SiteCustomerQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def id(self, id):
		return self.filter(id=id)

	def not_the_buyinggroup(self):
		return self.filter(represent_this_buyinggroup=False)

	def with_login(self):
		return self.filter(customer__isnull=False)

class SiteCustomerManager(models.Manager):
    def get_queryset(self):
        return SiteCustomerQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

    def id(self, id):
        return self.get_queryset().id(id)

class SiteCustomer(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	customer = models.ForeignKey(
		Customer, 
		verbose_name=_("customer"),
		blank=True, null=True,
		on_delete=models.PROTECT)
	short_basket_name = models.CharField(
		_("short_basket_name"), max_length=25,null=False)
	long_basket_name = models.CharField(
		_("long_basket_name"), max_length=100,null=True)
	date_previous_balance = models.DateField(
		_("date_previous_balance"), default=datetime.date.today)
	previous_balance = models.DecimalField(
		_("previous_balance"), max_digits=8, decimal_places=2, default = 0)
	amount_in = models.DecimalField(
		_("amount_in"), max_digits=8, decimal_places=2, default = 0)
	amount_out = models.DecimalField(
		_("amount_out"), max_digits=8, decimal_places=2, default = 0)
	represent_this_buyinggroup = models.BooleanField(
		_("represent_this_buyinggroup"), default = False)
	is_active = models.BooleanField(_("is_active"), default=True)
	objects = SiteCustomerManager()
	objects_without_filter = models.Manager()

	def __unicode__(self):
		return self.short_basket_name
	
	class Meta:
		verbose_name = _("site customer")
		verbose_name_plural = _("site customers")
		ordering = ("short_basket_name",)
		unique_together = ("site", "customer",)
		index_together = [
			["site", "customer"],
			["site", "short_basket_name"],
			["short_basket_name"],
		]

@receiver(post_save, sender=SiteCustomer)
def site_customer_post_save(sender, **kwargs):
	# give access to the customer to private documents for the site
	site_customer = kwargs['instance']
	if site_customer.customer:
		site = Site.objects.get(id=settings.SITE_ID) 
		group = Group.objects.get(name=site.domain)
		group.user_set.add(site_customer.customer.user)

@receiver(post_delete, sender=SiteCustomer)
def site_customer_post_delete(sender, **kwargs):
	# remove access to the customer to private documents for the site
	site_customer = kwargs['instance']
	if site_customer.customer:
		site = Site.objects.get(id=settings.SITE_ID) 
		group = Group.objects.get(name=site.domain) 
		group.user_set.remove(site_customer.customer.user)

class StaffQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def id(self, id):
		return self.filter(id = id)

class StaffManager(models.Manager):
    def get_queryset(self):
        return SiteProducerQuerySet(self.model, using=self._db).filter(
        	login_site=settings.SITE_ID)

class Staff(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL, verbose_name=_("login"))
	login_site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	customer_responsible =  models.ForeignKey(
		SiteCustomer, verbose_name=_("customer_responsible"),
		on_delete=models.PROTECT)
	long_name = models.CharField(
		_("long_name"), max_length=100,null=True)
	memo = HTMLField(
		_("memo"), blank=True)
	is_active = models.BooleanField(_("is_active"), default=True)
	objects = StaffManager()
	objects_without_filter = models.Manager()

	def __unicode__(self):
		return self.long_name

	class Meta:
		verbose_name = _("staff member")
		verbose_name_plural = _("staff members")
		ordering = ("customer_responsible__short_basket_name",)

class ProductQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

	def site_producer_is(self, id):
		return self.filter(site_producer__id__exact=id)

	def department_for_producer_is(self, id):
		return self.filter(department_for_producer__id__exact=id)

	def is_not_selected_for_offer(self):
		return self.filter(is_into_offer=False)

	def is_selected_for_offer(self):
		return self.filter(is_into_offer=True)

class ProductManager(models.Manager):
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

class Product(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	site_producer = models.ForeignKey(
		SiteProducer, verbose_name=_("producer"), on_delete=models.PROTECT)
	long_name = models.CharField(_("long_name"), max_length=100)
	production_mode = models.ForeignKey(
		LUT_ProductionMode, verbose_name=_("production mode"), 
		related_name = 'production_mode+', on_delete=models.PROTECT)
	picture = FilerImageField(
		verbose_name=_("picture"), related_name="picture", 
		null=True, blank=True)
	order_description = HTMLField(_("order_description"), blank=True) 
	usage_description = HTMLField(_("usage_description"), blank=True) 

	department_for_customer = models.ForeignKey(
		LUT_DepartmentForCustomer, verbose_name=_("department_for_customer"), 
		on_delete=models.PROTECT)
	department_for_producer = models.ForeignKey(
		LUT_DepartmentForProducer, 
		verbose_name=_("department_for_producer"), on_delete=models.PROTECT)
	product_order = models.PositiveIntegerField(
		_("position_into_products_list_of_the_producer"), 
		default=0, blank=False, null=False)	
	placement = models.CharField(
		max_length=3, 
		choices=LUT_PRODUCT_PLACEMENT,
		default=PRODUCT_PLACEMENT_BASKET_MIDDLE,
		verbose_name=_("product_placement"), 
		help_text=_('used for helping to determine the order of prepration of this product'))

	order_by_kg_pay_by_kg = models.BooleanField(
		_("order_by_kg_pay_by_kg"),
		help_text=_('order_by_kg_pay_by_kg (yes / no)'))
	order_by_piece_pay_by_kg = models.BooleanField(
		_("order_by_piece_pay_by_kg"),
		help_text=_('order_by_piece_pay_by_kg (yes / no)'))
	order_average_weight = models.DecimalField(
		_("order_average_weight"),
		help_text=_('if usefull, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
		default=0, max_digits=6, decimal_places=3)
	order_by_piece_pay_by_piece = models.BooleanField(
		_("order_by_piece_pay_by_piece"),
		help_text=_('order_by_piece_pay_by_piece (yes / no)'))

	producer_must_give_order_detail_per_customer = models.BooleanField(
		_("individual package (yes/no)"),
		help_text=_("producer_must_give_order_detail_per_customer"))
	producer_unit_price = models.DecimalField(
		_("producer_unit_price"),
		help_text=_('last known price (into the billing unit)'), 
		max_digits=8, decimal_places=2)

	customer_minimum_order_quantity = models.DecimalField(
		_("customer_minimum_order_quantity"),
		help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
		default=0, max_digits=6, decimal_places=3)
	customer_increment_order_quantity = models.DecimalField(
		_("customer_increment_order_quantity"), 
		help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50 gr], 1 piece, 3 Kg)'),
		default=0, max_digits=6, decimal_places=3)
	customer_alert_order_quantity = models.DecimalField(
		_("customer_alert_order_quantity"), 
		help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
		default=0, max_digits=6, decimal_places=3)

	permanences = models.ManyToManyField(
		'Permanence', through='OfferItem', null=True, blank=True)
	is_into_offer = models.BooleanField(_("is_into_offer"))
	is_active = models.BooleanField(_("is_active"), default=True)
	is_created_on = models.DateTimeField(
		_("is_cretaed_on"), auto_now_add = True, blank=True)
	is_updated_on = models.DateTimeField(
		_("is_updated_on"), auto_now=True, blank=True)
	objects = ProductManager()
	objects_without_filter = models.Manager()

	def __unicode__(self):
		return self.site_producer.short_profile_name + ', ' + self.long_name

	class Meta:
		verbose_name = _("product")
		verbose_name_plural = _("products")
		# First field of ordering must be position_for_producer for 'adminsortable' 
		ordering = ("product_order",)
		unique_together = ("site", "site_producer", "long_name",)
		index_together = [
			["site", "product_order"],
			["site", "site_producer", "long_name"],
		]

class PermanenceQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

class PermanenceManager(models.Manager):
    def get_queryset(self):
        return PermanenceQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

class Permanence(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)

	short_name = models.CharField(_("short_name"), max_length=25, blank=True)
	status = models.CharField(
		max_length=3, 
		choices=LUT_PERMANENCE_STATUS,
		default=PERMANENCE_PLANIFIED,
		verbose_name=_("permanence_status"), 
		help_text=_('status of the permanence from planified, orders opened, orders closed, send, done'))
	distribution_date = models.DateField(_("distribution_date"))
	memo = HTMLField(_("memo"),blank=True)
	producers = models.ManyToManyField(
		'SiteProducer',	null=True, blank=True, 
		limit_choices_to={'site__exact': settings.SITE_ID})
	products = models.ManyToManyField(
		'Product', through='OfferItem',	null=True, blank=True)
	is_created_on = models.DateTimeField(
		_("is_cretaed_on"), auto_now_add = True)
	is_updated_on = models.DateTimeField(
		_("is_updated_on"), auto_now=True)
	objects = PermanenceManager()
	objects_without_filter = models.Manager()

	def get_producers(self):
		if self.id:
			changelist_url = urlresolvers.reverse(
			'admin:repanier_productselected_changelist', 
			)
			return u", ".join([u'<a href="' + changelist_url + \
				'?site_producer=' + str(p.id) + '">' + \
#				'?site_producer=' + str(p.id) + '" target="_blank">' + \
				 p.short_profile_name + '</a>' for p in self.producers.all()])
		return u''
	get_producers.short_description=(_("producers in this permanence"))
	get_producers.allow_tags = True

	def get_sitecustomers(self):
		if self.id:
			changelist_url = urlresolvers.reverse(
			'admin:repanier_purchase_changelist', 
			)
			return u", ".join([u'<a href="' + changelist_url + \
				'?site_customer=' + str(c.id) + '">' + \
#				'?site_customer=' + str(c.id) + '" target="_blank">' + \
				c.short_basket_name + '</a>' 
				for c in SiteCustomer.objects.filter(
					purchase__permanence_id=self.id).distinct()])
		return u''
	get_sitecustomers.short_description=(_("customers in this permanence"))
	get_sitecustomers.allow_tags = True


	def get_board(self):
		board = ""
		if self.id:
			permanenceboard_set = PermanenceBoard.objects.filter(
				permanence=self)
			first_board = True
			if permanenceboard_set:
				for permanenceboard in permanenceboard_set:
					r_link = ''
					r=permanenceboard.permanence_role
					if r:
						r_url = urlresolvers.reverse(
							'admin:repanier_lut_permanencerole_change', 
							args=(r.id,)
						)
						r_link = '<a href="' + r_url + \
							'" target="_blank">' + r.short_name + '</a>'
					c_link = ''
					c=permanenceboard.site_customer
					if c:
						c_url = urlresolvers.reverse(
							'admin:repanier_customer_change', 
							args=(c.customer.id,)
						)
						c_link = ' -> <a href="' + c_url + \
							'" target="_blank">' + c.short_basket_name + '</a>'
					if not(first_board):
						board += '<br/>'
					board += r_link + c_link
					first_board = False
		return board
	get_board.short_description=(_("permanence board"))
	get_board.allow_tags = True

	def __unicode__(self):
		if not self.short_name:
			label = _("Permanence on ")
			return label + self.distribution_date.strftime('%d-%m-%Y')
		return self.short_name

	class Meta:
		verbose_name = _("permanence")
		verbose_name_plural = _("permanences")
		ordering = ("distribution_date","short_name",)
		unique_together = ("site", "distribution_date", "short_name",)
		index_together = [
			["site", "distribution_date", "short_name"],
			["distribution_date", "short_name"],
		]

class PermanenceBoard(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	site_customer = models.ForeignKey(
		SiteCustomer, verbose_name=_("customer"),
		null=True, blank=True, on_delete=models.PROTECT)
	permanence = models.ForeignKey(
		Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
	permanence_role = models.ForeignKey(
		LUT_PermanenceRole, verbose_name=_("permanence_role"),
		on_delete=models.PROTECT)

	class Meta:
		verbose_name = _("permanence board")
		verbose_name_plural = _("permanences board")
		ordering = ("permanence","permanence_role","site_customer",)
		unique_together = ("permanence","permanence_role","site_customer",)
		index_together = [
			["permanence","permanence_role","site_customer"],
		]

class PermanenceInPreparation(Permanence):
	class Meta:
		proxy = True
		verbose_name = _("permanence in preparation")
		verbose_name_plural = _("permanences in preparation")

class PermanenceDone(Permanence):
	class Meta:
		proxy = True
		verbose_name = _("permanence done")
		verbose_name_plural = _("permanences done")

class OfferItemQuerySet(QuerySet):
	def active(self):
		return self.filter(is_active=True)

class OfferItemManager(models.Manager):
    def get_queryset(self):
        return OfferItemQuerySet(self.model, using=self._db)

class OfferItem(models.Model):
	permanence = models.ForeignKey(
		Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
	product = models.ForeignKey(
		Product, verbose_name=_("product"), on_delete=models.PROTECT)
	producer_unit_price = models.DecimalField(
		_("producer_unit_price"),
		help_text=_('last known price (into the billing unit)'), 
		max_digits=8, decimal_places=2, null = True, blank=True)
	is_active = models.BooleanField(_("is_active"), default=True)

	def __unicode__(self):
		return self.permanence.__unicode__() + ", " + \
			self.product.__unicode__()

	class Meta:
		verbose_name = _("offer's item")
		verbose_name_plural = _("offer's items")
		ordering = ("permanence","product",)
		unique_together = ("permanence","product",)
		index_together = [
			["permanence","product"],
		]


class PurchaseQuerySet(QuerySet):
	def premanence(self,permanence):
		return self.filter(permanence=permanence)

class PurchaseManager(models.Manager):
    def get_queryset(self):
        return PurchaseQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

class Purchase(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	offer_item = models.ForeignKey(
		OfferItem, verbose_name=_("offer_item"), on_delete=models.PROTECT)
	site_producer = models.ForeignKey(
		SiteProducer, verbose_name=_("producer"), on_delete=models.PROTECT)
	site_customer = models.ForeignKey(
		SiteCustomer, verbose_name=_("customer"), on_delete=models.PROTECT)
	permanence = models.ForeignKey(
		Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)	

	order_quantity = models.DecimalField(
		_("order_quantity"), max_digits=9, decimal_places=3, default = 0)
	validated_quantity = models.DecimalField(
		_("validated_quantity"), max_digits=9, decimal_places=3, 
		blank=True, null=True)
	# price, quantity or weight
	preparator_recorded_quantity = models.DecimalField(
		_("preparator_recorded_quantity"), 
		max_digits=9, decimal_places=3, blank=True, null=True)
	comment = models.CharField(
		_("comment"), max_length=200, default = '', blank=True, null=True)
	effective_balance = models.DecimalField(
		_("effective_balance"), max_digits=8, decimal_places=2, 
		blank=True, null=True)
	is_recorded_on_site_customer = models.BooleanField(
		_("is_recorded_on_sitecustomer"), default=False)
	is_recorded_on_site_producer = models.BooleanField(
		_("is_recorded_on_siteproducer"), default=False)
	is_recorded_on_previous_site_customer = models.BooleanField(
		_("is_recorded_on_previous_sitecustomer"), default=False)
	is_recorded_on_previous_site_producer = models.BooleanField(
		_("is_recorded_on_previous_siteproducer"), default=False)
	is_created_on = models.DateTimeField(
		_("is_cretaed_on"), auto_now_add=True)
	is_updated_on = models.DateTimeField(
		_("is_updated_on"), auto_now=True)
	objects = PurchaseManager()
	objects_without_filter = models.Manager()

	class Meta:
		verbose_name = _("purchase")
		verbose_name_plural = _("purchases")
		ordering = ("permanence", "offer_item", "site_customer")
		unique_together = ("permanence", "offer_item", "site_customer",)
		index_together = [
			["permanence", "offer_item", "site_customer"],
		]

class BankAccountQuerySet(QuerySet):
	def premanence(self,permanence):
		return self.filter(permanence=permanence)

class BankAccountManager(models.Manager):
    def get_queryset(self):
        return BankAccountQuerySet(self.model, using=self._db).filter(
        	site=settings.SITE_ID)

class BankAccount(models.Model):
	site = models.ForeignKey(
		Site, verbose_name=_("site"), default=settings.SITE_ID)
	site_producer = models.ForeignKey(
		SiteProducer, verbose_name=_("producer"), 
		on_delete=models.PROTECT, blank=True, null=True)
	site_customer = models.ForeignKey(
		SiteCustomer, verbose_name=_("customer"), 
		on_delete=models.PROTECT, blank=True, null=True)
	operation_date = models.DateField(_("operation_date"))
	operation_comment = models.CharField(
		_("operation_comment"), max_length=200, null = True, blank=True)
	bank_amount_in = models.DecimalField(
		_("bank_amount_in"), help_text=_('payment_on_the_account'),
		max_digits=8, decimal_places=2, blank=True, null=True)
	bank_amount_out = models.DecimalField(
		_("bank_amount_out"), help_text=_('payment_from_the_account'),
		max_digits=8, decimal_places=2, blank=True, null=True)
	is_recorded_on_site_customer = models.BooleanField(
		_("is_recorded_on_sitecustomer"), default=False)
	is_recorded_on_site_producer = models.BooleanField(
		_("is_recorded_on_siteproducer"), default=False)
	is_recorded_on_previous_site_customer = models.BooleanField(
		_("is_recorded_on_previous_sitecustomer"), default=False)
	is_recorded_on_previous_site_producer = models.BooleanField(
		_("is_recorded_on_previous_siteproducer"), default=False)
	is_created_on = models.DateTimeField(
		_("is_cretaed_on"), auto_now_add = True)
	is_updated_on = models.DateTimeField(
		_("is_updated_on"), auto_now=True)
	objects =BankAccountManager()
	objects_without_filter = models.Manager()

	class Meta:
		verbose_name = _("bank account movement")
		verbose_name_plural = _("bank account movements")
		ordering = ("site_producer", "site_customer")
		index_together = [
			["site_producer", "site_customer"],
			["site_customer", "is_recorded_on_site_customer"],
			["site_producer", "is_recorded_on_site_producer"],
		]