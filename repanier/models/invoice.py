# -*- coding: utf-8

import datetime

from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.db.models import F, Sum, Q, DecimalField
from django.urls import reverse
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.deliveryboard import DeliveryBoard
from repanier.tools import create_or_update_one_cart_item, round_gov_be, get_repanier_template_name


class Invoice(models.Model):
    permanence = models.ForeignKey(
        'Permanence', verbose_name=_('Order'),
        on_delete=models.PROTECT, db_index=True)
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Status"))
    date_previous_balance = models.DateField(
        _("Date previous balance"), default=datetime.date.today)
    previous_balance = ModelMoneyField(
        _("Previous balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # Calculated with Purchase
    total_price_with_tax = ModelMoneyField(
        _("Invoiced TVAC"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Purchase to add amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        help_text=_("Transport to add"),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    total_vat = ModelMoneyField(
        _("VAT"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_vat = ModelMoneyField(
        _("VAT to add"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_('Surcharge'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = ModelMoneyField(
        _("Cash in"), help_text=_('Payment on the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = ModelMoneyField(
        _("Cash out"), help_text=_('Payment from the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    date_balance = models.DateField(
        _("Date balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("Balance"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)

    def get_delta_price_with_tax(self):
        return self.delta_price_with_tax.amount

    def get_abs_delta_price_with_tax(self):
        return abs(self.delta_price_with_tax.amount)

    def __str__(self):
        return _("Invoice")

    class Meta:
        abstract = True


class CustomerInvoice(Invoice):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("Customer"),
        on_delete=models.PROTECT)
    customer_charged = models.ForeignKey(
        'Customer', verbose_name=_("Customer"), related_name='invoices_paid', blank=True, null=True,
        on_delete=models.PROTECT, db_index=True)
    delivery = models.ForeignKey(
        'DeliveryBoard', verbose_name=_("Delivery board"),
        null=True, blank=True, default=None,
        on_delete=models.PROTECT)
    # IMPORTANT: default = True -> for the order form, to display nothing at the begin of the order
    # is_order_confirm_send and total_price_with_tax = 0 --> display nothing
    # otherwise display
    # - send a mail with the order to me
    # - confirm the order (if REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER) and send a mail with the order to me
    # - mail send to XYZ
    # - order confirmed (if REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER) and mail send to XYZ
    is_order_confirm_send = models.BooleanField(_("Confirmation of the order send"), choices=settings.LUT_CONFIRM,
                                                default=False)
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    price_list_multiplier = models.DecimalField(
        _("Delivery point coefficient applied to the producer tariff to calculate the consumer tariff"),
        help_text=_(
            "This multiplier is applied once for groups with entitled customer or at each customer invoice for open groups."),
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
    master_permanence = models.ForeignKey(
        'Permanence', verbose_name=_("Master permanence"),
        related_name='child_customer_invoice',
        blank=True, null=True, default=None,
        on_delete=models.PROTECT, db_index=True)
    is_group = models.BooleanField(_("Group"), default=False)

    def get_abs_delta_vat(self):
        return abs(self.delta_vat)

    def get_total_price_with_tax(self, customer_charged=False):
        if self.customer_id == self.customer_charged_id:
            return self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport
        else:
            if self.status < PERMANENCE_INVOICED or not customer_charged:
                return self.total_price_with_tax
            else:
                return self.customer_charged  # if self.total_price_with_tax != DECIMAL_ZERO else RepanierMoney()

    def get_total_price_wo_tax(self):
        return self.get_total_price_with_tax() - self.get_total_tax()

    def get_total_tax(self):
        # round to 2 decimals
        return RepanierMoney(self.total_vat.amount + self.delta_vat.amount)

    @property
    def has_purchase(self):
        if self.total_price_with_tax.amount != DECIMAL_ZERO or self.is_order_confirm_send:
            return True

        from repanier.models.purchase import PurchaseWoReceiver

        result_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id,
            customer_invoice_id=self.id
        ).aggregate(
            qty_ordered=Sum(
                'quantity_ordered',
                output_field=DecimalField(max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
            ),
            qty_invoiced=Sum(
                'quantity_invoiced',
                output_field=DecimalField(max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
            )
        )
        qty_ordered = result_set["qty_ordered"] \
            if result_set["qty_ordered"] is not None else DECIMAL_ZERO
        qty_invoiced = result_set["qty_invoiced"] \
            if result_set["qty_invoiced"] is not None else DECIMAL_ZERO
        return qty_ordered != DECIMAL_ZERO or qty_invoiced != DECIMAL_ZERO

    def get_html_delivery_select(self):
        """
        Returns the `select` part when there is a delivery point to select.
        """

        if self.delivery is not None:
            label = self.delivery.get_delivery_customer_display()
            delivery_id = self.delivery_id
        else:
            delivery_id = 0

            if self.customer.delivery_point is not None:
                qs = DeliveryBoard.objects.filter(
                    Q(
                        permanence_id=self.permanence.id,
                        delivery_point_id=self.customer.delivery_point_id,
                        status=PERMANENCE_OPENED
                    ) | Q(
                        permanence_id=self.permanence.id,
                        delivery_point__customer_responsible__isnull=True,
                        status=PERMANENCE_OPENED
                    )
                )
            else:
                qs = DeliveryBoard.objects.filter(
                    permanence_id=self.permanence.id,
                    delivery_point__customer_responsible__isnull=True,
                    status=PERMANENCE_OPENED
                )
            if qs.exists():
                label = "{}".format(_('Please, select a delivery point'))
                CustomerInvoice.objects.filter(
                    permanence_id=self.permanence.id,
                    customer_id=self.customer_id).update(
                    status=PERMANENCE_OPENED)
            else:
                label = "{}".format(_('No delivery point is open for you. You can not place order.'))
                # IMPORTANT :
                # 1 / This prohibit to place an order into the customer UI
                # 2 / task_order.close_send_order will delete any CLOSED orders without any delivery point
                CustomerInvoice.objects.filter(
                    permanence_id=self.permanence.id,
                    customer_id=self.customer_id
                ).update(
                    status=PERMANENCE_CLOSED
                )
        if self.customer_id != self.customer_charged_id:
            msg_price = msg_transport = EMPTY_STRING
        else:
            if self.transport.amount <= DECIMAL_ZERO:
                transport = False
                msg_transport = EMPTY_STRING
            else:
                transport = True
                if self.min_transport.amount > DECIMAL_ZERO:
                    msg_transport = "{}".format(
                        _(
                            'The shipping costs for this delivery point amount to %(transport)s for orders of less than %(min_transport)s.') % {
                            'transport': self.transport,
                            'min_transport': self.min_transport
                        })
                else:
                    msg_transport = "{}".format(
                        _(
                            'The shipping costs for this delivery point amount to %(transport)s.') % {
                            'transport': self.transport,
                        })
            if self.price_list_multiplier == DECIMAL_ONE:
                msg_price = EMPTY_STRING
            else:
                if transport:
                    if self.price_list_multiplier > DECIMAL_ONE:
                        msg_price = "{}".format(
                            _(
                                'In addition, a surcharge of %(increase)s %% is applied to the billed total. It does not apply to deposits or fees.') % {
                                'increase': number_format(
                                    (self.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                            })
                    else:
                        msg_price = "{}".format(
                            _(
                                'In addition a reduction of %(decrease)s %% is applied to the billed total. It does not apply to deposits or fees.') % {
                                'decrease': number_format(
                                    (DECIMAL_ONE - self.price_list_multiplier) * 100, 2)
                            })
                else:
                    if self.price_list_multiplier > DECIMAL_ONE:
                        msg_price = "{}".format(
                            _(
                                'For this delivery point, an overload of %(increase)s %% is applied to the billed total (out of deposit).') % {
                                'increase': number_format(
                                    (self.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                            })
                    else:
                        msg_price = "{}".format(
                            _(
                                'For this delivery point, a reduction of %(decrease)s %% is applied to the invoiced total (out of deposit).') % {
                                'decrease': number_format(
                                    (DECIMAL_ONE - self.price_list_multiplier) * 100, 2)
                            })

        return mark_safe(render_to_string(
            get_repanier_template_name("widgets/select_delivery_point.html"),
            {'delivery_id': delivery_id, 'label': label, 'msg_transport': msg_transport, 'msg_price': msg_price}
        ))

    def get_html_my_order_confirmation(self, permanence, is_basket=False, basket_message=EMPTY_STRING):
        """
        Returns the order confirmation (= basket) display.
        """

        # render <select> HTML-element to pick the delivery point
        msg_delivery = self.get_html_delivery_select() if permanence.with_delivery_point else EMPTY_STRING

        msg_confirmation1 = EMPTY_STRING
        msg_confirmation2 = self.customer.my_order_confirmation_email_send_to() if self.is_order_confirm_send else EMPTY_STRING
        confirm_btn_disabled = "disabled" if permanence.status != PERMANENCE_OPENED or \
            (permanence.with_delivery_point and self.delivery is None) or \
            not self.has_purchase \
            else EMPTY_STRING

        if not is_basket and not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            # or customer_invoice.total_price_with_tax.amount != DECIMAL_ZERO:
            # If REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER then permanence.with_delivery_point is also True
            msg_html = EMPTY_STRING
        # the order has been confirmed + confirm email sent -> all set !
        else:
            msg_html = render_to_string(
                get_repanier_template_name("widgets/order_confirmation.html"),
                {'msg_confirmation1': msg_confirmation1,
                 'msg_confirmation2': msg_confirmation2,
                 'msg_delivery': msg_delivery,
                 'basket_message': basket_message,
                 'is_basket': is_basket,
                 'is_order_confirm_send': self.is_order_confirm_send,
                 'permanence': self.permanence,
                 'confirm_btn_disabled': confirm_btn_disabled,
                 'should_confirm': settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            })
        return {"#span_btn_confirm_order": mark_safe(msg_html)}

    @transaction.atomic
    def confirm_order(self):
        if not self.is_order_confirm_send:
            # Change of confirmation status
            from repanier.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(
                customer_invoice__id=self.id
            ).update(quantity_confirmed=F('quantity_ordered'))
        # Recalculate transport cost
        self.is_order_confirm_send = True

    @transaction.atomic
    def cancel_confirm_order(self):
        if self.is_order_confirm_send:
            # Change of confirmation status
            self.is_order_confirm_send = False
            return True
        else:
            # No change of confirmation status
            return False

    @transaction.atomic
    def set_order_delivery(self, delivery):
        # May not use delivery_id because it won't reload customer_invoice.delivery
        # Important
        # If it's an invoice of a member of a group :
        #   self.customer_charged_id != self.customer_id
        #   self.customer_charged_id == owner of the group
        #   price_list_multiplier = DECIMAL_ONE
        # Else :
        #   self.customer_charged_id = self.customer_id
        #   price_list_multiplier may vary
        if delivery is None:
            if self.permanence.with_delivery_point:
                # If the customer is member of a group set the group as default delivery point
                delivery_point = self.customer.delivery_point
                delivery = DeliveryBoard.objects.filter(
                    delivery_point=delivery_point,
                    permanence=self.permanence
                ).first()
            else:
                delivery_point = None
        else:
            delivery_point = delivery.delivery_point
        self.delivery = delivery

        if delivery_point is None:
            self.customer_charged = self.customer
            self.price_list_multiplier = DECIMAL_ONE
            self.transport = DECIMAL_ZERO
            self.min_transport = DECIMAL_ZERO
        else:
            customer_responsible = delivery_point.customer_responsible
            if customer_responsible is None:
                self.customer_charged = self.customer
                self.price_list_multiplier = DECIMAL_ONE
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
                    )
                    if not customer_invoice_charged.exists():
                        CustomerInvoice.objects.create(
                            permanence_id=self.permanence_id,
                            customer_id=customer_responsible.id,
                            status=self.status,
                            customer_charged_id=customer_responsible.id,
                            price_list_multiplier=customer_responsible.price_list_multiplier,
                            transport=delivery_point.transport,
                            min_transport=delivery_point.min_transport,
                            is_order_confirm_send=True,
                            is_group=True,
                            delivery=delivery
                        )

    def calculate_order_price(self):
        from repanier.models.purchase import PurchaseWoReceiver

        self.delta_price_with_tax.amount = DECIMAL_ZERO
        self.delta_vat.amount = DECIMAL_ZERO

        if self.customer_id == self.customer_charged_id:
            # It's an invoice of a group, or of a customer who is not member of a group :
            #   self.customer_charged_id = self.customer_id
            #   self.price_list_multiplier may vary
            if self.price_list_multiplier != DECIMAL_ONE:
                result_set = PurchaseWoReceiver.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_invoice__customer_charged_id=self.customer_id,
                    is_resale_price_fixed=False
                ).aggregate(
                    customer_vat = Sum(
                        'customer_vat',
                        output_field=DecimalField(max_digits=8, decimal_places=4, default=DECIMAL_ZERO)
                    ),
                    deposit = Sum(
                        'deposit',
                        output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                    ),
                    selling_price = Sum(
                        'selling_price',
                        output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                    )
                )

                total_vat = result_set["customer_vat"] \
                    if result_set["customer_vat"] is not None else DECIMAL_ZERO
                total_deposit = result_set["deposit"] \
                    if result_set["deposit"] is not None else DECIMAL_ZERO
                total_selling_price_with_tax = result_set["selling_price"] \
                    if result_set["selling_price"] is not None else DECIMAL_ZERO

                total_selling_price_with_tax_wo_deposit = total_selling_price_with_tax - total_deposit
                self.delta_price_with_tax.amount = (
                        (
                                total_selling_price_with_tax_wo_deposit * self.price_list_multiplier
                        ).quantize(TWO_DECIMALS) - total_selling_price_with_tax_wo_deposit
                )
                self.delta_vat.amount = -(
                        (total_vat * self.price_list_multiplier
                         ).quantize(FOUR_DECIMALS) - total_vat
                )

            result_set = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_invoice__customer_charged_id=self.customer_id,
            ).aggregate(
                customer_vat=Sum(
                    'customer_vat',
                    output_field=DecimalField(max_digits=8, decimal_places=4, default=DECIMAL_ZERO)
                ),
                deposit=Sum(
                    'deposit',
                    output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                ),
                selling_price=Sum(
                    'selling_price',
                    output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                )
            )
        else:
            # It's an invoice of a member of a group
            #   self.customer_charged_id != self.customer_id
            #   self.customer_charged_id == owner of the group
            #   assertion : self.price_list_multiplier always == DECIMAL_ONE
            result_set = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_id=self.customer_id,
            ).aggregate(
                customer_vat=Sum(
                    'customer_vat',
                    output_field=DecimalField(max_digits=8, decimal_places=4, default=DECIMAL_ZERO)
                ),
                deposit=Sum(
                    'deposit',
                    output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                ),
                selling_price=Sum(
                    'selling_price',
                    output_field=DecimalField(max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
                )
            )

        self.total_vat.amount = result_set["customer_vat"] \
            if result_set["customer_vat"] is not None else DECIMAL_ZERO
        self.total_deposit.amount = result_set["deposit"] \
            if result_set["deposit"] is not None else DECIMAL_ZERO
        self.total_price_with_tax.amount = result_set["selling_price"] \
            if result_set["selling_price"] is not None else DECIMAL_ZERO

        if settings.REPANIER_SETTINGS_ROUND_INVOICES:
            total_price = self.total_price_with_tax.amount + self.delta_price_with_tax.amount
            total_price_gov_be = round_gov_be(total_price)
            self.delta_price_with_tax.amount += (total_price_gov_be - total_price)
        self.calculate_order_transport()

    def calculate_order_transport(self):
        if self.customer_id == self.customer_charged_id:
            # It's an invoice of a group, or of a customer who is not member of a group :
            #   self.customer_charged_id = self.customer_id
            #   self.price_list_multiplier may vary
            if self.transport.amount != DECIMAL_ZERO:
                total_price_with_tax = self.total_price_with_tax.amount + self.delta_price_with_tax.amount
                if total_price_with_tax != DECIMAL_ZERO:
                    if self.min_transport.amount == DECIMAL_ZERO:
                        self.delta_transport.amount = self.transport.amount
                    elif total_price_with_tax < self.min_transport.amount:
                        self.delta_transport.amount = min(
                            self.min_transport.amount - total_price_with_tax,
                            self.transport.amount
                        )
                else:
                    self.delta_transport.amount = DECIMAL_ZERO
            else:
                self.delta_transport.amount = DECIMAL_ZERO
        else:
            self.delta_transport.amount = DECIMAL_ZERO

    def create_child(self, new_permanence):
        if self.customer_id != self.customer_charged_id:
            customer_invoice = CustomerInvoice.objects.filter(
                permanence_id=self.permanence_id,
                customer_id=self.customer_charged_id
            ).only("id")
            if not customer_invoice.exists():
                customer_invoice = CustomerInvoice.objects.create(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_charged_id,
                    customer_charged_id=self.customer_charged_id,
                    status=new_permanence.status
                )
                customer_invoice.set_order_delivery(delivery=None)
                customer_invoice.calculate_order_price()
                customer_invoice.save()
        return CustomerInvoice.objects.create(
            permanence_id=new_permanence.id,
            customer_id=self.customer_id,
            master_permanence_id=self.permanence_id,
            customer_charged_id=self.customer_charged_id,
            status=new_permanence.status
        )

    def cancel_if_unconfirmed(self, permanence):
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER \
                and not self.is_order_confirm_send \
                and self.has_purchase:
            from repanier.email.email_order import export_order_2_1_customer
            from repanier.models.purchase import PurchaseWoReceiver

            filename = "{}-{}.xlsx".format(
                _("Canceled order"),
                permanence
            )

            export_order_2_1_customer(
                self.customer, filename, permanence,
                cancel_order=True
            )
            purchase_qs = PurchaseWoReceiver.objects.filter(
                customer_invoice_id=self.id,
                is_box_content=False,
            )
            for a_purchase in purchase_qs.select_related("customer"):
                create_or_update_one_cart_item(
                    customer=a_purchase.customer,
                    offer_item_id=a_purchase.offer_item_id,
                    q_order=DECIMAL_ZERO,
                    batch_job=True,
                    comment=_("Qty not confirmed : {}").format(number_format(a_purchase.quantity_ordered, 4))
                )

    def __str__(self):
        return "{}, {}".format(self.customer, self.permanence)

    class Meta:
        verbose_name = _("Customer invoice")
        verbose_name_plural = _("Customers invoices")
        unique_together = ("permanence", "customer",)


class ProducerInvoice(Invoice):
    producer = models.ForeignKey(
        'Producer', verbose_name=_("Producer"),
        # related_name='producer_invoice',
        on_delete=models.PROTECT)

    delta_stock_with_tax = ModelMoneyField(
        _("Amount deducted from the stock"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    delta_stock_vat = ModelMoneyField(
        _("Total VAT deducted from the stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_('+ Deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_stock_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_('+ Deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    to_be_paid = models.BooleanField(_("To be paid"), choices=LUT_BANK_NOTE, default=False)
    calculated_invoiced_balance = ModelMoneyField(
        _("Amount due to the producer as calculated by Repanier"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    to_be_invoiced_balance = ModelMoneyField(
        _("Amount claimed by the producer"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    invoice_reference = models.CharField(
        _("Invoice reference"),
        max_length=100, blank=True, default=EMPTY_STRING)

    def get_negative_previous_balance(self):
        return - self.previous_balance

    def get_negative_balance(self):
        return - self.balance

    def get_total_price_with_tax(self):
        return self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport + self.delta_stock_with_tax

    def get_total_vat(self):
        return self.total_vat + self.delta_stock_vat

    def get_total_deposit(self):
        return self.total_deposit + self.delta_stock_deposit

    def get_order_json(self):
        a_producer = self.producer
        json_dict = {}
        if a_producer.minimum_order_value.amount > DECIMAL_ZERO:
            ratio = self.total_price_with_tax.amount / a_producer.minimum_order_value.amount
            if ratio >= DECIMAL_ONE:
                ratio = 100
            else:
                ratio *= 100
            json_dict["#order_procent{}".format(a_producer.id)] = "{}%".format(number_format(ratio, 0))
        return json_dict

    def __str__(self):
        return "{}, {}".format(self.producer, self.permanence)

    class Meta:
        verbose_name = _("Producer invoice")
        verbose_name_plural = _("Producers invoices")
        unique_together = ("permanence", "producer",)


class CustomerProducerInvoice(models.Model):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("Customer"),
        on_delete=models.PROTECT)
    producer = models.ForeignKey(
        'Producer', verbose_name=_("Producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=_('Order'), on_delete=models.PROTECT,
        db_index=True)
    # Calculated with Purchase
    total_purchase_with_tax = ModelMoneyField(
        _("Producer amount invoiced"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase
    total_selling_with_tax = ModelMoneyField(
        _("Invoiced to the consumer including tax"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_html_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return format_html("<b>{}</b>", self.total_purchase_with_tax)
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = (_("Producer amount invoiced"))
    get_html_producer_price_purchased.admin_order_field = 'total_purchase_with_tax'

    def __str__(self):
        return "{}, {}".format(self.producer, self.customer)

    class Meta:
        unique_together = ("permanence", "customer", "producer",)


class CustomerSend(CustomerProducerInvoice):
    def __str__(self):
        return "{}, {}".format(self.producer, self.customer)

    class Meta:
        proxy = True
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
