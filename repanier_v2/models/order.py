import datetime
import logging
from typing import List

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool

from repanier_v2.const import *
from repanier_v2.middleware import add_filter
from repanier_v2.models.bank_account import BankAccount
from repanier_v2.models.customer import Customer
from repanier_v2.models.deliveryboard import DeliveryBoard
from repanier_v2.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier_v2.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier_v2.models.order_task import OrderTask
from repanier_v2.models.producer import Producer
from repanier_v2.models.product import Product
from repanier_v2.picture.const import SIZE_L
from repanier_v2.picture.fields import RepanierPictureField
from repanier_v2.tools import cap, create_or_update_one_purchase, debug_parameters

logger = logging.getLogger(__name__)

refresh_status = [
    ORDER_WAIT_FOR_OPEN,
    ORDER_WAIT_FOR_CLOSED,
    ORDER_CLOSED,
    ORDER_WAIT_FOR_SEND,
    ORDER_WAIT_FOR_INVOICED,
]


class Order(models.Model):
    short_name = models.CharField(_("Offer name"), max_length=50, blank=True)
    description = HTMLField(
        _("Offer description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        help_text=_(
            "This message is send by mail to all customers when opening the order or on top."
        ),
        blank=True,
        default=EMPTY_STRING,
    )
    status = models.CharField(
        _("Status"),
        max_length=3,
        choices=LUT_ORDER_STATUS,
        default=ORDER_PLANNED,
    )
    order_date = models.DateField(_("Date"), db_index=True)
    payment_date = models.DateField(
        _("Payment date"), blank=True, null=True, db_index=True
    )
    producers = models.ManyToManyField(
        "Producer", verbose_name=_("Producers"), blank=True
    )
    boxes = models.ManyToManyField("Box", verbose_name=_("Boxes"), blank=True)

    with_delivery_point = models.BooleanField(_("With delivery point"), default=False)
    automatically_closed = models.BooleanField(
        _("Closing AND automatically transmitting orders"), default=False
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_ORDER_STATUS,
        default=ORDER_PLANNED,
        verbose_name=_("Highest status"),
    )
    master_order = models.ForeignKey(
        "Order",
        verbose_name=_("Master order"),
        related_name="child_order",
        blank=True,
        null=True,
        default=None,
        on_delete=models.PROTECT,
        db_index=True,
    )
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"), default=None, blank=True, null=True
    )
    # canceled_invoice_sort_order is used in admin.order_closed to display cancelled orders in the correct order
    canceled_invoice_sort_order = models.IntegerField(
        _("Canceled invoice sort order"), default=None, blank=True, null=True
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="order",
        size=SIZE_L,
    )
    gauge = models.IntegerField(default=0, editable=False)

    @cached_property
    def get_html_producers_with_download(self):
        return self.get_html_producers(with_download=True)

    get_html_producers_with_download.short_description = _("Offers from")

    @cached_property
    def get_html_producers_without_download(self):
        return self.get_html_producers(with_download=False)

    get_html_producers_without_download.short_description = _("Offers from")

    def get_html_producers(self, with_download):

        producers: List[str] = []
        if self.status == ORDER_PLANNED:
            download_url = add_filter(
                reverse("admin:order-export-offer", args=[self.id])
            )
            button_download = format_html(
                '<span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" href="{}" data-repanier_v2-tooltip="{}"><i class="fas fa-download"></i></a></span>',
                download_url,
                _("Export"),
            )
            if len(self.producers.all()) > 0:
                changelist_url = reverse("admin:repanier_product_changelist")
                for p in self.producers.all():
                    producers.append(
                        '<a href="{}?producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            p.id,
                            p.short_name.replace(" ", "&nbsp;"),
                        )
                    )
        elif self.status == ORDER_OPENED:
            close_offeritem_changelist_url = reverse(
                "admin:repanier_offeritemclosed_changelist"
            )
            download_url = add_filter(
                reverse("admin:order-export-producer-opened-order", args=[self.id])
            )
            button_download = format_html(
                '<span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" href="{}" data-repanier_v2-tooltip="{}"><i class="fas fa-download"></i></a></span>',
                download_url,
                _("Export"),
            )

            for p in self.producers.all().only("id"):
                pi = (
                    ProducerInvoice.objects.filter(producer_id=p.id, order_id=self.id)
                    .order_by("?")
                    .first()
                )
                if pi is not None:
                    if pi.status == ORDER_OPENED:
                        label = (
                            "{} ({}) ".format(p.short_name, pi.balance_calculated)
                        ).replace(" ", "&nbsp;")
                        offeritem_changelist_url = close_offeritem_changelist_url
                    else:
                        label = (
                            "{} ({}) {}".format(
                                p.short_name,
                                pi.balance_calculated,
                                settings.LOCK_UNICODE,
                            )
                        ).replace(" ", "&nbsp;")
                        offeritem_changelist_url = close_offeritem_changelist_url
                else:
                    label = ("{} ".format(p.short_name)).replace(" ", "&nbsp;")
                    offeritem_changelist_url = close_offeritem_changelist_url
                producers.append(
                    '<a href="{}?order={}&producer={}">{}</a>'.format(
                        offeritem_changelist_url, self.id, p.id, label
                    )
                )

        elif self.status in [ORDER_SEND, ORDER_INVOICED, ORDER_ARCHIVED]:
            if self.status == ORDER_SEND:
                download_url = add_filter(
                    reverse("admin:order-export-producer-closed-order", args=[self.id])
                )
                button_download = format_html(
                    '<span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" href="{}" data-repanier_v2-tooltip="{}"><i class="fas fa-download"></i></a></span>',
                    download_url,
                    _("Export"),
                )
            else:
                button_download = EMPTY_STRING
            send_offeritem_changelist_url = reverse(
                "admin:repanier_offeritemsend_changelist"
            )
            send_customer_changelist_url = reverse(
                "admin:repanier_customersend_changelist"
            )
            for pi in (
                ProducerInvoice.objects.filter(order_id=self.id)
                .select_related("producer")
                .order_by("producer")
            ):
                if pi.status == ORDER_SEND:
                    if pi.producer.invoice_by_basket:
                        changelist_url = send_customer_changelist_url
                    else:
                        changelist_url = send_offeritem_changelist_url
                    # Important : no target="_blank"
                    label = "{} ({})".format(
                        pi.producer.short_name, pi.balance_calculated
                    )
                    producers.append(
                        '<a href="{}?order={}&producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            self.id,
                            pi.producer_id,
                            label.replace(" ", "&nbsp;"),
                        )
                    )
                else:
                    if pi.reference:
                        if (
                            pi.balance_invoiced != DECIMAL_ZERO
                            or pi.balance_calculated != DECIMAL_ZERO
                        ):
                            label = "{} ({} - {})".format(
                                pi.producer.short_name,
                                pi.balance_invoiced,
                                cap(pi.reference, 15),
                            )
                        else:
                            label = "{} ({})".format(
                                pi.producer.short_name,
                                cap(pi.reference, 15),
                            )
                    else:
                        if (
                            pi.balance_invoiced != DECIMAL_ZERO
                            or pi.balance_calculated != DECIMAL_ZERO
                        ):
                            label = "{} ({})".format(
                                pi.producer.short_name,
                                pi.balance_invoiced,
                            )
                        else:
                            continue
                    # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                    # Such that they can be accessed by the producer and by the staff
                    producers.append(
                        '<a href="{}" target="_blank">{}</a>'.format(
                            reverse(
                                "repanier_v2:producer_invoice_view",
                                args=(pi.id, pi.producer.login_uuid),
                            ),
                            label.replace(" ", "&nbsp;"),
                        )
                    )
        else:
            button_download = EMPTY_STRING
            producers = [
                p.short_name
                for p in Producer.objects.filter(producerinvoice__order_id=self.id).only(
                    "short_name"
                )
            ]
        if len(producers) > 0:
            if not with_download:
                button_download = EMPTY_STRING
            if len(producers) > 3:
                msg_html = """
        <div id="id_hide_producers_{}" style="display:block;" class="repanier_v2-button-row">{}
            <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                    onclick="document.getElementById('id_show_producers_{}').style.display = 'block'; document.getElementById('id_hide_producers_{}').style.display = 'none'; return false;">
                <i
                        class="far fa-eye"></i></a></span>
        </div>
        <div id="id_show_producers_{}" style="display:none;" class="repanier_v2-button-row">{}
            <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                    onclick="document.getElementById('id_show_producers_{}').style.display = 'none'; document.getElementById('id_hide_producers_{}').style.display = 'block'; return false;">
                <i
                        class="far fa-eye-slash"></i></a></span>
            <p><br><div class="wrap-text">{}</div></p>
        </div>
                """.format(
                    self.id,
                    button_download,
                    _("Show"),
                    self.id,
                    self.id,
                    self.id,
                    button_download,
                    _("Hide"),
                    self.id,
                    self.id,
                    ", ".join(producers),
                )
            else:
                msg_html = """
        <div style="display:block;" class="repanier_v2-button-row">
            {}<p><br><div class="wrap-text">{}</div></p>
        </div>
                """.format(
                    button_download,
                    ", ".join(producers),
                )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No offer")))

    @cached_property
    def get_html_customers_with_download(self):
        return self.get_html_customers(with_download=True)

    get_html_customers_with_download.short_description = _("Orders from")

    @cached_property
    def get_html_customers_without_download(self):
        return self.get_html_customers(with_download=False)

    get_html_customers_without_download.short_description = _("Orders from")

    def get_html_customers(self, with_download):
        customers: List[str] = []
        if self.status in [ORDER_OPENED, ORDER_SEND]:
            changelist_url = reverse("admin:repanier_purchase_changelist")
            if self.status == ORDER_OPENED:
                download_url = add_filter(
                    reverse("admin:order-export-customer-opened-order", args=[self.id])
                )
            else:
                download_url = add_filter(
                    reverse("admin:order-export-customer-closed-order", args=[self.id])
                )
            button_download = format_html(
                '<span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" href="{}" data-repanier_v2-tooltip="{}"><i class="fas fa-download"></i></a></span> ',
                download_url,
                _("Export"),
            )

            delivery_save = None
            for ci in (
                CustomerInvoice.objects.filter(order_id=self.id)
                .select_related("customer")
                .order_by("delivery", "customer")
            ):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        customers.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        customers.append("<br><br>--")
                total_price_with_tax = ci.balance_calculated
                # if ci.is_order_confirm_send:
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_name,
                    "-"
                    if ci.is_group or total_price_with_tax == DECIMAL_ZERO
                    else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : no target="_blank"
                customers.append(
                    '<a href="{}?order={}&customer={}">{}</a>'.format(
                        changelist_url,
                        self.id,
                        ci.customer_id,
                        label.replace(" ", "&nbsp;"),
                    )
                )
        elif self.status in [ORDER_INVOICED, ORDER_ARCHIVED]:
            button_download = EMPTY_STRING
            delivery_save = None
            for ci in (
                CustomerInvoice.objects.filter(order_id=self.id)
                .select_related("customer")
                .order_by("delivery", "customer")
            ):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        customers.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        customers.append("<br><br>--")
                total_price_with_tax = ci.balance_calculated
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_name,
                    "-"
                    if total_price_with_tax == DECIMAL_ZERO
                    else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                # Such that they can be accessed by the customer and by the staff
                customers.append(
                    '<a href="{}" target="_blank">{}</a>'.format(
                        reverse(
                            "repanier_v2:customer_invoice_view",
                            args=(ci.id, ci.customer_id),
                        ),
                        label.replace(" ", "&nbsp;"),
                    )
                )
        else:
            button_download = EMPTY_STRING
            customers = [
                c.short_name
                for c in Customer.objects.filter(customerinvoice__order_id=self.id).only(
                    "short_name"
                )
            ]
        if len(customers) > 0:
            if not with_download:
                button_download = EMPTY_STRING
            if len(customers) > 3:
                msg_html = """
    <div id="id_hide_customers_{}" style="display:block;" class="repanier_v2-button-row">{}
        <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                onclick="document.getElementById('id_show_customers_{}').style.display = 'block'; document.getElementById('id_hide_customers_{}').style.display = 'none'; return false;">
            <i
                    class="far fa-eye"></i></a></span>
    </div>
    <div id="id_show_customers_{}" style="display:none;" class="repanier_v2-button-row">{}
        <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                onclick="document.getElementById('id_show_customers_{}').style.display = 'none'; document.getElementById('id_hide_customers_{}').style.display = 'block'; return false;">
            <i
                    class="far fa-eye-slash"></i></a></span>
        <p><br><div class="wrap-text">{}</div></p>
    </div>
                """.format(
                    self.id,
                    button_download,
                    _("Show"),
                    self.id,
                    self.id,
                    self.id,
                    button_download,
                    _("Hide"),
                    self.id,
                    self.id,
                    ", ".join(customers),
                )
            else:
                msg_html = """
    <div style="display:block;" class="repanier_v2-button-row">
        {}<p><br><div class="wrap-text">{}</div></p>
    </div>
                """.format(
                    button_download,
                    ", ".join(customers),
                )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No purchase")))

    get_html_customers.short_description = _("Purchases by")

    def get_html_purchases_changelist_link(self):
        link = "{url}?order={pk}".format(
            url=reverse("admin:repanier_purchase_changelist"), pk=self.pk
        )

        return mark_safe(
            '<a href="{link}">{msg}</a>'.format(link=link, msg=_("Manage purchases"))
        )

    get_html_purchases_changelist_link.short_description = _("Manage purchases")

    @cached_property
    def get_html_board(self):
        sa_set = OrderTask.objects.filter(
            order=self, task__rght=F("task__lft") + 1
        )
        first_board = True
        board = EMPTY_STRING
        if sa_set:
            for sa in sa_set:
                r_link = EMPTY_STRING
                r = sa.task
                if r:
                    r_url = add_filter(
                        reverse("admin:repanier_task_change", args=(r.id,))
                    )
                    r_link = (
                        '<a href="'
                        + r_url
                        + '" target="_blank">'
                        + r.short_name.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                c_link = EMPTY_STRING
                c = sa.customer
                if c:
                    c_url = add_filter(
                        reverse("admin:repanier_customer_change", args=(c.id,))
                    )
                    c_link = (
                        '&nbsp;->&nbsp;<a href="'
                        + c_url
                        + '" target="_blank">'
                        + c.short_name.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                if not first_board:
                    board += "<br>"
                board += r_link + c_link
                first_board = False
        if not first_board:
            # At least one role is defined in the order activities
            msg_html = """
    <div id="id_hide_board_{}" style="display:block;" class="repanier_v2-button-row">
        <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                onclick="document.getElementById('id_show_board_{}').style.display = 'block'; document.getElementById('id_hide_board_{}').style.display = 'none'; return false;">
            <i
                    class="far fa-eye"></i></a></span>
    </div>
    <div id="id_show_board_{}" style="display:none;" class="repanier_v2-button-row">
        <span class="repanier_v2-a-container"><a class="repanier_v2-a-tooltip repanier_v2-a-info" data-repanier_v2-tooltip="{}"
                onclick="document.getElementById('id_show_board_{}').style.display = 'none'; document.getElementById('id_hide_board_{}').style.display = 'block'; return false;">
            <i
                    class="far fa-eye-slash"></i></a></span>
        <p><br><div class="wrap-text">{}</div></p>
    </div>
            """.format(
                self.id,
                _("Show"),
                self.id,
                self.id,
                self.id,
                _("Hide"),
                self.id,
                self.id,
                board,
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No task")))

    get_html_board.short_description = _("Tasks")

    @transaction.atomic
    # @debug_parameters
    def set_status(
        self,
        old_status=None,
        new_status=None,
        everything=True,
        deliveries_id=(),
        update_payment_date=False,
        payment_date=None,
    ):
        if everything:
            order = (
                Order.objects.select_for_update()
                .filter(id=self.id, status=old_status)
                .exclude(status=new_status)
                .first()
            )
        else:
            order = (
                Order.objects.select_for_update()
                .filter(id=self.id)
                .exclude(status=new_status)
                .first()
            )
        if order is None:
            raise ValueError

        if self.with_delivery_point:
            qs = (
                DeliveryBoard.objects.filter(order_id=self.id)
                .exclude(status=new_status)
                .order_by("?")
            )
            if not everything:
                qs = qs.filter(id__in=deliveries_id)
            for delivery_point in qs:
                delivery_point.set_status(new_status)
            if everything:
                ProducerInvoice.objects.filter(order_id=self.id).order_by("?").update(
                    status=new_status
                )
        else:
            from repanier_v2.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(order_id=self.id).exclude(
                status=new_status
            ).order_by("?").update(status=new_status)
            CustomerInvoice.objects.filter(order_id=self.id).order_by("?").update(
                status=new_status
            )
            ProducerInvoice.objects.filter(order_id=self.id).order_by("?").update(
                status=new_status
            )
        if everything:
            now = timezone.now().date()
            order.is_updated_on = self.is_updated_on = now
            order.status = self.status = new_status
            if self.highest_status < new_status:
                order.highest_status = self.highest_status = new_status
            if update_payment_date:
                if payment_date is None:
                    order.payment_date = self.payment_date = now
                else:
                    order.payment_date = self.payment_date = payment_date
        # Unlock order
        order.save()
        menu_pool.clear(all=True)
        cache.clear()

    @transaction.atomic
    def back_to_scheduled(self):
        self.producers.clear()
        for offer_item in (
            OfferItemWoReceiver.objects.filter(order_id=self.id, may_order=True)
            .order_by("producer_id")
            .distinct("producer_id")
        ):
            self.producers.add(offer_item.producer_id)
        OfferItemWoReceiver.objects.filter(order_id=self.id).update(may_order=False)

    @transaction.atomic
    def close_order(self, everything, deliveries_id=(), send_mail=True):
        from repanier_v2.globals import (
            REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION,
            REPANIER_SETTINGS_MEMBERSHIP_FEE,
        )

        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            # Cancel unconfirmed purchases whichever the producer is
            customer_invoice_qs = CustomerInvoice.objects.filter(
                order_id=self.id, is_order_confirm_send=False, status=self.status
            ).order_by("?")
            if self.with_delivery_point:
                customer_invoice_qs = customer_invoice_qs.filter(
                    delivery_id__in=deliveries_id
                )
            for customer_invoice in customer_invoice_qs:
                customer_invoice.cancel_if_unconfirmed(self, send_mail=send_mail)
        if everything:
            # Add membership fee
            if (
                REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION > 0
                and REPANIER_SETTINGS_MEMBERSHIP_FEE > 0
            ):
                membership_fee_product = (
                    Product.objects.filter(
                        order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE, is_active=True
                    )
                    .order_by("?")
                    .first()
                )
                membership_fee_product.producer_unit_price = (
                    REPANIER_SETTINGS_MEMBERSHIP_FEE
                )
                # Update the prices
                membership_fee_product.save()

                customer_invoice_qs = (
                    CustomerInvoice.objects.filter(
                        order_id=self.id, customer_charged_id=F("customer_id")
                    )
                    .select_related("customer")
                    .order_by("?")
                )
                if self.with_delivery_point:
                    customer_invoice_qs = customer_invoice_qs.filter(
                        delivery_id__in=deliveries_id
                    )

                for customer_invoice in customer_invoice_qs:
                    customer = customer_invoice.customer
                    if not customer.is_default:
                        # Should pay a membership fee
                        if customer.membership_fee_valid_until < self.order_date:
                            membership_fee_offer_item = (
                                membership_fee_product.get_or_create_offer_item(self)
                            )
                            self.producers.add(membership_fee_offer_item.producer_id)
                            create_or_update_one_purchase(
                                customer_id=customer.id,
                                offer_item=membership_fee_offer_item,
                                status=ORDER_OPENED,
                                q_order=1,
                                batch_job=True,
                                is_box_content=False,
                                comment=EMPTY_STRING,
                            )
                            membership_fee_valid_until = (
                                customer.membership_fee_valid_until
                                + relativedelta(
                                    months=int(
                                        REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION
                                    )
                                )
                            )
                            today = timezone.now().date()
                            if membership_fee_valid_until < today:
                                # For or occasional customer
                                membership_fee_valid_until = today
                            # customer.save(update_fields=['membership_fee_valid_until', ])
                            # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
                            Customer.objects.filter(id=customer.id).order_by(
                                "?"
                            ).update(
                                membership_fee_valid_until=membership_fee_valid_until
                            )
        if everything or self.with_delivery_point:
            # Add deposit products to be able to return them
            customer_qs = Customer.objects.filter(
                may_order=True,
                customerinvoice__order_id=self.id,
                is_default=False,
            ).order_by("?")
            if self.with_delivery_point:
                customer_qs = customer_qs.filter(
                    customerinvoice__delivery_id__in=deliveries_id
                )
            for customer in customer_qs:
                offer_item_qs = OfferItem.objects.filter(
                    order_id=self.id, order_unit=PRODUCT_ORDER_UNIT_DEPOSIT
                ).order_by("?")
                # if not everything:
                #     offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
                for offer_item in offer_item_qs:
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=ORDER_OPENED,
                        q_order=1,
                        batch_job=True,
                        is_box_content=False,
                        comment=EMPTY_STRING,
                    )
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=ORDER_OPENED,
                        q_order=0,
                        batch_job=True,
                        is_box_content=False,
                        comment=EMPTY_STRING,
                    )

    @transaction.atomic
    @debug_parameters
    def invoice(self, payment_date):
        from repanier_v2.models.purchase import PurchaseWoReceiver

        bank_account_balance = BankAccount.get_balance()
        default_producer = Producer.get_or_create_default()
        default_customer = Customer.get_or_create_default()

        self.set_status(old_status=ORDER_SEND, new_status=ORDER_WAIT_FOR_INVOICED)

        default_customer_invoice = CustomerInvoice.get_or_create(
            order_id=self.id, customer_id=default_customer.id
        )
        default_customer_invoice.set_next_balance(payment_date)
        default_customer_invoice.save()

        if ProducerInvoice.objects.do_not_invoice(order_id=self.id).exists():
            # Move the producers not invoiced into a new order
            producers_to_keep = list(
                ProducerInvoice.objects.to_be_invoiced(
                    order_id=self.id,
                ).values_list("producer_id", flat=True)
            )
            self.producers.clear()
            self.producers.add(*producers_to_keep)
            producers_to_move = list(
                ProducerInvoice.objects.do_not_invoice(
                    order_id=self.id,
                ).values_list("producer_id", flat=True)
            )
            customers_to_move = list(
                CustomerProducerInvoice.objects.filter(
                    order_id=self.id, producer_id__in=producers_to_move
                ).values_list("customer_id", flat=True)
            )
            new_order = self.create_child()
            new_order.producers.add(*producers_to_move)
            ProducerInvoice.objects.filter(
                order_id=self.id, producer_id__in=producers_to_move
            ).update(order_id=new_order.id, status=ORDER_SEND)
            CustomerProducerInvoice.objects.filter(
                order_id=self.id,
                producer_id__in=producers_to_move
                # Redundant : customer_id__in=customers_to_move
            ).order_by("?").update(order_id=new_order.id)
            OfferItemWoReceiver.objects.filter(
                order_id=self.id, producer_id__in=producers_to_move
            ).order_by("?").update(order_id=new_order.id)

            for old_customer_invoice in CustomerInvoice.objects.filter(
                order_id=self.id, customer_id__in=customers_to_move
            ).order_by("?"):
                new_customer_invoice = CustomerInvoice.get_or_create(
                    order_id=new_order.id,
                    customer_id=old_customer_invoice.customer_id,
                    delivery_board=old_customer_invoice.delivery,
                )

                PurchaseWoReceiver.objects.filter(
                    customer_invoice_id=old_customer_invoice.id,
                    producer_id__in=producers_to_move,
                ).order_by("?").update(
                    order_id=new_order.id,
                    customer_invoice_id=new_customer_invoice.id,
                    status=new_order.status,
                )
            for new_customer_invoice in CustomerInvoice.objects.filter(
                order_id=new_order
            ).order_by("?"):
                new_customer_invoice.set_total()
                new_customer_invoice.save()

            new_order.set_status(old_status=ORDER_WAIT_FOR_INVOICED, new_status=ORDER_SEND)
            new_order.recalculate_order_amount(re_init=True)
            new_order.save()

        for customer_invoice in CustomerInvoice.objects.filter(
            order_id=self.id, customer_id=F("customer_charged_id")
        ).order_by("?"):
            customer_invoice.set_total()
            customer_invoice.save()

        self.recalculate_order_amount(re_init=True)
        self.save()

        for bank_account in (
            BankAccount.objects.select_for_update()
            .filter(
                customer_invoice__isnull=True,
                producer_invoice__isnull=True,
                customer__isnull=False,
                operation_date__lte=payment_date,
            )
            .order_by("?")
        ):
            CustomerInvoice.get_or_create(
                order_id=self.id, customer_id=bank_account.customer_id
            )
        for customer_invoice in CustomerInvoice.objects.filter(
            order_id=self.id
        ).order_by("?"):
            customer_invoice.set_next_balance(payment_date)
            customer_invoice.save()
            Customer.objects.filter(id=customer_invoice.customer_id).update(
                date_balance=payment_date,
                balance=customer_invoice.balance,
            )

        for bank_account in (
            BankAccount.objects.select_for_update()
            .filter(
                customer_invoice__isnull=True,
                producer_invoice__isnull=True,
                producer__isnull=False,
                operation_date__lte=payment_date,
            )
            .order_by("?")
        ):
            ProducerInvoice.get_or_create(
                order_id=self.id, producer_id=bank_account.producer_id
            )
        for producer_invoice in ProducerInvoice.objects.filter(
            order_id=self.id
        ).order_by("?"):
            producer_invoice.set_next_balance(payment_date)
            producer_invoice.save()
            Producer.objects.filter(id=producer_invoice.producer_id).update(
                date_balance=payment_date, balance=producer_invoice.balance
            )

        self.generate_bank_payment(payment_date=payment_date)

        BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by(
            "?"
        ).update(operation_status=BANK_NOT_LATEST_TOTAL)
        # Important : Create a new bank total for this order even if there is no bank movement
        bank_account = BankAccount.objects.create(
            order_id=self.id,
            producer=None,
            customer=None,
            operation_date=payment_date,
            operation_status=BANK_LATEST_TOTAL,
            operation_comment=cap(str(self), 100),
            bank_amount_in=bank_account_balance
            if bank_account_balance >= DECIMAL_ZERO
            else DECIMAL_ZERO,
            bank_amount_out=-bank_account_balance
            if bank_account_balance < DECIMAL_ZERO
            else DECIMAL_ZERO,
            customer_invoice=None,
            producer_invoice=None,
        )

        ProducerInvoice.objects.filter(order_id=self.id).order_by("?").update(
            invoice_sort_order=bank_account.id
        )
        CustomerInvoice.objects.filter(order_id=self.id).order_by("?").update(
            invoice_sort_order=bank_account.id
        )
        Order.objects.filter(id=self.id).order_by("?").update(
            invoice_sort_order=bank_account.id, canceled_invoice_sort_order=None
        )

        new_status = (
            ORDER_INVOICED
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING
            else ORDER_ARCHIVED
        )
        self.set_status(
            old_status=ORDER_WAIT_FOR_INVOICED,
            new_status=new_status,
            update_payment_date=True,
            payment_date=payment_date,
        )

    @transaction.atomic
    def cancel_invoice(self, last_bank_account_total):
        self.set_status(
            old_status=ORDER_INVOICED,
            new_status=ORDER_WAIT_FOR_CANCEL_INVOICE,
        )
        CustomerInvoice.objects.filter(order_id=self.id).order_by("?").update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )
        for customer_invoice in CustomerInvoice.objects.filter(
            order_id=self.id
        ).order_by("?"):
            # customer = customer_invoice.customer
            # customer.balance = customer_invoice.previous_balance
            # customer.date_balance = customer_invoice.date_previous_balance
            # customer.save(update_fields=['balance', 'date_balance'])
            # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
            Customer.objects.filter(id=customer_invoice.customer_id).order_by(
                "?"
            ).update(
                balance=customer_invoice.previous_balance,
                date_balance=customer_invoice.date_previous_balance,
            )
            BankAccount.objects.filter(
                customer_invoice_id=customer_invoice.id
            ).order_by("?").update(customer_invoice=None)
        ProducerInvoice.objects.filter(
            order_id=self.id, producer__is_default=False
        ).order_by("?").update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            delta_price_with_tax=DECIMAL_ZERO,
            delta_vat=DECIMAL_ZERO,
            transport=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )
        # Important : Restore delta from delivery points added into invoice.confirm_order()
        ProducerInvoice.objects.filter(
            order_id=self.id, producer__is_default=True
        ).order_by("?").update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )

        for producer_invoice in ProducerInvoice.objects.filter(
            order_id=self.id
        ).order_by("?"):
            Producer.objects.filter(id=producer_invoice.producer_id).order_by(
                "?"
            ).update(
                balance=producer_invoice.previous_balance,
                date_balance=producer_invoice.date_previous_balance,
            )
            BankAccount.objects.all().filter(
                producer_invoice_id=producer_invoice.id
            ).order_by("?").update(producer_invoice=None)
        # IMPORTANT : Do not update stock when canceling
        last_bank_account_total.delete()
        bank_account = (
            BankAccount.objects.filter(customer=None, producer=None)
            .order_by("-id")
            .first()
        )
        if bank_account is not None:
            bank_account.operation_status = BANK_LATEST_TOTAL
            bank_account.save()
        # Delete also all payments recorded to producers, bank profit, bank tax
        # Delete also all compensation recorded to producers
        BankAccount.objects.filter(
            order_id=self.id,
            operation_status__in=[
                BANK_CALCULATED_INVOICE,
                BANK_PROFIT,
                BANK_TAX,
                BANK_MEMBERSHIP_FEE,
            ],
        ).order_by("?").delete()
        Order.objects.filter(id=self.id).order_by("?").update(
            canceled_invoice_sort_order=F("invoice_sort_order"), invoice_sort_order=None
        )
        self.set_status(old_status=ORDER_WAIT_FOR_CANCEL_INVOICE, new_status=ORDER_SEND)

    @transaction.atomic
    def cancel_delivery(self):
        self.set_status(old_status=ORDER_SEND, new_status=ORDER_CANCELLED)
        bank_account = BankAccount.get_closest_to(self.order_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    @transaction.atomic
    def archive(self):
        self.set_status(old_status=ORDER_SEND, new_status=ORDER_ARCHIVED)
        bank_account = BankAccount.get_closest_to(self.order_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    def duplicate(self, dates):
        creation_counter = 0
        short_name = self.short_name
        for date in dates[:56]:
            # Limit to 56 weeks
            same_exists = self.check_if_same_exists(date, short_name, cur_language)
            if not same_exists:
                creation_counter += 1
                new_order = Order.objects.create(order_date=date)
                self.duplicate_short_name(new_order)
                self.duplicate_order_board(new_order)
                self.duplicate_delivery_board(new_order)
                self.duplicate_producers(new_order)
        return creation_counter

    def create_child(self):
        new_child_order = Order.objects.create(
            order_date=self.order_date,
            master_order_id=self.id,
            status=self.status,
        )
        self.duplicate_short_name(new_child_order)
        self.duplicate_order_board_and_registration(new_child_order)
        self.duplicate_delivery_board(new_child_order)
        return new_child_order

    def check_if_same_exists(self, date, short_name):
        if short_name != EMPTY_STRING:
            # Mandatory because of Parler
            same_exists = (
                Order.objects.filter(
                    order_date=date,
                    short_name=short_name,
                )
                .exists()
            )
        else:
            same_exists = False
            for existing_order in Order.objects.filter(order_date=date):
                short_name = existing_order.short_name
                same_exists = short_name == EMPTY_STRING
                if same_exists:
                    break
        return same_exists

    def duplicate_short_name(self, new_order):
        new_order.short_name = self.short_name

    def duplicate_producers(self, new_order):
        for a_producer in self.producers.all():
            new_order.producers.add(a_producer)

    def duplicate_delivery_board(self, new_order):
        for delivery_board in DeliveryBoard.objects.filter(order=self):
            new_delivery_board = DeliveryBoard.objects.create(
                order=new_order, delivery_point=delivery_board.delivery_point
            )
            new_delivery_board.delivery_comment = delivery_board.delivery_comment

    def duplicate_order_board(self, new_order):
        for sa in OrderTask.objects.filter(order=self).order_by("?"):
            OrderTask.objects.create(
                order=new_order,
                order_date=new_order.order_date,
                order_role=sa.task,
            )

    def duplicate_order_board_and_registration(self, new_order):
        for order_board in OrderTask.objects.filter(order=self).order_by("?"):
            OrderTask.objects.create(
                order=new_order,
                order_date=new_order.order_date,
                order_role=order_board.order_role,
                customer=order_board.customer,
                is_registered_on=order_board.is_registered_on,
            )

    def generate_bank_payment(self, payment_date: datetime):

        for producer_invoice in ProducerInvoice.objects.filter(
            order_id=self.id, invoice_sort_order__isnull=True
        ).select_related("producer"):
            # We have to pay something
            producer = producer_invoice.producer
            if producer_invoice.balance_invoiced.amount > DECIMAL_ZERO:

                if producer_invoice.reference:
                    operation_comment = producer_invoice.reference
                else:
                    if producer.is_default:
                        operation_comment = self.get_order_display()
                    else:
                        operation_comment = _(
                            "Delivery %(current_site)s - %(order)s. Thanks!"
                        ) % {
                            "current_site": settings.REPANIER_SETTINGS_GROUP_NAME,
                            "order": self.get_order_display(),
                        }

                BankAccount.objects.create(
                    order_id=None,
                    producer_id=producer.id,
                    customer=None,
                    operation_date=payment_date,
                    operation_status=BANK_CALCULATED_INVOICE,
                    operation_comment=cap(operation_comment, 100),
                    bank_amount_out=producer_invoice.balance_invoiced.amount,
                    customer_invoice=None,
                    producer_invoice=None,
                )

            delta = (
                producer_invoice.balance_invoiced.amount
                - producer_invoice.balance_calculated.amount
            ).quantize(TWO_DECIMALS)
            if delta != DECIMAL_ZERO:
                # Profit or loss for the group
                customer_buyinggroup = Customer.get_or_create_default()
                operation_comment = _("Correction %(producer)s") % {
                    "producer": producer.short_name
                }
                BankAccount.objects.create(
                    order_id=self.id,
                    producer=None,
                    customer_id=customer_buyinggroup.id,
                    operation_date=payment_date,
                    operation_status=BANK_PROFIT,
                    operation_comment=cap(operation_comment, 100),
                    bank_amount_in=-delta if delta < DECIMAL_ZERO else DECIMAL_ZERO,
                    bank_amount_out=delta if delta > DECIMAL_ZERO else DECIMAL_ZERO,
                    customer_invoice_id=None,
                    producer_invoice=None,
                )
            producer_invoice.balance.amount -= delta
            producer_invoice.save(update_fields=["balance"])
            producer.balance.amount -= delta
            producer.save(update_fields=["balance"])

        return

    def set_qty_invoiced(self):
        from repanier_v2.models.purchase import PurchaseWoReceiver

        for offer_item in OfferItem.objects.filter(
            order_id=self.id, order_unit=PRODUCT_ORDER_UNIT_PC_KG
        ).only("order_average_weight"):
            PurchaseWoReceiver.objects.filter(
                # status=ORDER_WAIT_FOR_SEND,
                offer_item_id=offer_item.id,
            ).update(qty=F("qty") * offer_item.order_average_weight)
        OfferItemWoReceiver.objects.filter(
            order_id=self.id, order_unit=PRODUCT_ORDER_UNIT_PC_KG
        ).order_by("?").update(order_unit=PRODUCT_ORDER_UNIT_KG)

    def recalculate_order_amount(self, offer_item_qs=None, re_init=False):
        from repanier_v2.models.purchase import Purchase

        if re_init:
            assert (
                offer_item_qs is None
            ), "offer_item_qs must be set to None when send_to_producer or re_init"
            ProducerInvoice.objects.filter(order_id=self.id).order_by("?").update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            CustomerInvoice.objects.filter(order_id=self.id).order_by("?").update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            CustomerProducerInvoice.objects.filter(order_id=self.id).order_by(
                "?"
            ).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO,
            )
            OfferItemWoReceiver.objects.filter(order_id=self.id).order_by("?").update(
                qty=DECIMAL_ZERO,
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO,
            )

        purchase_set = Purchase.objects.filter(order_id=self.id).order_by("?")
        if offer_item_qs is not None:
            purchase_set = purchase_set.filter(offer_item__in=offer_item_qs)

        for purchase in purchase_set:
            # Recalculate the total_price_with_tax of ProducerInvoice,
            # the total_price_with_tax of CustomerInvoice,
            # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
            # and qty_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
            if re_init:
                purchase.previous_qty = DECIMAL_ZERO
                purchase.previous_purchase_price = DECIMAL_ZERO
                purchase.previous_selling_price = DECIMAL_ZERO
                purchase.previous_producer_vat = DECIMAL_ZERO
                purchase.previous_customer_vat = DECIMAL_ZERO
                purchase.previous_deposit = DECIMAL_ZERO
            purchase.save()

        self.save()

    def reorder_purchases(self):
        from repanier_v2.models.purchase import Purchase

        # Order the purchases such that lower quantity are before larger quantity
        Purchase.objects.filter(order_id=self.id).update(
            qty_for_preparation_sort_order=DECIMAL_ZERO
        )
        Purchase.objects.filter(
            order_id=self.id,
            offer_item__wrapped=False,
            offer_item__order_unit__in=[
                PRODUCT_ORDER_UNIT_KG,
                PRODUCT_ORDER_UNIT_PC_KG,
            ],
        ).update(qty_for_preparation_sort_order=F("qty"))

    def reorder_offer_items(self):
        from repanier_v2.models.offeritem import OfferItemWoReceiver

        # calculate the sort order of the order display screen
        offer_item_qs = OfferItemWoReceiver.objects.filter(order_id=self.id).order_by(
            "?"
        )

        i = 0
        reorder_queryset = offer_item_qs.filter(
            is_box=False
        ).order_by(
            "department",
            "long_name",
            "order_average_weight",
            "producer__short_name",
        )
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = (
                offer_item.order_sort_order
            ) = offer_item.preparation_sort_order = i
            offer_item.save()
            if i < 9999:
                i += 1
        # producer lists sort order : sort by reference if needed, otherwise sort by order_sort_order
        i = 9999
        reorder_queryset = offer_item_qs.filter(
            is_box=False,
            producer__sort_products_by_reference=True,
        ).order_by("department", "reference")
        for offer_item in reorder_queryset:
            offer_item.producer_sort_order = i
            offer_item.save()
            if i < 19999:
                i += 1
        # preparation lists sort order
        i = -9999
        reorder_queryset = offer_item_qs.filter(
            is_box=True
        ).order_by(
            "customer_unit_price",
            # "department__lft",
            "unit_deposit",
            "long_name",
        )
        # 'TranslatableQuerySet' object has no attribute 'desc'
        for offer_item in reorder_queryset:
            # display box on top
            offer_item.producer_sort_order = (
                offer_item.order_sort_order
            ) = offer_item.preparation_sort_order = i
            offer_item.save()
            if i < -1:
                i += 1

    @cached_property
    def get_html_new_products(self):
        assert self.status < ORDER_SEND
        result = []
        for a_producer in self.producers.all():
            current_products = list(
                OfferItemWoReceiver.objects.filter(
                    is_active=True,
                    may_order=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                    order_id=self.id,
                    producer=a_producer,
                )
                .values_list("product", flat=True)
                .order_by("?")
            )
            six_months_ago = timezone.now().date() - datetime.timedelta(days=6 * 30)
            previous_order = (
                Order.objects.filter(
                    status__gte=ORDER_SEND,
                    producers=a_producer,
                    order_date__gte=six_months_ago,
                )
                .order_by("-order_date", "status")
                .first()
            )
            if previous_order is not None:
                previous_products = list(
                    OfferItemWoReceiver.objects.filter(
                        is_active=True,
                        may_order=True,
                        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                        order_id=previous_order.id,
                        producer=a_producer,
                    )
                    .values_list("product", flat=True)
                    .order_by("?")
                )
                new_products = [
                    item for item in current_products if item not in previous_products
                ]
            else:
                new_products = current_products

            qs = OfferItemWoReceiver.objects.filter(
                order_id=self.id,
                product__in=new_products,
                translations__language_code=translation.get_language(),
            ).order_by("translations__order_sort_order")
            department_save = None
            for o in qs:
                if department_save != o.department:
                    if department_save is not None:
                        result.append("</ul></li>")
                    department_save = o.department
                    result.append("<li>{}<ul>".format(department_save))
                result.append(
                    "<li>{}</li>".format(o.get_long_name_with_producer(is_html=True))
                )
            if department_save is not None:
                result.append("</ul>")
        if result:
            return mark_safe("<ul>{}</ul>".format(EMPTY_STRING.join(result)))
        return EMPTY_STRING

    def get_html_status_display(self, force_refresh=True):
        need_to_refresh_status = force_refresh or self.status in refresh_status
        if self.with_delivery_point and self.status < ORDER_INVOICED:
            status_list = []
            status = None
            status_counter = 0
            for delivery in DeliveryBoard.objects.filter(order_id=self.id).order_by(
                "status", "id"
            ):
                need_to_refresh_status |= delivery.status in refresh_status
                if status != delivery.status:
                    status = delivery.status
                    status_counter += 1
                    status_list.append(
                        "<b>{}</b>".format(delivery.get_status_display())
                    )
                status_list.append(
                    "- {}".format(delivery.get_delivery_display(color=True))
                )
            message = "<br>".join(status_list)
        else:
            message = self.get_status_display()
        if need_to_refresh_status:
            url = reverse("repanier_v2:display_status", args=(self.id,))
            if force_refresh:
                # force self.gauge to 3 so that next call the guage will be set to 0
                self.gauge = 3
                progress = EMPTY_STRING
                delay = 1000
            else:
                progress = "{} ".format("◤◥◢◣"[self.gauge])  # "◴◷◶◵" "▛▜▟▙"
                self.gauge = (self.gauge + 1) % 4
                delay = 500
            self.save(update_fields=["gauge"])
            msg_html = """
                    <div class="wrap-text" id="id_get_status_{}">
                    <script type="text/javascript">
                        window.setTimeout(function(){{
                            django.jQuery.ajax({{
                                url: '{}',
                                cache: false,
                                async: true,
                                success: function (result) {{
                                    django.jQuery("#id_get_status_{}").html(result);
                                }}
                            }});
                        }}, {});
                    </script>
                    {}{}</div>
                """.format(
                self.id, url, self.id, delay, progress, message
            )

        else:
            msg_html = '<div class="wrap-text">{}</div>'.format(message)
        return mark_safe(msg_html)

    get_html_status_display.short_description = _("Status")

    def get_order_display(self):
        short_name = self.safe_translation_getter("short_name", any_language=True)
        if short_name:
            order_display = "{}".format(short_name)
        else:
            from repanier_v2.globals import REPANIER_SETTINGS_ORDER_ON_NAME

            order_display = "{}{}".format(
                REPANIER_SETTINGS_ORDER_ON_NAME,
                self.order_date.strftime(settings.DJANGO_SETTINGS_DATE),
            )
        return order_display

    def get_order_admin_display(self):
        return self.get_order_display()

    get_order_admin_display.short_description = _("Offers")

    def get_html_order_title_display(self):
        return self.get_html_order_display(align="vertical-align: bottom; ")

    def get_html_order_display(self, align=EMPTY_STRING):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
            if self.status == ORDER_OPENED:
                return "{} - {}".format(
                    self.get_order_display(), self.get_status_display()
                )
            else:
                return "{} - {}".format(self.get_order_display(), _("Orders closed"))
        else:
            if self.status == ORDER_OPENED:
                return mark_safe(
                    '<span class="fa fa-unlock" style="{}color:#cdff60"></span> {}'.format(
                        align, self.get_order_display()
                    )
                )
            else:
                return mark_safe(
                    '<span class="fa fa-lock" style="{}color:Tomato"></span> {}'.format(
                        align, self.get_order_display()
                    )
                )

    def get_html_order_card_display(self):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
            offer_description = Truncator(
                self.safe_translation_getter(
                    "offer_description", any_language=True, default=EMPTY_STRING
                )
            )
            return mark_safe(
                """
            <a href="{href}" class="card-body offer">
                <h4>{title}</h4>
                <div class="excerpt">{offer_description}</div>
            </a>
            """.format(
                    href=reverse("repanier_v2:order_view", args=(self.id,)),
                    title=self.get_html_order_display(),
                    offer_description=offer_description.words(30, html=True),
                )
            )
        return EMPTY_STRING

    def get_html_board_composition(self):
        from repanier_v2.models.order_task import OrderTask

        board_composition = []
        for task in OrderTask.objects.filter(order_id=self.id).order_by(
            "order_role__tree_id", "order_role__lft"
        ):
            member = task.get_html_board_member
            if member is not None:
                board_composition.append(member)

        return mark_safe("<br>".join(board_composition))

    def __str__(self):
        return self.get_order_display()

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

        index_together = [["order_date"]]


class OrderInPreparation(Order):
    class Meta:
        proxy = True
        verbose_name = _("Offer in preparation")
        verbose_name_plural = _("Offers in preparation")


class OrderClosed(Order):
    class Meta:
        proxy = True
        verbose_name = _("Billing offer")
        verbose_name_plural = _("Billing offers")
