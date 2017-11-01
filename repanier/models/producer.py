# -*- coding: utf-8

import datetime
import uuid

from django.conf import settings
from django.core import urlresolvers
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import ProducerInvoice
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.product import Product
from repanier.picture.const import SIZE_L
from repanier.picture.fields import AjaxPictureField
from repanier.tools import update_offer_item


class Producer(models.Model):
    short_profile_name = models.CharField(
        _("Short name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_profile_name = models.CharField(
        _("Long name"), max_length=100, null=True, default=EMPTY_STRING)
    email = models.EmailField(
        _("Email"), null=True, blank=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("Secondary email"), null=True, blank=True, default=EMPTY_STRING)
    email3 = models.EmailField(
        _("Secondary email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("Language"))
    picture = AjaxPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="producer", size=SIZE_L)
    phone1 = models.CharField(
        _("Phone1"),
        max_length=25,
        null=True, blank=True, default=EMPTY_STRING)
    phone2 = models.CharField(
        _("Phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    bank_account = models.CharField(_("Bank account"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    vat_id = models.CharField(
        _("VAT id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    fax = models.CharField(
        _("Fax"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(_("Address"), null=True, blank=True, default=EMPTY_STRING)
    city = models.CharField(
        _("City"), max_length=50, null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("Memo"), null=True, blank=True, default=EMPTY_STRING)
    reference_site = models.URLField(
        _("Reference site"), null=True, blank=True, default=EMPTY_STRING)
    web_services_activated = models.BooleanField(_('Web services activated'), default=False)
    # uuid used to access to producer invoices without login
    uuid = models.CharField(
        "uuid", max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_uuid = models.CharField(
        "uuid", max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_filled = models.BooleanField(_("Offer filled"), default=False)
    invoice_by_basket = models.BooleanField(_("Invoice by basket"), default=False)
    manage_replenishment = models.BooleanField(_("Manage replenishment"), default=False)
    producer_pre_opening = models.BooleanField(_("Pre-open the orders"), default=False)
    producer_price_are_wo_vat = models.BooleanField(_("Producer price are wo vat"), default=False)
    sort_products_by_reference = models.BooleanField(_("Sort products by reference"), default=False)

    price_list_multiplier = models.DecimalField(
        _("Price list multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])
    is_resale_price_fixed = models.BooleanField(_("The resale price is set by the producer"),
                                                default=False)
    minimum_order_value = ModelMoneyField(
        _("Minimum order value"),
        help_text=_("0 mean : no minimum order value."),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)])

    date_balance = models.DateField(
        _("Date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    initial_balance = ModelMoneyField(
        _("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("Represent this buyinggroup"), default=False)
    is_active = models.BooleanField(_("Active"), default=True)

    def get_negative_balance(self):
        return - self.balance

    def get_products(self):
        # This producer may have product's list
        if self.is_active:
            changeproductslist_url = urlresolvers.reverse(
                'admin:repanier_product_changelist',
            )
            link = "<a href=\"{}?is_active__exact=1&producer={}\" class=\"btn addlink\">&nbsp;{}</a>".format(
                changeproductslist_url, str(self.id), _("Products"))
            return link
        return EMPTY_STRING

    get_products.short_description = (_("Link to his products"))
    get_products.allow_tags = True

    def get_admin_date_balance(self):
        if self.id is not None:
            bank_account = BankAccount.objects.filter(
                producer_id=self.id, producer_invoice__isnull=True
            ).order_by("-operation_date").only("operation_date").first()
            if bank_account is not None:
                return bank_account.operation_date
            return self.date_balance
        else:
            return timezone.now().date()

    get_admin_date_balance.short_description = (_("Date_balance"))
    get_admin_date_balance.allow_tags = False

    def get_admin_balance(self):
        if self.id is not None:
            return self.balance - self.get_bank_not_invoiced() + self.get_order_not_invoiced()
        else:
            return REPANIER_MONEY_ZERO

    get_admin_balance.short_description = (_("Balance"))
    get_admin_balance.allow_tags = False

    def get_order_not_invoiced(self):
        from repanier.apps import REPANIER_SETTINGS_INVOICE
        if REPANIER_SETTINGS_INVOICE:
            result_set = ProducerInvoice.objects.filter(
                producer_id=self.id,
                status__gte=PERMANENCE_OPENED,
                status__lte=PERMANENCE_SEND
            ).order_by('?').aggregate(Sum('total_price_with_tax'), Sum('delta_price_with_tax'), Sum('delta_transport'))
            if result_set["total_price_with_tax__sum"] is not None:
                order_not_invoiced = RepanierMoney(result_set["total_price_with_tax__sum"])
            else:
                order_not_invoiced = REPANIER_MONEY_ZERO
            if result_set["delta_price_with_tax__sum"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_price_with_tax__sum"])
            if result_set["delta_transport__sum"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_transport__sum"])
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        from repanier.apps import REPANIER_SETTINGS_INVOICE
        if REPANIER_SETTINGS_INVOICE:
            result_set = BankAccount.objects.filter(
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
            bank_not_invoiced = bank_in - bank_out
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO

        return bank_not_invoiced

    def get_calculated_invoiced_balance(self, permanence_id):
        bank_not_invoiced = self.get_bank_not_invoiced()
        # IMPORTANT : when is_resale_price_fixed=True then price_list_multiplier == 1
        # Do not take into account product whose order unit is >= PRODUCT_ORDER_UNIT_DEPOSIT
        result_set = OfferItemWoReceiver.objects.filter(
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
        result_set = OfferItemWoReceiver.objects.filter(
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
        calculated_invoiced_balance = self.balance - bank_not_invoiced + payment_needed
        if self.manage_replenishment:
            for offer_item in OfferItemWoReceiver.objects.filter(
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

    get_calculated_invoiced_balance.short_description = (_("Balance"))
    get_calculated_invoiced_balance.allow_tags = False

    def get_balance(self):
        last_producer_invoice_set = ProducerInvoice.objects.filter(
            producer_id=self.id, invoice_sort_order__isnull=False
        ).order_by('?')

        balance = self.get_admin_balance()
        if last_producer_invoice_set.exists():
            if balance.amount < 0:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:#298A08\">{}</span>".format(-balance)) + '</a>'
            elif balance.amount == 0:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:#32CD32\">{}</span>".format(-balance)) + '</a>'
            elif balance.amount > 30:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:red\">{}</span>".format(-balance)) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:#696969\">{}</span>".format(-balance)) + '</a>'
        else:
            if balance.amount < 0:
                return "<span style=\"color:#298A08\">{}</span>".format(-balance)
            elif balance.amount == 0:
                return "<span style=\"color:#32CD32\">{}</span>".format(-balance)
            elif balance.amount > 30:
                return "<span style=\"color:red\">{}</span>".format(-balance)
            else:
                return "<span style=\"color:#696969\">{}</span>".format(-balance)

    get_balance.short_description = _("Balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_last_invoice(self):
        producer_last_invoice = ProducerInvoice.objects.filter(
            producer_id=self.id, invoice_sort_order__isnull=False
        ).order_by("-id").first()
        if producer_last_invoice is not None:
            if producer_last_invoice.total_price_with_tax < DECIMAL_ZERO:
                return "<span style=\"color:#298A08\">{}</span>".format(
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax == DECIMAL_ZERO:
                return "<span style=\"color:#32CD32\">{}</span>".format(
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax > 30:
                return "<span style=\"color:red\">{}</span>".format(
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            else:
                return "<span style=\"color:#696969\">{}</span>".format(
                    number_format(producer_last_invoice.total_price_with_tax, 2))
        else:
            return "<span style=\"color:#32CD32\">{}</span>".format(number_format(0, 2))

    get_last_invoice.short_description = _("Last invoice")
    get_last_invoice.allow_tags = True

    def get_on_hold_movement_json(self, to_json):
        bank_not_invoiced = self.get_bank_not_invoiced()
        order_not_invoiced = self.get_order_not_invoiced()

        if order_not_invoiced.amount != DECIMAL_ZERO or bank_not_invoiced.amount != DECIMAL_ZERO:
            if order_not_invoiced.amount != DECIMAL_ZERO:
                if bank_not_invoiced.amount == DECIMAL_ZERO:
                    producer_on_hold_movement = \
                        _('This balance does not take account of any unbilled sales %(other_order)s.') % {
                            'other_order': order_not_invoiced
                        }
                else:
                    producer_on_hold_movement = \
                        _(
                            'This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s.') \
                        % {
                            'bank'       : bank_not_invoiced,
                            'other_order': order_not_invoiced
                        }
            else:
                producer_on_hold_movement = \
                    _(
                        'This balance does not take account of any unrecognized payments %(bank)s.') % {
                        'bank': bank_not_invoiced
                    }
            option_dict = {'id': "#basket_message", 'html': mark_safe(producer_on_hold_movement)}
            to_json.append(option_dict)

        return

    def __str__(self):
        if self.producer_price_are_wo_vat:
            return "{} {}".format(self.short_profile_name, _("wo tax"))
        return self.short_profile_name

    class Meta:
        verbose_name = _("Producer")
        verbose_name_plural = _("Producers")
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
        # Used to make difference between the stock of the group and the stock of the producer
        producer.manage_replenishment = False
        producer.is_resale_price_fixed = False
    elif producer.manage_replenishment:
        # Needed to compute ProducerInvoice.total_price_with_tax
        producer.invoice_by_basket = False
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE
    if not producer.uuid:
        producer.uuid = uuid.uuid1()
    if producer.bank_account is not None and len(producer.bank_account.strip()) == 0:
        producer.bank_account = None

@receiver(post_save, sender=Producer)
def producer_post_save(sender, **kwargs):
    producer = kwargs["instance"]
    for a_product in Product.objects.filter(producer_id=producer.id).order_by('?'):
        a_product.save()
    update_offer_item(producer_id=producer.id)
