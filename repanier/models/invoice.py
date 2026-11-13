import datetime

from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import F, Sum, Q, DecimalField
from django.template.loader import render_to_string
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.db import models
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.const import (
    DECIMAL_ONE, DECIMAL_ZERO, EMPTY_STRING, LUT_BANK_NOTE, SaleStatus
)
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.models.deliveryboard import DeliveryBoard
from repanier.tools import create_or_update_one_cart_item, round_gov_be


class Invoice(models.Model):
    permanence = models.ForeignKey(
        "Permanence", verbose_name=_("Sale"), on_delete=models.PROTECT, db_index=True
    )
    status = models.CharField(
        max_length=3,
        choices=SaleStatus.choices,
        default=SaleStatus.PLANNED,
        verbose_name=_("Status"),
    )
    date_previous_balance = models.DateField(
        _("Date previous balance"), default=datetime.date.today
    )
    previous_balance = ModelRepanierMoneyField(
        _("Previous balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    # Calculated with Purchase
    total_price_with_tax = ModelRepanierMoneyField(
        _("Accounted for incl. VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    delta_price_with_tax = ModelRepanierMoneyField(
        _("Total amount"),
        help_text=_("Purchase to add amount incl. VAT"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    delta_transport = ModelRepanierMoneyField(
        _("Shipping cost"),
        help_text=_("Transport to add"),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    total_vat = ModelRepanierMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=9, decimal_places=4
    )
    delta_vat = ModelRepanierMoneyField(
        _("VAT to add"), default=DECIMAL_ZERO, max_digits=9, decimal_places=4
    )
    total_deposit = ModelRepanierMoneyField(
        _("Deposit"),
        help_text=_("Surcharge"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    bank_amount_in = ModelRepanierMoneyField(
        _("Cash in"),
        help_text=_("Payment on the account"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    bank_amount_out = ModelRepanierMoneyField(
        _("Cash out"),
        help_text=_("Payment from the account"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    date_balance = models.DateField(_("Balance date"), default=datetime.date.today)
    balance = ModelRepanierMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )

    def get_delta_price_with_tax(self):
        return self.delta_price_with_tax.amount

    def get_abs_delta_price_with_tax(self):
        return (
            -self.delta_price_with_tax
            if self.delta_price_with_tax.amount < DECIMAL_ZERO
            else self.delta_price_with_tax
        )

    def calculate_order_rounding(self):
        if settings.REPANIER_SETTINGS_ROUND_INVOICES:
            total_price = (
                self.total_price_with_tax.amount
                + self.delta_price_with_tax.amount
                + self.delta_transport.amount
            )
            total_price_gov_be = round_gov_be(total_price)
            self.delta_price_with_tax.amount += total_price_gov_be - total_price

    def __str__(self):
        return _("Accounting entry")

    class Meta:
        abstract = True


class CustomerInvoice(Invoice):
    customer = models.ForeignKey(
        "Customer", verbose_name=_("Customer"), on_delete=models.PROTECT
    )
    customer_charged = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        related_name="invoices_paid",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        db_index=True,
    )
    delivery = models.ForeignKey(
        "DeliveryBoard",
        verbose_name=_("Delivery board"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.PROTECT,
    )
    # IMPORTANT: default = True -> for the order form, to display nothing at the begin of the order
    # is_order_confirm_send and total_price_with_tax = 0 --> display nothing
    # otherwise display
    # - send a mail with the order to me
    # - confirm the order (if REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER) and send a mail with the order to me
    # - mail send to XYZ
    # - order confirmed (if REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER) and mail send to XYZ
    is_order_confirm_send = models.BooleanField(
        _("Confirmation of the order send"), choices=settings.LUT_CONFIRM, default=False
    )
    invoice_sort_order = models.IntegerField(
        _("Accounting entry sort order"), default=None, blank=True, null=True, db_index=True
    )
    price_list_multiplier = models.DecimalField(
        _(
            "Delivery point coefficient applied to the producer tariff to calculate the customer tariff"
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    transport = ModelRepanierMoneyField(
        _("Shipping cost"),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    min_transport = ModelRepanierMoneyField(
        _("Minimum order amount for free shipping cost"),
        help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    is_group = models.BooleanField(_("Group"), default=False)
    # Membership fee snapshot: the renewal date the customer had BEFORE
    # close_order() forced the fee. Revert flows (cancel_invoice,
    # cancel_delivery) restore the customer renewal date from it;
    # restore_delivery and a re-invoicing re-apply the extension from it.
    membership_fee_valid_until_save = models.DateField(
        _("Membership fee valid until, before this permanence"),
        default=None,
        blank=True,
        null=True,
    )

    def cancel_membership_fee_extension(self):
        """Restore the renewal date the customer had before close_order()
        forced the membership fee.

        No-op when the fee was never forced (no snapshot). Never shortens
        a date extended by another permanence: the update only fires when
        the current date is still the one this permanence computed."""
        from repanier.models.customer import Customer

        if self.membership_fee_valid_until_save is not None:
            Customer.objects.filter(
                id=self.customer_id,
                membership_fee_valid_until__gt=self.membership_fee_valid_until_save,
            ).update(
                membership_fee_valid_until=self.membership_fee_valid_until_save
            )

    def restore_membership_fee_extension(self):
        """Re-apply the membership extension computed at close time, when
        a cancellation has been cancelled. Idempotent: in the normal flow
        close_order() already extended the date, and the update only fires
        when the current date is the snapshot itself."""
        from repanier.models.customer import Customer

        if self.membership_fee_valid_until_save is not None:
            valid_until = Customer.compute_membership_fee_valid_until(
                self.membership_fee_valid_until_save
            )
            Customer.objects.filter(
                id=self.customer_id,
                membership_fee_valid_until__lt=valid_until,
            ).update(membership_fee_valid_until=valid_until)

    def get_abs_delta_vat(self):
        return abs(self.delta_vat)

    def get_total_price_with_tax(self, customer_charged=False):
        if self.customer_id == self.customer_charged_id:
            return (
                self.total_price_with_tax
                + self.delta_price_with_tax
                + self.delta_transport
            )
        else:
            if self.status < SaleStatus.INVOICED or not customer_charged:
                return self.total_price_with_tax
            else:
                return self.customer_charged

    def get_total_price_wo_tax(self):
        return self.get_total_price_with_tax() - self.get_total_tax()

    def get_total_tax(self):
        # round to 2 decimals
        return RepanierMoney(self.total_vat.amount + self.delta_vat.amount)

    def is_pending(self):
        return self.status < SaleStatus.CLOSED

    def is_invoiced(self):
        return self.status == SaleStatus.INVOICED

    def is_archived(self):
        return self.status == SaleStatus.ARCHIVED
    @classmethod
    def get_or_create_invoice(cls, permanence_id, customer_id, status):
        customer_invoice = CustomerInvoice.objects.filter(
            permanence_id=permanence_id, customer_id=customer_id
        ).first()
        if customer_invoice is None:
            customer_invoice = CustomerInvoice.objects.create(
                permanence_id=permanence_id,
                customer_id=customer_id,
                customer_charged_id=customer_id,
                status=status,
            )
            customer_invoice.set_order_delivery(delivery=None)
            customer_invoice.save()
        return customer_invoice

    @property
    def has_purchase(self):
        if (
            self.total_price_with_tax.amount != DECIMAL_ZERO
            or self.is_order_confirm_send
        ):
            return True

        from repanier.models.purchase import PurchaseWoReceiver

        result_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id, customer_invoice_id=self.id
        ).aggregate(
            qty_ordered=Sum(
                "quantity_ordered",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            qty_invoiced=Sum(
                "quantity_invoiced",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
        )
        qty_ordered = (
            result_set["qty_ordered"]
            if result_set["qty_ordered"] is not None
            else DECIMAL_ZERO
        )
        qty_invoiced = (
            result_set["qty_invoiced"]
            if result_set["qty_invoiced"] is not None
            else DECIMAL_ZERO
        )
        return qty_ordered != DECIMAL_ZERO or qty_invoiced != DECIMAL_ZERO

    def is_confirm_disabled(self, permanence):
        """The confirm step is locked until the basket contains an order
        and, on a permanence with delivery points, a delivery is chosen.
        Everything is locked once the permanence is no longer open."""
        if self.status == SaleStatus.OPENED:
            return (
                permanence.with_delivery_point and self.delivery is None
            ) or not self.has_purchase
        return True

    def get_html_my_order_confirmation(
        self,
        permanence,
        is_basket=False,
        basket_message=EMPTY_STRING,
        delivery_message=EMPTY_STRING,
    ):
        """Render the order confirmation box.

        The markup lives in repanier/order_confirmation_box.html; the
        AJAX callers inject the returned fragment into
        #span_btn_confirm_order. Displayed on the basket page, or on the
        order page when the group forces the confirmation step.
        """
        if not is_basket and not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            # If REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER,
            # then permanence.with_delivery_point is also True
            confirm_box = EMPTY_STRING
        else:
            confirm_button_label = EMPTY_STRING
            if self.is_order_confirm_send:
                # Nothing to confirm: only the basket page keeps a link
                # to the history.
                show_history = is_basket
                show_confirm_basket = False
                show_goto_basket = False
                email_sent_to = self.customer.my_order_confirmation_email_send_to()
            else:
                show_history = True
                show_confirm_basket = is_basket
                # The confirm button (basket page) and the go to basket
                # link (order page) replace each other.
                show_goto_basket = bool(
                    settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
                    and not is_basket
                )
                if is_basket:
                    if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                        confirm_button_label = _(
                            "➜ Confirm this order and receive an email containing its summary."
                        )
                    else:
                        confirm_button_label = _(
                            "Receive an email containing this order summary."
                        )
                email_sent_to = EMPTY_STRING

            confirm_box = render_to_string(
                "repanier/order_confirmation_box.html",
                {
                    "basket_message": basket_message,
                    # Produced by repanier itself, not user input: keep it
                    # as html.
                    "delivery_message": mark_safe(delivery_message),
                    "is_order_confirm_send": self.is_order_confirm_send,
                    "email_sent_to": email_sent_to,
                    "warning_unconfirmed_orders": bool(
                        settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
                        and not self.is_order_confirm_send
                        and self.status == SaleStatus.OPENED
                    ),
                    "confirm_basket": show_confirm_basket,
                    "goto_basket": show_goto_basket,
                    "confirm_disabled": self.is_confirm_disabled(permanence),
                    "confirm_button_label": confirm_button_label,
                    "show_history": show_history,
                    "order_url": permanence.get_order_url(),
                    "customer_id": self.customer.id,
                },
            )
        return {"#span_btn_confirm_order": mark_safe(confirm_box)}

    def get_html_select_delivery_point(self, permanence, status, is_basket=False):
        if status == SaleStatus.OPENED and permanence.with_delivery_point:
            has_delivery_points = True
            if self.delivery is not None:
                label = self.delivery.get_delivery_customer_display()
            else:
                if self.customer.group is not None:
                    qs = DeliveryBoard.objects.filter(
                        Q(
                            permanence_id=permanence.id,
                            delivery_point__group_id=self.customer.group_id,
                            status=SaleStatus.OPENED,
                        )
                        | Q(
                            permanence_id=permanence.id,
                            delivery_point__group__isnull=True,
                            status=SaleStatus.OPENED,
                        )
                    )

                else:
                    qs = DeliveryBoard.objects.filter(
                        permanence_id=permanence.id,
                        delivery_point__group__isnull=True,
                        status=SaleStatus.OPENED,
                    )

                if qs.exists():
                    label = _("Please select a delivery point")
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id, customer_id=self.customer_id
                    ).update(status=SaleStatus.OPENED)
                else:
                    has_delivery_points = False
                    label = _(
                        "No delivery point is open for you. You cannot place an order."
                    )
                    # IMPORTANT :
                    # 1 / This prohibits to place an order into the customer UI
                    # 2 / task_order.close_send_order will delete any CLOSED orders without any delivery point
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id, customer_id=self.customer_id
                    ).update(status=SaleStatus.CLOSED)

            if self.customer_id != self.customer_charged_id:
                msg_transport = EMPTY_STRING
            else:
                if self.transport.amount <= DECIMAL_ZERO:
                    msg_transport = EMPTY_STRING
                elif self.min_transport.amount > DECIMAL_ZERO:
                    msg_transport = _(
                        "The shipping costs for this delivery point amount to "
                        "%(transport)s for orders of less than %(min_transport)s."
                    ) % {
                        "transport": self.transport,
                        "min_transport": self.min_transport,
                    }
                else:
                    msg_transport = _(
                        "The shipping costs for this delivery point amount to "
                        "%(transport)s."
                    ) % {"transport": self.transport}

            # The markup lives in repanier/bootstrap5_delivery_dropdown.html:
            # a Bootstrap 5 dropdown, like the quantity ones.
            msg_delivery = render_to_string(
                "repanier/bootstrap5_delivery_dropdown.html",
                {
                    "permanence_id": permanence.id,
                    "label": label,
                    "has_delivery_points": has_delivery_points,
                    "msg_transport": msg_transport,
                    "is_basket": is_basket,
                },
            )
        else:
            msg_delivery = EMPTY_STRING
        return msg_delivery

    @transaction.atomic
    def confirm_order(self):
        if not self.is_order_confirm_send:
            # Change of confirmation status
            from repanier.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(customer_invoice__id=self.id).update(
                quantity_confirmed=F("quantity_ordered")
            )
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
        # Don't use delivery_id because it won't reload customer_invoice.delivery
        # Important
        # If it's an invoice for a group:
        #   self.is_group == True
        #   self.price_list_multiplier == DECIMAL_ONE
        #   self.customer_charged_id == self.customer_id
        # Else:
        #   self.price_list_multiplier may vary
        #   If it's an invoice for a member of a group :
        #       self.customer_charged_id != self.customer_id
        #       self.customer_charged_id == owner of the group
        #       self.price_list_multiplier == self.customer_charged.price_list_multiplier
        #   Else:
        #       self.customer_charged_id == self.customer_id
        #       self.price_list_multiplier == self.customer.price_list_multiplier
        if delivery is None:
            delivery_point = None
            if self.permanence.with_delivery_point:
                # If the customer is member of a group set the group as default delivery point
                group_id = self.customer.group_id
                if group_id is not None:
                    default_delivery = DeliveryBoard.objects.filter(
                        permanence_id=self.permanence_id,
                        delivery_point__group_id=group_id,
                    ).first()
                    if default_delivery is not None:
                        delivery = default_delivery
                        delivery_point = default_delivery.delivery_point
        else:
            delivery_point = delivery.delivery_point
        self.delivery = delivery

        if delivery_point is None:
            self.customer_charged = self.customer
            self.price_list_multiplier = self.customer.price_list_multiplier
            self.transport.amount = DECIMAL_ZERO
            self.min_transport.amount = DECIMAL_ZERO
        else:
            group = delivery_point.group
            if group is None:
                self.customer_charged = self.customer
                self.price_list_multiplier = self.customer.price_list_multiplier
                self.transport = delivery_point.transport
                self.min_transport = delivery_point.min_transport
            else:
                assert self.customer_id != group.id, "A group may not place an order"
                self.customer_charged = group
                self.price_list_multiplier = DECIMAL_ONE
                self.transport.amount = DECIMAL_ZERO
                self.min_transport.amount = DECIMAL_ZERO

                customer_invoice_charged = CustomerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_id=group.id,
                )
                if not customer_invoice_charged.exists():
                    CustomerInvoice.objects.create(
                        permanence_id=self.permanence_id,
                        customer_id=group.id,
                        status=self.status,
                        customer_charged_id=group.id,
                        price_list_multiplier=self.price_list_multiplier,
                        transport=self.transport,
                        min_transport=self.min_transport,
                        is_order_confirm_send=True,
                        is_group=True,
                        delivery=delivery,
                    )

    def calculate_order_amount(self):
        from repanier.models.purchase import PurchaseWoReceiver

        self.delta_price_with_tax.amount = DECIMAL_ZERO
        self.delta_vat.amount = DECIMAL_ZERO

        if self.is_group:
            query_set = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_invoice__customer_charged_id=self.customer_id,
            )
        else:
            query_set = PurchaseWoReceiver.objects.filter(
                permanence_id=self.permanence_id,
                customer_id=self.customer_id,
            )

        result_set = query_set.aggregate(
            customer_vat=Sum(
                "customer_vat",
                output_field=DecimalField(
                    max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            deposit=Sum(
                "deposit",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            selling_price=Sum(
                "selling_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        self.total_price_with_tax.amount = (
            result_set["selling_price"]
            if result_set["selling_price"] is not None
            else DECIMAL_ZERO
        )
        self.total_vat.amount = (
            result_set["customer_vat"]
            if result_set["customer_vat"] is not None
            else DECIMAL_ZERO
        )
        self.total_deposit.amount = (
            result_set["deposit"] if result_set["deposit"] is not None else DECIMAL_ZERO
        )

        self.calculate_order_transport()
        self.calculate_order_rounding()

    def calculate_order_transport(self):
        if self.customer_id == self.customer_charged_id:
            # It's an invoice for a group, or of a customer who is not member of a group :
            #   self.customer_charged_id = self.customer_id
            #   self.price_list_multiplier may vary
            if self.transport.amount != DECIMAL_ZERO:
                total_price_with_tax = (
                    self.total_price_with_tax.amount + self.delta_price_with_tax.amount
                )
                if total_price_with_tax != DECIMAL_ZERO:
                    if self.min_transport.amount == DECIMAL_ZERO:
                        self.delta_transport.amount = self.transport.amount
                    elif total_price_with_tax < self.min_transport.amount:
                        self.delta_transport.amount = min(
                            self.min_transport.amount - total_price_with_tax,
                            self.transport.amount,
                        )
                else:
                    self.delta_transport.amount = DECIMAL_ZERO
            else:
                self.delta_transport.amount = DECIMAL_ZERO
        else:
            self.delta_transport.amount = DECIMAL_ZERO

    def create_child(self, new_permanence):
        if self.customer_id != self.customer_charged_id:
            # An invoice must exist for the customer who will be charged
            new_customer_charged_invoice = CustomerInvoice.objects.filter(
                permanence_id=new_permanence.id,
                customer_id=self.customer_charged_id,
            ).only("id")

            if not new_customer_charged_invoice.exists():
                old_customer_charged_invoice = CustomerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_charged_id,
                ).first()
                CustomerInvoice.objects.create(
                    permanence_id=new_permanence.id,
                    customer_id=self.customer_charged_id,
                    customer_charged_id=self.customer_charged_id,
                    delivery_id=old_customer_charged_invoice.delivery_id,
                    is_order_confirm_send=old_customer_charged_invoice.is_order_confirm_send,
                    price_list_multiplier=old_customer_charged_invoice.price_list_multiplier,
                    transport=DECIMAL_ZERO,  # Do not invoice transport twice
                    min_transport=DECIMAL_ZERO,  # Do not invoice transport twice
                    is_group=old_customer_charged_invoice.is_group,
                    status=new_permanence.status,
                )
        return CustomerInvoice.objects.create(
            permanence_id=new_permanence.id,
            customer_id=self.customer_id,
            customer_charged_id=self.customer_charged_id,
            delivery_id=self.delivery_id,
            is_order_confirm_send=self.is_order_confirm_send,
            price_list_multiplier=self.price_list_multiplier,
            transport=DECIMAL_ZERO,  # Do not invoice transport twice
            min_transport=DECIMAL_ZERO,  # Do not invoice transport twice
            is_group=self.is_group,
            status=new_permanence.status,
        )

    def cancel_if_unconfirmed(self, send_mail=True):
        if (
            settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            and not self.is_order_confirm_send
            and self.has_purchase
        ):
            if send_mail:
                from repanier.email.email_order import export_order_2_1_customer

                filename = "{}-{}.xlsx".format(_("Cancelled order"), self.permanence)

                export_order_2_1_customer(
                    self.customer, filename, self.permanence, cancel_order=True
                )

            self.cancel()

    def cancel(self):
        from repanier.models.purchase import PurchaseWoReceiver

        purchase_qs = PurchaseWoReceiver.objects.filter(customer_invoice_id=self.id)
        for a_purchase in purchase_qs.select_related("customer"):
            create_or_update_one_cart_item(
                customer=a_purchase.customer,
                offer_item_id=a_purchase.offer_item_id,
                q_order=DECIMAL_ZERO,
                batch_job=True,
                comment=_("Qty not confirmed : {}").format(
                    number_format(a_purchase.quantity_ordered, 4)
                ),
            )

    def get_delivery_display(self):
        if self.delivery is None:
            return EMPTY_STRING
        return self.delivery.get_delivery_display()

    get_delivery_display.short_description = _("Delivery point")

    def __str__(self):
        return "{}, {}".format(self.customer, self.permanence)

    class Meta:
        verbose_name = _("Accounting entry")
        verbose_name_plural = _("Accounting entries")
        unique_together = (("permanence", "customer"),)


class ProducerInvoice(Invoice):
    producer = models.ForeignKey(
        "Producer",
        verbose_name=_("Producer"),
        # related_name='producer_invoice',
        on_delete=models.PROTECT,
    )

    to_be_paid = models.BooleanField(
        _("To be booked"), choices=LUT_BANK_NOTE, default=False
    )
    calculated_invoiced_balance = ModelRepanierMoneyField(
        _("Amount due to the producer as calculated by Repanier"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    to_be_invoiced_balance = ModelRepanierMoneyField(
        _("Amount claimed by the producer"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    invoice_sort_order = models.IntegerField(
        _("Accounting entry sort order"), default=None, blank=True, null=True, db_index=True
    )
    invoice_reference = models.CharField(
        _("Accounting reference"), max_length=100, blank=True, default=EMPTY_STRING
    )

    def get_negative_previous_balance(self):
        return -self.previous_balance

    def get_negative_balance(self):
        return -self.balance

    def get_total_price_with_tax(self):
        return (
            self.total_price_with_tax + self.delta_price_with_tax + self.delta_transport
        )

    def get_order_json(self):
        a_producer = self.producer
        json_dict = {}
        if a_producer.minimum_order_value.amount > DECIMAL_ZERO:
            ratio = (
                self.total_price_with_tax.amount / a_producer.minimum_order_value.amount
            )
            if ratio >= DECIMAL_ONE:
                ratio = 100
            else:
                ratio *= 100
            json_dict["#order_procent{}".format(a_producer.id)] = "{}%".format(
                number_format(ratio, 0)
            )
        return json_dict

    @classmethod
    def get_or_create_invoice(cls, permanence_id, producer_id, status):
        producer_invoice = ProducerInvoice.objects.filter(
            permanence_id=permanence_id, producer_id=producer_id
        ).first()
        if producer_invoice is None:
            producer_invoice = ProducerInvoice.objects.create(
                permanence_id=permanence_id,
                producer_id=producer_id,
                status=status,
            )
        return producer_invoice

    def calculate_order_amount(self):
        from repanier.models.purchase import PurchaseWoReceiver

        self.delta_price_with_tax.amount = DECIMAL_ZERO
        self.delta_vat.amount = DECIMAL_ZERO

        query_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id,
            producer_id=self.producer_id,
        )

        result_set = query_set.aggregate(
            producer_vat=Sum(
                "producer_vat",
                output_field=DecimalField(
                    max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            deposit=Sum(
                "deposit",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            purchase_price=Sum(
                "purchase_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        self.total_price_with_tax.amount = (
            result_set["purchase_price"]
            if result_set["purchase_price"] is not None
            else DECIMAL_ZERO
        )
        self.total_vat.amount = (
            result_set["producer_vat"]
            if result_set["producer_vat"] is not None
            else DECIMAL_ZERO
        )
        self.total_deposit.amount = (
            result_set["deposit"] if result_set["deposit"] is not None else DECIMAL_ZERO
        )

        # self.calculate_order_rounding()

    def __str__(self):
        return "{}, {}".format(self.producer, self.permanence)

    class Meta:
        verbose_name = _("Accounting entry")
        verbose_name_plural = _("Accounting entries")
        unique_together = (("permanence", "producer"),)


class CustomerProducerInvoice(models.Model):
    customer = models.ForeignKey(
        "Customer", verbose_name=_("Customer"), on_delete=models.PROTECT
    )
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    permanence = models.ForeignKey(
        "Permanence", verbose_name=_("Sale"), on_delete=models.PROTECT, db_index=True
    )
    # Calculated with Purchase
    total_purchase_with_tax = ModelRepanierMoneyField(
        _("Producer amount booked"),
        help_text=_("Total selling amount vat included"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )
    # Calculated with Purchase
    total_selling_with_tax = ModelRepanierMoneyField(
        _("Accounted to the customer incl. VAT"),
        help_text=_("Total selling amount vat included"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
    )

    def get_html_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return format_html("<b>{}</b>", self.total_purchase_with_tax)
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = _("Line amount")
    get_html_producer_price_purchased.admin_order_field = "total_purchase_with_tax"

    @classmethod
    def get_or_create_invoice(cls, permanence_id, customer_id, producer_id):
        customer_producer_invoice = CustomerProducerInvoice.objects.filter(
            permanence_id=permanence_id,
            customer_id=customer_id,
            producer_id=producer_id,
        ).first()
        if customer_producer_invoice is None:
            customer_producer_invoice = CustomerProducerInvoice.objects.create(
                permanence_id=permanence_id,
                customer_id=customer_id,
                producer_id=producer_id,
            )
        return customer_producer_invoice

    def calculate_order_amount(self):
        from repanier.models.purchase import PurchaseWoReceiver

        query_set = PurchaseWoReceiver.objects.filter(
            permanence_id=self.permanence_id,
            producer_id=self.producer_id,
            customer_id=self.customer_id,
        )

        result_set = query_set.aggregate(
            # deposit=Sum(
            #     "deposit",
            #     output_field=DecimalField(
            #         max_digits=8, decimal_places=2, default=DECIMAL_ZERO
            #     ),
            # ),
            purchase_price=Sum(
                "purchase_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
            selling_price=Sum(
                "selling_price",
                output_field=DecimalField(
                    max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )
        self.total_purchase_with_tax.amount = (
            result_set["purchase_price"]
            if result_set["purchase_price"] is not None
            else DECIMAL_ZERO
        )
        self.total_selling_with_tax.amount = (
            result_set["selling_price"]
            if result_set["selling_price"] is not None
            else DECIMAL_ZERO
        )

    def __str__(self):
        return "{}, {}".format(self.producer, self.customer)

    class Meta:
        unique_together = (("permanence", "customer", "producer"),)


class CustomerSend(CustomerProducerInvoice):
    def __str__(self):
        return "{}, {}".format(self.producer, self.customer)

    class Meta:
        proxy = True
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
