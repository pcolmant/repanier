# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.db.models.query import QuerySet

from django.contrib.auth.models import User
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
    return LUTQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, short_name):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(short_name=short_name)

class LUT(models.Model):
  short_name = models.CharField(_("short_name"), max_length=40, db_index=True, unique=True)
  description = HTMLField(_("description"), blank=True)
  is_active = models.BooleanField(_("is_active"), default=True)
  objects = LUTManager()

  def natural_key(self):
    return (self.short_name)

  def __unicode__(self):
    return self.short_name

  class Meta:
    abstract = True
    ordering = ("short_name",)

class LUT_ProductionMode(LUT):

  class Meta(LUT.Meta):
    verbose_name = _("production mode")
    verbose_name_plural = _("production modes")


class LUT_DepartmentForCustomer(LUT):

  class Meta(LUT.Meta):
    verbose_name = _("department for customer")
    verbose_name_plural = _("departments for customer")

class LUT_DepartmentForProducer(LUT):

  class Meta(LUT.Meta):
    verbose_name = _("department for producer")
    verbose_name_plural = _("departments for producer")

class LUT_PermanenceRole(LUT):

  class Meta(LUT.Meta):
    verbose_name = _("permanence role")
    verbose_name_plural = _("permanences roles")

class ProducerQuerySet(QuerySet):
  def active(self):
    return self.filter(is_active=True)

  def id(self, id):
    return self.filter(id = id)

  def not_the_buyinggroup(self):
    return self.filter(represent_this_buyinggroup=False)


class ProducerManager(models.Manager):
  def get_queryset(self):
    return ProducerQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, short_profile_name):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(
      short_profile_name = short_profile_name
    )

  def id(self, id):
    return self.get_queryset().id(id)

  def not_producer_of_the_buyinggroup(self):
    # Don't allow to add the same producer twice
    return self.get_queryset(
      ).active()

class Producer(models.Model):
  short_profile_name = models.CharField(
    _("short_profile_name"), max_length=25,null=False, db_index=True, unique=True)
  long_profile_name = models.CharField(
    _("long_profile_name"), max_length=100,null=True)
  email = models.CharField(
    _("email"), max_length=100,null=True)
  phone1 = models.CharField(
    _("phone1"), max_length=20,null=True)
  phone2 = models.CharField(
    _("phone2"), max_length=20,null=True, blank=True)
  fax = models.CharField(
    _("fax"), max_length=100,null=True, blank=True)
  bank_account = models.CharField(
    _("bank_account"), max_length=100,null=True, blank=True)
  vat_id = models.CharField(
    _("vat_id"), max_length=20,null=True, blank=True)
  address = models.TextField(_("address"), null=True, blank=True)
  password_reset_on = models.DateTimeField(
    _("password_reset_on"), null=True, blank=True)
  price_list_multiplier = models.DecimalField(
    _("price_list_multiplier"),
    help_text=_('This multiplier is applied to each price automaticaly imported/pushed.'), 
    default=0, max_digits=4, decimal_places=2)
  order_description = HTMLField(
    _("order_description"),
    help_text=_('This message is send by mail when we ordered something.'),
    blank=True)
  invoice_description = HTMLField(
    _("invoice_description"),
    help_text=_('This message is send by mail with the invoice report when we ordered something when closing the permanence.'),
    blank=True)
  date_balance = models.DateTimeField(
    _("date_balance"),  default=datetime.date.today)
  balance = models.DecimalField(
    _("balance"), max_digits=8, decimal_places=2, default = 0)
  represent_this_buyinggroup = models.BooleanField(
    _("represent_this_buyinggroup"), default = False)
  is_active = models.BooleanField(_("is_active"), default=True)
  objects = ProducerManager()

  def natural_key(self):
    return self.short_profile_name

  def get_products(self):
    link = ''
    if self.id:
      # changeproducer_url = urlresolvers.reverse(
      #   'admin:repanier_producer_change', args=(self.id,)
      # )
      # link = u'<a href="' + changeproducer_url + '">  ' + unicode(self) + '</a>'
      # if self.producer:
      # This producer may have product's list
      changeproductslist_url = urlresolvers.reverse(
        'admin:repanier_product_changelist', 
      )
      # &&& is used to hide the producer filter
      link = u'<a href="' + changeproductslist_url + \
        '?is_active__exact=1&department_for_this_producer=all&producer=' + \
        str(self.id) + '">  ' + \
        unicode(_("his_products")) + '</a>'
    return link
  get_products.short_description=(_("link to his products"))
  get_products.allow_tags = True

  def __unicode__(self):
    return self.short_profile_name
  
  class Meta:
    verbose_name = _("producer")
    verbose_name_plural = _("producers")
    ordering = ("short_profile_name",)

class CustomerQuerySet(QuerySet):
  def active(self):
    return self.filter(is_active=True)

  def may_order(self):
    return self.filter(may_order=True)

  def id(self, id):
    return self.filter(id=id)

  def not_the_buyinggroup(self):
    return self.filter(represent_this_buyinggroup=False)

  def the_buyinggroup(self):
    return self.filter(represent_this_buyinggroup=True)

class CustomerManager(models.Manager):
  def get_queryset(self):
    return CustomerQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, short_basket_name):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(
      short_basket_name = short_basket_name
    )

  def id(self, id):
    return self.get_queryset().id(id)


class Customer(models.Model):
  user = models.OneToOneField(settings.AUTH_USER_MODEL)
  short_basket_name = models.CharField(
    _("short_basket_name"), max_length=25,null=False, db_index=True, unique=True)
  long_basket_name = models.CharField(
    _("long_basket_name"), max_length=100,null=True)
  phone1 = models.CharField(
    _("phone1"), max_length=25,null=True)
  phone2 = models.CharField(
    _("phone2"), max_length=25,null=True, blank=True)
  vat_id = models.CharField(
    _("vat_id"), max_length=20,null=True, blank=True)
  address = models.TextField(
    _("address"), null=True, blank=True)
  password_reset_on = models.DateTimeField(
    _("password_reset_on"), null=True, blank=True)
  date_balance = models.DateTimeField(
    _("date_balance"), default=datetime.date.today)
  balance = models.DecimalField(
    _("balance"), max_digits=8, decimal_places=2, default = 0)
  represent_this_buyinggroup = models.BooleanField(
    _("represent_this_buyinggroup"), default = False)
  is_active = models.BooleanField(_("is_active"), default=True)
  may_order = models.BooleanField(_("may_order"), default=True)
  objects = CustomerManager()

  def natural_key(self):
    return (self.short_basket_name)
  natural_key.dependencies = ['repanier.customer']

  def __unicode__(self):
    return self.short_basket_name

  class Meta:
    verbose_name = _("customer")
    verbose_name_plural = _("customers")
    ordering = ("short_basket_name",)

class StaffQuerySet(QuerySet):
  def active(self):
    return self.filter(is_active=True)

  def id(self, id):
    return self.filter(id = id)

class StaffManager(models.Manager):
  def get_queryset(self):
    return StaffQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, *user_key):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(
      user = User.objects.get_by_natural_key(*user_key)
    )

class Staff(models.Model):
  user = models.OneToOneField(
    settings.AUTH_USER_MODEL, verbose_name=_("login"))
  customer_responsible =  models.ForeignKey(
    Customer, verbose_name=_("customer_responsible"),
    on_delete=models.PROTECT, blank=True, null=True)
  long_name = models.CharField(
    _("long_name"), max_length=100,null=True)
  function_description = HTMLField(
    _("function_description"),
    blank=True)
  is_reply_to_order_email = models.BooleanField(_("is_reply_to_order_email"), 
    default=False)
  is_reply_to_invoice_email = models.BooleanField(_("is_reply_to_invoice_email"),
    default=False)
  password_reset_on = models.DateTimeField(
    _("password_reset_on"), null=True, blank=True)
  is_active = models.BooleanField(_("is_active"), default=True)
  objects = StaffManager()

  def natural_key(self):
    return self.user.natural_key()
  natural_key.dependencies = ['auth.user']

  def get_customer_phone1(self):
    try:
      return self.customer_responsible.phone1
    except:
      return "N/A"
  get_customer_phone1.short_description=(_("phone1"))
  get_customer_phone1.allow_tags = False

  def __unicode__(self):
    return self.long_name

  class Meta:
    verbose_name = _("staff member")
    verbose_name_plural = _("staff members")
    ordering = ("long_name",)
    # ordering = ("customer_responsible__short_basket_name",)


class ProductQuerySet(QuerySet):

  def id(self, id):
    return self.filter(id=id)

  def active(self):
    return self.filter(is_active=True)

  def producer_is(self, id):
    return self.filter(producer__id__exact=id)

  def department_for_producer_is(self, id):
    return self.filter(department_for_producer__id__exact=id)

  def is_not_selected_for_offer(self):
    return self.filter(is_into_offer=False)

  def is_selected_for_offer(self):
    return self.filter(is_into_offer=True)

  def add_product_manually(self):
    return self.filter(automatically_added=ADD_PORDUCT_MANUALY)

  def is_waiting_to_be_selected_for_offer(self):
    return self.filter(is_into_offer=None)

class ProductManager(models.Manager):
  def get_queryset(self):
    return ProductQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, long_name, *producer_key):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(
      long_name = long_name,
      producer = Producer.objects.get_by_natural_key(*producer_key)
    )

  def id(self, id):
    return self.get_queryset().id(id)

class Product(models.Model):
  producer = models.ForeignKey(
    Producer, verbose_name=_("producer"), on_delete=models.PROTECT)
  long_name = models.CharField(_("long_name"), max_length=100)
  production_mode = models.ForeignKey(
    LUT_ProductionMode, verbose_name=_("production mode"), 
    related_name = 'production_mode+', 
    null=True, blank=True, on_delete=models.PROTECT)
  picture = FilerImageField(
    verbose_name=_("picture"), related_name="picture", 
    null=True, blank=True)
  offer_description = HTMLField(_("offer_description"), blank=True) 
  usage_description = HTMLField(_("usage_description"), blank=True) 

  department_for_customer = models.ForeignKey(
    LUT_DepartmentForCustomer, verbose_name=_("department_for_customer"), 
    null=True, blank=True, on_delete=models.PROTECT)
  department_for_producer = models.ForeignKey(
    LUT_DepartmentForProducer, 
    verbose_name=_("department_for_producer"), 
    null=True, blank=True, on_delete=models.PROTECT)
  product_order = models.PositiveIntegerField(
    _("position_into_products_list_of_the_producer"), 
    default=0, blank=False, null=False)
  product_reorder = models.PositiveIntegerField(
    _("position_into_products_list_of_the_producer"), 
    default=0)  
  placement = models.CharField(
    max_length=3, 
    choices=LUT_PRODUCT_PLACEMENT,
    default=PRODUCT_PLACEMENT_BASKET_MIDDLE,
    verbose_name=_("product_placement"), 
    help_text=_('used for helping to determine the order of prepration of this product'))

  order_by_kg_pay_by_kg = models.BooleanField(
    _("order_by_kg_pay_by_kg"))
  order_by_piece_pay_by_kg = models.BooleanField(
    _("order_by_piece_pay_by_kg"))
  order_average_weight = models.DecimalField(
    _("order_average_weight"),
    help_text=_('if usefull, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
    default=0, max_digits=6, decimal_places=3)
  order_by_piece_pay_by_piece = models.BooleanField(
    _("order_by_piece_pay_by_piece"))

  producer_must_give_order_detail_per_customer = models.BooleanField(
    _("individual package (yes/no)"),
    help_text=_("producer_must_give_order_detail_per_customer"))
  # 3 decimals required for rounding raisons
  producer_original_unit_price = models.DecimalField(
    _("producer_original_unit_price"),
    help_text=_('last known price before reduction (or ...) (into the billing unit), vat or potential compensation included'), 
    default=0, max_digits=9, decimal_places=3)
  # 3 decimals required for rounding raisons
  producer_unit_price = models.DecimalField(
    _("producer_unit_price"),
    help_text=_('last known price (into the billing unit), vat or potential compensation included'), 
    default=0, max_digits=9, decimal_places=2)
  vat_level = models.CharField(
    max_length=3, 
    choices=LUT_VAT,
    default=VAT_400,
    verbose_name=_("vat or compensation"), 
    help_text=_('When the vendor is in agricultural regime select the correct compensation %. In the other cases select the correct vat %'))

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

  automatically_added = models.CharField(
    max_length=3, 
    choices=LUT_ADD_PRODUCT,
    default=ADD_PORDUCT_MANUALY,
    verbose_name=_("If is into offer, automatically"), 
    help_text=_('this represent returnable, special offer, subscription and is automaticaly added to customer or group basket at order closure'))

  is_active = models.BooleanField(_("is_active"), default=True)
  is_created_on = models.DateTimeField(
    _("is_cretaed_on"), auto_now_add = True, blank=True)
  is_updated_on = models.DateTimeField(
    _("is_updated_on"), auto_now=True, blank=True)
  objects = ProductManager()

  def natural_key(self):
    return (self.long_name) + self.producer.natural_key()
  natural_key.dependencies = ['repanier.producer']

  def __unicode__(self):
    return self.producer.short_profile_name + ', ' + self.long_name

  class Meta:
    verbose_name = _("product")
    verbose_name_plural = _("products")
    # First field of ordering must be position_for_producer for 'adminsortable' 
    ordering = ("product_order",)
    unique_together = ("producer", "long_name",)
    index_together = [
      ["product_order", "id"],
      ["producer", "long_name"],
    ]

class PermanenceQuerySet(QuerySet):
  def is_opened(self):
    return self.filter(status=PERMANENCE_OPENED)

  def is_send(self):
    return self.filter(status=PERMANENCE_SEND)

class PermanenceManager(models.Manager):
  def get_queryset(self):
    return PermanenceQuerySet(self.model, using=self._db)

  def get_by_natural_key(self, distribution_date, short_name):
    # don't use the filtered qet_queryset but use the default one.
    return QuerySet(self.model, using=self._db).get(
      distribution_date = distribution_date,
      short_name = short_name
    )

class Permanence(models.Model):
  short_name = models.CharField(_("short_name"), max_length=40, blank=True)
  status = models.CharField(
    max_length=3, 
    choices=LUT_PERMANENCE_STATUS,
    default=PERMANENCE_PLANIFIED,
    verbose_name=_("permanence_status"), 
    help_text=_('status of the permanence from planified, orders opened, orders closed, send, done'))
  distribution_date = models.DateField(_("distribution_date"))
  offer_description = HTMLField(_("offer_description"),
    help_text=_('This message is send by mail to all customers when opening the order or on top of the web order screen.'),
    blank=True)
  order_description = HTMLField(
    _("order_description"),
    help_text=_('This message is send by mail to all customers having bought something and to the preparation team when sending the orders to the producers.'),
    blank=True)
  invoice_description = HTMLField(
    _("invoice_description"),
    help_text=_('This message is send by mail to all customers having bought something when closing the permamence.'),
    blank=True)
  producers = models.ManyToManyField(
    'Producer', null=True, blank=True,
    verbose_name = _("producers"))
  automaticaly_closed_on = models.DateTimeField(
    _("is_automaticaly_closed_on"), blank=True, null=True)
  is_done_on = models.DateTimeField(
    _("is_done_on"), blank=True, null=True)

  is_created_on = models.DateTimeField(
    _("is_cretaed_on"), auto_now_add = True)
  is_updated_on = models.DateTimeField(
    _("is_updated_on"), auto_now=True)
  objects = PermanenceManager()

  def natural_key(self):
    return (self.distribution_date, self.short_name)

  def get_producers(self):
    if self.id:
      if self.status==PERMANENCE_PLANIFIED:
        changelist_url = urlresolvers.reverse(
        'admin:repanier_product_changelist', 
        )
        return u", ".join([u'<a href="' + changelist_url + \
          '?department_for_this_producer=all&producer=' + str(p.id) + '" target="_blank">' + \
           p.short_profile_name + '</a>' for p in self.producers.all()])
      else:
        # change_url = urlresolvers.reverse(
        #   'admin:repanier_permanenceinpreparation_change', 
        #   args=(self.id,)
        #   )
        return u", ".join([
          p.short_profile_name + '</a>' for p in self.producers.all()
        ])
    return u''
  get_producers.short_description=(_("producers in this permanence"))
  get_producers.allow_tags = True

  def get_customers(self):
    if self.id:
      changelist_url = urlresolvers.reverse(
      'admin:repanier_purchase_changelist', 
      )
      return u", ".join([u'<a href="' + changelist_url + \
        '?permanence=' + str(self.id) + \
        '&customer=' + str(c.id) + '" target="_blank">' + \
        c.short_basket_name + '</a>' 
        for c in Customer.objects.filter(
          purchase__permanence_id=self.id).distinct()])
    return u''
  get_customers.short_description=(_("customers in this permanence"))
  get_customers.allow_tags = True

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
          c=permanenceboard.customer
          if c:
            c_url = urlresolvers.reverse(
              'admin:repanier_customer_change', 
              args=(c.id,)
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
    # ordering = ("distribution_date","short_name",)
    unique_together = ("distribution_date", "short_name",)
    index_together = [
      ["distribution_date", "short_name"],
    ]

class PermanenceBoard(models.Model):
  customer = models.ForeignKey(
    Customer, verbose_name=_("customer"),
    null=True, blank=True, on_delete=models.PROTECT)
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
  permanence_role = models.ForeignKey(
    LUT_PermanenceRole, verbose_name=_("permanence_role"),
    on_delete=models.PROTECT)

  class Meta:
    verbose_name = _("permanence board")
    verbose_name_plural = _("permanences board")
    ordering = ("permanence","permanence_role","customer",)
    unique_together = ("permanence","permanence_role","customer",)
    index_together = [
      ["permanence","permanence_role","customer"],
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

  def product(self,product):
    return self.filter(product=product)

  def add_product_manualy(self):
    return self.filter(automatically_added=ADD_PORDUCT_MANUALY)

  def permanence(self,permanence):
    return self.filter(permanence=permanence)

class OfferItemManager(models.Manager):
  def get_queryset(self):
    return OfferItemQuerySet(self.model, using=self._db)

class OfferItem(models.Model):
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
  product = models.ForeignKey(
    Product, verbose_name=_("product"), on_delete=models.PROTECT)
  automatically_added = models.CharField(
    max_length=3, 
    choices=LUT_ADD_PRODUCT_DISPLAY,
    default=ADD_PORDUCT_MANUALY,
    verbose_name=_("If is into offer, automatically"), 
    help_text=_('this represent returnable, special offer, subscription and is automaticaly added to customer or group basket at order closure'))
  is_active = models.BooleanField(_("is_active"), default=True)
  objects = OfferItemManager()

  def get_total_order_quantity(self):
    total_order_quantity = 0
    if self.id:
      if self.permanence.status<=PERMANENCE_PLANIFIED:
        pass
      elif self.permanence.status <= PERMANENCE_SEND:
        result_set = Purchase.objects.filter(
          product_id=self.product.id, permanence_id=self.permanence_id).values(
          'product_id', 'permanence_id').annotate(
          total_order_quantity=Sum('order_quantity')).values(
          'total_order_quantity').order_by()[:1]
        if result_set:
          total_order_quantity = result_set[0].get('total_order_quantity')
        if total_order_quantity == None:
          total_order_quantity = 0
      else:
        result_set = Purchase.objects.filter(
          product_id=self.product.id, permanence_id=self.permanence_id).values(
          'product_id', 'permanence_id').annotate(
          total_order_quantity=Sum('prepared_quantity')).values(
          'total_order_quantity').order_by()[:1]
        if result_set:
          total_order_quantity = result_set[0].get('total_order_quantity')
        if total_order_quantity == None:
          total_order_quantity = 0
    return total_order_quantity

  get_total_order_quantity.short_description=(_("total order quantity"))
  get_total_order_quantity.allow_tags = False

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

class CustomerInvoice(models.Model):
  customer = models.ForeignKey(
    Customer, verbose_name=_("customer"), 
    on_delete=models.PROTECT)
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT, db_index=True) 
  date_previous_balance = models.DateTimeField(
    _("date_previous_balance"), default=datetime.date.today)
  previous_balance = models.DecimalField(
    _("previous_balance"), max_digits=8, decimal_places=2, default = 0)
  purchase_amount = models.DecimalField(
    _("purchase_amount"), help_text=_('purchased amount'),
    max_digits=8, decimal_places=2,  default = 0)
  bank_amount_in = models.DecimalField(
    _("bank_amount_in"), help_text=_('payment_on_the_account'),
    max_digits=8, decimal_places=2,  default = 0)
  bank_amount_out = models.DecimalField(
    _("bank_amount_out"), help_text=_('payment_from_the_account'),
    max_digits=8, decimal_places=2,  default = 0)
  date_balance = models.DateTimeField(
    _("date_balance"),  default=datetime.date.today)
  balance = models.DecimalField(
    _("balance"), 
    max_digits=8, decimal_places=2, default = 0)

  def __unicode__(self):
    return self.customer.__unicode__() + " " + self.permanence.__unicode__()

  class Meta:
    verbose_name = _("customer invoice")
    verbose_name_plural = _("customers invoices")
    unique_together = ("permanence","customer",)
    index_together = [
      ["permanence","customer",]
    ]

class ProducerInvoice(models.Model):
  producer = models.ForeignKey(
    Producer, verbose_name=_("producer"), 
    on_delete=models.PROTECT)
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT, db_index=True) 
  date_previous_balance = models.DateTimeField(
    _("date_previous_balance"), default=datetime.date.today)
  previous_balance = models.DecimalField(
    _("previous_balance"), max_digits=8, decimal_places=2, default = 0)
  purchase_amount = models.DecimalField(
    _("purchase_amount"), help_text=_('purchased amount'),
    max_digits=8, decimal_places=2, default = 0)
  bank_amount_in = models.DecimalField(
    _("bank_amount_in"), help_text=_('payment_on_the_account'),
    max_digits=8, decimal_places=2, default = 0)
  bank_amount_out = models.DecimalField(
    _("bank_amount_out"), help_text=_('payment_from_the_account'),
    max_digits=8, decimal_places=2, default = 0)
  date_balance = models.DateTimeField(
    _("date_balance"),  default=datetime.date.today)
  balance = models.DecimalField(
    _("balance"),
    max_digits=8, decimal_places=2, default = 0)

  def __unicode__(self):
    return self.producer.__unicode__() + " " + self.permanence.__unicode__()

  class Meta:
    verbose_name = _("producer invoice")
    verbose_name_plural = _("producers invoices")
    unique_together = ("permanence","producer",)
    index_together = [
      ["permanence","producer",]
    ]

class PurchaseQuerySet(QuerySet):
  def product(self,product):
    return self.filter(product=product)

  def permanence(self,permanence):
    return self.filter(permanence=permanence)

  def customer(self,customer):
    return self.filter(customer=customer)

class PurchaseManager(models.Manager):
  def get_queryset(self):
    return PurchaseQuerySet(self.model, using=self._db)

class Purchase(models.Model):
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), 
    on_delete=models.PROTECT) 
  distribution_date = models.DateField(_("distribution_date"))
  product = models.ForeignKey(
    Product, verbose_name=_("product"), blank=True, null=True, on_delete=models.PROTECT)
  offer_item = models.ForeignKey(
    OfferItem, verbose_name=_("offer_item"), blank=True, null=True, on_delete=models.PROTECT)
  producer = models.ForeignKey(
    Producer, verbose_name=_("producer"), blank=True, null=True, on_delete=models.PROTECT)
  customer = models.ForeignKey(
    Customer, verbose_name=_("customer"), 
    blank=True, null=True, on_delete=models.PROTECT,
    db_index=True)

  order_quantity = models.DecimalField(
    _("order_quantity"), max_digits=9, decimal_places=3, default = 0)
  order_amount = models.DecimalField(
    _("order_amount"), 
    max_digits=8, decimal_places=2, default = 0)
  long_name = models.CharField(_("long_name"), max_length=100,
    default='', blank=True, null=True)
  order_by_piece_pay_by_kg = models.BooleanField(
    _("order_by_piece_pay_by_kg"),
    default=False,
    help_text=_('order_by_piece_pay_by_kg (yes / no)'))
  prepared_quantity = models.DecimalField(
    _("preparared_quantity"), 
    max_digits=9, decimal_places=3, blank=True, null=True, default=0)
  prepared_unit_price = models.DecimalField(
    _("prepared_unit_price"),
    help_text=_('last known price (into the billing unit)'), 
    max_digits=8, decimal_places=2, default=0)
  prepared_amount = models.DecimalField(
    _("effective_balance"), 
    max_digits=8, decimal_places=2, default=0)
  vat_level = models.CharField(
    max_length=3, 
    choices=LUT_VAT,
    default=VAT_400,
    verbose_name=_("vat or compensation"), 
    help_text=_('When the vendor is in agricultural regime select the correct compensation %. In the other cases select the correct vat %'))
  comment = models.CharField(
    _("comment"), max_length=200, default = '', blank=True, null=True)
  is_to_be_prepared = models.NullBooleanField(_("is_to_be_prepared"))
  is_recorded_on_customer_invoice =  models.ForeignKey(
    CustomerInvoice, verbose_name=_("customer invoice"),
    on_delete=models.PROTECT, blank=True, null=True,
    db_index=True)
  is_recorded_on_producer_invoice = models.ForeignKey(
    ProducerInvoice, verbose_name=_("producer invoice"),
    on_delete=models.PROTECT, blank=True, null=True,
    db_index=True)
  is_created_on = models.DateTimeField(
    _("is_cretaed_on"), auto_now_add=True)
  is_updated_on = models.DateTimeField(
    _("is_updated_on"), auto_now=True)
  objects = PurchaseManager()

  class Meta:
    verbose_name = _("purchase")
    verbose_name_plural = _("purchases")
    ordering = ("permanence", "customer", "product")
    unique_together = ("permanence", "product", "customer",)
    index_together = [
      ["permanence", "product", "customer"],
      ["offer_item", "permanence", "customer"],
      ["permanence", "customer", "product"],
    ]

class CustomerOrder(models.Model):
  permanence = models.ForeignKey(
    Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT) 
  customer = models.ForeignKey(
    Customer, verbose_name=_("customer"), 
    on_delete=models.PROTECT, blank=True, null=True)
  order_amount = models.DecimalField(
    _("order_amount"), help_text=_('order amount'),
    max_digits=8, decimal_places=2,  default = 0)

  class Meta:
    verbose_name = _("customer order")
    verbose_name_plural = _("customers orders")
    index_together = [
      ["permanence", "customer"],
    ]

class BankAccountQuerySet(QuerySet):
  def permanence(self,permanence):
    return self.filter(permanence=permanence)

class BankAccountManager(models.Manager):
  def get_queryset(self):
    return BankAccountQuerySet(self.model, using=self._db)

class BankAccount(models.Model):
  producer = models.ForeignKey(
    Producer, verbose_name=_("producer"), 
    on_delete=models.PROTECT, blank=True, null=True)
  customer = models.ForeignKey(
    Customer, verbose_name=_("customer"), 
    on_delete=models.PROTECT, blank=True, null=True)
  operation_date = models.DateField(_("operation_date"),
    db_index=True)
  operation_comment = models.CharField(
    _("operation_comment"), max_length=200, null = True, blank=True)
  bank_amount_in = models.DecimalField(
    _("bank_amount_in"), help_text=_('payment_on_the_account'),
    max_digits=8, decimal_places=2, default = 0)
  bank_amount_out = models.DecimalField(
    _("bank_amount_out"), help_text=_('payment_from_the_account'),
    max_digits=8, decimal_places=2, default = 0)
  is_recorded_on_customer_invoice =  models.ForeignKey(
    CustomerInvoice, verbose_name=_("customer invoice"),
    on_delete=models.PROTECT, blank=True, null=True,
    db_index=True)
  is_recorded_on_producer_invoice = models.ForeignKey(
    ProducerInvoice, verbose_name=_("producer invoice"),
    on_delete=models.PROTECT, blank=True, null=True,
    db_index=True)
  is_created_on = models.DateTimeField(
    _("is_cretaed_on"), auto_now_add = True)
  is_updated_on = models.DateTimeField(
    _("is_updated_on"), auto_now=True)
  objects =BankAccountManager()

  class Meta:
    verbose_name = _("bank account movement")
    verbose_name_plural = _("bank account movements")
    ordering = ("producer", "customer")
    index_together = [
      ["producer", "customer"],
    ]
