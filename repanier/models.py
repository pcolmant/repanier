# -*- coding: utf-8 -*-
import uuid

# sudo -u postgres psql
# \c ptidej
# ALTER TABLE repanier_purchase ADD COLUMN order_unit character varying(3);
# ALTER TABLE repanier_purchase ALTER COLUMN order_unit SET NOT NULL;
# ALTER TABLE repanier_purchase ALTER COLUMN order_unit SET DEFAULT 100;
# ALTER TABLE repanier_product ADD COLUMN order_unit character varying(3);
# ALTER TABLE repanier_product ALTER COLUMN order_unit SET NOT NULL;
# ALTER TABLE repanier_product ALTER COLUMN order_unit SET DEFAULT 100;
# ALTER TABLE repanier_purchase ADD COLUMN department_for_customer_id integer;
# CREATE INDEX repanier_purchase_department_for_customer_id
# ON repanier_purchase
# USING btree
# (department_for_customer_id);
# ALTER TABLE repanier_bankaccount ADD COLUMN permanence_id integer;
# CREATE INDEX repanier_bankaccount_permanence_id
# ON repanier_bankaccount
# USING btree
# (permanence_id);
# ALTER TABLE repanier_producer ADD COLUMN invoice_by_basket boolean;
# update repanier_producer set invoice_by_basket = FALSE;
# ALTER TABLE repanier_producer ALTER COLUMN invoice_by_basket SET NOT NULL;

# ALTER TABLE repanier_purchase DROP COLUMN order_by_kg_pay_by_kg;
# ALTER TABLE repanier_purchase DROP COLUMN order_by_piece_pay_by_kg;
# ALTER TABLE repanier_purchase DROP COLUMN producer_must_give_order_detail_per_customer;
# ALTER TABLE repanier_purchase DROP COLUMN product_order;
# ALTER TABLE repanier_purchase DROP COLUMN is_to_be_prepared;
# ALTER TABLE repanier_product DROP COLUMN product_order;
# ALTER TABLE repanier_product DROP COLUMN product_reorder;
# ALTER TABLE repanier_product DROP COLUMN order_by_kg_pay_by_kg;
# ALTER TABLE repanier_product DROP COLUMN order_by_piece_pay_by_kg;
# ALTER TABLE repanier_product DROP COLUMN order_by_piece_pay_by_piece;
# ALTER TABLE repanier_product DROP COLUMN producer_must_give_order_detail_per_customer;
# ALTER TABLE repanier_product DROP COLUMN automatically_added;
# ALTER TABLE repanier_producer DROP COLUMN order_description;
# ALTER TABLE repanier_permanence DROP COLUMN order_description;
# ALTER TABLE repanier_offeritem DROP COLUMN automatically_added;
# ALTER TABLE repanier_product DROP COLUMN usage_description;
# ALTER TABLE repanier_purchase DROP COLUMN price_list_multiplier;
# ALTER TABLE repanier_product DROP COLUMN price_list_multiplier;
# ALTER TABLE repanier_producer DROP COLUMN invoice_description;

# ALTER TABLE repanier_product
# ALTER COLUMN unit_price_without_tax TYPE numeric(8,2);
# ALTER TABLE repanier_product
# ALTER COLUMN unit_price_with_compensation TYPE numeric(8,2);
# ALTER TABLE repanier_purchase
# ALTER COLUMN price_without_tax TYPE numeric(8,2);

# ALTER TABLE repanier_purchase ADD COLUMN quantity_for_preparation_order numeric(9,3) DEFAULT 0;
# ALTER TABLE repanier_purchase ALTER COLUMN quantity_for_preparation_order SET NOT NULL;
# ALTER TABLE repanier_producer ADD COLUMN initial_balance numeric(8,2) DEFAULT 0;
# ALTER TABLE repanier_producer ALTER COLUMN initial_balance SET NOT NULL;
# ALTER TABLE repanier_customer ADD COLUMN initial_balance numeric(8,2) DEFAULT 0;
# ALTER TABLE repanier_customer ALTER COLUMN initial_balance SET NOT NULL;

# ALTER TABLE repanier_purchase RENAME price_without_tax  TO price_with_vat;
# ALTER TABLE repanier_purchase RENAME price_with_tax  TO price_with_compensation;
# UPDATE repanier_purchase set price_with_vat = price_with_compensation;
# ALTER TABLE repanier_product DROP COLUMN unit_price_without_tax;

# ALTER TABLE repanier_purchase ADD COLUMN order_average_weight numeric(6,3);
# UPDATE repanier_purchase set order_average_weight = 0;
# ALTER TABLE repanier_purchase ALTER COLUMN order_average_weight SET NOT NULL;

# ALTER TABLE repanier_staff ADD COLUMN is_external_group boolean;
# update repanier_staff set is_external_group = false;
# ALTER TABLE repanier_staff ALTER COLUMN is_external_group SET NOT NULL;

# ALTER TABLE repanier_producer ADD COLUMN limit_to_alert_order_quantity boolean;
# UPDATE repanier_producer set limit_to_alert_order_quantity = false;
# ALTER TABLE repanier_producer ALTER COLUMN limit_to_alert_order_quantity SET NOT NULL;
# ALTER TABLE repanier_offeritem ADD COLUMN limit_to_alert_order_quantity boolean;
# UPDATE repanier_offeritem set limit_to_alert_order_quantity = false;
# ALTER TABLE repanier_offeritem ALTER COLUMN limit_to_alert_order_quantity SET NOT NULL;
# ALTER TABLE repanier_offeritem ADD COLUMN customer_alert_order_quantity numeric(6,3);

# ALTER TABLE repanier_permanence RENAME automaticaly_closed  TO automatically_closed;

# ALTER TABLE repanier_lut_productionmode ADD COLUMN picture_id integer;
# ALTER TABLE repanier_lut_productionmode
#   ADD CONSTRAINT repanier_lut_productionmode_picture_id_fkey FOREIGN KEY (picture_id)
#       REFERENCES filer_image (file_ptr_id) MATCH SIMPLE
#       ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
# CREATE INDEX repanier_lut_productionmode_picture_id
#   ON repanier_lut_productionmode
#   USING btree
#   (picture_id);

from const import *
from django.conf import settings
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import pre_save
from django.db.models.signals import post_save
from django.db.models.signals import post_delete

from django.contrib.auth.models import Group
from django.dispatch import receiver
from djangocms_text_ckeditor.fields import HTMLField
from django.utils.translation import ugettext_lazy as _
from django.utils.formats import number_format
from filer.fields.image import FilerImageField
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
        return self.short_name

    def __unicode__(self):
        return u'%s' % self.short_name

    class Meta:
        abstract = True
        ordering = ("short_name",)


class LUT_ProductionMode(LUT):
    picture = FilerImageField(
        verbose_name=_("picture"), related_name="picture",
        null=True, blank=True)

    class Meta(LUT.Meta):
        verbose_name = _("production mode")
        verbose_name_plural = _("production modes")


class LUT_DepartmentForCustomer(LUT):
    class Meta(LUT.Meta):
        verbose_name = _("department for customer")
        verbose_name_plural = _("departments for customer")


class LUT_PermanenceRole(LUT):
    automatically_added = models.BooleanField(_("automatically added to the new permanences"), default=False)

    class Meta(LUT.Meta):
        verbose_name = _("permanence role")
        verbose_name_plural = _("permanences roles")


@receiver(pre_save, sender=LUT_PermanenceRole)
def lut_permanence_role_pre_save(sender, **kwargs):
    lut_permanence_role = kwargs['instance']
    if not lut_permanence_role.is_active:
        lut_permanence_role.automatically_added = False


class Producer(models.Model):
    short_profile_name = models.CharField(
        _("short_profile_name"), max_length=25, null=False, db_index=True, unique=True)
    long_profile_name = models.CharField(
        _("long_profile_name"), max_length=100, null=True)
    email = models.CharField(
        _("email"), max_length=100, null=True)
    phone1 = models.CharField(
        _("phone1"), max_length=20, null=True)
    phone2 = models.CharField(
        _("phone2"), max_length=20, null=True, blank=True)
    fax = models.CharField(
        _("fax"), max_length=100, null=True, blank=True)
    address = models.TextField(_("address"), null=True, blank=True)
    # uuid used to access to producer invoices without login
    uuid = models.CharField(
        _("uuid"), max_length=36, null=True)
    invoice_by_basket = models.BooleanField(_("invoice by basket"), default=False)
    limit_to_alert_order_quantity = models.BooleanField(_("limit maximum order qty to alert qty"), default=False)

    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=0, max_digits=4, decimal_places=2)
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("Default vat or compensation"),
        help_text=_(
            "When the vendor is in agricultural"
            " regime select the correct compensation %. In the other cases select the correct vat %"))

    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"), max_digits=8, decimal_places=2, default=0)
    # The initial balance is needed to compute the invoice control list
    initial_balance = models.DecimalField(
        _("initial balance"), max_digits=8, decimal_places=2, default=0)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)

    def natural_key(self):
        return self.short_profile_name

    def get_products(self):
        link = ''
        if self.id:
            # This producer may have product's list
            changeproductslist_url = urlresolvers.reverse(
                'admin:repanier_product_changelist',
            )
            link = u'<a href="' + changeproductslist_url + \
                   '?is_active__exact=1&producer=' + \
                   str(self.id) + '" target="_blank" class="addlink">&nbsp;' + \
                   unicode(_("his_products")) + '</a>'
        return link

    get_products.short_description = (_("link to his products"))
    get_products.allow_tags = True

    def get_balance(self):
        producer_invoice_set_exist = ProducerInvoice.objects.filter(producer_id=self.id).order_by()[:1]
        if producer_invoice_set_exist:
            if self.balance < 0:
                return '<a href="' + urlresolvers.reverse('invoicep_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#298A08">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance == 0:
                return '<a href="' + urlresolvers.reverse('invoicep_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#74DF00">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance > 30:
                return '<a href="' + urlresolvers.reverse('invoicep_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#FF4000">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('invoicep_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#DF013A">%s</span>' % (number_format(self.balance, 2))) + '</a>'
        else:
            if self.balance < 0:
                return '<span style="color:#298A08">%s</span>' % (number_format(self.balance, 2))
            elif self.balance == 0:
                return '<span style="color:#74DF00">%s</span>' % (number_format(self.balance, 2))
            elif self.balance > 30:
                return '<span style="color:#FF4000">%s</span>' % (number_format(self.balance, 2))
            else:
                return '<span style="color:#DF013A">%s</span>' % (number_format(self.balance, 2))

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True

    def get_last_invoice(self):
        producer_last_invoice = ProducerInvoice.objects.filter(producer_id=self.id).order_by("-id").first()
        if producer_last_invoice:
            if producer_last_invoice.total_price_with_tax < 0:
                return '<span style="color:#298A08">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax == 0:
                return '<span style="color:#74DF00">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax > 30:
                return '<span style="color:#FF4000">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            else:
                return '<span style="color:#DF013A">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
        else:
            return '<span style="color:#74DF00">%s</span>' % (number_format(0, 2))

    get_last_invoice.short_description = _("last invoice")
    get_last_invoice.allow_tags = True

    def __unicode__(self):
        return u'%s' % self.short_profile_name

    class Meta:
        verbose_name = _("producer")
        verbose_name_plural = _("producers")
        ordering = ("short_profile_name",)


@receiver(pre_save, sender=Producer)
def producer_pre_save(sender, **kwargs):
    producer = kwargs['instance']
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE
    # The first producer created represents the buying group
    # It's important to have one and only one producer representing the buying group
    # producer_set = Producer.objects.all().the_buyinggroup().order_by()[:1]
    # if not producer_set:
    # producer.represent_this_buyinggroup = True
    # else:
    # producer.represent_this_buyinggroup = False
    if producer.uuid is None:
        producer.uuid = uuid.uuid4()
    if producer.id is None:
        producer.balance = producer.initial_balance
        bank_account_set = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by()[:1]
        if bank_account_set:
            producer.date_balance = bank_account_set[0].operation_date
    else:
        producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer.id).order_by()[:1]
        if producer_invoice_set:
            # Do not modify the balance, an invoice already exist
            pass
        else:
            producer.balance = producer.initial_balance
            bank_account_set = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by()[:1]
            if bank_account_set:
                producer.date_balance = bank_account_set[0].operation_date


class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    short_basket_name = models.CharField(
        _("short_basket_name"), max_length=25, null=False, db_index=True, unique=True)
    long_basket_name = models.CharField(
        _("long_basket_name"), max_length=100, null=True)
    email2 = models.EmailField(_('secondary email address'), null=True, blank=True)
    phone1 = models.CharField(
        _("phone1"), max_length=25, null=True)
    phone2 = models.CharField(
        _("phone2"), max_length=25, null=True, blank=True)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True)
    address = models.TextField(
        _("address"), null=True, blank=True)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"), max_digits=8, decimal_places=2, default=0)
    # The initial balance is needed to compute the invoice control list
    initial_balance = models.DecimalField(
        _("initial balance"), max_digits=8, decimal_places=2, default=0)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)
    may_order = models.BooleanField(_("may_order"), default=True)

    def get_balance(self):
        last_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=self.id).order_by()[:1]
        if last_customer_invoice_set:
            if self.balance >= 30:
                return '<a href="' + urlresolvers.reverse('invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#74DF00">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance >= -10:
                return '<a href="' + urlresolvers.reverse('invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#DF013A">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#FF4000">%s</span>' % (number_format(self.balance, 2))) + '</a>'
        else:
            if self.balance >= 30:
                return '<span style="color:#74DF00">%s</span>' % (number_format(self.balance, 2))
            elif self.balance >= -10:
                return '<span style="color:#DF013A">%s</span>' % (number_format(self.balance, 2))
            else:
                return '<span style="color:#FF4000">%s</span>' % (number_format(self.balance, 2))

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True

    def natural_key(self):
        return self.short_basket_name

    natural_key.dependencies = ['repanier.customer']

    def __unicode__(self):
        return u'%s' % self.short_basket_name

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        ordering = ("short_basket_name",)


@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, **kwargs):
    customer = kwargs['instance']
    if not customer.is_active:
        customer.may_order = False
    if customer.id is None:
        customer.balance = customer.initial_balance
        bank_account_set = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by()[:1]
        if bank_account_set:
            customer.date_balance = bank_account_set[0].operation_date
    else:
        customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer.id).order_by()[:1]
        if customer_invoice_set:
            # Do not modify the balance, an invoice already exist
            pass
        else:
            customer.balance = customer.initial_balance
            bank_account_set = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by()[:1]
            if bank_account_set:
                customer.date_balance = bank_account_set[0].operation_date
                # The first customer created represents the buying group
                # It's important to have one and only one customer representing the buying group
                # customer_set = Customer.objects.all().the_buyinggroup().order_by()[:1]
                # if not customer_set:
                # customer.represent_this_buyinggroup = True
                # else:
                # customer.represent_this_buyinggroup = False


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs['instance']
    user = customer.user
    user.delete()


class Staff(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("login"))
    customer_responsible = models.ForeignKey(
        Customer, verbose_name=_("customer_responsible"),
        on_delete=models.PROTECT, blank=True, null=True)
    long_name = models.CharField(
        _("long_name"), max_length=100, null=True)
    function_description = HTMLField(
        _("function_description"),
        blank=True)
    is_reply_to_order_email = models.BooleanField(_("is_reply_to_order_email"),
                                                  default=False)
    is_reply_to_invoice_email = models.BooleanField(_("is_reply_to_invoice_email"),
                                                    default=False)
    is_external_group = models.BooleanField(_("is external group"),
                                            default=False)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True)
    is_active = models.BooleanField(_("is_active"), default=True)

    def natural_key(self):
        return self.user.natural_key()

    natural_key.dependencies = ['auth.user']

    def get_customer_phone1(self):
        try:
            return self.customer_responsible.phone1
        except:
            return "N/A"

    get_customer_phone1.short_description = (_("phone1"))
    get_customer_phone1.allow_tags = False

    def __unicode__(self):
        return u'%s' % self.long_name

    class Meta:
        verbose_name = _("staff member")
        verbose_name_plural = _("staff members")
        ordering = ("long_name",)
        # ordering = ("customer_responsible__short_basket_name",)


@receiver(post_save, sender=Staff)
def staff_post_save(sender, **kwargs):
    staff = kwargs['instance']
    if staff.id is not None:
        user = staff.user
        user.groups.clear()
        if staff.is_external_group:
            group_id = Group.objects.filter(name=READ_ONLY_GROUP).first()
            user.groups.add(group_id)
        else:
            if not staff.is_reply_to_order_email:
                group_id = Group.objects.filter(name=INVOICE_GROUP).first()
                user.groups.add(group_id)
            if not staff.is_reply_to_invoice_email:
                group_id = Group.objects.filter(name=ORDER_GROUP).first()
                user.groups.add(group_id)


@receiver(post_delete, sender=Staff)
def staff_post_delete(sender, **kwargs):
    staff = kwargs['instance']
    user = staff.user
    user.delete()


class Product(models.Model):
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"), on_delete=models.PROTECT)
    long_name = models.CharField(_("long_name"), max_length=100)
    production_mode = models.ForeignKey(
        LUT_ProductionMode, verbose_name=_("production mode"),
        related_name='production_mode+',
        on_delete=models.PROTECT)
    picture = FilerImageField(
        verbose_name=_("picture"), related_name="picture",
        null=True, blank=True)
    offer_description = HTMLField(_("offer_description"), blank=True)

    department_for_customer = models.ForeignKey(
        LUT_DepartmentForCustomer,
        verbose_name=_("department_for_customer"),
        on_delete=models.PROTECT)

    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("product_placement"),
        help_text=_('used for helping to determine the order of preparation of this product'))

    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=0, max_digits=6, decimal_places=3)

    original_unit_price = models.DecimalField(
        _("original unit price"),
        help_text=_('last known price (/piece or /kg) from the producer price list'),
        default=0, max_digits=8, decimal_places=2)
    unit_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=0, max_digits=8, decimal_places=2)
    unit_price_with_vat = models.DecimalField(
        _("unit price with vat"),
        help_text=_('last known price (/piece or /kg), vat included'),
        default=0, max_digits=8, decimal_places=2)
    unit_price_with_compensation = models.DecimalField(
        _("unit price with compensation"),
        help_text=_('last known price (/piece or /kg), compensation included'),
        default=0, max_digits=8, decimal_places=2)
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("vat or compensation"))

    customer_minimum_order_quantity = models.DecimalField(
        _("customer_minimum_order_quantity"),
        help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
        default=0, max_digits=6, decimal_places=3)
    customer_increment_order_quantity = models.DecimalField(
        _("customer_increment_order_quantity"),
        help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50max 1 piece, 3 Kg)'),
        default=0, max_digits=6, decimal_places=3)
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=0, max_digits=6, decimal_places=3)

    permanences = models.ManyToManyField(
        'Permanence', through='OfferItem', null=True, blank=True)
    is_into_offer = models.BooleanField(_("is_into_offer"))

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_LOOSE_PC,
        verbose_name=_("order unit"))

    is_active = models.BooleanField(_("is_active"), default=True)
    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True, blank=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, blank=True)

    def natural_key(self):
        return self.long_name + self.producer.natural_key()

    natural_key.dependencies = ['repanier.producer']

    def __unicode__(self):
        return u'%s, %s' % (self.producer.short_profile_name, self.long_name)

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ("producer", "long_name",)
        unique_together = ("producer", "department_for_customer", "long_name",)
        index_together = [
            ["id"],
            ["producer", "department_for_customer", "long_name"],
        ]


@receiver(pre_save, sender=Product)
def product_pre_save(sender, **kwargs):
    product = kwargs['instance']
    if not product.is_active:
        product.is_into_offer = False
    # Calculate compensation when "regime agricole"
    product.unit_price_with_vat = (product.original_unit_price * product.producer.price_list_multiplier).quantize(
        TWO_DECIMALS)
    product.unit_price_with_compensation = product.unit_price_with_vat
    if product.vat_level == VAT_200:
        product.unit_price_with_compensation = (product.unit_price_with_vat * DECIMAL_1_02).quantize(TWO_DECIMALS)
    elif product.vat_level == VAT_300:
        product.unit_price_with_compensation = (product.unit_price_with_vat * DECIMAL_1_06).quantize(TWO_DECIMALS)

    if product.customer_minimum_order_quantity <= 0:
        product.customer_minimum_order_quantity = 1
    if product.customer_increment_order_quantity <= 0:
        product.customer_increment_order_quantity = 1
    if product.customer_alert_order_quantity <= product.customer_minimum_order_quantity:
        product.customer_alert_order_quantity = product.customer_minimum_order_quantity
    if product.order_average_weight <= 0:
        product.order_average_weight = 1


class Permanence(models.Model):
    short_name = models.CharField(_("short_name"), max_length=40, blank=True)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))
    distribution_date = models.DateField(_("distribution_date"), db_index=True)
    offer_description = HTMLField(_("offer_description"),
                                  help_text=_(
                                      "This message is send by mail to all customers when opening the order or on top "
                                      "of the web order screen."),
                                  blank=True)
    invoice_description = HTMLField(
        _("invoice_description"),
        help_text=_(
            'This message is send by mail to all customers having bought something when closing the permanence.'),
        blank=True)
    producers = models.ManyToManyField(
        'Producer', null=True, blank=True,
        verbose_name=_("producers"))

    automatically_closed = models.BooleanField(
        _("automatically_closed"), default=False)

    is_done_on = models.DateTimeField(
        _("is_done_on"), blank=True, null=True)

    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)

    def natural_key(self):
        return self.distribution_date, self.short_name

    def get_producers(self):
        if self.id:
            if self.status == PERMANENCE_PLANNED:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_product_changelist',
                )
                return u", ".join([u'<a href="' + changelist_url + \
                                   '?producer=' + str(p.id) + '" target="_blank" class="addlink">&nbsp;' + \
                                   p.short_profile_name + '</a>' for p in self.producers.all()])
            else:
                # change_url = urlresolvers.reverse(
                # 'admin:repanier_permanenceinpreparation_change',
                # args=(self.id,)
                # )
                return u", ".join([
                    p.short_profile_name + '</a>' for p in self.producers.all()
                ])
        return u''

    get_producers.short_description = (_("producers in this permanence"))
    get_producers.allow_tags = True

    def get_customers(self):
        if self.id:
            changelist_url = urlresolvers.reverse(
                'admin:repanier_purchase_changelist',
            )
            return u", ".join([u'<a href="' + changelist_url + \
                               '?permanence=' + str(self.id) + \
                               '&customer=' + str(c.id) + '" target="_blank"  class="addlink">&nbsp;' + \
                               c.short_basket_name + '</a>'
                               for c in Customer.objects.filter(purchase__permanence_id=self.id).distinct()])
        return u''

    get_customers.short_description = (_("customers in this permanence"))
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
                    r = permanenceboard.permanence_role
                    if r:
                        r_url = urlresolvers.reverse(
                            'admin:repanier_lut_permanencerole_change',
                            args=(r.id,)
                        )
                        r_link = '<a href="' + r_url + \
                                 '" target="_blank">' + r.short_name + '</a>'
                    c_link = ''
                    c = permanenceboard.customer
                    if c:
                        c_url = urlresolvers.reverse(
                            'admin:repanier_customer_change',
                            args=(c.id,)
                        )
                        c_link = ' -> <a href="' + c_url + \
                                 '" target="_blank">' + c.short_basket_name + '</a>'
                    if not (first_board):
                        board += '<br/>'
                    board += r_link + c_link
                    first_board = False
        return board

    get_board.short_description = (_("permanence board"))
    get_board.allow_tags = True

    def __unicode__(self):
        if not self.short_name:
            return unicode(_("Permanence on ")) + u'%s' % (self.distribution_date.strftime('%d-%m-%Y'))
        else:
            return unicode(_("Permanence on ")) + u'%s (%s)' % (
                self.distribution_date.strftime('%d-%m-%Y'), self.short_name)

    class Meta:
        verbose_name = _("permanence")
        verbose_name_plural = _("permanences")
        unique_together = ("distribution_date", "short_name",)
        index_together = [
            ["distribution_date", "short_name"],
        ]


class PermanenceBoard(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
    # Distribution_date duplicated to quickly calculte # particpation of lasts 12 months
    distribution_date = models.DateField(_("distribution_date"), db_index=True)
    permanence_role = models.ForeignKey(
        LUT_PermanenceRole, verbose_name=_("permanence_role"),
        on_delete=models.PROTECT)

    class Meta:
        verbose_name = _("permanence board")
        verbose_name_plural = _("permanences board")
        ordering = ("permanence", "permanence_role", "customer",)
        unique_together = ("permanence", "permanence_role", "customer",)
        index_together = [
            ["permanence", "permanence_role", "customer"],
            ["distribution_date", "permanence", "permanence_role"],
        ]


@receiver(pre_save, sender=PermanenceBoard)
def permanence_board_pre_save(sender, **kwargs):
    permanence_board = kwargs['instance']
    permanence_board.distribution_date = permanence_board.permanence.distribution_date


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("permanence in preparation")
        verbose_name_plural = _("permanences in preparation")


@receiver(post_save, sender=PermanenceInPreparation)
def permanence_post_save(sender, **kwargs):
    permanence = kwargs['instance']
    created = kwargs['created']
    if permanence.id is not None and created:
        lut_permanence_role_set = LUT_PermanenceRole.objects.filter(is_active=True, automatically_added=True)
        for lut_permanence_role in lut_permanence_role_set:
            PermanenceBoard.objects.create(
                permanence=permanence,
                permanence_role=lut_permanence_role
            )


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("permanence done")
        verbose_name_plural = _("permanences done")


class OfferItem(models.Model):
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT)
    product = models.ForeignKey(
        Product, verbose_name=_("product"), on_delete=models.PROTECT)
    is_active = models.BooleanField(_("is_active"), default=True)
    limit_to_alert_order_quantity = models.BooleanField(_("limit maximum order qty to alert qty"), default=False)
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=0, max_digits=6, decimal_places=3)

    def get_producer(self):
        if self.id:
            return self.product.producer.short_profile_name
        return "N/A"

    get_producer.short_description = (_("producers"))
    get_producer.allow_tags = False

    def get_product(self):
        if self.id:
            return self.product.long_name
        return "N/A"

    get_product.short_description = (_("products"))
    get_product.allow_tags = False

    # def get_total_order_quantity(self):
    # total_order_quantity = 0
    # if self.id:
    # if self.permanence.status<=PERMANENCE_PLANNED:
    # pass
    # elif self.permanence.status <= PERMANENCE_SEND:
    # result_set = Purchase.objects.filter(
    # product_id=self.product.id, permanence_id=self.permanence_id).values(
    #         'product_id', 'permanence_id').annotate(
    #         total_order_quantity=Sum('order_quantity')).values(
    #         'total_order_quantity').order_by()[:1]
    #       if result_set:
    #         total_order_quantity = result_set[0].get('total_order_quantity')
    #       if total_order_quantity == None:
    #         total_order_quantity = 0
    #     else:
    #       result_set = Purchase.objects.filter(
    #         product_id=self.product.id, permanence_id=self.permanence_id).values(
    #         'product_id', 'permanence_id').annotate(
    #         total_order_quantity=Sum('prepared_quantity')).values(
    #         'total_order_quantity').order_by()[:1]
    #       if result_set:
    #         total_order_quantity = result_set[0].get('total_order_quantity')
    #       if total_order_quantity == None:
    #         total_order_quantity = 0
    #   return total_order_quantity

    # get_total_order_quantity.short_description=(_("total order quantity"))
    # get_total_order_quantity.allow_tags = False

    def __unicode__(self):
        return u'%s, %s' % (self.permanence.__unicode__(), self.product.__unicode__())

    class Meta:
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")
        ordering = ("permanence", "product",)
        unique_together = ("permanence", "product",)
        index_together = [
            ["permanence", "product"],
        ]


class CustomerInvoice(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = models.DecimalField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=0)
    total_price_with_tax = models.DecimalField(
        _("Total price"),
        help_text=_('Total price vat or compensation if applicable included'),
        default=0, max_digits=8, decimal_places=2)
    total_vat = models.DecimalField(
        _("Total vat"),
        help_text=_('Vat part of the total price'),
        default=0, max_digits=9, decimal_places=3)
    total_compensation = models.DecimalField(
        _("Total compensation"),
        help_text=_('Compensation part of the total price'),
        default=0, max_digits=9, decimal_places=3)
    total_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=0, max_digits=8, decimal_places=2)
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=0)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=0)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"),
        max_digits=8, decimal_places=2, default=0)

    def __unicode__(self):
        return u'%s, %s' % (self.customer.__unicode__(), self.permanence.__unicode__())

    class Meta:
        verbose_name = _("customer invoice")
        verbose_name_plural = _("customers invoices")
        unique_together = ("permanence", "customer",)
        index_together = [
            ["permanence", "customer", ]
        ]


class ProducerInvoice(models.Model):
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"), on_delete=models.PROTECT, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = models.DecimalField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=0)
    total_price_with_tax = models.DecimalField(
        _("Total price"),
        help_text=_('Total price vat or compensation if applicable included'),
        default=0, max_digits=8, decimal_places=2)
    total_vat = models.DecimalField(
        _("Total vat"),
        help_text=_('Vat part of the total price'),
        default=0, max_digits=9, decimal_places=3)
    total_compensation = models.DecimalField(
        _("Total compensation"),
        help_text=_('Compensation part of the total price'),
        default=0, max_digits=9, decimal_places=3)
    total_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=0, max_digits=8, decimal_places=2)
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=0)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=0)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"),
        max_digits=8, decimal_places=2, default=0)

    def __unicode__(self):
        return u'%s, %s' % (self.producer.__unicode__(), self.permanence.__unicode__())

    class Meta:
        verbose_name = _("producer invoice")
        verbose_name_plural = _("producers invoices")
        unique_together = ("permanence", "producer",)
        index_together = [
            ["permanence", "producer", ]
        ]


class Purchase(models.Model):
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"),
        on_delete=models.PROTECT)
    distribution_date = models.DateField(_("distribution_date"))
    product = models.ForeignKey(
        Product, verbose_name=_("product"), blank=True, null=True, on_delete=models.PROTECT)
    department_for_customer = models.ForeignKey(
        LUT_DepartmentForCustomer,
        verbose_name=_("department_for_customer"), blank=True, null=True, on_delete=models.PROTECT)
    offer_item = models.ForeignKey(
        OfferItem, verbose_name=_("offer_item"), blank=True, null=True, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"), blank=True, null=True, on_delete=models.PROTECT)
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT,
        db_index=True)

    quantity = models.DecimalField(
        _("order quantity"),
        max_digits=9, decimal_places=4, default=0)
    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=0, max_digits=6, decimal_places=3)
    quantity_send_to_producer = models.DecimalField(
        _("quantity send to producer"),
        max_digits=9, decimal_places=3, default=0)
    # 0 if this is not a KG product -> the preparation list for this product will be produced by familly
    # qty if not -> the preparation list for this product will be produced by qty then by familly
    quantity_for_preparation_order = models.DecimalField(
        _("preparation order quantity"),
        max_digits=9, decimal_places=4, default=0)
    long_name = models.CharField(_("long_name"), max_length=100,
                                 default='', blank=True, null=True)
    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_LOOSE_PC,
        verbose_name=_("order unit"))
    original_unit_price = models.DecimalField(
        _("original unit price"),
        help_text=_('last known price (/piece or /kg) from the producer price list'),
        default=0, max_digits=8, decimal_places=2)
    unit_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=0, max_digits=8, decimal_places=2)
    original_price = models.DecimalField(
        _("original row price"),
        help_text=_('total from last known price (/piece or /kg) of the producer price list'),
        default=0, max_digits=8, decimal_places=2)
    price_with_vat = models.DecimalField(
        _("total price with tva"),
        help_text=_('total vat included'),
        default=0, max_digits=8, decimal_places=2)
    price_with_compensation = models.DecimalField(
        _("total price with compensation"),
        help_text=_('total compensation included'),
        default=0, max_digits=8, decimal_places=2)

    invoiced_price_with_compensation = models.BooleanField(
        _("Set if the invoiced price is the price with compensation, otherwise it's the price with vat"), default=True)
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("vat or compensation"),
        help_text=_(
            'When the vendor is in agricultural regime select the correct compensation %. '
            'In the other cases select the correct vat %'))

    comment = models.CharField(
        _("comment"), max_length=100, default='', blank=True, null=True)
    is_recorded_on_customer_invoice = models.ForeignKey(
        CustomerInvoice, verbose_name=_("customer invoice"),
        on_delete=models.PROTECT, blank=True, null=True,
        db_index=True)
    is_recorded_on_producer_invoice = models.ForeignKey(
        ProducerInvoice, verbose_name=_("producer invoice"),
        on_delete=models.PROTECT, blank=True, null=True,
        db_index=True)
    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)

    @property
    def quantity_deposit(self):
        self._quantity_deposit = DECIMAL_ZERO
        if self.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC, PRODUCT_ORDER_UNIT_NAMED_PC]:
            self._quantity_deposit = self.quantity
        elif self.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_BT_LT, PRODUCT_ORDER_UNIT_NAMED_LT]:
            if self.permanence.status < PERMANENCE_SEND:
                self._quantity_deposit = self.quantity
            else:
                self._quantity_deposit = (self.quantity / self.order_average_weight).quantize(ZERO_DECIMAL)
        return self._quantity_deposit

    @property
    def real_unit_price(self):
        final_price = self.price_with_vat
        if self.invoiced_price_with_compensation:
            final_price = self.price_with_compensation
        final_price -= self.quantity * self.unit_deposit
        if self.quantity == DECIMAL_ZERO:
            return final_price.quantize(TWO_DECIMALS)
        else:
            return (final_price / self.quantity).quantize(TWO_DECIMALS)

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
    total_price_with_tax = models.DecimalField(
        _("Total price"),
        help_text=_('Total price vat or compensation if applicable included'),
        default=0, max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = _("customer order")
        verbose_name_plural = _("customers orders")
        index_together = [
            ["permanence", "customer"],
        ]


class BankAccount(models.Model):
    permanence = models.ForeignKey(
        Permanence, verbose_name=_("permanence"),
        on_delete=models.PROTECT, blank=True, null=True)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"),
        on_delete=models.PROTECT, blank=True, null=True)
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT, blank=True, null=True)
    operation_date = models.DateField(_("operation_date"),
                                      db_index=True)
    operation_comment = models.CharField(
        _("operation_comment"), max_length=100, null=True, blank=True)
    operation_status = models.CharField(
        max_length=3,
        choices=LUT_BANK_TOTAL,
        default=BANK_NOT_LATEST_TOTAL,
        verbose_name=_("Bank balance status"),
    )
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=0)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=0)
    is_recorded_on_customer_invoice = models.ForeignKey(
        CustomerInvoice, verbose_name=_("customer invoice"),
        on_delete=models.PROTECT, blank=True, null=True,
        db_index=True)
    is_recorded_on_producer_invoice = models.ForeignKey(
        ProducerInvoice, verbose_name=_("producer invoice"),
        on_delete=models.PROTECT, blank=True, null=True,
        db_index=True)
    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)

    def get_bank_amount_in(self):
        if self.id:
            if self.bank_amount_in != 0:
                return self.bank_amount_in
            else:
                return ""
        return "N/A"

    get_bank_amount_in.short_description = (_("bank_amount_in"))
    get_bank_amount_in.allow_tags = False

    def get_bank_amount_out(self):
        if self.id:
            if self.bank_amount_out != 0:
                return self.bank_amount_out
            else:
                return ""
        return "N/A"

    get_bank_amount_out.short_description = (_("bank_amount_out"))
    get_bank_amount_out.allow_tags = False

    def get_producer(self):
        if self.id:
            if self.producer:
                return self.producer
            else:
                if self.customer == None:
                    # This is a total, show it
                    if self.operation_status == BANK_LATEST_TOTAL:
                        return "=============="
                    else:
                        return "--------------"
                return ""
        return "N/A"

    get_producer.short_description = (_("producer"))
    get_producer.allow_tags = False

    def get_customer(self):
        if self.id:
            if self.customer:
                return self.customer
            else:
                if self.producer == None:
                    # This is a total, show it
                    if self.operation_status == BANK_LATEST_TOTAL:
                        return "=============="
                    else:
                        return "--------------"
                return ""
        return "N/A"

    get_customer.short_description = (_("customers"))
    get_customer.allow_tags = False

    class Meta:
        verbose_name = _("bank account movement")
        verbose_name_plural = _("bank account movements")
        ordering = ('-operation_date', '-id')
        index_together = [
            ['operation_date', 'id'],
            ['is_recorded_on_customer_invoice', 'operation_date'],
            ['is_recorded_on_producer_invoice', 'operation_date'],
        ]


@receiver(pre_save, sender=BankAccount)
def bank_account_pre_save(sender, **kwargs):
    bank_account = kwargs['instance']
    if bank_account.producer is None and bank_account.customer is None:
        bank_account_set = BankAccount.objects.exclude(
            operation_status=BANK_NOT_LATEST_TOTAL).order_by()[:1]
        if not bank_account_set:
            bank_account.operation_status = BANK_LATEST_TOTAL