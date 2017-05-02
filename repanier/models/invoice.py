# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.db.models import F, Sum
from django.utils.encoding import python_2_unicode_compatible
from django.utils.formats import number_format
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

import producer
import purchase
from repanier.apps import DJANGO_IS_MIGRATION_RUNNING
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.tools import update_or_create_purchase, get_signature


def permanence_verbose_name():
    if DJANGO_IS_MIGRATION_RUNNING:
        return EMPTY_STRING
    from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
    return lambda: "%s" % REPANIER_SETTINGS_PERMANENCE_NAME


@python_2_unicode_compatible
class CustomerInvoice(models.Model):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("customer"),
        on_delete=models.PROTECT)
    customer_charged = models.ForeignKey(
        'Customer', verbose_name=_("customer"), related_name='invoices_paid', blank=True, null=True,
        on_delete=models.PROTECT, db_index=True)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=permanence_verbose_name(),
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
    delta_transport = ModelMoneyField(
        _("Delivery point transport"),
        help_text=_("transport to add"),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
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
    # customer_charged = models.ForeignKey(
    #     'Customer', verbose_name=_("customer"),
    #     related_name='invoices_paid',
    #     on_delete=models.PROTECT, db_index=True)
    master_permanence = models.ForeignKey(
        'Permanence', verbose_name=_("master permanence"),
        related_name='child_customer_invoice',
        blank=True, null=True, default=None,
        on_delete=models.PROTECT, db_index=True)

    def get_delta_price_with_tax(self):
        return self.delta_price_with_tax.amount

    def get_abs_delta_price_with_tax(self):
        return abs(self.delta_price_with_tax)

    def get_abs_delta_vat(self):
        return abs(self.delta_vat)

    def get_total_price_with_tax(self, customer_charged=False):
        if self.customer_id == self.customer_charged_id:
            return self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport
        else:
            if self.status < PERMANENCE_INVOICED or not customer_charged:
                return self.total_price_with_tax
            else:
                return self.customer_charged # if self.total_price_with_tax != DECIMAL_ZERO else RepanierMoney()

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
            self.customer_charged = self.customer
            self.price_list_multiplier = DECIMAL_ONE
            self.transport = REPANIER_SETTINGS_TRANSPORT
            self.min_transport = REPANIER_SETTINGS_MIN_TRANSPORT
        else:
            customer_responsible = delivery_point.customer_responsible
            if customer_responsible is None:
                self.customer_charged = self.customer
                self.price_list_multiplier = delivery_point.price_list_multiplier
                self.transport = delivery_point.transport
                self.min_transport = delivery_point.min_transport
            else:
                self.customer_charged = customer_responsible
                self.price_list_multiplier = DECIMAL_ONE
                self.transport = REPANIER_MONEY_ZERO
                self.min_transport = REPANIER_MONEY_ZERO
                if self.customer_id != customer_responsible.id:
                    customer_invoice_charged = CustomerInvoice.objects.filter(
                        permanence_id=self.permanence_id,
                        customer_id=customer_responsible.id
                    ).order_by('?')
                    if not customer_invoice_charged.exists():
                        CustomerInvoice.objects.create(
                            permanence_id=self.permanence_id,
                            customer_id=customer_responsible.id,
                            status=self.status,
                            customer_charged_id=customer_responsible.id,
                            price_list_multiplier=delivery_point.price_list_multiplier,
                            transport=delivery_point.transport,
                            min_transport=delivery_point.min_transport,
                            is_order_confirm_send=True
                        )

    @transaction.atomic
    def confirm_order(self):
        purchase.Purchase.objects.filter(
            customer_invoice__id=self.id
        ).update(quantity_confirmed=F('quantity_ordered'))
        self.calculate_and_save_delta_buyinggroup()
        self.is_order_confirm_send = True

    @transaction.atomic
    def calculate_and_save_delta_buyinggroup(self):
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
        else:
            producer_invoice_buyinggroup.delta_price_with_tax.amount -= self.delta_price_with_tax.amount
            producer_invoice_buyinggroup.delta_vat.amount -= self.delta_vat.amount
            producer_invoice_buyinggroup.delta_transport.amount -= self.delta_transport.amount

        self.calculate_delta_price()
        self.calculate_delta_transport()
        self.save()

        producer_invoice_buyinggroup.delta_price_with_tax.amount += self.delta_price_with_tax.amount
        producer_invoice_buyinggroup.delta_vat.amount += self.delta_vat.amount
        producer_invoice_buyinggroup.delta_transport.amount += self.delta_transport.amount

        producer_invoice_buyinggroup.save()

    def calculate_delta_price(self):
        getcontext().rounding = ROUND_HALF_UP

        result_set = purchase.Purchase.objects.filter(
            permanence_id=self.permanence_id,
            customer_id=self.customer_id,
        ).order_by('?').aggregate(
            Sum('customer_vat'),
            Sum('deposit'),
            Sum('selling_price')
        )
        if result_set["customer_vat__sum"] is not None:
            self.total_vat.amount = result_set["customer_vat__sum"]
        else:
            self.total_vat.amount = DECIMAL_ZERO
        if result_set["deposit__sum"] is not None:
            self.total_deposit.amount = result_set["deposit__sum"]
        else:
            self.total_deposit.amount = DECIMAL_ZERO
        if result_set["selling_price__sum"] is not None:
            self.total_price_with_tax.amount = result_set["selling_price__sum"]
        else:
            self.total_price_with_tax.amount = DECIMAL_ZERO

        if self.price_list_multiplier != DECIMAL_ONE:

            result_set = purchase.Purchase.objects.filter(
                permanence_id=self.permanence_id,
                customer_id=self.customer_id,
                is_resale_price_fixed=True
            ).order_by('?').aggregate(
                Sum('customer_vat'),
                Sum('deposit'),
                Sum('selling_price')
            )
            if result_set["customer_vat__sum"] is not None:
                total_vat = result_set["customer_vat__sum"]
            else:
                total_vat = DECIMAL_ZERO
            if result_set["deposit__sum"] is not None:
                total_deposit = result_set["deposit__sum"]
            else:
                total_deposit = DECIMAL_ZERO
            if result_set["selling_price__sum"] is not None:
                total_price_with_tax = result_set["selling_price__sum"]
            else:
                total_price_with_tax = DECIMAL_ZERO

            total_price_with_tax_wo_deposit = total_price_with_tax - total_deposit
            self.delta_price_with_tax.amount = -(
                total_price_with_tax_wo_deposit - (
                    total_price_with_tax_wo_deposit * self.price_list_multiplier
                ).quantize(TWO_DECIMALS)
            )
            self.delta_vat.amount = -(
                total_vat - (
                    total_vat * self.price_list_multiplier
                ).quantize(FOUR_DECIMALS)
            )
        else:
            self.delta_price_with_tax.amount = DECIMAL_ZERO
            self.delta_vat.amount = DECIMAL_ZERO

    def calculate_delta_transport(self):

        self.delta_transport.amount = DECIMAL_ZERO
        if self.master_permanence_id is None and self.transport.amount != DECIMAL_ZERO:
            # Calculate transport only on master customer invoice
            # But take into account the children customer invoices
            result_set = CustomerInvoice.objects.filter(
                master_permanence=self.permanence
            ).order_by('?').aggregate(
                Sum('total_price_with_tax'),
                Sum('delta_price_with_tax')
            )
            if result_set["total_price_with_tax__sum"] is not None:
                sum_total_price_with_tax = result_set["total_price_with_tax__sum"]
            else:
                sum_total_price_with_tax = DECIMAL_ZERO
            if result_set["delta_price_with_tax__sum"] is not None:
                sum_delta_price_with_tax = result_set["delta_price_with_tax__sum"]
            else:
                sum_delta_price_with_tax = DECIMAL_ZERO

            sum_total_price_with_tax += self.total_price_with_tax.amount
            sum_delta_price_with_tax += self.delta_price_with_tax.amount

            total_price_with_tax = sum_total_price_with_tax + sum_delta_price_with_tax
            if total_price_with_tax != DECIMAL_ZERO:
                if self.min_transport.amount == DECIMAL_ZERO:
                    self.delta_transport.amount = self.transport.amount
                elif total_price_with_tax < self.min_transport.amount:
                    self.delta_transport.amount = min(
                        self.min_transport.amount - total_price_with_tax,
                        self.transport.amount
                    )

    def cancel_confirm_order(self):
        if self.is_order_confirm_send:
            # Change of confirmation status
            self.is_order_confirm_send = False
            return True
        else:
            # No change of confirmation status
            return False

    def create_child(self, new_permanence):
        return CustomerInvoice.objects.create(
            permanence_id=new_permanence.id,
            customer_id=self.customer_id,
            master_permanence_id=self.permanence_id,
            customer_charged_id=self.customer_id,
            status=self.status
        )

    def delete_if_unconfirmed(self, permanence):
        if not self.is_order_confirm_send:
            from repanier.email.email_order import export_order_2_1_customer

            filename = "{0}-{1}.xlsx".format(
                slugify(_("Canceled order")),
                slugify(permanence)
            )
            sender_email, sender_function, signature, cc_email_staff = get_signature(
                is_reply_to_order_email=True)
            export_order_2_1_customer(
                self.customer, filename, permanence, sender_email,
                sender_function, signature,
                cancel_order=True
            )
            purchase_qs = purchase.Purchase.objects.filter(
                customer_invoice_id=self.id,
                is_box_content=False,
            ).order_by('?')
            for a_purchase in purchase_qs.select_related("customer"):
                update_or_create_purchase(
                    customer=a_purchase.customer,
                    offer_item_id=a_purchase.offer_item_id,
                    q_order=DECIMAL_ZERO,
                    batch_job=True,
                    comment=_("Cancelled qty : %s") % number_format(a_purchase.quantity_ordered, 4)
                )

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
        'Permanence', verbose_name=permanence_verbose_name(),
        on_delete=models.PROTECT, db_index=True)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("invoice_status"))
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

    to_be_paid = models.BooleanField(_("to be paid"), choices=LUT_BANK_NOTE, default=False)
    calculated_invoiced_balance = ModelMoneyField(
        _("calculated balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    to_be_invoiced_balance = ModelMoneyField(
        _("balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    invoice_reference = models.CharField(
        _("invoice reference"), max_length=100, null=True, blank=True)

    def get_negative_previous_balance(self):
        return - self.previous_balance

    def get_negative_balance(self):
        return - self.balance

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
        'Permanence', verbose_name=permanence_verbose_name(), on_delete=models.PROTECT,
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
