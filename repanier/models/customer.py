# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.core import urlresolvers
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

import bankaccount
import invoice
import permanenceboard
import purchase
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.picture.const import SIZE_S
from repanier.picture.fields import AjaxPictureField


@python_2_unicode_compatible
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)

    short_basket_name = models.CharField(
        _("short_basket_name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_basket_name = models.CharField(
        _("long_basket_name"), max_length=100, null=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("secondary email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("language"))

    picture = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="customer", size=SIZE_S)
    phone1 = models.CharField(
        _("phone1"),
        max_length=25,
        null=True, blank=True, default=EMPTY_STRING)
    phone2 = models.CharField(
        _("phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    bank_account1 = models.CharField(_("main bank account"), max_length=100, null=True, blank=True,
                                     default=EMPTY_STRING)
    bank_account2 = models.CharField(_("secondary bank account"), max_length=100, null=True, blank=True,
                                     default=EMPTY_STRING)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(
        _("address"), null=True, blank=True, default=EMPTY_STRING)
    city = models.CharField(
        _("city"), max_length=50, null=True, blank=True, default=EMPTY_STRING)
    about_me = models.TextField(
        _("about me"), null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("memo"), null=True, blank=True, default=EMPTY_STRING)
    accept_mails_from_members = models.BooleanField(
        _("show my mail to other members"), default=False)
    accept_phone_call_from_members = models.BooleanField(
        _("show my phone to other members"), default=False)
    membership_fee_valid_until = models.DateField(
        _("membership fee valid until"),
        default=datetime.date.today
    )
    # If this customer is member of a closed group, the customer.price_list_multiplier is not used
    # Invoices are sent to the consumer responsible of the group who is
    # also responsible for collecting the payments.
    # The LUT_DeliveryPoint.price_list_multiplier will be used when invoicing the consumer responsible
    # At this stage, the link between the customer invoice and this customer responsible is made with
    # CustomerInvoice.customer_charged
    price_list_multiplier = models.DecimalField(
        _("Customer price list multiplier"),
        help_text=_("This multiplier is applied to each product ordered by this customer."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])

    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True, default=None)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # The initial balance is needed to compute the invoice control list
    initial_balance = ModelMoneyField(
        _("initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    delivery_point = models.ForeignKey(
        'LUT_DeliveryPoint',
        verbose_name=_("delivery point"),
        blank=True, null=True, default=None)
    is_active = models.BooleanField(_("is_active"), default=True)
    is_group = models.BooleanField(_("is a group"), default=False)
    may_order = models.BooleanField(_("may_order"), default=True)
    valid_email = models.NullBooleanField(_("valid_email"), default=None)
    subscribe_to_email = models.BooleanField(_("subscribe to email"), default=True)
    preparation_order = models.IntegerField(null=True, blank=True, default=0)

    def get_admin_date_balance(self):
        return timezone.now().date().strftime(settings.DJANGO_SETTINGS_DATE)

    get_admin_date_balance.short_description = (_("date_balance"))
    get_admin_date_balance.allow_tags = False

    def get_admin_date_joined(self):
        return self.user.date_joined.strftime(settings.DJANGO_SETTINGS_DATE)

    get_admin_date_joined.short_description = _("date joined")
    get_admin_date_joined.allow_tags = False

    def get_admin_balance(self):
        return self.balance + self.get_bank_not_invoiced() - self.get_order_not_invoiced()

    get_admin_balance.short_description = (_("balance"))
    get_admin_balance.allow_tags = False

    def get_order_not_invoiced(self):
        result_set = invoice.CustomerInvoice.objects.filter(
            customer_id=self.id,
            status__gte=PERMANENCE_OPENED,
            status__lte=PERMANENCE_SEND,
            customer_charged_id=self.id
        ).order_by('?').aggregate(Sum('total_price_with_tax'), Sum('delta_price_with_tax'), Sum('delta_transport'))
        if result_set["total_price_with_tax__sum"] is not None:
            order_not_invoiced = RepanierMoney(result_set["total_price_with_tax__sum"])
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        if result_set["delta_price_with_tax__sum"] is not None:
            order_not_invoiced += RepanierMoney(result_set["delta_price_with_tax__sum"])
        if result_set["delta_transport__sum"] is not None:
            order_not_invoiced += RepanierMoney(result_set["delta_transport__sum"])
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        result_set = bankaccount.BankAccount.objects.filter(
            customer_id=self.id, customer_invoice__isnull=True
        ).order_by('?').aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
        if result_set["bank_amount_in__sum"] is not None:
            bank_in = RepanierMoney(result_set["bank_amount_in__sum"])
        else:
            bank_in = REPANIER_MONEY_ZERO
        if result_set["bank_amount_out__sum"] is not None:
            bank_out = RepanierMoney(result_set["bank_amount_out__sum"])
        else:
            bank_out = REPANIER_MONEY_ZERO
        bank_not_invoiced = bank_in - bank_out
        return bank_not_invoiced

    def get_balance(self):
        last_customer_invoice = invoice.CustomerInvoice.objects.filter(
            customer_id=self.id, invoice_sort_order__isnull=False
        ).order_by('?')
        balance = self.get_admin_balance()
        if last_customer_invoice.exists():
            if balance.amount >= 30:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           '<span style="color:#32CD32">%s</span>' % (balance,)) + '</a>'
            elif balance.amount >= -10:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           '<span style="color:#696969">%s</span>' % (balance,)) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           '<span style="color:red">%s</span>' % (balance,)) + '</a>'
        else:
            if balance.amount >= 30:
                return '<span style="color:#32CD32">%s</span>' % (balance,)
            elif balance.amount >= -10:
                return '<span style="color:#696969">%s</span>' % (balance,)
            else:
                return '<span style="color:red">%s</span>' % (balance,)

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_last_membership_fee(self):
        last_membership_fee = purchase.Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE
        ).order_by("-id")
        if last_membership_fee.exists():
            return last_membership_fee.first().selling_price

    get_last_membership_fee.short_description = _("last membership fee")
    get_last_membership_fee.allow_tags = False

    def last_membership_fee_date(self):
        last_membership_fee = purchase.Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE
        ).order_by("-id").prefetch_related("customer_invoice")
        if last_membership_fee.exists():
            return last_membership_fee.first().customer_invoice.date_balance

    last_membership_fee_date.short_description = _("last membership fee date")
    last_membership_fee_date.allow_tags = False

    def get_last_membership_fee_date(self):
        # Format it for the admin
        # Don't format it form import/export
        last_membership_fee_date = self.last_membership_fee_date()
        if last_membership_fee_date is not None:
            return last_membership_fee_date.strftime(settings.DJANGO_SETTINGS_DATE)
        return EMPTY_STRING

    get_last_membership_fee_date.short_description = _("last membership fee date")
    get_last_membership_fee_date.allow_tags = False

    def get_participation(self):
        now = timezone.now()
        return permanenceboard.PermanenceBoard.objects.filter(
            customer_id=self.id,
            permanence_date__gte=now - datetime.timedelta(
                days=365),
            permanence_date__lt=now,
            permanence_role__is_counted_as_participation=True
        ).order_by('?').count()

    get_participation.short_description = _("participation")
    get_participation.allow_tags = False

    def get_purchase(self):
        now = timezone.now()
        return invoice.CustomerInvoice.objects.filter(
            customer_id=self.id,
            total_price_with_tax__gt=DECIMAL_ZERO,
            date_balance__gte=now - datetime.timedelta(365)
        ).count()

    get_purchase.short_description = _("purchase")
    get_purchase.allow_tags = False

    @property
    def who_is_who_display(self):
        return self.picture or self.accept_mails_from_members or self.accept_phone_call_from_members \
               or (self.about_me is not None and len(self.about_me.strip()) > 1)

    def __str__(self):
        return self.short_basket_name

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        ordering = ("short_basket_name",)
        index_together = [
            ["user", "is_active", "may_order"],
        ]


@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, **kwargs):
    customer = kwargs["instance"]
    if customer.represent_this_buyinggroup:
        # The buying group may not be de activated
        customer.is_active = True
        customer.is_group = False
    if customer.email2 is not None:
        customer.email2 = customer.email2.lower()
    if customer.vat_id is not None and len(customer.vat_id.strip()) == 0:
        customer.vat_id = None
    if customer.bank_account1 is not None and len(customer.bank_account1.strip()) == 0:
        customer.bank_account1 = None
    if customer.bank_account1:
        # Prohibit to have two customers with same bank account
        other_bank_account1 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account1) | Q(bank_account2=customer.bank_account1)
        ).order_by("?")
        if customer.id is not None:
            other_bank_account1 = other_bank_account1.exclude(id=customer.id)
        if other_bank_account1.exists():
            customer.bank_account1 = None
    if customer.bank_account2 is not None and len(customer.bank_account2.strip()) == 0:
        customer.bank_account2 = None
    if customer.bank_account2:
        # Prohibit to have two customers with same bank account
        other_bank_account2 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account2) | Q(bank_account2=customer.bank_account2)
        ).order_by("?")
        if customer.id is not None:
            other_bank_account2 = other_bank_account2.exclude(id=customer.id)
        if other_bank_account2.exists():
            customer.bank_account2 = None
    if not customer.is_active:
        customer.may_order = False
    if customer.is_group:
        customer.may_order = False
        customer.delivery_point = None
    if customer.price_list_multiplier <= DECIMAL_ZERO:
        customer.price_list_multiplier = DECIMAL_ONE
    if customer.delivery_point is not None and customer.delivery_point.customer_responsible is not None:
        # If the customer is member of a closed group with a customer_responsible, the customer.price_list_multiplier must be set to ONE
        customer.price_list_multiplier = DECIMAL_ONE
    customer.city = ("%s" % customer.city).upper()
    customer.login_attempt_counter = DECIMAL_ZERO
    customer.valid_email = None


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs["instance"]
    user = customer.user
    user.delete()
