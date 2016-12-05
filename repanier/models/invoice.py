# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
import producer
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField


@python_2_unicode_compatible
class CustomerInvoice(models.Model):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("customer"),
        on_delete=models.PROTECT)
    customer_who_pays = models.ForeignKey(
        'Customer', verbose_name=_("customer"), related_name='invoices_paid', blank=True, null=True,
        on_delete=models.PROTECT, db_index=True)

    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, db_index=True)
    delivery = models.ForeignKey(
        'DeliveryBoard', verbose_name=_("delivery board"),
        null=True, blank=True, default=None,
        on_delete=models.PROTECT)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("invoice_status"))

    # IMPORTANT: default = True -> for the order form, to display nothing at the begin of the order
    # is_order_confirm_send and total_price_with_tax = 0 --> display nothing
    # otherwise display
    # - send a mail with the order to me
    # - confirm the order (if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS) and send a mail with the order to me
    # - mail send to XYZ
    # - order confirmed (if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS) and mail send to XYZ
    is_order_confirm_send = models.BooleanField(_("is_order_confirm_send"), choices=LUT_CONFIRM, default=False)
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = ModelMoneyField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # Calculated with Purchase
    total_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    # total_compensation = ModelMoneyField(
    #     _("Total compensation"),
    #     help_text=_('Compensation part of the total purchased'),
    #     default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('purchase to add amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('vat to add'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    # delta_compensation = ModelMoneyField(
    #     _("Total compensation"),
    #     help_text=_('compensation to add'),
    #     default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_transport = ModelMoneyField(
        _("Delivery point transport"),
        help_text=_("transport to add"),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    # delta_deposit = ModelMoneyField(
    #     _("deposit"),
    #     help_text=_('deposit to add'),
    #     default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = ModelMoneyField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = ModelMoneyField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("balance"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    price_list_multiplier = models.DecimalField(
        _("Delivery point price list multiplier"),
        help_text=_("This multiplier is applied once for groups with entitled customer or at each customer invoice for open groups."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])
    transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        help_text=_("This amount is added once for groups with entitled customer or at each customer for open groups."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    min_transport = ModelMoneyField(
        _("Minium order amount for free shipping cost"),
        help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])

    def get_delta_price_with_tax(self):
        return self.delta_price_with_tax.amount

    def get_abs_delta_price_with_tax(self):
        return abs(self.delta_price_with_tax)

    def get_abs_delta_vat(self):
        return abs(self.delta_vat)

    def get_total_price_with_tax(self, customer_who_pays=False):
        if self.customer_id == self.customer_who_pays_id:
            return self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport
        else:
            if self.status < PERMANENCE_DONE or not customer_who_pays:
                return self.total_price_with_tax
            else:
                return self.customer_who_pays if self.total_price_with_tax != DECIMAL_ZERO else DECIMAL_ZERO

    def get_total_price_wo_tax(self):
        return self.get_total_price_with_tax() - self.get_total_tax()

    def get_total_tax(self):
        # round to 2 decimals
        return RepanierMoney(self.total_vat.amount + self.delta_vat.amount)

    @transaction.atomic
    def set_delivery(self, delivery):
        # May not use delivery_id because it won't reload customer_invoice.delivery
        from repanier.apps import REPANIER_SETTINGS_TRANSPORT, REPANIER_SETTINGS_MIN_TRANSPORT
        self.delivery = delivery
        if delivery is None:
            if self.permanence.with_delivery_point:
                delivery_point = self.customer.delivery_point
            else:
                delivery_point = None
        else:
            delivery_point = delivery.delivery_point

        if delivery_point is None:
            self.customer_who_pays = self.customer
            self.price_list_multiplier = DECIMAL_ONE
            self.transport = REPANIER_SETTINGS_TRANSPORT
            self.min_transport = REPANIER_SETTINGS_MIN_TRANSPORT
        else:
            customer_responsible = delivery_point.customer_responsible
            if customer_responsible is None:
                self.customer_who_pays = self.customer
                self.price_list_multiplier = delivery_point.price_list_multiplier
                self.transport = delivery_point.transport
                self.min_transport = delivery_point.min_transport
            else:
                self.customer_who_pays = customer_responsible
                self.price_list_multiplier = delivery_point.price_list_multiplier
                self.transport = REPANIER_MONEY_ZERO
                self.min_transport = REPANIER_MONEY_ZERO
                if self.customer_id != customer_responsible.id:
                    customer_invoice_who_pays = CustomerInvoice.objects.filter(
                        permanence_id=self.permanence_id,
                        customer_id=customer_responsible.id
                    ).order_by('?').first()
                    if customer_invoice_who_pays is None:
                        CustomerInvoice.objects.create(
                            permanence_id=self.permanence_id,
                            customer_id=customer_responsible.id,
                            status=self.status,
                            customer_who_pays_id=customer_responsible.id,
                            price_list_multiplier=delivery_point.price_list_multiplier,
                            transport=delivery_point.transport,
                            min_transport=delivery_point.min_transport,
                            is_order_confirm_send=True
                        )
                    else:
                        # TODO : May be removed after migration
                        customer_invoice_who_pays.price_list_multiplier = delivery_point.price_list_multiplier
                        customer_invoice_who_pays.transport = delivery_point.transport
                        customer_invoice_who_pays.min_transport = delivery_point.min_transport
                        customer_invoice_who_pays.is_order_confirm_send = True
                        customer_invoice_who_pays.save()
                        # EOF TODO

    @transaction.atomic
    def confirm_order(self):
        getcontext().rounding = ROUND_HALF_UP
        producer_invoice_buyinggroup = ProducerInvoice.objects.filter(
            producer__represent_this_buyinggroup=True,
            permanence_id=self.permanence_id,
        ).order_by('?').first()
        if producer_invoice_buyinggroup is not None:
            producer_invoice_buyinggroup.delta_price_with_tax.amount -= self.delta_price_with_tax.amount
            producer_invoice_buyinggroup.delta_vat.amount -= self.delta_vat.amount
            producer_invoice_buyinggroup.delta_transport.amount -= self.delta_transport.amount
        else:
            producer_buyinggroup = producer.Producer.objects.filter(
                represent_this_buyinggroup=True
            ).order_by('?').first()
            producer_invoice_buyinggroup = ProducerInvoice.objects.create(
                producer_id=producer_buyinggroup.id,
                permanence_id=self.permanence_id,
                status=self.permanence.status
            )

        if self.price_list_multiplier != DECIMAL_ONE:
            total_price_with_tax_wo_deposit = self.total_price_with_tax.amount - self.total_deposit.amount
            self.delta_price_with_tax.amount = -(
                total_price_with_tax_wo_deposit - (
                    total_price_with_tax_wo_deposit * self.price_list_multiplier
                ).quantize(TWO_DECIMALS)
            )
            self.delta_vat.amount = -(
                self.total_vat - (
                    self.total_vat.amount * self.price_list_multiplier
                ).quantize(FOUR_DECIMALS)
            )
        else:
            self.delta_price_with_tax.amount = DECIMAL_ZERO
            self.delta_vat.amount = DECIMAL_ZERO

        self.calculate_transport()

        delta = self.delta_price_with_tax.amount + self.delta_vat.amount + self.delta_transport.amount
        if delta != DECIMAL_ZERO:
            producer_invoice_buyinggroup.delta_price_with_tax.amount += self.delta_price_with_tax.amount
            producer_invoice_buyinggroup.delta_vat.amount += self.delta_vat.amount
            producer_invoice_buyinggroup.delta_transport.amount += self.delta_transport.amount

        producer_invoice_buyinggroup.save()

        self.is_order_confirm_send = True

    def calculate_transport(self):
        total_price_with_tax = self.total_price_with_tax + self.delta_price_with_tax
        if self.transport.amount != DECIMAL_ZERO \
                and total_price_with_tax != DECIMAL_ZERO:
            if self.min_transport.amount == DECIMAL_ZERO:
                self.delta_transport.amount = self.transport.amount
            elif total_price_with_tax < self.min_transport.amount:
                self.delta_transport.amount = min(
                    self.min_transport.amount - total_price_with_tax,
                    self.transport.amount
                )
        else:
            self.delta_transport.amount = DECIMAL_ZERO

    def cancel_confirm_order(self):
        self.is_order_confirm_send = False

        producer_invoice_buyinggroup = ProducerInvoice.objects.filter(
            producer__represent_this_buyinggroup=True,
            permanence_id=self.permanence_id,
        ).order_by('?').first()
        if producer_invoice_buyinggroup is None:
            producer_buyinggroup = producer.Producer.objects.filter(
                represent_this_buyinggroup=True
            ).order_by('?').first()
            producer_invoice_buyinggroup = ProducerInvoice.objects.create(
                producer_id=producer_buyinggroup.id,
                permanence_id=self.permanence_id,
                status=self.permanence.status
            )
        producer_invoice_buyinggroup.delta_price_with_tax.amount -= self.delta_price_with_tax.amount
        producer_invoice_buyinggroup.delta_vat.amount -= self.delta_vat.amount
        producer_invoice_buyinggroup.delta_transport.amount -= self.delta_transport.amount
        producer_invoice_buyinggroup.save()

        self.delta_price_with_tax.amount = DECIMAL_ZERO
        self.delta_vat.amount = DECIMAL_ZERO
        self.delta_transport = DECIMAL_ZERO

    def __str__(self):
        return '%s, %s' % (self.customer, self.permanence)

    class Meta:
        verbose_name = _("customer invoice")
        verbose_name_plural = _("customers invoices")
        unique_together = ("permanence", "customer",)


@python_2_unicode_compatible
class ProducerInvoice(models.Model):
    producer = models.ForeignKey(
        'Producer', verbose_name=_("producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, db_index=True)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("invoice_status"))
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = ModelMoneyField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # Calculated with Purchase
    total_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_profit_with_tax = ModelMoneyField(
        _("Total profit vat included"),
        help_text=_('Difference between purchase and selling price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_profit_vat = ModelMoneyField(
        _("Total profit vat"),
        help_text=_('Vat part of the profit'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = ModelMoneyField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = ModelMoneyField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("balance"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    delta_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('purchase to add amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_stock_with_tax = ModelMoneyField(
        _("Total stock"),
        help_text=_('stock taken amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('vat to add'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_stock_vat = ModelMoneyField(
        _("Total stock vat"),
        help_text=_('vat to add'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_transport = ModelMoneyField(
        _("Delivery point transport"),
        help_text=_("transport to add"),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    delta_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_stock_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    calculated_invoiced_balance = ModelMoneyField(
        _("calculated balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    to_be_paid = models.BooleanField(_("to be paid"), choices=LUT_CONFIRM, default=False)
    to_be_invoiced_balance = ModelMoneyField(
        _("balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    invoice_reference = models.CharField(
        _("invoice reference"), max_length=100, null=True, blank=True)

    def get_delta_price_with_tax(self):
        return self.delta_price_with_tax.amount

    def get_abs_delta_price_with_tax(self):
        return abs(self.delta_price_with_tax)

    def get_total_price_with_tax(self):
        return self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport + self.delta_stock_with_tax

    def get_total_vat(self):
        return self.total_vat + self.delta_stock_vat

    def get_total_deposit(self):
        return self.total_deposit + self.delta_stock_deposit

    def __str__(self):
        return '%s, %s' % (self.producer, self.permanence)

    class Meta:
        verbose_name = _("producer invoice")
        verbose_name_plural = _("producers invoices")
        unique_together = ("permanence", "producer",)


@python_2_unicode_compatible
class CustomerProducerInvoice(models.Model):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("customer"),
        on_delete=models.PROTECT)
    producer = models.ForeignKey(
        'Producer', verbose_name=_("producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT,
        db_index=True)
    # Calculated with Purchase
    total_purchase_with_tax = ModelMoneyField(
        _("producer amount invoiced"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase
    total_selling_with_tax = ModelMoneyField(
        _("customer amount invoiced"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_html_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return _("<b>%(price)s</b>") % {'price': self.total_purchase_with_tax}
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = (_("producer amount invoiced"))
    get_html_producer_price_purchased.allow_tags = True
    get_html_producer_price_purchased.admin_order_field = 'total_purchase_with_tax'

    def __str__(self):
        return '%s, %s' % (self.producer, self.customer)

    class Meta:
        verbose_name = _("customer x producer invoice")
        verbose_name_plural = _("customers x producers invoices")
        unique_together = ("permanence", "customer", "producer",)


@python_2_unicode_compatible
class CustomerSend(CustomerProducerInvoice):
    def __str__(self):
        return '%s, %s' % (self.producer, self.customer)

    class Meta:
        proxy = True
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
