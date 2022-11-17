import datetime
import logging

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db import transaction, connection
from django.db.models import F, Sum, DecimalField
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from repanier.const import *
from repanier.middleware import add_filter
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.offeritem import OfferItem, OfferItemReadOnly
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.picture.const import SIZE_L
from repanier.picture.fields import RepanierPictureField
from repanier.tools import (
    cap,
    create_or_update_one_purchase,
    get_repanier_template_name,
    debug_parameters,
)

logger = logging.getLogger(__name__)

refresh_status = [
    SaleStatus.WAIT_FOR_OPEN,
    SaleStatus.WAIT_FOR_CLOSED,
    SaleStatus.CLOSED,
    SaleStatus.WAIT_FOR_SEND,
    SaleStatus.WAIT_FOR_INVOICED,
]


class Permanence(models.Model):
    short_name_v2 = models.CharField(_("Offer name"), max_length=50, blank=True)
    offer_description_v2 = HTMLField(
        _("Offer description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        help_text=_(
            "This message is send by mail to all customers when opening the order or on top."
        ),
        blank=True,
        default=EMPTY_STRING,
    )
    invoice_description_v2 = HTMLField(
        _("Invoice description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        help_text=_(
            "This message is send by mail to all customers having bought something when closing the permanence."
        ),
        blank=True,
        default=EMPTY_STRING,
    )

    status = models.CharField(
        _("Status"),
        max_length=3,
        choices=SaleStatus.choices,
        default=SaleStatus.PLANNED,
    )
    permanence_date = models.DateField(_("Date"), db_index=True)
    payment_date = models.DateField(
        _("Payment date"), blank=True, null=True, db_index=True
    )
    producers = models.ManyToManyField(
        "Producer", verbose_name=_("Producers"), blank=True
    )

    with_delivery_point = models.BooleanField(_("With delivery point"), default=False)
    automatically_closed = models.BooleanField(
        _("Closing AND automatically transmitting orders"), default=False
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=SaleStatus.choices,
        default=SaleStatus.PLANNED,
        verbose_name=_("Highest status"),
    )
    master_permanence = models.ForeignKey(
        "Permanence",
        verbose_name=_("Master permanence"),
        related_name="child_permanence",
        blank=True,
        null=True,
        default=None,
        on_delete=models.PROTECT,
        db_index=True,
    )
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"), default=None, blank=True, null=True
    )
    # canceled_invoice_sort_order is used in admin.permanence_done to display the canceled permanence in correct order
    canceled_invoice_sort_order = models.IntegerField(
        _("Canceled invoice sort order"), default=None, blank=True, null=True
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="permanence",
        size=SIZE_L,
    )
    gauge = models.IntegerField(default=0, editable=False)

    @cached_property
    def get_producers_with_download(self):
        return self.get_producers(with_download=True)

    get_producers_with_download.short_description = _("Offers from")

    @cached_property
    def get_producers_without_download(self):
        return self.get_producers(with_download=False)

    get_producers_without_download.short_description = _("Offers from")

    def get_producers(self, with_download):
        if self.status == SaleStatus.PLANNED:
            download_url = add_filter(
                reverse("admin:permanence-export-offer", args=[self.id])
            )
            button_download = format_html(
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a>',
                download_url,
                _("Export"),
            )
            producers = []
            producers_html = []
            if len(self.producers.all()) > 0:
                changelist_url = reverse("admin:repanier_product_changelist")
                for p in self.producers.all():
                    producers.append(p.short_profile_name)
                    producers_html.append(
                        '<a href="{}?producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            p.id,
                            p.short_profile_name.replace(" ", "&nbsp;"),
                        )
                    )
        elif self.status == SaleStatus.OPENED:
            changelist_url = reverse("admin:repanier_product_changelist")
            download_url = add_filter(
                reverse("admin:permanence-export-producer-opened-order", args=[self.id])
            )
            button_download = format_html(
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a>',
                download_url,
                _("Export"),
            )

            producers = []
            producers_html = []
            for p in self.producers.all():
                producers.append(p.short_profile_name)
                producers_html.append(
                    '<a href="{}?permanences={}&producer={}">{}</a>'.format(
                        changelist_url,
                        self.id,
                        p.id,
                        p.get_filter_display(self.id).replace(" ", "&nbsp;"),
                    )
                )

        elif self.status in [SaleStatus.SEND, SaleStatus.INVOICED, SaleStatus.ARCHIVED]:
            if self.status == SaleStatus.SEND:
                download_url = add_filter(
                    reverse(
                        "admin:permanence-export-producer-closed-order", args=[self.id]
                    )
                )
                button_download = format_html(
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a>',
                    download_url,
                    _("Export"),
                )
            else:
                button_download = EMPTY_STRING
            send_offeritem_changelist_url = "{}?is_filled_exact=1&".format(
                reverse("admin:repanier_offeritemsend_changelist")
            )
            send_customer_changelist_url = "{}?".format(
                reverse("admin:repanier_customersend_changelist")
            )
            producers = []
            producers_html = []
            for pi in (
                ProducerInvoice.objects.filter(permanence_id=self.id)
                .select_related("producer")
                .order_by("producer")
            ):
                if pi.status == SaleStatus.SEND:
                    if pi.producer.invoice_by_basket:
                        changelist_url = send_customer_changelist_url
                    else:
                        changelist_url = send_offeritem_changelist_url
                    # Important : no target="_blank"
                    label = "{} ({})".format(
                        pi.producer.short_profile_name, pi.get_total_price_with_tax()
                    )
                    producers.append(label)
                    producers_html.append(
                        '<a href="{}permanence={}&producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            self.id,
                            pi.producer_id,
                            label.replace(" ", "&nbsp;"),
                        )
                    )
                else:
                    group_id = Producer.get_or_create_group().id
                    if pi.invoice_reference:
                        if (
                            pi.to_be_invoiced_balance != DECIMAL_ZERO
                            or pi.total_price_with_tax != DECIMAL_ZERO
                        ):
                            label = "{} ({} - {})".format(
                                pi.producer.short_profile_name,
                                pi.get_total_price_with_tax()
                                if pi.producer_id == group_id
                                else pi.to_be_invoiced_balance,
                                cap(pi.invoice_reference, 15),
                            )
                        else:
                            label = "{} ({})".format(
                                pi.producer.short_profile_name,
                                cap(pi.invoice_reference, 15),
                            )
                    else:
                        if (
                            pi.to_be_invoiced_balance != DECIMAL_ZERO
                            or pi.total_price_with_tax != DECIMAL_ZERO
                        ):
                            label = "{} ({})".format(
                                pi.producer.short_profile_name,
                                pi.get_total_price_with_tax()
                                if pi.producer_id == group_id
                                else pi.to_be_invoiced_balance,
                            )
                        else:
                            continue
                    # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                    # Such that they can be accessed by the producer and by the staff
                    producers.append(label)
                    producers_html.append(
                        '<a href="{}?producer={}" target="_blank">{}</a>'.format(
                            reverse("repanier:producer_invoice_view", args=(pi.id,)),
                            pi.producer_id,
                            label.replace(" ", "&nbsp;"),
                        )
                    )
        else:
            button_download = EMPTY_STRING
            producers = [
                p.short_profile_name
                for p in Producer.objects.filter(
                    producerinvoice__permanence_id=self.id
                ).only("short_profile_name")
            ]
            producers_html = producers
        len_producer = len(producers)
        if len_producer > 0:
            if not with_download:
                button_download = EMPTY_STRING
            msg_producers_html = ", ".join(producers_html)
            msg_html = """
    <div id="id_show_producers_{id}" style="display:block;" class="repanier-button-row">{button_download}
        <p></p><div class="wrap-text">{msg_producers_html}</div>
    </div>
            """.format(
                id=self.id,
                button_download=button_download,
                msg_producers_html=msg_producers_html,
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No offer")))

    @cached_property
    def get_customers_with_download(self):
        return self.get_customers(with_download=True)

    get_customers_with_download.short_description = _("Orders from")

    @cached_property
    def get_customers_without_download(self):
        return self.get_customers(with_download=False)

    get_customers_without_download.short_description = _("Orders from")

    def get_customers(self, with_download):
        button_add = EMPTY_STRING
        if self.status in [SaleStatus.OPENED, SaleStatus.SEND]:
            changelist_url = reverse("admin:repanier_purchase_changelist")
            if self.status == SaleStatus.OPENED:
                download_url = add_filter(
                    reverse(
                        "admin:permanence-export-customer-opened-order", args=[self.id]
                    )
                )
            else:
                download_url = add_filter(
                    reverse(
                        "admin:permanence-export-customer-closed-order", args=[self.id]
                    )
                )
            button_download = format_html(
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a> ',
                download_url,
                _("Export"),
            )
            add_url = "{}?permanence={}".format(
                reverse("admin:repanier_purchase_add"), self.id
            )
            button_add = format_html(
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-edit"></i></a> ',
                add_url,
                _("Edit purchases"),
            )
            customers = []
            customers_html = []
            delivery_save = None
            for ci in (
                CustomerInvoice.objects.filter(permanence_id=self.id, is_group=False)
                .select_related("customer")
                .order_by("delivery", "customer")
            ):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        customers_html.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        customers_html.append("<br><br>--")
                total_price_with_tax = ci.get_total_price_with_tax(
                    customer_charged=True
                )
                # if ci.is_order_confirm_send:
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-"
                    if ci.is_group or total_price_with_tax == DECIMAL_ZERO
                    else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : no target="_blank"
                customers_html.append(
                    '<a href="{}?permanence={}&customer={}">{}</a>'.format(
                        changelist_url,
                        self.id,
                        ci.customer_id,
                        label.replace(" ", "&nbsp;"),
                    )
                )
                customers.append(label)
        elif self.status in [SaleStatus.INVOICED, SaleStatus.ARCHIVED]:
            button_download = EMPTY_STRING
            customers = []
            customers_html = []
            delivery_save = None
            display_total = True
            total_price_with_tax_save = REPANIER_MONEY_ZERO
            for ci in (
                CustomerInvoice.objects.filter(permanence_id=self.id)
                .select_related("customer")
                .order_by("delivery", "is_group", "customer")
            ):
                if delivery_save != ci.delivery:
                    if delivery_save is not None and display_total:
                        customers_html.append(
                            '<a href="\043"><br><b><i>= {} ({})</i></b></a><br/>'.format(
                                "-"
                                if total_price_with_tax_save == DECIMAL_ZERO
                                else total_price_with_tax_save,
                                _("Total amount"),
                            )
                        )
                    display_total = True
                    total_price_with_tax_save = REPANIER_MONEY_ZERO
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        customers_html.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        customers_html.append("<br><br>--")
                total_price_with_tax = ci.get_total_price_with_tax(
                    customer_charged=True
                )
                if type(total_price_with_tax) == RepanierMoney:
                    total_price_with_tax_save += total_price_with_tax
                if ci.is_group:
                    display_total = False
                    label = "<b><i>= {} ({})</i></b></br>".format(
                        "-"
                        if total_price_with_tax == DECIMAL_ZERO
                        else total_price_with_tax,
                        _("Total amount"),
                    )
                else:
                    label = "{} ({}) {}".format(
                        "-"
                        if total_price_with_tax == DECIMAL_ZERO
                        else total_price_with_tax,
                        ci.customer.short_basket_name,
                        ci.get_is_order_confirm_send_display(),
                    )
                # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                # Such that they can be accessed by the customer and by the staff
                customers_html.append(
                    '<a href="{}" target="_blank">{}</a>'.format(
                        reverse(
                            "repanier:customer_invoice_view_with_customer",
                            args=(
                                ci.id,
                                ci.customer_id,
                            ),
                        ),
                        label.replace(" ", "&nbsp;"),
                    )
                )
                customers.append(label)
        else:
            button_download = EMPTY_STRING
            customers = [
                c.short_basket_name
                for c in Customer.objects.filter(
                    customerinvoice__permanence_id=self.id
                ).only("short_basket_name")
            ]
            customers_html = customers
        len_customers = len(customers)
        if len_customers > 0:
            if not with_download:
                button_download = EMPTY_STRING
            msg_customers_html = ", ".join(customers_html)
            msg_show = _("Show")
            msg_hide = _("Hide")

            if len_customers > 0:
                # Do not display the customers by default if more than 0 customers
                display_customers = "none"
                hide_customers = ""
            else:
                display_customers = "block"
                hide_customers = "none"
            msg_html = """
    <div id="id_hide_customers_{id}" style="display:{hide_producers};" class="repanier-button-row">{button_download}{button_add}
        <a class="repanier-a-tooltip repanier-a-info" href="#" data-repanier-tooltip="{msg_show}"
                onclick="document.getElementById('id_show_customers_{id}').style.display = 'block'; document.getElementById('id_hide_customers_{id}').style.display = 'none'; return false;">
            <i
                    class="far fa-eye"></i> {len_customers}</a>
    </div>
    <div id="id_show_customers_{id}" style="display:{display_producers};" class="repanier-button-row">{button_download}{button_add}
        <a class="repanier-a-tooltip repanier-a-info" href="#" data-repanier-tooltip="{msg_hide}"
                onclick="document.getElementById('id_show_customers_{id}').style.display = 'none'; document.getElementById('id_hide_customers_{id}').style.display = ''; return false;">
            <i
                    class="far fa-eye-slash"></i></a>
        <p></p><div class="wrap-text">{msg_producers_html}</div>
    </div>
            """.format(
                id=self.id,
                button_download=button_download,
                button_add=button_add,
                msg_show=msg_show,
                msg_hide=msg_hide,
                display_producers=display_customers,
                hide_producers=hide_customers,
                msg_producers_html=msg_customers_html,
                len_customers=len_customers,
            )
            return mark_safe(msg_html)
        else:
            if button_add:
                return mark_safe(
                    '<div class="repanier-button-row">{button_add}</div><p></p><div class="wrap-text">{no_purchase}</div>'.format(
                        button_add=button_add, no_purchase=_("No purchase")
                    )
                )
            else:
                return mark_safe(
                    '<div class="wrap-text">{no_purchase}</div>'.format(
                        no_purchase=_("No purchase")
                    )
                )

    get_customers.short_description = _("Purchases by")

    def get_purchases_changelist_link(self):
        link = "{url}?permanence={pk}".format(
            url=reverse("admin:repanier_purchase_changelist"), pk=self.pk
        )

        return mark_safe(
            '<a href="{link}">{msg}</a>'.format(link=link, msg=_("Manage purchases"))
        )

    get_purchases_changelist_link.short_description = _("Manage purchases")

    @cached_property
    def get_board(self):
        permanenceboard_set = PermanenceBoard.objects.filter(
            permanence=self, permanence_role__rght=F("permanence_role__lft") + 1
        ).order_by("permanence_role__tree_id", "permanence_role__lft")
        max_board_entry = 0
        board = []
        board_html = []
        if permanenceboard_set:
            for permanenceboard_row in permanenceboard_set:
                max_board_entry += 1
                r_link = EMPTY_STRING
                r = permanenceboard_row.permanence_role
                if r:
                    r_url = add_filter(
                        reverse(
                            "admin:repanier_lut_permanencerole_change", args=(r.id,)
                        )
                    )
                    r_link = (
                        '<a href="'
                        + r_url
                        + '" target="_blank">'
                        + r.short_name_v2.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                c_link = EMPTY_STRING
                c = permanenceboard_row.customer
                if c:
                    c_url = add_filter(
                        reverse("admin:repanier_customer_change", args=(c.id,))
                    )
                    c_link = (
                        '&nbsp;->&nbsp;<a href="'
                        + c_url
                        + '" target="_blank">'
                        + c.short_basket_name.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                    board.append(c.short_basket_name)
                board_html.append(r_link + c_link)
        len_board = len(board)
        if len_board > 0 or max_board_entry > 0:
            # At least one role is defined in the permanence board
            # msg_board = cap(" ".join(board), 50)
            msg_board_html = "<br> ".join(board_html)
            msg_show = _("Show")
            msg_hide = _("Hide")
            if len_board == max_board_entry:
                msg_len = len_board
            else:
                msg_len = "{} / {}".format(len_board, max_board_entry)
            msg_html = """
    <div id="id_hide_board_{id}" style="display:block;" class="repanier-button-row">
        <a class="repanier-a-tooltip repanier-a-info" href="#" data-repanier-tooltip="{msg_show}"
                onclick="document.getElementById('id_show_board_{id}').style.display = 'block'; document.getElementById('id_hide_board_{id}').style.display = 'none'; return false;">
            <i
                    class="far fa-eye"></i> {msg_len}</a>
    </div>
    <div id="id_show_board_{id}" style="display:none;" class="repanier-button-row">
        <a class="repanier-a-tooltip repanier-a-info" href="#" data-repanier-tooltip="{msg_hide}"
                onclick="document.getElementById('id_show_board_{id}').style.display = 'none'; document.getElementById('id_hide_board_{id}').style.display = 'block'; return false;">
            <i
                    class="far fa-eye-slash"></i></a>
        <p></p><div class="wrap-text">{msg_board_html}</div>
    </div>
            """.format(
                id=self.id,
                msg_show=msg_show,
                msg_hide=msg_hide,
                msg_board_html=msg_board_html,
                msg_len=msg_len,
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No task")))

    get_board.short_description = _("Tasks")

    @transaction.atomic
    # @debug_parameters
    def set_status(
        self,
        old_status : SaleStatus,
        new_status : SaleStatus,
        everything=True,
        deliveries_id=(),
        update_payment_date=False,
        payment_date=None,
    ):
        if everything:
            permanence = (
                Permanence.objects.select_for_update()
                .filter(id=self.id, status=old_status)
                .exclude(status=new_status)
                .first()
            )
        else:
            permanence = (
                Permanence.objects.select_for_update()
                .filter(id=self.id)
                .exclude(status=new_status)
                .first()
            )
        if permanence is None:
            raise ValueError

        if self.with_delivery_point:
            qs = DeliveryBoard.objects.filter(permanence_id=self.id).exclude(
                status=new_status
            )
            if not everything:
                qs = qs.filter(id__in=deliveries_id)
            for delivery_point in qs:
                delivery_point.set_status(new_status)
            if everything:
                # Cancel also purchases without any delivery point
                for customer_invoice in CustomerInvoice.objects.filter(
                    permanence_id=self.id, delivery_id=None
                ):
                    customer_invoice.cancel()

        if everything:
            from repanier.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(permanence_id=self.id).exclude(
                status=new_status
            ).update(status=new_status)
            CustomerInvoice.objects.filter(permanence_id=self.id).update(
                status=new_status
            )
            ProducerInvoice.objects.filter(permanence_id=self.id).update(
                status=new_status
            )

            now = timezone.now().date()
            permanence.is_updated_on = self.is_updated_on = now
            permanence.status = self.status = new_status
            if self.highest_status < new_status:
                permanence.highest_status = self.highest_status = new_status
            if update_payment_date:
                if payment_date is None:
                    permanence.payment_date = self.payment_date = now
                else:
                    permanence.payment_date = self.payment_date = payment_date
        # Unlock permanence
        permanence.save()
        menu_pool.clear(all=True)
        cache.clear()

    @transaction.atomic
    def back_to_scheduled(self):
        self.producers.clear()
        for offer_item in (
            OfferItemReadOnly.objects.filter(permanence_id=self.id, may_order=True)
            .order_by("producer_id")
            .distinct("producer_id")
        ):
            self.producers.add(offer_item.producer_id)
        OfferItemReadOnly.objects.filter(permanence_id=self.id).update(may_order=False)

    @transaction.atomic
    def close_order(self, everything, deliveries_id=(), send_mail=True):
        from repanier.apps import (
            REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION,
            REPANIER_SETTINGS_MEMBERSHIP_FEE,
        )

        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            # Cancel unconfirmed purchases whichever the producer is
            customer_invoice_qs = CustomerInvoice.objects.filter(
                permanence_id=self.id, is_order_confirm_send=False, status=self.status
            )
            if self.with_delivery_point:
                customer_invoice_qs = customer_invoice_qs.filter(
                    delivery_id__in=deliveries_id
                )
            for customer_invoice in customer_invoice_qs:
                customer_invoice.cancel_if_unconfirmed(send_mail=send_mail)
        if everything:
            # Add membership fee
            if (
                REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION > 0
                and REPANIER_SETTINGS_MEMBERSHIP_FEE > 0
            ):
                membership_fee_product = Product.objects.filter(
                    order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE, is_active=True
                ).first()
                membership_fee_product.producer_unit_price = (
                    REPANIER_SETTINGS_MEMBERSHIP_FEE
                )
                # Update the prices
                membership_fee_product.save()

                customer_invoice_qs = CustomerInvoice.objects.filter(
                    permanence_id=self.id, customer_charged_id=F("customer_id")
                ).select_related("customer")
                if self.with_delivery_point:
                    customer_invoice_qs = customer_invoice_qs.filter(
                        delivery_id__in=deliveries_id
                    )

                for customer_invoice in customer_invoice_qs:
                    customer = customer_invoice.customer
                    if not customer.represent_this_buyinggroup:
                        # Should pay a membership fee
                        if customer.membership_fee_valid_until < self.permanence_date:
                            membership_fee_offer_item = (
                                membership_fee_product.get_or_create_offer_item(self)
                            )
                            self.producers.add(membership_fee_offer_item.producer_id)
                            create_or_update_one_purchase(
                                customer_id=customer.id,
                                offer_item=membership_fee_offer_item,
                                status=SaleStatus.OPENED,
                                q_order=1,
                                batch_job=True,
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
                            Customer.objects.filter(id=customer.id).update(
                                membership_fee_valid_until=membership_fee_valid_until
                            )
        if everything or self.with_delivery_point:
            # Add deposit products to be able to return them
            customer_qs = Customer.objects.filter(
                may_order=True,
                customerinvoice__permanence_id=self.id,
                represent_this_buyinggroup=False,
            )
            if self.with_delivery_point:
                customer_qs = customer_qs.filter(
                    customerinvoice__delivery_id__in=deliveries_id
                )
            for customer in customer_qs:
                offer_item_qs = OfferItem.objects.filter(
                    permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_DEPOSIT
                )
                # if not everything:
                #     offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
                for offer_item in offer_item_qs:
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=SaleStatus.OPENED,
                        q_order=1,
                        batch_job=True,
                        comment=EMPTY_STRING,
                    )
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=SaleStatus.OPENED,
                        q_order=0,
                        batch_job=True,
                        comment=EMPTY_STRING,
                    )
        if everything:
            # # Round to multiple producer_order_by_quantity
            # offer_item_qs = OfferItem.objects.filter(
            #     permanence_id=self.id,
            #     may_order=True,
            #     order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
            #     producer_order_by_quantity__gt=1,
            #     quantity_invoiced__gt=0,
            # )

            # Add Transport
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_TRANSPORTATION
            )
            group_id = Customer.get_or_create_group().id
            for offer_item in offer_item_qs:
                create_or_update_one_purchase(
                    customer_id=group_id,
                    offer_item=offer_item,
                    status=SaleStatus.OPENED,
                    q_order=1,
                    batch_job=True,
                    comment=EMPTY_STRING,
                )

    def send_to_producer(self):
        from repanier.models.purchase import PurchaseWoReceiver

        # PurchaseWoReceiver.objects.filter(
        #     permanence_id=self.id,
        #     status=PERMANENCE_WAIT_FOR_SEND,
        #     offer_item__order_unit=PRODUCT_ORDER_UNIT_PC_KG,
        # ).update(
        #     quantity_invoiced=F("quantity_ordered")
        #     * F("offer_item__order_average_weight"),
        # )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE repanier_purchase AS a SET "
                " quantity_invoiced = quantity_ordered * b.order_average_weight "
                " FROM repanier_offeritem AS b "
                " WHERE a.offer_item_id = b.id "
                " AND a.permanence_id = %s "
                " AND a.status = %s "
                " AND b.order_unit = %s ",
                [self.id, SaleStatus.WAIT_FOR_SEND.value, PRODUCT_ORDER_UNIT_PC_KG],
            )
        # for p in PurchaseWoReceiver.objects.filter(
        #     permanence_id=self.id,
        #     status=PERMANENCE_WAIT_FOR_SEND,
        #     offer_item__order_unit=PRODUCT_ORDER_UNIT_PC_KG,
        # ):
        #     p.quantity_invoiced = p.quantity_ordered * p.offer_item.order_average_weight
        #     p.save()
        PurchaseWoReceiver.objects.filter(
            permanence_id=self.id,
            status=SaleStatus.WAIT_FOR_SEND,
        ).exclude(offer_item__order_unit=PRODUCT_ORDER_UNIT_PC_KG,).update(
            quantity_invoiced=F("quantity_ordered"),
        )
        OfferItemReadOnly.objects.filter(
            permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_PC_KG
        ).update(use_order_unit_converted=True)

    @transaction.atomic
    @debug_parameters
    def invoice(self, payment_date):
        from repanier.models.purchase import PurchaseWoReceiver

        bank_account_latest_total = BankAccount.get_latest_total()
        producer_buyinggroup = Producer.get_or_create_group()
        customer_buyinggroup = Customer.get_or_create_group()
        if (
            bank_account_latest_total is None
            or producer_buyinggroup is None
            or customer_buyinggroup is None
        ):
            return
        self.set_status(
            old_status=SaleStatus.SEND, new_status=SaleStatus.WAIT_FOR_INVOICED
        )

        customer_invoice_buyinggroup = CustomerInvoice.get_or_create_invoice(
            permanence_id=self.id,
            customer_id=customer_buyinggroup.id,
            status=self.status,
        )

        permanence_partially_invoiced = (
            ProducerInvoice.objects.filter(
                permanence_id=self.id, invoice_sort_order__isnull=True, to_be_paid=False
            ).count()
            - ProducerInvoice.objects.filter(permanence_id=self.id).count()
        )
        if permanence_partially_invoiced > 0:
            # Move the producers not invoiced into a new permanence
            producers_to_keep = list(
                ProducerInvoice.objects.filter(
                    permanence_id=self.id,
                    invoice_sort_order__isnull=True,
                    to_be_paid=True,
                ).values_list("producer_id", flat=True)
            )
            self.producers.clear()
            self.producers.add(*producers_to_keep)
            producers_to_move = list(
                ProducerInvoice.objects.filter(
                    permanence_id=self.id,
                    invoice_sort_order__isnull=True,
                    to_be_paid=False,
                ).values_list("producer_id", flat=True)
            )
            customers_to_move = list(
                CustomerProducerInvoice.objects.filter(
                    permanence_id=self.id, producer_id__in=producers_to_move
                ).values_list("customer_id", flat=True)
            )
            new_permanence = self.create_child(SaleStatus.SEND)
            new_permanence.producers.add(*producers_to_move)
            ProducerInvoice.objects.filter(
                permanence_id=self.id, producer_id__in=producers_to_move
            ).update(permanence_id=new_permanence.id, status=SaleStatus.SEND)
            CustomerProducerInvoice.objects.filter(
                permanence_id=self.id,
                producer_id__in=producers_to_move
                # Redundant : customer_id__in=customers_to_move
            ).update(permanence_id=new_permanence.id)
            OfferItemReadOnly.objects.filter(
                permanence_id=self.id, producer_id__in=producers_to_move
            ).update(permanence_id=new_permanence.id)

            for old_customer_invoice in CustomerInvoice.objects.filter(
                permanence_id=self.id, customer_id__in=customers_to_move
            ):
                new_customer_invoice = old_customer_invoice.create_child(
                    new_permanence=new_permanence
                )
                PurchaseWoReceiver.objects.filter(
                    customer_invoice_id=old_customer_invoice.id,
                    producer_id__in=producers_to_move,
                ).update(
                    permanence_id=new_permanence.id,
                    customer_invoice_id=new_customer_invoice.id,
                    status=new_permanence.status,
                )

            new_permanence.calculate_order_amount()

        self.calculate_order_amount()

        for customer_invoice in CustomerInvoice.objects.filter(permanence_id=self.id):
            # customer_invoice.calculate_order_amount()
            customer_invoice.balance = (
                customer_invoice.previous_balance
            ) = customer_invoice.customer.balance
            customer_invoice.date_previous_balance = (
                customer_invoice.customer.date_balance
            )
            customer_invoice.date_balance = payment_date

            if customer_invoice.customer_id == customer_invoice.customer_charged_id:
                # ajuster la balance de celui qui paye
                # celui qui paye a droit aux réductions
                total_price_with_tax = (
                    customer_invoice.get_total_price_with_tax().amount
                )
                customer_invoice.balance.amount -= total_price_with_tax
                Customer.objects.filter(id=customer_invoice.customer_id).update(
                    date_balance=payment_date,
                    balance=F("balance") - total_price_with_tax,
                )
            else:
                # ne pas modifier sa balance car il ne paye pas
                Customer.objects.filter(id=customer_invoice.customer_id).update(
                    date_balance=payment_date
                )
            customer_invoice.save()

        for producer_invoice in ProducerInvoice.objects.filter(permanence_id=self.id):
            # producer_invoice.calculate_order_amount()
            producer_invoice.balance = (
                producer_invoice.previous_balance
            ) = producer_invoice.producer.balance
            producer_invoice.date_previous_balance = (
                producer_invoice.producer.date_balance
            )
            producer_invoice.date_balance = payment_date
            total_price_with_tax = producer_invoice.get_total_price_with_tax().amount
            producer_invoice.balance.amount += total_price_with_tax
            producer_invoice.save()
            Producer.objects.filter(id=producer_invoice.producer_id).update(
                date_balance=payment_date, balance=F("balance") + total_price_with_tax
            )
            producer_invoice.save()

        # for customer_producer_invoice in CustomerProducerInvoice.objects.filter(
        #     permanence_id=self.id
        # ):
        #     customer_producer_invoice.calculate_order_amount()
        #     customer_producer_invoice.save()
        #
        # for offer_item in OfferItemReadOnly.objects.filter(permanence_id=self.id):
        #     offer_item.calculate_order_amount()
        #     offer_item.save()

        # result_set = PurchaseWoReceiver.objects.filter(
        #     permanence_id=self.id,
        #     offer_item__is_resale_price_fixed=True,
        # ).aggregate(
        #     purchase_price=Sum(
        #         "purchase_price",
        #         output_field=DecimalField(
        #             max_digits=8, decimal_places=2, default=DECIMAL_ZERO
        #         ),
        #     ),
        #     selling_price=Sum(
        #         "selling_price",
        #         output_field=DecimalField(
        #             max_digits=8, decimal_places=2, default=DECIMAL_ZERO
        #         ),
        #     ),
        #     producer_vat=Sum(
        #         "producer_vat",
        #         output_field=DecimalField(
        #             max_digits=8, decimal_places=4, default=DECIMAL_ZERO
        #         ),
        #     ),
        #     customer_vat=Sum(
        #         "customer_vat",
        #         output_field=DecimalField(
        #             max_digits=8, decimal_places=4, default=DECIMAL_ZERO
        #         ),
        #     ),
        # )
        #
        # total_purchase_price_with_tax = (
        #     result_set["purchase_price"]
        #     if result_set["purchase_price"] is not None
        #     else DECIMAL_ZERO
        # )
        # total_selling_price_with_tax = (
        #     result_set["selling_price"]
        #     if result_set["selling_price"] is not None
        #     else DECIMAL_ZERO
        # )
        # total_customer_vat = (
        #     result_set["customer_vat"]
        #     if result_set["customer_vat"] is not None
        #     else DECIMAL_ZERO
        # )
        # total_producer_vat = (
        #     result_set["producer_vat"]
        #     if result_set["producer_vat"] is not None
        #     else DECIMAL_ZERO
        # )
        #
        # purchases_delta_vat = total_customer_vat - total_producer_vat
        # purchases_delta_price_with_tax = (
        #     total_selling_price_with_tax - total_purchase_price_with_tax
        # )
        #
        # purchases_delta_price_wo_tax = (
        #     purchases_delta_price_with_tax - purchases_delta_vat
        # )
        #
        # if purchases_delta_price_wo_tax != DECIMAL_ZERO:
        #     BankAccount.objects.create(
        #         permanence_id=self.id,
        #         producer=None,
        #         customer_id=customer_buyinggroup.id,
        #         operation_date=payment_date,
        #         operation_status=BANK_PROFIT,
        #         operation_comment=_("Profit")
        #         if purchases_delta_price_wo_tax >= DECIMAL_ZERO
        #         else _("Lost"),
        #         bank_amount_out=-purchases_delta_price_wo_tax
        #         if purchases_delta_price_wo_tax < DECIMAL_ZERO
        #         else DECIMAL_ZERO,
        #         bank_amount_in=purchases_delta_price_wo_tax
        #         if purchases_delta_price_wo_tax > DECIMAL_ZERO
        #         else DECIMAL_ZERO,
        #         customer_invoice_id=None,
        #         producer_invoice=None,
        #     )
        # if purchases_delta_vat != DECIMAL_ZERO:
        #     BankAccount.objects.create(
        #         permanence_id=self.id,
        #         producer=None,
        #         customer_id=customer_buyinggroup.id,
        #         operation_date=payment_date,
        #         operation_status=BANK_TAX,
        #         operation_comment=_("VAT to be paid to the administration")
        #         if purchases_delta_vat >= DECIMAL_ZERO
        #         else _("VAT receivable from the administration"),
        #         bank_amount_out=-purchases_delta_vat
        #         if purchases_delta_vat < DECIMAL_ZERO
        #         else DECIMAL_ZERO,
        #         bank_amount_in=purchases_delta_vat
        #         if purchases_delta_vat > DECIMAL_ZERO
        #         else DECIMAL_ZERO,
        #         customer_invoice_id=None,
        #         producer_invoice=None,
        #     )

        # for customer_invoice in CustomerInvoice.objects.filter(
        #     permanence_id=self.id
        # ).exclude(customer_id=customer_buyinggroup.id, delta_transport=DECIMAL_ZERO):
        #     if customer_invoice.delta_transport != DECIMAL_ZERO:
        #         # --> This bank movement is not a real entry
        #         # customer_invoice_id=customer_invoice_buyinggroup.id
        #         # making this, it will not be counted into the customer_buyinggroup movements twice
        #         # because Repanier will see it has already been counted into the customer_buyinggroup movements
        #         BankAccount.objects.create(
        #             permanence_id=self.id,
        #             producer=None,
        #             customer_id=customer_buyinggroup.id,
        #             operation_date=payment_date,
        #             operation_status=BANK_PROFIT,
        #             operation_comment="{} : {}".format(
        #                 _("Shipping"), customer_invoice.customer.short_basket_name
        #             ),
        #             bank_amount_in=customer_invoice.delta_transport,
        #             bank_amount_out=DECIMAL_ZERO,
        #             customer_invoice_id=customer_invoice_buyinggroup.id,
        #             producer_invoice=None,
        #         )

        # generate bank account movements

        self.generate_bank_account_movement(payment_date=payment_date)
        new_bank_latest_total = (
            bank_account_latest_total.bank_amount_in.amount
            - bank_account_latest_total.bank_amount_out.amount
        )

        # Calculate new current balance : Bank
        for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            operation_status__in=[BankMovement.PROFIT, BankMovement.TAX],
            customer_id=customer_buyinggroup.id,
            operation_date__lte=payment_date,
        ):
            # --> This bank movement is not a real entry
            # It will not be counted into the customer_buyinggroup bank movements twice
            Customer.objects.filter(id=bank_account.customer_id).update(
                date_balance=payment_date,
                balance=F("balance")
                + bank_account.bank_amount_in.amount
                - bank_account.bank_amount_out.amount,
            )
            CustomerInvoice.objects.filter(
                customer_id=bank_account.customer_id, permanence_id=self.id
            ).update(
                date_balance=payment_date,
                balance=F("balance")
                + bank_account.bank_amount_in.amount
                - bank_account.bank_amount_out.amount,
            )
            bank_account.customer_invoice_id = customer_invoice_buyinggroup.id
            bank_account.save(update_fields=["customer_invoice"])

        for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            customer__isnull=False,
            operation_date__lte=payment_date,
        ):

            customer_invoice = CustomerInvoice.objects.filter(
                customer_id=bank_account.customer_id, permanence_id=self.id
            ).first()
            if customer_invoice is None:
                customer_invoice = CustomerInvoice.objects.create(
                    customer_id=bank_account.customer_id,
                    permanence_id=self.id,
                    date_previous_balance=bank_account.customer.date_balance,
                    previous_balance=bank_account.customer.balance,
                    date_balance=payment_date,
                    balance=bank_account.customer.balance,
                    customer_charged_id=bank_account.customer_id,
                    transport=DECIMAL_ZERO,
                    min_transport=DECIMAL_ZERO,
                )
            bank_amount_in = bank_account.bank_amount_in.amount
            new_bank_latest_total += bank_amount_in
            bank_amount_out = bank_account.bank_amount_out.amount
            new_bank_latest_total -= bank_amount_out
            customer_invoice.date_balance = payment_date
            customer_invoice.bank_amount_in.amount += bank_amount_in
            customer_invoice.bank_amount_out.amount += bank_amount_out
            customer_invoice.balance.amount += bank_amount_in - bank_amount_out

            customer_invoice.save()
            Customer.objects.filter(id=bank_account.customer_id).update(
                date_balance=payment_date,
                balance=F("balance") + bank_amount_in - bank_amount_out,
            )
            bank_account.customer_invoice_id = customer_invoice.id
            bank_account.permanence_id = self.id
            bank_account.save()

        for bank_account in BankAccount.objects.select_for_update().filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            producer__isnull=False,
            operation_date__lte=payment_date,
        ):

            producer_invoice = ProducerInvoice.objects.filter(
                producer_id=bank_account.producer_id, permanence_id=self.id
            ).first()
            if producer_invoice is None:
                producer_invoice = ProducerInvoice.objects.create(
                    producer=bank_account.producer,
                    permanence_id=self.id,
                    price_list_multiplier=bank_account.producer.price_list_multiplier,
                    date_previous_balance=bank_account.producer.date_balance,
                    previous_balance=bank_account.producer.balance,
                    date_balance=payment_date,
                    balance=bank_account.producer.balance,
                )
            bank_amount_in = bank_account.bank_amount_in.amount
            new_bank_latest_total += bank_amount_in
            bank_amount_out = bank_account.bank_amount_out.amount
            new_bank_latest_total -= bank_amount_out
            producer_invoice.date_balance = payment_date
            producer_invoice.bank_amount_in.amount += bank_amount_in
            producer_invoice.bank_amount_out.amount += bank_amount_out
            producer_invoice.balance.amount += bank_amount_in - bank_amount_out
            producer_invoice.save()
            Producer.objects.filter(id=bank_account.producer_id).update(
                date_balance=payment_date,
                balance=F("balance") + bank_amount_in - bank_amount_out,
            )
            bank_account.permanence_id = self.id
            bank_account.producer_invoice_id = producer_invoice.id
            bank_account.save()

        BankAccount.objects.filter(operation_status=BankMovement.LATEST_TOTAL).update(
            operation_status=BankMovement.NOT_LATEST_TOTAL
        )
        # Important : Create a new bank total for this permanence even if there is no bank movement
        bank_account = BankAccount.objects.create(
            permanence_id=self.id,
            producer=None,
            customer=None,
            operation_date=payment_date,
            operation_status=BankMovement.LATEST_TOTAL,
            operation_comment=cap(str(self), 100),
            bank_amount_in=new_bank_latest_total
            if new_bank_latest_total >= DECIMAL_ZERO
            else DECIMAL_ZERO,
            bank_amount_out=-new_bank_latest_total
            if new_bank_latest_total < DECIMAL_ZERO
            else DECIMAL_ZERO,
            customer_invoice=None,
            producer_invoice=None,
        )

        ProducerInvoice.objects.filter(permanence_id=self.id).update(
            invoice_sort_order=bank_account.id
        )
        CustomerInvoice.objects.filter(permanence_id=self.id).update(
            invoice_sort_order=bank_account.id
        )
        Permanence.objects.filter(id=self.id).update(
            invoice_sort_order=bank_account.id, canceled_invoice_sort_order=None
        )

        new_status = (
            SaleStatus.INVOICED
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING
            else SaleStatus.ARCHIVED
        )
        self.set_status(
            old_status=SaleStatus.WAIT_FOR_INVOICED,
            new_status=new_status,
            update_payment_date=True,
            payment_date=payment_date,
        )

    # def get_or_create_group_invoice(self, customer_buyinggroup, payment_date, status):
    #     customer_invoice_buyinggroup = CustomerInvoice.objects.filter(
    #         customer_id=customer_buyinggroup.id, permanence_id=self.id
    #     ).first()
    #     if customer_invoice_buyinggroup is None:
    #         customer_invoice_buyinggroup = CustomerInvoice.objects.create(
    #             permanence_id=self.id,
    #             customer_id=customer_buyinggroup.id,
    #             status=status,
    #             date_previous_balance=customer_buyinggroup.date_balance,
    #             previous_balance=customer_buyinggroup.balance,
    #             date_balance=payment_date,
    #             balance=customer_buyinggroup.balance,
    #             customer_charged_id=customer_buyinggroup.id,
    #             transport=DECIMAL_ZERO,
    #             min_transport=DECIMAL_ZERO,
    #             price_list_multiplier=DECIMAL_ONE,
    #         )
    #     return customer_invoice_buyinggroup

    @transaction.atomic
    def cancel_invoice(self, last_bank_account_total):
        self.set_status(
            old_status=SaleStatus.INVOICED,
            new_status=SaleStatus.WAIT_FOR_CANCEL_INVOICE,
        )
        CustomerInvoice.objects.filter(permanence_id=self.id).update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )
        for customer_invoice in CustomerInvoice.objects.filter(permanence_id=self.id):
            # customer = customer_invoice.customer
            # customer.balance = customer_invoice.previous_balance
            # customer.date_balance = customer_invoice.date_previous_balance
            # customer.save(update_fields=['balance', 'date_balance'])
            # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
            Customer.objects.filter(id=customer_invoice.customer_id).update(
                balance=customer_invoice.previous_balance,
                date_balance=customer_invoice.date_previous_balance,
            )
            BankAccount.objects.filter(customer_invoice_id=customer_invoice.id).update(
                customer_invoice=None
            )
        ProducerInvoice.objects.filter(
            permanence_id=self.id, producer__represent_this_buyinggroup=False
        ).update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            delta_price_with_tax=DECIMAL_ZERO,
            delta_vat=DECIMAL_ZERO,
            delta_transport=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )
        # Important : Restore delta from delivery points added into invoice.confirm_order()
        ProducerInvoice.objects.filter(
            permanence_id=self.id, producer__represent_this_buyinggroup=True
        ).update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )

        for producer_invoice in ProducerInvoice.objects.filter(permanence_id=self.id):
            Producer.objects.filter(id=producer_invoice.producer_id).update(
                balance=producer_invoice.previous_balance,
                date_balance=producer_invoice.date_previous_balance,
            )
            BankAccount.objects.all().filter(
                producer_invoice_id=producer_invoice.id
            ).update(producer_invoice=None)
        # IMPORTANT : Do not update stock when canceling
        last_bank_account_total.delete()
        bank_account = (
            BankAccount.objects.filter(customer=None, producer=None)
            .order_by("-id")
            .first()
        )
        if bank_account is not None:
            bank_account.operation_status = BankMovement.LATEST_TOTAL
            bank_account.save()
        # Delete also all payments recorded to producers, bank profit, bank tax
        # Delete also all compensation recorded to producers
        BankAccount.objects.filter(
            permanence_id=self.id,
            operation_status__in=[
                BankMovement.CALCULATED_INVOICE,
                BankMovement.PROFIT,
                BankMovement.TAX,
                BankMovement.MEMBERSHIP_FEE,
                BankMovement.COMPENSATION,  # BANK_COMPENSATION may occurs in previous release of Repanier
            ],
        ).delete()
        Permanence.objects.filter(id=self.id).update(
            canceled_invoice_sort_order=F("invoice_sort_order"), invoice_sort_order=None
        )
        self.set_status(
            old_status=SaleStatus.WAIT_FOR_CANCEL_INVOICE, new_status=SaleStatus.SEND
        )

    @transaction.atomic
    def cancel_delivery(self):
        self.set_status(old_status=SaleStatus.SEND, new_status=SaleStatus.CANCELLED)
        bank_account = BankAccount.get_closest_to(self.permanence_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    @transaction.atomic
    def archive(self):
        self.set_status(old_status=SaleStatus.SEND, new_status=SaleStatus.ARCHIVED)
        bank_account = BankAccount.get_closest_to(self.permanence_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    def duplicate(self, dates):
        creation_counter = 0
        short_name = self.short_name_v2
        cur_language = translation.get_language()
        for date in dates[:56]:
            # Limit to 56 weeks
            same_exists = self.check_if_same_exists(date, short_name, cur_language)
            if not same_exists:
                creation_counter += 1
                new_permanence = Permanence.objects.create(permanence_date=date)
                self.duplicate_short_name(new_permanence, cur_language)
                self.duplicate_permanence_board(new_permanence)
                self.duplicate_delivery_board(new_permanence, cur_language)
                self.duplicate_producers(new_permanence)
        return creation_counter

    def create_child(self, status):
        new_child_permanence = Permanence.objects.create(
            permanence_date=self.permanence_date,
            master_permanence_id=self.id,
            status=status,
        )
        cur_language = translation.get_language()
        self.duplicate_short_name(new_child_permanence, cur_language)
        self.duplicate_permanence_board_and_registration(new_child_permanence)
        self.duplicate_delivery_board(new_child_permanence, cur_language)
        return new_child_permanence

    def check_if_same_exists(self, date, short_name, cur_language):
        if short_name != EMPTY_STRING:
            # Mandatory because of Parler
            same_exists = Permanence.objects.filter(
                permanence_date=date,
                short_name_v2=short_name,
            ).exists()
        else:
            same_exists = False
        return same_exists

    def duplicate_short_name(self, new_permanence, cur_language):
        new_permanence.short_name_v2 = self.short_name_v2
        new_permanence.save()

    def duplicate_producers(self, new_permanence):
        for a_producer in self.producers.all():
            new_permanence.producers.add(a_producer)

    def duplicate_delivery_board(self, new_permanence, cur_language):
        for delivery_board in DeliveryBoard.objects.filter(permanence=self):
            new_delivery_board = DeliveryBoard.objects.create(
                permanence=new_permanence,
                delivery_point=delivery_board.delivery_point,
                delivery_comment_v2=delivery_board.delivery_comment_v2,
            )

    def duplicate_permanence_board(self, new_permanence):
        for permanence_board in PermanenceBoard.objects.filter(permanence=self):
            PermanenceBoard.objects.create(
                permanence=new_permanence,
                permanence_date=new_permanence.permanence_date,
                permanence_role=permanence_board.permanence_role,
            )

    def duplicate_permanence_board_and_registration(self, new_permanence):
        for permanence_board in PermanenceBoard.objects.filter(permanence=self):
            PermanenceBoard.objects.create(
                permanence=new_permanence,
                permanence_date=new_permanence.permanence_date,
                permanence_role=permanence_board.permanence_role,
                customer=permanence_board.customer,
                is_registered_on=permanence_board.is_registered_on,
            )

    def generate_bank_account_movement(self, payment_date):

        for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=self.id, invoice_sort_order__isnull=True, to_be_paid=True
        ).select_related("producer"):
            # We have to pay something
            producer = producer_invoice.producer
            bank_not_invoiced = producer.get_bank_not_invoiced()
            if (
                producer.balance.amount != DECIMAL_ZERO
                or producer_invoice.to_be_invoiced_balance.amount != DECIMAL_ZERO
                or bank_not_invoiced.amount != DECIMAL_ZERO
            ):
                delta = (
                    producer_invoice.to_be_invoiced_balance.amount
                    - bank_not_invoiced.amount
                ).quantize(RoundUpTo.TWO_DECIMALS)
                if delta > DECIMAL_ZERO:
                    if producer_invoice.invoice_reference:
                        operation_comment = producer_invoice.invoice_reference
                    else:
                        if producer.represent_this_buyinggroup:
                            operation_comment = self.get_permanence_display()
                        else:
                            if producer_invoice is not None:
                                if (
                                    producer_invoice.get_total_price_with_tax().amount
                                    == delta
                                ):
                                    operation_comment = _(
                                        "Delivery %(current_site)s - %(permanence)s. Thanks!"
                                    ) % {
                                        "current_site": settings.REPANIER_SETTINGS_GROUP_NAME,
                                        "permanence": self.get_permanence_display(),
                                    }
                                else:
                                    operation_comment = _(
                                        "Deliveries %(current_site)s - up to the %(permanence)s (included). Thanks!"
                                    ) % {
                                        "current_site": settings.REPANIER_SETTINGS_GROUP_NAME,
                                        "permanence": self.get_permanence_display(),
                                    }
                            else:
                                operation_comment = _(
                                    "Deliveries %(current_site)s - up to %(payment_date)s (included). Thanks!"
                                ) % {
                                    "current_site": settings.REPANIER_SETTINGS_GROUP_NAME,
                                    "payment_date": payment_date.strftime(
                                        settings.DJANGO_SETTINGS_DATE
                                    ),
                                }
                    BankAccount.objects.create(
                        permanence_id=None,
                        producer_id=producer.id,
                        customer=None,
                        operation_date=payment_date,
                        operation_status=BankMovement.CALCULATED_INVOICE,
                        operation_comment=cap(operation_comment, 100),
                        bank_amount_out=delta,
                        customer_invoice=None,
                        producer_invoice=None,
                    )
            delta = (
                producer.balance.amount - producer_invoice.to_be_invoiced_balance.amount
            ).quantize(RoundUpTo.TWO_DECIMALS)
            if delta != DECIMAL_ZERO:
                # Profit or loss for the group
                customer_buyinggroup = Customer.get_or_create_group()
                operation_comment = _("Correction %(producer)s") % {
                    "producer": producer.short_profile_name
                }
                BankAccount.objects.create(
                    permanence_id=self.id,
                    producer=None,
                    customer_id=customer_buyinggroup.id,
                    operation_date=payment_date,
                    operation_status=BankMovement.PROFIT,
                    operation_comment=cap(operation_comment, 100),
                    bank_amount_in=delta if delta > DECIMAL_ZERO else DECIMAL_ZERO,
                    bank_amount_out=-delta if delta < DECIMAL_ZERO else DECIMAL_ZERO,
                    customer_invoice_id=None,
                    producer_invoice=None,
                )
            producer_invoice.balance.amount -= delta
            producer_invoice.save(update_fields=["balance"])
            # Do not invoke producer_post_save using producer.save(update_fields=["balance"])
            Producer.objects.order_by("?").filter(id=producer.id).update(
                balance=F("balance") - delta
            )
        return

    def clean_offer_item(self, offer_item_qs):
        if self.status > SaleStatus.SEND:
            # The purchases are already invoiced.
            # The offer item may not be modified any more
            raise ValueError(
                "Not offer item may be cleaned when permanence.status > SaleStatus.SEND"
            )
        permanence_offer_item_qs = offer_item_qs.filter(permanence_id=self.id)
        for offer_item in permanence_offer_item_qs.select_related(
            "producer", "product"
        ):
            product = offer_item.product
            producer = offer_item.producer

            offer_item.set_from(product)

            offer_item.manage_production = producer.represent_this_buyinggroup
            # Offer_items are not subjects to customer price modifications
            # if product.is_box or product.is_box_content or product.order_unit >= const.PRODUCT_ORDER_UNIT_DEPOSIT
            offer_item.is_resale_price_fixed = (
                not (offer_item.manage_production)
                or product.order_unit >= PRODUCT_ORDER_UNIT_DEPOSIT
            )

            offer_item.may_order = False
            if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                offer_item.may_order = product.is_into_offer

            # The group must pay the VAT, so it's easier to always have
            # offer_item with VAT included
            # if producer.producer_price_are_wo_vat:
            #     offer_item.producer_unit_price += offer_item.producer_vat
            # offer_item.producer_price_are_wo_vat = False

            offer_item.save()

        # Now got everything to calculate the sort order of the order display screen
        template_cache_part_a = get_repanier_template_name("cache_part_a.html")
        template_cache_part_b = get_repanier_template_name("cache_part_b.html")

        for offer_item in permanence_offer_item_qs.select_related(
            "producer", "department_for_customer"
        ):
            offer_item.long_name_v2 = offer_item.product.long_name_v2
            offer_item.cache_part_a_v2 = render_to_string(
                template_cache_part_a,
                {"offer": offer_item, "MEDIA_URL": settings.MEDIA_URL},
            )
            offer_item.cache_part_b_v2 = render_to_string(
                template_cache_part_b,
                {"offer": offer_item, "MEDIA_URL": settings.MEDIA_URL},
            )
            offer_item.save()

    def calculate_order_amount(self):
        for customer_invoice in CustomerInvoice.objects.filter(permanence_id=self.id):
            customer_invoice.calculate_order_amount()
            customer_invoice.save()

        for producer_invoice in ProducerInvoice.objects.filter(permanence_id=self.id):
            producer_invoice.calculate_order_amount()
            producer_invoice.save()

        for customer_producer_invoice in CustomerProducerInvoice.objects.filter(
            permanence_id=self.id
        ):
            customer_producer_invoice.calculate_order_amount()
            customer_producer_invoice.save()

        for offer_item in OfferItemReadOnly.objects.filter(permanence_id=self.id):
            offer_item.calculate_order_amount()
            offer_item.save()

        result_set = CustomerInvoice.objects.filter(permanence_id=self.id).aggregate(
            delta_price_with_tax=Sum(
                "delta_price_with_tax",
                output_field=DecimalField(
                    max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            delta_vat=Sum(
                "delta_vat",
                output_field=DecimalField(
                    max_digits=9, decimal_places=4, default=DECIMAL_ZERO
                ),
            ),
            delta_transport=Sum(
                "delta_transport",
                output_field=DecimalField(
                    max_digits=5, decimal_places=2, default=DECIMAL_ZERO
                ),
            ),
        )

        producer_buyinggroup = Producer.get_or_create_group()
        producer_invoice_buyinggroup = ProducerInvoice.get_or_create_invoice(
            permanence_id=self.id,
            producer_id=producer_buyinggroup.id,
            status=self.status,
        )
        producer_invoice_buyinggroup.delta_price_with_tax = (
            result_set["delta_price_with_tax"]
            if result_set["delta_price_with_tax"] is not None
            else DECIMAL_ZERO
        )
        producer_invoice_buyinggroup.delta_vat = (
            result_set["delta_vat"]
            if result_set["delta_vat"] is not None
            else DECIMAL_ZERO
        )
        producer_invoice_buyinggroup.delta_transport = (
            result_set["delta_transport"]
            if result_set["delta_transport"] is not None
            else DECIMAL_ZERO
        )
        producer_invoice_buyinggroup.save()

    def update_offer_item(self, offer_item_qs):
        from repanier.models.purchase import Purchase

        permanence_offer_item_qs = offer_item_qs.filter(permanence_id=self.id)
        purchase_set = Purchase.objects.filter(
            permanence_id=self.id,
            offer_item__in=permanence_offer_item_qs,
        )

        for a_purchase in purchase_set.select_related("offer_item", "customer_invoice"):
            a_purchase.save()

    @cached_property
    def get_new_products(self):
        assert self.status < SaleStatus.SEND
        result = []
        for a_producer in self.producers.all():
            current_products = list(
                OfferItemReadOnly.objects.filter(
                    is_active=True,
                    may_order=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                    permanence_id=self.id,
                    producer=a_producer,
                ).values_list("product", flat=True)
            )
            six_months_ago = timezone.now().date() - datetime.timedelta(days=6 * 30)
            previous_permanence = (
                Permanence.objects.filter(
                    status__gte=SaleStatus.SEND,
                    producers=a_producer,
                    permanence_date__gte=six_months_ago,
                )
                .order_by("-permanence_date", "status")
                .first()
            )
            if previous_permanence is not None:
                previous_products = list(
                    OfferItemReadOnly.objects.filter(
                        is_active=True,
                        may_order=True,
                        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                        permanence_id=previous_permanence.id,
                        producer=a_producer,
                    ).values_list("product", flat=True)
                )
                new_products = [
                    item for item in current_products if item not in previous_products
                ]
            else:
                new_products = current_products

            qs = OfferItemReadOnly.objects.filter(
                permanence_id=self.id,
                product__in=new_products,
            ).order_by("order_sort_order_v2")
            department_for_customer_save = None
            for o in qs:
                if department_for_customer_save != o.department_for_customer:
                    if department_for_customer_save is not None:
                        result.append("</ul></li>")
                    department_for_customer_save = o.department_for_customer
                    result.append(
                        "<li>{department}<ul>".format(
                            department=department_for_customer_save
                        )
                    )
                result.append(
                    "<li>{producer}, {product}</li>".format(
                        producer=o.producer.short_profile_name,
                        product=o.get_long_name_with_customer_price(),
                    )
                )
            if department_for_customer_save is not None:
                result.append("</ul>")
        if result:
            return mark_safe("<ul>{}</ul>".format(EMPTY_STRING.join(result)))
        return EMPTY_STRING

    def get_html_status_display(self, force_refresh=True):
        need_to_refresh_status = force_refresh or self.status in refresh_status
        if self.with_delivery_point and self.status < SaleStatus.INVOICED:
            status_list = []
            status = None
            status_counter = 0
            for delivery in DeliveryBoard.objects.filter(
                permanence_id=self.id
            ).order_by("status", "id"):
                need_to_refresh_status |= delivery.status in refresh_status
                if status != delivery.status:
                    status_counter += 1
                    status = delivery.status
                    if self.status <= delivery.status:
                        status_list.append(
                            "{}".format(
                                delivery.get_status_display().replace(" ", "&nbsp;")
                            )
                        )
                    else:
                        status_list.append(
                            "<b>{}</b>".format(_("Error, call helpdesk"))
                        )
                status_list.append(
                    "- {}".format(delivery.get_delivery_display(color=True))
                )
            message = "<br>".join(status_list)
        else:
            message = "{}".format(self.get_status_display())
        if need_to_refresh_status:
            url = reverse("repanier:display_status", args=(self.id,))
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

    def get_permanence_display(self):
        short_name = self.short_name_v2
        if short_name:
            permanence_display = "{}".format(short_name)
        else:
            from repanier.apps import REPANIER_SETTINGS_PERMANENCE_ON_NAME

            permanence_display = "{}{}".format(
                REPANIER_SETTINGS_PERMANENCE_ON_NAME,
                self.permanence_date.strftime(settings.DJANGO_SETTINGS_DATE),
            )
        return permanence_display

    def get_permanence_admin_display(self):
        return self.get_permanence_display()

    get_permanence_admin_display.short_description = _("Sales")

    def get_html_permanence_title_display(self):
        return self.get_html_permanence_display(align="vertical-align: bottom; ")

    def get_html_permanence_display(self, align=EMPTY_STRING):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
            if self.status == SaleStatus.OPENED:
                return "{} - {}".format(
                    self.get_permanence_display(), self.get_status_display()
                )
            else:
                return "{} - {}".format(
                    self.get_permanence_display(), _("Orders closed")
                )
        else:
            if self.status == SaleStatus.OPENED:
                return mark_safe(
                    '<span class="fa fa-unlock" style="{}color:#cdff60"></span> {}'.format(
                        align, self.get_permanence_display()
                    )
                )
            else:
                return mark_safe(
                    '<span class="fa fa-lock" style="{}color:Tomato"></span> {}'.format(
                        align, self.get_permanence_display()
                    )
                )

    def get_html_permanence_card_display(self):
        if settings.REPANIER_SETTINGS_TEMPLATE != "bs4":
            offer_description = Truncator(self.offer_description_v2)
            return mark_safe(
                """
            <a href="{href}" class="card-body offer">
                <h4>{title}</h4>
                <div class="excerpt">{offer_description}</div>
            </a>
            """.format(
                    href=reverse("repanier:order_view", args=(self.id,)),
                    title=self.get_html_permanence_display(),
                    offer_description=offer_description.words(30, html=True),
                )
            )
        return EMPTY_STRING

    def get_html_board_composition(self):
        from repanier.models.permanenceboard import PermanenceBoard

        board_composition = []
        for permanence_board in PermanenceBoard.objects.filter(
            permanence_id=self.id
        ).order_by("permanence_role__tree_id", "permanence_role__lft"):
            member = permanence_board.get_html_board_member
            if member is not None:
                board_composition.append(member)

        return mark_safe("<br>".join(board_composition))

    def __str__(self):
        return self.get_permanence_display()

    class Meta:
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")
        # TODO : check how to remove vvvvv
        index_together = [["permanence_date"]]


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("Offer in preparation")
        verbose_name_plural = _("Offers in preparation")


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("Offer in payment")
        verbose_name_plural = _("Offers in payment")
