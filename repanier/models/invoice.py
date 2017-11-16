# -*- coding: utf-8

import datetime

from django.core import urlresolvers
from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.db.models import F, Sum, Q
from django.utils.formats import number_format
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from repanier.apps import REPANIER_SETTINGS_GROUP_PRODUCER_ID
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.deliveryboard import DeliveryBoard
from repanier.tools import create_or_update_one_cart_item, get_signature


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
        _("Total amount"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_price_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Purchase to add amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_transport = ModelMoneyField(
        _("Delivery point transport"),
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
        help_text=_('Deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = ModelMoneyField(
        _("Bank amount in"), help_text=_('Payment on the account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = ModelMoneyField(
        _("Bank amount out"), help_text=_('Payment from the account'),
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
    # - confirm the order (if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS) and send a mail with the order to me
    # - mail send to XYZ
    # - order confirmed (if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS) and mail send to XYZ
    is_order_confirm_send = models.BooleanField(_("Confirmation of the order send"), choices=LUT_CONFIRM, default=False)
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
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
                return self.customer_charged # if self.total_price_with_tax != DECIMAL_ZERO else RepanierMoney()

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

        result = False
        result_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id,
            customer_invoice_id=self.id
        ).order_by('?').aggregate(
            Sum('quantity_ordered'),
            Sum('quantity_invoiced'),
        )
        if result_set["quantity_ordered__sum"] is not None:
            sum_quantity_ordered = result_set["quantity_ordered__sum"]
            if sum_quantity_ordered != DECIMAL_ZERO:
                result = True
        if result_set["quantity_invoiced__sum"] is not None:
            sum_quantity_invoiced = result_set["quantity_invoiced__sum"]
            if sum_quantity_invoiced != DECIMAL_ZERO:
                result = True
        return result

    @transaction.atomic
    def set_delivery(self, delivery):
        # May not use delivery_id because it won't reload customer_invoice.delivery
        # Important
        # If it's an invoice of a member of a group :
        #   self.customer_charged_id != self.customer_id
        #   self.customer_charged_id == owner of the group
        #   price_list_multiplier = DECIMAL_ONE
        # Else :
        #   self.customer_charged_id = self.customer_id
        #   price_list_multiplier may vary
        from repanier.apps import REPANIER_SETTINGS_TRANSPORT, REPANIER_SETTINGS_MIN_TRANSPORT
        if delivery is None:
            if self.permanence.with_delivery_point:
                # If the customer is member of a group set the group as default delivery point
                delivery_point = self.customer.delivery_point
                delivery = DeliveryBoard.objects.filter(
                    delivery_point=delivery_point,
                    permanence=self.permanence
                ).order_by('?').first()
            else:
                delivery_point = None
        else:
            delivery_point = delivery.delivery_point
        self.delivery = delivery

        if delivery_point is None:
            self.customer_charged = self.customer
            self.price_list_multiplier = DECIMAL_ONE
            self.transport = REPANIER_SETTINGS_TRANSPORT
            self.min_transport = REPANIER_SETTINGS_MIN_TRANSPORT
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
                    ).order_by('?')
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

    def my_order_confirmation(self, permanence, is_basket=False,
                              basket_message=EMPTY_STRING, to_json=None):
        from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS

        if permanence.with_delivery_point:
            if self.delivery is not None:
                label = self.delivery.get_delivery_customer_display()
                delivery_id = self.delivery_id
            else:
                delivery_id = 0

                if self.customer.delivery_point is not None:
                    qs = DeliveryBoard.objects.filter(
                        Q(
                            permanence_id=permanence.id,
                            delivery_point_id=self.customer.delivery_point_id,
                            status=PERMANENCE_OPENED
                        ) | Q(
                            permanence_id=permanence.id,
                            delivery_point__customer_responsible__isnull=True,
                            status=PERMANENCE_OPENED
                        )
                    ).order_by('?')
                else:
                    qs = DeliveryBoard.objects.filter(
                        permanence_id=permanence.id,
                        delivery_point__customer_responsible__isnull=True,
                        status=PERMANENCE_OPENED
                    ).order_by('?')
                if qs.exists():
                    label = "{}".format(_('Please, select a delivery point'))
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id,
                        customer_id=self.customer_id).order_by('?').update(
                        status=PERMANENCE_OPENED)
                else:
                    label = "{}".format(_('No delivery point is open for you. You can not place order.'))
                    # IMPORTANT :
                    # 1 / This prohibit to place an order into the customer UI
                    # 2 / task_order.close_send_order will delete any CLOSED orders without any delivery point
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id,
                        customer_id=self.customer_id
                    ).order_by('?').update(
                        status=PERMANENCE_CLOSED)
            if self.customer_id != self.customer_charged_id:
                msg_price = msg_transport = EMPTY_STRING
            else:
                if self.transport.amount <= DECIMAL_ZERO:
                    transport = False
                    msg_transport = EMPTY_STRING
                else:
                    transport = True
                    if self.min_transport.amount > DECIMAL_ZERO:
                        msg_transport = "{}<br>".format(
                                        _(
                                            'The shipping costs for this delivery point amount to %(transport)s for orders of less than %(min_transport)s.') % {
                                            'transport'    : self.transport,
                                            'min_transport': self.min_transport
                                        })
                    else:
                        msg_transport = "{}<br>".format(
                                        _(
                                            'The shipping costs for this delivery point amount to %(transport)s.') % {
                                            'transport': self.transport,
                                        })
                if self.price_list_multiplier == DECIMAL_ONE:
                    msg_price = EMPTY_STRING
                else:
                    if transport:
                        if self.price_list_multiplier > DECIMAL_ONE:
                            msg_price = "{}<br>".format(
                                        _(
                                            'A price increase of %(increase)s %% of the total invoiced is due for this delivery point. This does not apply to the cost of transport which is fixed.') % {
                                            'increase': number_format(
                                                (self.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                                        })
                        else:
                            msg_price = "{}<br>".format(
                                        _(
                                            'A price decrease of %(decrease)s %% of the total invoiced is given for this delivery point. This does not apply to the cost of transport which is fixed.') % {
                                            'decrease': number_format(
                                                (DECIMAL_ONE - self.price_list_multiplier) * 100, 2)
                                        })
                    else:
                        if self.price_list_multiplier > DECIMAL_ONE:
                            msg_price = "{}<br>".format(
                                        _(
                                            'A price increase of %(increase)s %% of the total invoiced is due for this delivery point.') % {
                                            'increase': number_format(
                                                (self.price_list_multiplier - DECIMAL_ONE) * 100, 2)
                                        })
                        else:
                            msg_price = "{}<br>".format(
                                        _(
                                            'A price decrease of %(decrease)s %% of the total invoiced is given for this delivery point.') % {
                                            'decrease': number_format(
                                                (DECIMAL_ONE - self.price_list_multiplier) * 100, 2)
                                        })

            msg_delivery = """
            {}<b><i>
            <select name=\"delivery\" id=\"delivery\" onmouseover=\"show_select_delivery_list_ajax({})\" onchange=\"delivery_ajax()\" class=\"form-control\">
            <option value=\"{}\" selected>{}</option>
            </select>
            </i></b><br>{}{}
            """.format(
                _("Delivery point"),
                delivery_id,
                delivery_id,
                label,
                msg_transport,
                msg_price
            )
        else:
            msg_delivery = EMPTY_STRING
        msg_confirmation1 = EMPTY_STRING
        if not is_basket and not REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
            # or customer_invoice.total_price_with_tax.amount != DECIMAL_ZERO:
            # If apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS is True,
            # then permanence.with_delivery_point is also True
            msg_html = EMPTY_STRING
        else:
            if self.is_order_confirm_send:
                msg_confirmation2 = self.customer.my_order_confirmation_email_send_to()
                msg_html = """
                <div class="row">
                <div class="panel panel-default">
                <div class="panel-heading">
                {}
                <p><font color="#51a351">{}</font><p/>
                {}
                </div>
                </div>
                </div>
                 """.format(msg_delivery, msg_confirmation2, basket_message)
            else:
                msg_html = None
                btn_disabled = EMPTY_STRING if permanence.status == PERMANENCE_OPENED else "disabled"
                msg_confirmation2 = EMPTY_STRING
                if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                    if is_basket:
                        if self.status == PERMANENCE_OPENED:
                            if (permanence.with_delivery_point and self.delivery is None) \
                                    or not self.has_purchase:
                                btn_disabled = "disabled"
                            msg_confirmation1 = "<font color=\"red\">{}</font><br>".format(_(
                                "/!\ Unconfirmed orders will be canceled."))
                            msg_confirmation2 = "<span class=\"glyphicon glyphicon-floppy-disk\"></span>&nbsp;&nbsp;{}".format(_(
                                "Confirm this order and receive an email containing its summary."))
                    else:
                        href = urlresolvers.reverse(
                            'order_view', args=(permanence.id,)
                        )
                        if self.status == PERMANENCE_OPENED:
                            msg_confirmation1 = "<font color=\"red\">{}</font><br>".format(_(
                                "/!\ Unconfirmed orders will be canceled."))
                            msg_confirmation2 = _("Verify my order content before validating it.")
                            msg_html = """
                                <div class="row">
                                <div class="panel panel-default">
                                <div class="panel-heading">
                                {}
                                {}
                                <a href="{}?is_basket=yes" class="btn btn-info" {}>{}</a>
                                </div>
                                </div>
                                </div>
                                 """.format(msg_delivery, msg_confirmation1, href, btn_disabled, msg_confirmation2)
                else:
                    if is_basket:
                        msg_confirmation2 = _("Receive an email containing this order summary.")
                    elif permanence.with_delivery_point:
                        msg_html = """
                            <div class="row">
                            <div class="panel panel-default">
                            <div class="panel-heading">
                            {}
                            </div>
                            </div>
                            </div>
                             """.format(msg_delivery)
                    else:
                        msg_html = EMPTY_STRING
                if msg_html is None:
                    if msg_confirmation2 == EMPTY_STRING:
                        msg_html = """
                        <div class="row">
                        <div class="panel panel-default">
                        <div class="panel-heading">
                        {}
                        <div class="clearfix"></div>
                        {}
                        </div>
                        </div>
                        </div>
                         """.format(msg_delivery, basket_message)
                    else:
                        msg_html = """
                        <div class="row">
                        <div class="panel panel-default">
                        <div class="panel-heading">
                        {}
                        {}
                        <button id="btn_confirm_order" class="btn btn-info" {} onclick="btn_receive_order_email();">{}</button>
                        <div class="clearfix"></div>
                        {}
                        </div>
                        </div>
                        </div>
                         """.format(msg_delivery, msg_confirmation1, btn_disabled, msg_confirmation2, basket_message)
        if to_json is not None:
            option_dict = {'id': "#span_btn_confirm_order", 'html': msg_html}
            to_json.append(option_dict)

    @transaction.atomic
    def confirm_order(self):
        from repanier.models.purchase import Purchase

        Purchase.objects.filter(
            customer_invoice__id=self.id
        ).update(quantity_confirmed=F('quantity_ordered'))
        self.calculate_and_save_delta_buyinggroup(confirm_order=True)
        self.is_order_confirm_send = True

    def calculate_and_save_delta_buyinggroup(self, confirm_order=False):
        previous_delta_price_with_tax = self.delta_price_with_tax.amount
        previous_delta_vat = self.delta_vat.amount
        previous_delta_transport = self.delta_transport.amount

        self.calculate_delta_price(confirm_order)
        self.calculate_delta_transport()

        if previous_delta_price_with_tax != self.delta_price_with_tax.amount or previous_delta_vat != self.delta_vat.amount or previous_delta_transport != self.delta_transport.amount:
            producer_invoice_buyinggroup = ProducerInvoice.objects.filter(
                producer__represent_this_buyinggroup=True,
                permanence_id=self.permanence_id,
            ).order_by('?').first()
            if producer_invoice_buyinggroup is None:
                # producer_buyinggroup = Producer.objects.filter(
                #     represent_this_buyinggroup=True
                # ).order_by('?').first()

                producer_invoice_buyinggroup = ProducerInvoice.objects.create(
                    producer_id=REPANIER_SETTINGS_GROUP_PRODUCER_ID,
                    permanence_id=self.permanence_id,
                    status=self.permanence.status
                )
            producer_invoice_buyinggroup.delta_price_with_tax.amount += self.delta_price_with_tax.amount - previous_delta_price_with_tax
            producer_invoice_buyinggroup.delta_vat.amount += self.delta_vat.amount - previous_delta_vat
            producer_invoice_buyinggroup.delta_transport.amount += self.delta_transport.amount - previous_delta_transport

            producer_invoice_buyinggroup.save()

    def calculate_delta_price(self, confirm_order=False):
        from repanier.models.purchase import Purchase
        getcontext().rounding = ROUND_HALF_UP

        self.delta_price_with_tax.amount = DECIMAL_ZERO
        self.delta_vat.amount = DECIMAL_ZERO

        # Important
        # Si c'est une facture du membre d'un groupe :
        #   self.customer_charged_id == purchase.customer_charged_id != self.customer_id
        #   self.customer_charged_id == purchase.customer_charged_id == owner of the group
        #   self.price_list_multiplier = DECIMAL_ONE
        # Si c'est une facture lambda ou d'un groupe :
        #   self.customer_charged_id == purchase.customer_charged_id = self.customer_id
        #   self.price_list_multiplier may vary
        if self.customer_id == self.customer_charged_id:

            if self.price_list_multiplier != DECIMAL_ONE:
                result_set = Purchase.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_invoice__customer_charged_id=self.customer_id,
                    is_resale_price_fixed=False
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

            result_set = Purchase.objects.filter(
                permanence_id=self.permanence_id,
                customer_invoice__customer_charged_id=self.customer_id,
            ).order_by('?').aggregate(
                Sum('customer_vat'),
                Sum('deposit'),
                Sum('selling_price')
            )
        else:
            result_set = Purchase.objects.filter(
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

    def calculate_delta_transport(self):

        self.delta_transport.amount = DECIMAL_ZERO
        if self.master_permanence_id is None and self.transport.amount != DECIMAL_ZERO:
            # Calculate transport only on master customer invoice
            # But take into account the children customer invoices
            result_set = CustomerInvoice.objects.filter(
                master_permanence_id=self.permanence_id
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
        if self.customer_id != self.customer_charged_id:
            # TODO : Créer la customer invoice du groupe
            customer_invoice = CustomerInvoice.objects.filter(
                permanence_id=self.permanence_id,
                customer_id=self.customer_charged_id
            ).only("id").order_by('?')
            if not customer_invoice.exists():
                customer_invoice = CustomerInvoice.objects.create(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_charged_id,
                    customer_charged_id=self.customer_charged_id,
                    status=self.status
                )
                customer_invoice.set_delivery(delivery=None)
                customer_invoice.save()
        return CustomerInvoice.objects.create(
            permanence_id=new_permanence.id,
            customer_id=self.customer_id,
            master_permanence_id=self.permanence_id,
            customer_charged_id=self.customer_charged_id,
            status=self.status
        )

    def cancel_if_unconfirmed(self, permanence):
        if not self.is_order_confirm_send and self.has_purchase:
            from repanier.email.email_order import export_order_2_1_customer
            from repanier.models.purchase import Purchase

            filename = "{0}-{1}.xlsx".format(
                _("Canceled order"),
                permanence
            )
            sender_email, sender_function, signature, cc_email_staff = get_signature(
                is_reply_to_order_email=True)
            export_order_2_1_customer(
                self.customer, filename, permanence, sender_email,
                sender_function, signature,
                cancel_order=True
            )
            purchase_qs = Purchase.objects.filter(
                customer_invoice_id=self.id,
                is_box_content=False,
            ).order_by('?')
            for a_purchase in purchase_qs.select_related("customer"):
                create_or_update_one_cart_item(
                    customer=a_purchase.customer,
                    offer_item_id=a_purchase.offer_item_id,
                    q_order=DECIMAL_ZERO,
                    batch_job=True,
                    comment=_("Cancelled qty : {}").format(number_format(a_purchase.quantity_ordered, 4))
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
        _("Total stock"),
        help_text=_('Stock taken amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    delta_stock_vat = ModelMoneyField(
        _("Total stock vat"),
        help_text=_('VAT to add'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    delta_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_('Deposit to add'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    delta_stock_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_('Deposit to add'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    to_be_paid = models.BooleanField(_("To be paid"), choices=LUT_BANK_NOTE, default=False)
    calculated_invoiced_balance = ModelMoneyField(
        _("Calculated balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    to_be_invoiced_balance = ModelMoneyField(
        _("Balance to be invoiced"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    invoice_reference = models.CharField(
        _("Invoice reference"), max_length=100, null=True, blank=True)

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

    def get_order_json(self, to_json):
        a_producer = self.producer
        if a_producer.minimum_order_value.amount > DECIMAL_ZERO:
            ratio = self.total_price_with_tax.amount / a_producer.minimum_order_value.amount
            if ratio >= DECIMAL_ONE:
                ratio = 100
            else:
                ratio *= 100
            option_dict = {'id'  : "#order_procent{}".format(a_producer.id),
                           'html': "{}%".format(number_format(ratio, 0))}
            to_json.append(option_dict)
        if self.status != PERMANENCE_OPENED:
            option_dict = {'id'  : "#order_closed{}".format(a_producer.id),
                           'html': '&nbsp;<span class="glyphicon glyphicon-ban-circle" aria-hidden="true"></span>'}
            to_json.append(option_dict)
        return

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
        _("Customer amount invoiced"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_html_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return _("<b>%(price)s</b>") % {'price': self.total_purchase_with_tax}
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = (_("Producer amount invoiced"))
    get_html_producer_price_purchased.allow_tags = True
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
