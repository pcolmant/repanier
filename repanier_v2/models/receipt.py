from __future__ import annotations

import datetime

from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.db.models import F, Sum, DecimalField
from django.urls import reverse
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier_v2.const import *
from repanier_v2.fields.RepanierMoneyField import ModelMoneyField
from repanier_v2.tools import create_or_update_one_cart_item, round_gov_be


class ReceiptQuerySet(models.QuerySet):
    pass


class Receipt(models.Model):
    order = models.ForeignKey("Order", on_delete=models.PROTECT, null=True, default=None, db_index=True)
    date_previous_balance = models.DateField(default=datetime.date.today)
    previous_balance = ModelMoneyField(
        max_digits=7, decimal_places=2, default=DECIMAL_ZERO
    )
    balance_invoiced = ModelMoneyField(
        max_digits=7,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        default=EMPTY_STRING,
    )
    transport = ModelMoneyField(
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
    )
    tax = ModelMoneyField(default=DECIMAL_ZERO, max_digits=7, decimal_places=2)
    deposit = ModelMoneyField(
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
    )
    invoice_sort_order = models.IntegerField(
        default=None, blank=True, null=True, db_index=True
    )
    bank_in = ModelMoneyField(
        max_digits=7,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    bank_out = ModelMoneyField(
        max_digits=7,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    date_next_balance = models.DateField(default=datetime.date.today)
    next_balance = ModelMoneyField(max_digits=7, decimal_places=2, default=DECIMAL_ZERO)

    def __str__(self):
        return _("Receipt")

    class Meta:
        abstract = True


class CustomerReceiptQuerySet(ReceiptQuerySet):
    def last_customer_invoice(self, pk: int, customer_id: int):
        if pk == 0:
            return self.filter(
                customer_id=customer_id, invoice_sort_order__isnull=False
            ).order_by("-invoice_sort_order")
        return self.filter(
            id=pk, customer_id=customer_id, invoice_sort_order__isnull=False
        )

    def previous_customer_invoice(self, customer_invoice: CustomerReceipt):
        return self.filter(
            customer_id=customer_invoice.customer_id,
            invoice_sort_order__isnull=False,
            invoice_sort_order__lt=customer_invoice.invoice_sort_order,
        ).order_by("-invoice_sort_order")

    def next_customer_invoice(self, customer_invoice: CustomerReceipt):
        return self.filter(
            customer_id=customer_invoice.customer_id,
            invoice_sort_order__isnull=False,
            invoice_sort_order__gt=customer_invoice.invoice_sort_order,
        ).order_by("invoice_sort_order")


class CustomerReceipt(Receipt):
    customer = models.ForeignKey(
        "Customer", verbose_name=_("Customer"), on_delete=models.PROTECT
    )
    invoiced_group = models.ForeignKey(
        "Customer",
        verbose_name=_("Receiptd group"),
        related_name="invoiced_group",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        db_index=True,
    )
    order_dispensing_point = models.ForeignKey(
        "OrderDispensingPoint",
        verbose_name=_("Order dispensing point"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.PROTECT,
    )
    sale_delivery_transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    sale_delivery_min_transport = ModelMoneyField(
        _("Minimum order amount for free shipping cost"),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    # sale_margin : from customer or from group
    sale_margin = models.DecimalField(
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    display_sale_margin = models.BooleanField(
        _("Display sales tariff to the customer"), default=False
    )
    customer_price = ModelMoneyField(
        _("Customer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )

    is_group = models.BooleanField(_("Group"), default=False)
    is_confirmed = models.BooleanField(choices=settings.LUT_CONFIRM, default=False)
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True, db_index=True)

    @classmethod
    def get_or_create(cls, permanence_id, customer_id, delivery_board=None):
        customer_invoice = CustomerReceipt.objects.filter(
            permanence_id=permanence_id, customer_id=customer_id
        ).first()
        if customer_invoice is None:
            customer_invoice = CustomerReceipt.create(
                permanence_id, customer_id, delivery_board=delivery_board
            )
        elif customer_invoice.invoice_sort_order is None:
            # if not already invoiced, update all totals
            customer_invoice.set_total()
            # 	delta_price_with_tax
            # 	delta_vat
            # 	total_vat
            # 	total_deposit
            # 	total_price_with_tax
            # 	transport = f(total_price_with_tax, transport, min_transport)
            customer_invoice.save()
        return customer_invoice

    @classmethod
    def create(cls, permanence_id, customer_id, delivery_board=None):
        customer_invoice = CustomerReceipt.objects.create(
            permanence_id=permanence_id,
            customer_id=customer_id,
            #
            #
            delta_price_with_tax=DECIMAL_ZERO,
            delta_vat=DECIMAL_ZERO,
            total_vat=DECIMAL_ZERO,
            total_deposit=DECIMAL_ZERO,
            total_price_with_tax=DECIMAL_ZERO,
            transport=DECIMAL_ZERO,
            #
            #
            is_order_confirm_send=False,
            invoice_sort_order=None,
            # 	date_previous_balance = undefined (today)
            # 	previous_balance = undefined (DECIMAL_ZERO)
            # 	date_balance = undefined (today)
            # 	balance = undefined (DECIMAL_ZERO)
        )
        customer_invoice.set_delivery_context(delivery_board=delivery_board)
        #   validated delivery = f(delivery/customer, default delivery = None)
        #   status = f(permanence, validated delivery),
        # 	is_group= f(validated delivery)
        #   group =  f(validated delivery)
        # 	customer_charged_id=f(group)
        # 	price_list_multiplier= f(group), default 1
        # 	transport= f(validated delivery/group), default 0
        # 	min_transport= f(validated delivery/group), default 0
        customer_invoice.save()
        return customer_invoice

    @property
    def has_purchase(self):
        if self.balance_calculated.amount != DECIMAL_ZERO or self.is_order_confirm_send:
            return True

        from repanier_v2.models.purchase import PurchaseWoReceiver

        result_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id, customer_invoice_id=self.id
        ).aggregate(
            qty=Sum(
                "qty",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
        )
        qty = result_set["qty"] or DECIMAL_ZERO
        return qty != DECIMAL_ZERO

    def get_html_my_order_confirmation(
        self, permanence, is_basket=False, basket_message=EMPTY_STRING
    ):

        if not is_basket and not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            return {"#span_btn_confirm_order": EMPTY_STRING}

        if not permanence.with_delivery_point:
            msg_delivery_html = EMPTY_STRING
        else:
            msg_delivery_point_html = self.get_msg_delivery_point_html(
                permanence_id=permanence.id
            )
            msg_transport_html = self.get_msg_transport_html()
            sales_tariff_margin_html = self.get_sales_tariff_margin_html()
            msg_delivery_html = "<br>".join(
                [msg_delivery_point_html, msg_transport_html, sales_tariff_margin_html]
            )

        msg_confirmation_email_html = self.get_msg_confirmation_email_html(
            is_basket,
            permanence_id=permanence.id,
            permanence_with_delivery_point=permanence.with_delivery_point,
        )

        if basket_message:
            basket_message_html = '<div class="clearfix"></div>{}'.format(
                basket_message
            )
        else:
            basket_message_html = EMPTY_STRING

        msg_html = """
            <div class="row">
            <div class="panel panel-default">
            <div class="panel-heading">
            {}
            {}
            {}
            </div>
            </div>
            </div>
             """.format(
            msg_delivery_html, msg_confirmation_email_html, basket_message_html
        )

        return {"#span_btn_confirm_order": mark_safe(msg_html)}

    def get_msg_confirmation_email_html(
        self, is_basket, permanence_id, permanence_with_delivery_point
    ):
        if self.is_confirmed:
            msg_confirmation_email_html = (
                '<p><font color="#51a351">{}</font><p/>'.format(
                    self.customer.my_order_confirmation_email_send_to()
                )
            )
        else:
            if self.status != ORDER_OPENED:
                msg_confirmation_email_html = EMPTY_STRING
            else:
                if (
                    permanence_with_delivery_point and self.delivery is None
                ) or not self.has_purchase:
                    btn_disabled = "disabled"
                else:
                    btn_disabled = EMPTY_STRING

                if not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                    msg_confirmation_email_html = """
                        <button id="btn_confirm_order" class="btn btn-info" {} onclick="btn_receive_order_email();">
                        {}
                        </button>
                    """.format(
                        btn_disabled,
                        _("Receive an email containing this order summary."),
                    )
                else:
                    if is_basket:
                        msg_confirmation_email_html = """
                            <span style="color: red; ">
                            {}
                            </span>
                            <br>
                            <button id="btn_confirm_order" class="btn btn-info" {} onclick="btn_receive_order_email();">
                            {}
                            </button>
                        """.format(
                            _("⚠ Unconfirmed orders will be canceled."),
                            btn_disabled,
                            _(
                                " ➜ Confirm this order and receive an email containing its summary."
                            ),
                        )
                    else:
                        msg_confirmation_email_html = """
                            <span style="color: red; ">
                            {}
                            </span>
                            <br>
                            <a href="{}?is_basket=yes" class="btn btn-info" {}>
                            {}
                            </a>
                        """.format(
                            _("⚠ Unconfirmed orders will be canceled."),
                            reverse("repanier_v2:order_view", args=(permanence_id,)),
                            btn_disabled,
                            _("➜ Go to the confirmation step of my order."),
                        )
        return msg_confirmation_email_html

    def get_sales_tariff_margin_html(self):
        sales_tariff_margin_html = EMPTY_STRING
        if self.display_sales_tariff and self.sales_tariff_margin != DECIMAL_ZERO:
            if self.sales_tariff_margin > DECIMAL_ONE:
                sales_tariff_margin_html = "{}".format(
                    _(
                        "For this delivery point, an overload of %(increase)s %% is applied to the billed total (out of deposit)."
                    )
                    % {
                        "increase": number_format(
                            (self.sales_tariff_margin - DECIMAL_ONE) * 100,
                            2,
                        )
                    }
                )
            else:
                sales_tariff_margin_html = "{}".format(
                    _(
                        "For this delivery point, a reduction of %(decrease)s %% is applied to the invoiced total (out of deposit)."
                    )
                    % {
                        "decrease": number_format(
                            (DECIMAL_ONE - self.sales_tariff_margin) * 100,
                            2,
                        )
                    }
                )
        return sales_tariff_margin_html

    def get_msg_transport_html(self):
        msg_transport_html = EMPTY_STRING
        if self.delivery_transport.amount > DECIMAL_ZERO:
            if self.delivery_min_transport.amount > DECIMAL_ZERO:
                msg_transport_html = "{}".format(
                    _(
                        "The shipping costs for this delivery point amount to %(transport)s for orders of less than %(min_transport)s."
                    )
                    % {
                        "transport": self.transport,
                        "min_transport": self.delivery_min_transport,
                    }
                )
            else:
                msg_transport_html = "{}".format(
                    _(
                        "The shipping costs for this delivery point amount to %(transport)s."
                    )
                    % {"transport": self.transport}
                )
        return msg_transport_html

    def get_msg_delivery_point_html(self, permanence_id):
        if self.delivery_board is not None:
            delivery_board_id = self.delivery_board_id
            label_delivery_board = self.delivery.get_delivery_status_display()
        else:
            delivery_board_id = 0
            qs = self.customer.get_available_deliveries_qs(
                permanence_id=permanence_id, delivery_board_id=delivery_board_id
            )
            if qs.exists():
                label_delivery_board = "{}".format(_("Please, select a delivery point"))
                CustomerReceipt.objects.filter(
                    permanence_id=permanence_id, customer_id=self.customer_id
                ).update(status=ORDER_OPENED)
            else:
                label_delivery_board = "{}".format(
                    _("No delivery point is open for you. You can not place order.")
                )
                # IMPORTANT :
                # 1 / This prohibit to place an order into the customer UI
                # 2 / task_order.close_send_order will delete any CLOSED orders without any delivery point
                CustomerReceipt.objects.filter(
                    permanence_id=permanence_id, customer_id=self.customer_id
                ).update(status=ORDER_CLOSED)
        msg_delivery_point_html = """
                        {}<b><i>
                        <select name=\"delivery\" id=\"delivery\" onmouseover=\"show_select_delivery_list_ajax({})\" onchange=\"delivery_ajax()\" class=\"form-control\">
                        <option value=\"{}\" selected>{}</option>
                        </select>
                        </i></b>
                        """.format(
            _("Delivery point"),
            delivery_board_id,
            delivery_board_id,
            label_delivery_board,
        )
        return msg_delivery_point_html

    @transaction.atomic
    def confirm_order(self):
        if not self.is_order_confirm_send:
            # Change of confirmation status
            from repanier_v2.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(customer_invoice__id=self.id).update(
                qty_confirmed=F("qty")
            )
        self.is_order_confirm_send = True

    def cancel_confirm_order(self):
        if self.is_order_confirm_send:
            # Change of confirmation status
            self.is_order_confirm_send = False
            return True
        else:
            # No change of confirmation status
            return False

    @transaction.atomic
    def set_delivery_context(self, delivery_board=None):
        """
        Calculate
            (1) keep a valid delivery (with default as self.customer.delivery_point) or None
            (2) based on delivery.delivery_point calculate
                self.customer_charged
                self.price_list_multiplier
                self.delivery_transport
                self.delivery_min_transport
                self.status
            (3) if needed, create an invoice for the group

        """
        if self.is_group:
            return
        if delivery_board is None:
            if self.permanence.with_delivery_point:
                qs = self.customer.get_available_deliveries_qs(
                    permanence_id=self.permanence_id
                )
                valid_delivery_board = qs.first()
            else:
                valid_delivery_board = None
        else:
            assert self.permanence.with_delivery_point is True
            assert self.permanence_id == delivery_board.permanence_id
            valid_delivery_board = delivery_board

        if valid_delivery_board is None:
            status = self.permanence.status
        else:
            status = valid_delivery_board.status

        self.delivery = valid_delivery_board
        self.status = status

        if self.delivery is None:
            # Receipt of a customer who is not part of a group and does not have a delivery point
            self.customer_charged = self.customer
            self.sales_tariff_margin = self.customer.custom_tariff_margin
            self.display_sales_tariff = True
            self.delivery_transport = DECIMAL_ZERO
            self.delivery_min_transport = DECIMAL_ZERO
            self.is_group = False
        else:
            delivery_point = self.delivery.delivery_point
            customer_responsible = delivery_point.customer_responsible
            if customer_responsible is None or not customer_responsible.is_group:
                # Receipt  of a customer who is not part of a group and does have a delivery point
                self.customer_charged = self.customer
                self.sales_tariff_margin = self.customer.custom_tariff_margin
                self.display_sales_tariff = True
                self.delivery_transport = delivery_point.transport
                self.delivery_min_transport = delivery_point.min_transport
                self.is_group = False
            else:
                if self.customer_id != customer_responsible.id:
                    # Receipt of a customer belonging to a group
                    self.customer_charged = customer_responsible
                    self.sales_tariff_margin = customer_responsible.custom_tariff_margin
                    self.display_sales_tariff = (
                        customer_responsible.display_group_tariff
                    )
                    self.delivery_transport = REPANIER_MONEY_ZERO
                    self.delivery_min_transport = REPANIER_MONEY_ZERO
                    self.is_group = False
                    # Receipt of the group
                    customer_invoice_charged = CustomerReceipt.objects.filter(
                        permanence_id=self.permanence_id,
                        customer_id=customer_responsible.id,
                    )
                    if not customer_invoice_charged.exists():
                        CustomerReceipt.objects.create(
                            permanence_id=self.permanence_id,
                            customer_id=customer_responsible.id,
                            status=status,
                            customer_charged_id=customer_responsible.id,
                            sales_tariff_margin=customer_responsible.custom_tariff_margin,
                            display_sales_tariff=True,
                            delivery_transport=delivery_point.transport,
                            delivery_min_transport=delivery_point.min_transport,
                            is_order_confirm_send=True,  # None ?
                            is_group=True,
                            delivery=self.delivery,
                        )
                else:
                    assert self.is_group
                    assert self.customer_id == customer_responsible.id

    def set_total(self):
        #
        # return :
        # - at_customer_tariff
        # - at_sales_tariff
        # - tax_at_purchase_tariff
        # - deposit
        # - transport

        from repanier_v2.models.purchase import PurchaseWoReceiver

        if self.is_group:
            qs = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_invoice__customer_charged_id=self.customer_id,
            )
        else:
            qs = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_invoice_id=self.id,
            )
        result_set = qs.aggregate(
            at_customer_tariff=Sum(
                "at_customer_tariff",
                output_field=DecimalField(
                    max_digits=7, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            at_sales_tariff=Sum(
                "at_sales_tariff",
                output_field=DecimalField(
                    max_digits=7, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            tax_at_sales_tariff=Sum(
                "tax_at_sales_tariff",
                output_field=DecimalField(
                    max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            deposit=Sum(
                "deposit",
                output_field=DecimalField(
                    max_digits=7, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )

        self.at_customer_tariff.amount = (
            result_set["at_customer_tariff"] or DECIMAL_ZERO
        )
        self.at_sales_tariff.amount = result_set["at_sales_tariff"] or DECIMAL_ZERO
        self.tax_at_sales_tariff.amount = (
            result_set["tax_at_sales_tariff"] or DECIMAL_ZERO
        )
        self.deposit.amount = result_set["deposit"] or DECIMAL_ZERO

        # Calculate the transport
        self.transport.amount = DECIMAL_ZERO
        if self.delivery_transport.amount > DECIMAL_ZERO:
            if self.at_sales_tariff.amount > DECIMAL_ZERO:
                if self.delivery_min_transport.amount == DECIMAL_ZERO:
                    self.transport.amount = self.delivery_transport.amount
                elif self.at_sales_tariff.amount < self.delivery_min_transport.amount:
                    self.transport.amount = min(
                        self.delivery_min_transport.amount
                        - self.at_sales_tariff.amount,
                        self.delivery_transport.amount,
                    )

        self.at_sales_tariff.amount += self.transport.amount

        if settings.REPANIER_SETTINGS_ROUND_INVOICES:
            self.at_sales_tariff.amount = round_gov_be(self.at_sales_tariff.amount)

    def set_next_balance(self, payment_date):
        from repanier_v2.models.bank_account import BankAccount

        self.date_previous_balance = self.customer.date_balance
        self.date_next_balance = payment_date
        self.next_balance = self.previous_balance = self.customer.balance

        bank_in = DECIMAL_ZERO
        bank_out = DECIMAL_ZERO
        for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            customer_id=self.customer_id,
            producer__isnul=True,
            operation_date__lte=payment_date,
        ):
            bank_in += bank_account.bank_amount_in.amount
            bank_out += bank_account.bank_amount_out.amount

            bank_account.customer_invoice_id = self.id
            bank_account.permanence_id = self.permanence_id
            bank_account.save()

        self.bank_in.amount = bank_in
        self.bank_out.amount = bank_out
        self.next_balance.amount -= self.balance_invoiced.amount + bank_in - bank_out

    def cancel_if_unconfirmed(self, permanence, send_mail=True):
        if (
            settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            and not self.is_order_confirm_send
            and self.has_purchase
        ):
            if send_mail:
                from repanier_v2.email.email_order import export_order_2_1_customer

                filename = "{}-{}.xlsx".format(_("Canceled order"), permanence)

                export_order_2_1_customer(
                    self.customer, filename, permanence, cancel_order=True
                )

            from repanier_v2.models.purchase import PurchaseWoReceiver

            purchase_qs = PurchaseWoReceiver.objects.filter(
                customer_invoice_id=self.id, is_box_content=False
            )

            for a_purchase in purchase_qs.select_related("customer"):
                create_or_update_one_cart_item(
                    customer=a_purchase.customer,
                    offer_item_id=a_purchase.offer_item_id,
                    q_order=DECIMAL_ZERO,
                    batch_job=True,
                    comment=_("Qty not confirmed : {}").format(
                        number_format(a_purchase.qty, 4)
                    ),
                )

    objects = CustomerReceiptQuerySet.as_manager()

    def __str__(self):
        return f"{self.customer}, {self.permanence}"

    class Meta:
        verbose_name = _("Customer invoice")
        verbose_name_plural = _("Customers invoices")
        db_table = "repanier_c_receipt"
        unique_together = (("order", "customer"),)


class ProducerReceiptQuerySet(ReceiptQuerySet):
    def do_not_invoice(self, permanence_id: int, **kwargs):
        return self.filter(
            permanence_id=permanence_id,
            invoice_sort_order__isnull=True,
            is_to_be_paid=False,
            **kwargs,
        )

    def to_be_invoiced(self, permanence_id: int, **kwargs):
        return self.filter(
            permanence_id=permanence_id,
            invoice_sort_order__isnull=True,
            is_to_be_paid=True,
            **kwargs,
        )

    def last_producer_invoice(self, pk: int, producer_login_uuid: str, **kwargs):
        if pk == 0:
            return self.filter(
                producer__login_uuid=producer_login_uuid,
                invoice_sort_order__isnull=False,
            ).order_by("-invoice_sort_order")
        return self.filter(
            id=pk,
            producer__login_uuid=producer_login_uuid,
            invoice_sort_order__isnull=False,
        )

    def previous_producer_invoice(self, producer_invoice: ProducerReceipt):
        return self.filter(
            producer_id=producer_invoice.producer_id,
            invoice_sort_order__isnull=False,
            invoice_sort_order__lt=producer_invoice.invoice_sort_order,
        ).order_by("-invoice_sort_order")

    def next_producer_invoice(self, producer_invoice: ProducerReceipt):
        return self.filter(
            producer_id=producer_invoice.producer_id,
            invoice_sort_order__isnull=False,
            invoice_sort_order__gt=producer_invoice.invoice_sort_order,
        ).order_by("invoice_sort_order")


class ProducerReceipt(Receipt):
    producer = models.ForeignKey(
        "Producer",
        verbose_name=_("Producer"),
        # related_name='producer_invoice',
        on_delete=models.PROTECT,
    )
    purchase_price = ModelMoneyField(
        _("Purchase tariff"), max_digits=7, decimal_places=2, default=DECIMAL_ZERO
    )
    to_be_invoiced = models.BooleanField(
        default=False,
    )

    @classmethod
    def get_or_create(cls, permanence_id, producer_id):
        producer_invoice = ProducerReceipt.objects.filter(
            permanence_id=permanence_id, producer_id=producer_id
        ).first()
        if producer_invoice is None:
            producer_invoice = ProducerReceipt.create(permanence_id, producer_id)
        elif producer_invoice.invoice_sort_order is None:
            # if not already invoiced, update all totals
            producer_invoice.set_total()
            # 	delta_price_with_tax
            # 	delta_vat
            # 	total_vat
            # 	total_deposit
            # 	total_price_with_tax
            # 	transport = f(total_price_with_tax, transport, min_transport)
            producer_invoice.save()
        return producer_invoice

    @classmethod
    def create(cls, permanence_id, producer_id):
        producer_invoice = ProducerReceipt.objects.create(
            permanence_id=permanence_id,
            producer_id=producer_id,
            #
            #
            is_order_confirm_send=False,
            invoice_sort_order=None,
            # 	date_previous_balance = undefined (today)
            # 	previous_balance = undefined (DECIMAL_ZERO)
            # 	date_balance = undefined (today)
            # 	balance = undefined (DECIMAL_ZERO)
        )
        return producer_invoice

    def set_total(self):
        #
        # return :
        # - at_purchase_tariff
        # - tax_at_purchase_tariff
        # - deposit
        # - transport

        from repanier_v2.models.purchase import PurchaseWoReceiver

        result_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id,
            producer_id=self.producer_id,
        ).aggregate(
            at_purchase_tariff=Sum(
                "at_purchase_tariff",
                output_field=DecimalField(
                    max_digits=7, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            tax_at_purchase_tariff=Sum(
                "tax_at_purchase_tariff",
                output_field=DecimalField(
                    max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            deposit=Sum(
                "deposit",
                output_field=DecimalField(
                    max_digits=7, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )

        self.at_purchase_tariff.amount = (
            result_set["at_purchase_tariff"] or DECIMAL_ZERO
        )
        self.tax_at_purchase_tariff.amount = (
            result_set["tax_at_purchase_tariff"] or DECIMAL_ZERO
        )
        self.deposit.amount = result_set["deposit"] or DECIMAL_ZERO
        self.transport.amount = DECIMAL_ZERO

        if settings.REPANIER_SETTINGS_ROUND_INVOICES:
            self.at_purchase_tariff.amount = round_gov_be(
                self.at_purchase_tariff.amount
            )

    def get_negative_previous_balance(self):
        return -self.previous_balance

    def get_negative_balance(self):
        return -self.balance

    def set_next_balance(self, payment_date):
        from repanier_v2.models.bank_account import BankAccount

        self.date_previous_balance = self.producer.date_balance
        self.date_next_balance = payment_date
        self.next_balance = self.previous_balance = self.producer.balance

        bank_in = DECIMAL_ZERO
        bank_out = DECIMAL_ZERO
        for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            producer_id=self.producer_id,
            customer__isnul=True,
            operation_date__lte=payment_date,
        ):
            bank_in += bank_account.bank_amount_in.amount
            bank_out += bank_account.bank_amount_out.amount

            bank_account.customer_invoice_id = self.id
            bank_account.permanence_id = self.permanence_id
            bank_account.save()

        self.bank_in.amount = bank_in
        self.bank_out.amount = bank_out
        self.next_balance.amount -= self.balance_calculated.amount + bank_in - bank_out

    def get_order_json(self):
        a_producer = self.producer
        json_dict = {}
        if a_producer.minimum_order_value.amount > DECIMAL_ZERO:
            ratio = (
                self.balance_calculated.amount / a_producer.minimum_order_value.amount
            )
            if ratio >= DECIMAL_ONE:
                ratio = 100
            else:
                ratio *= 100
            json_dict["#order_procent{}".format(a_producer.id)] = "{}%".format(
                number_format(ratio, 0)
            )
        return json_dict

    objects = ProducerReceiptQuerySet.as_manager()

    def __str__(self):
        return f"{self.producer}, {self.permanence}"

    class Meta:
        verbose_name = _("Producer invoice")
        verbose_name_plural = _("Producers invoices")
        db_table = "repanier_p_receipt"
        unique_together = (("order", "producer"),)


class CustomerProducerReceipt(models.Model):
    order = models.ForeignKey(
        "Order", on_delete=models.PROTECT, null=True, default=None, db_index=True
    )
    customer = models.ForeignKey(
        "Customer", verbose_name=_("Customer"), on_delete=models.PROTECT
    )
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    purchase_price = ModelMoneyField(
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
    )

    def get_html_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return format_html("<b>{}</b>", self.total_purchase_with_tax)
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = _("Producer amount invoiced")
    get_html_producer_price_purchased.admin_order_field = "total_purchase_with_tax"

    def __str__(self):
        return f"{self.producer}, {self.customer}"

    class Meta:
        db_table = "repanier_cxp_receipt"
        unique_together = (("order", "customer", "producer"),)


# class CustomerSend(CustomerProducerReceipt):
#     def __str__(self):
#         return f"{self.producer}, {self.customer}"
#
#     class Meta:
#         proxy = True
#         verbose_name = _("Customer")
#         verbose_name_plural = _("Customers")

