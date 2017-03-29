# -*- coding: utf-8
from __future__ import unicode_literals

import datetime
import uuid

from django.conf import settings
from django.core import urlresolvers
# from django.core.validators import MinLengthValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.formats import number_format
from django.utils.translation import ugettext_lazy as _

import bankaccount
import invoice
import offeritem
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney


@python_2_unicode_compatible
class Producer(models.Model):
    short_profile_name = models.CharField(
        _("short_profile_name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_profile_name = models.CharField(
        _("long_profile_name"), max_length=100, null=True, default=EMPTY_STRING)
    email = models.EmailField(
        _("email"), null=True, blank=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("secondary email"), null=True, blank=True, default=EMPTY_STRING)
    email3 = models.EmailField(
        _("secondary email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("language"))
    phone1 = models.CharField(
        _("phone1"),
        max_length=25,
        null=True, blank=True, default=EMPTY_STRING)
    phone2 = models.CharField(
        _("phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    bank_account = models.CharField(_("bank account"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    fax = models.CharField(
        _("fax"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(_("address"), null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("memo"), null=True, blank=True, default=EMPTY_STRING)
    reference_site = models.URLField(
        _("reference site"), null=True, blank=True, default=EMPTY_STRING)
    web_services_activated = models.BooleanField(_('Web services activated'), default=False)
    # uuid used to access to producer invoices without login
    uuid = models.CharField(
        _("uuid"), max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_uuid = models.CharField(
        _("uuid"), max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_filled = models.BooleanField(_("offer filled"), default=False)
    invoice_by_basket = models.BooleanField(_("invoice by basket"), default=False)
    manage_replenishment = models.BooleanField(_("manage stock"), default=False)
    manage_production = models.BooleanField(_("manage production"), default=False)
    producer_pre_opening = models.BooleanField(_("producer pre-opening"), default=False)
    producer_price_are_wo_vat = models.BooleanField(_("producer price are wo vat"), default=False)
    sort_products_by_reference = models.BooleanField(_("sort products by reference"), default=False)
    to_be_paid = models.BooleanField(_("to be paid"), choices=LUT_BANK_NOTE, default=False)

    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])
    is_resale_price_fixed = models.BooleanField(_("the resale price is set by the producer"),
                                                default=False)
    minimum_order_value = ModelMoneyField(
        _("minimum order value"),
        help_text=_("0 mean : no minimum order value."),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)])

    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    initial_balance = ModelMoneyField(
        _("initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)

    def get_products(self):
        link = EMPTY_STRING
        if self.id:
            # This producer may have product's list
            changeproductslist_url = urlresolvers.reverse(
                'admin:repanier_product_changelist',
            )
            link = '<a href="%s?is_active__exact=1&producer=%s" class="addlink">&nbsp;%s</a>' \
                   % (changeproductslist_url, str(self.id), _("his_products"))
        return link

    get_products.short_description = (_("link to his products"))
    get_products.allow_tags = True

    def get_admin_date_balance(self):
        if self.id is not None:
            bank_account = bankaccount.BankAccount.objects.filter(
                producer_id=self.id, producer_invoice__isnull=True
            ).order_by("-operation_date").only("operation_date").first()
            if bank_account is not None:
                return bank_account.operation_date
            return self.date_balance
        else:
            return timezone.now().date()

    get_admin_date_balance.short_description = (_("date_balance"))
    get_admin_date_balance.allow_tags = False

    def get_admin_balance(self):
        if self.id is not None:
            result_set = bankaccount.BankAccount.objects.filter(
                producer_id=self.id, producer_invoice__isnull=True
            ).order_by('?').aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
            if result_set["bank_amount_in__sum"] is not None:
                bank_in = RepanierMoney(result_set["bank_amount_in__sum"])
            else:
                bank_in = REPANIER_MONEY_ZERO
            if result_set["bank_amount_out__sum"] is not None:
                bank_out = RepanierMoney(result_set["bank_amount_out__sum"])
            else:
                bank_out = REPANIER_MONEY_ZERO
            bank_not_invoiced = bank_out - bank_in
            result_set = invoice.ProducerInvoice.objects.filter(
                producer_id=self.id,
                status=PERMANENCE_SEND
            ).order_by('?').aggregate(Sum('total_price_with_tax'))
            if result_set["total_price_with_tax__sum"] is not None:
                payment_needed = RepanierMoney(result_set["total_price_with_tax__sum"])
            else:
                payment_needed = REPANIER_MONEY_ZERO
            return self.balance - bank_not_invoiced + payment_needed
        else:
            return REPANIER_MONEY_ZERO

    get_admin_balance.short_description = (_("balance"))
    get_admin_balance.allow_tags = False

    def get_calculated_invoiced_balance(self, permanence_id):
        # print('------------------ get_calculated_invoiced_balance')
        result_set = bankaccount.BankAccount.objects.filter(
            producer_id=self.id, producer_invoice__isnull=True, permanence__isnull=True
        ).order_by('?').aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
        if result_set["bank_amount_in__sum"] is not None:
            bank_in = RepanierMoney(result_set["bank_amount_in__sum"])
        else:
            bank_in = REPANIER_MONEY_ZERO
        # print("bank_in %f" % bank_in)
        if result_set["bank_amount_out__sum"] is not None:
            bank_out = RepanierMoney(result_set["bank_amount_out__sum"])
        else:
            bank_out = REPANIER_MONEY_ZERO
        # print("bank_out %f" % bank_out)
        bank_not_invoiced = bank_out - bank_in
        # print("bank_not_invoiced %f" % bank_not_invoiced)
        # IMPORTANT : when is_resale_price_fixed=True then price_list_multiplier == 1
        # Do not take into account product whose order unit is >= PRODUCT_ORDER_UNIT_DEPOSIT
        result_set = offeritem.OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer_id=self.id,
            price_list_multiplier__lt=1
        ).exclude(
            order_unit__gte=PRODUCT_ORDER_UNIT_DEPOSIT
        ).order_by('?').aggregate(
            Sum('total_selling_with_tax')
        )
        if result_set["total_selling_with_tax__sum"] is not None:
            payment_needed = result_set["total_selling_with_tax__sum"]
        else:
            payment_needed = DECIMAL_ZERO
        # print("payment_needed (1) %f" % payment_needed)
        result_set = offeritem.OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer_id=self.id,
            price_list_multiplier__gte=1,
        ).exclude(
            order_unit__gte=PRODUCT_ORDER_UNIT_DEPOSIT
        ).order_by('?').aggregate(
            Sum('total_purchase_with_tax'),
        )
        if result_set["total_purchase_with_tax__sum"] is not None:
            payment_needed += result_set["total_purchase_with_tax__sum"]
        # print("payment_needed (2) %f" % payment_needed)
        calculated_invoiced_balance = self.balance - bank_not_invoiced + payment_needed
        # print("calculated_invoiced_balance %f" % calculated_invoiced_balance)
        if self.manage_replenishment:
            for offer_item in offeritem.OfferItem.objects.filter(
                    is_active=True,
                    permanence_id=permanence_id,
                    producer_id=self.id,
                    manage_replenishment=True,
            ).order_by('?'):
                invoiced_qty, taken_from_stock, customer_qty = offer_item.get_producer_qty_stock_invoiced()
                if offer_item.price_list_multiplier < DECIMAL_ONE: # or offer_item.is_resale_price_fixed:
                    unit_price = offer_item.customer_unit_price.amount
                else:
                    unit_price = offer_item.producer_unit_price.amount
                if taken_from_stock > DECIMAL_ZERO:
                    delta_price_with_tax = (
                        (unit_price + offer_item.unit_deposit.amount)
                        * taken_from_stock
                    ).quantize(TWO_DECIMALS)
                    calculated_invoiced_balance -= delta_price_with_tax
        return calculated_invoiced_balance

    get_calculated_invoiced_balance.short_description = (_("balance"))
    get_calculated_invoiced_balance.allow_tags = False

    def get_balance(self):
        last_producer_invoice_set = invoice.ProducerInvoice.objects.filter(
            producer_id=self.id, invoice_sort_order__isnull=False
        ).order_by('?')
        balance = self.get_admin_balance()
        if last_producer_invoice_set.exists():
            if balance.amount < 0:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#298A08">%s</span>' % (balance,)) + '</a>'
            elif balance.amount == 0:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#32CD32">%s</span>' % (balance,)) + '</a>'
            elif balance.amount > 30:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:red">%s</span>' % (balance,)) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#696969">%s</span>' % (balance,)) + '</a>'
        else:
            if balance.amount < 0:
                return '<span style="color:#298A08">%s</span>' % (balance,)
            elif balance.amount == 0:
                return '<span style="color:#32CD32">%s</span>' % (balance,)
            elif balance.amount > 30:
                return '<span style="color:red">%s</span>' % (balance,)
            else:
                return '<span style="color:#696969">%s</span>' % (balance,)

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_last_invoice(self):
        producer_last_invoice = invoice.ProducerInvoice.objects.filter(producer_id=self.id).order_by("-id").first()
        if producer_last_invoice:
            if producer_last_invoice.total_price_with_tax < DECIMAL_ZERO:
                return '<span style="color:#298A08">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax == DECIMAL_ZERO:
                return '<span style="color:#32CD32">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax > 30:
                return '<span style="color:red">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            else:
                return '<span style="color:#696969">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
        else:
            return '<span style="color:#32CD32">%s</span>' % (number_format(0, 2))

    get_last_invoice.short_description = _("last invoice")
    get_last_invoice.allow_tags = True

    def __str__(self):
        if self.producer_price_are_wo_vat:
            return "%s %s" % (self.short_profile_name, _("wo tax"))
        return self.short_profile_name

    class Meta:
        verbose_name = _("producer")
        verbose_name_plural = _("producers")
        ordering = ("short_profile_name",)


@receiver(pre_save, sender=Producer)
def producer_pre_save(sender, **kwargs):
    producer = kwargs["instance"]
    if producer.represent_this_buyinggroup:
        # The buying group may not be de activated
        producer.is_active = True
    if producer.email:
        producer.email = producer.email.lower()
    if producer.email2:
        producer.email2 = producer.email2.lower()
    if producer.email3:
        producer.email3 = producer.email3.lower()
    if producer.producer_pre_opening:
        # Important to make difference between the stock of the group and the stock of the producer
        producer.manage_replenishment = False
        producer.manage_production = True
        producer.is_resale_price_fixed = False
    elif producer.manage_replenishment:
        # Important to compute ProducerInvoice.total_price_with_tax
        producer.invoice_by_basket = False
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE
    if not producer.uuid:
        producer.uuid = uuid.uuid4()
    if producer.bank_account is not None and len(producer.bank_account.strip()) == 0:
        producer.bank_account = None
