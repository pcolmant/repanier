# -*- coding: utf-8

import datetime
import logging

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import F, Sum, DecimalField
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

from repanier.const import *
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.picture.const import SIZE_L
from repanier.picture.fields import RepanierPictureField
from repanier.tools import cap, create_or_update_one_purchase, debug_parameters

logger = logging.getLogger(__name__)

refresh_status = [
    PERMANENCE_WAIT_FOR_PRE_OPEN,
    PERMANENCE_WAIT_FOR_OPEN,
    PERMANENCE_WAIT_FOR_CLOSED,
    PERMANENCE_CLOSED,
    PERMANENCE_WAIT_FOR_SEND,
    PERMANENCE_WAIT_FOR_INVOICED,
]


class Permanence(TranslatableModel):
    translations = TranslatedFields(
        short_name=models.CharField(_("Offer name"), max_length=50, blank=True),
        offer_description=HTMLField(
            _("Offer description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            help_text=_(
                "This message is send by mail to all customers when opening the order or on top "
            ),
            blank=True,
            default=EMPTY_STRING,
        ),
        invoice_description=HTMLField(
            _("Invoice description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            help_text=_(
                "This message is send by mail to all customers having bought something when closing the permanence."
            ),
            blank=True,
            default=EMPTY_STRING,
        ),
    )

    status = models.CharField(
        _("Status"),
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
    )
    permanence_date = models.DateField(_("Date"), db_index=True)
    payment_date = models.DateField(
        _("Payment date"), blank=True, null=True, db_index=True
    )
    producers = models.ManyToManyField(
        "Producer", verbose_name=_("Producers"), blank=True
    )
    boxes = models.ManyToManyField("Box", verbose_name=_("Boxes"), blank=True)
    contract = models.ForeignKey(
        "Contract",
        verbose_name=_("Commitment"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=None,
    )

    with_delivery_point = models.BooleanField(_("With delivery point"), default=False)
    automatically_closed = models.BooleanField(
        _("Closing AND automatically transmitting orders"), default=False
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
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
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="permanence",
        size=SIZE_L,
    )
    gauge = models.IntegerField(default=0, editable=False)

    @cached_property
    def get_producers(self):
        if self.status == PERMANENCE_PLANNED:
            link = []
            if self.contract and len(self.contract.producers.all()) > 0:
                changelist_url = reverse("admin:repanier_product_changelist")
                for p in self.contract.producers.all():
                    link.append(
                        '<a href="{}?producer={}&commitment={}">&nbsp;{}&nbsp;{}</a>'.format(
                            changelist_url,
                            p.id,
                            self.contract.id,
                            LINK_UNICODE,
                            p.short_profile_name.replace(" ", "&nbsp;"),
                        )
                    )
            elif len(self.producers.all()) > 0:
                changelist_url = reverse("admin:repanier_product_changelist")
                for p in self.producers.all():
                    link.append(
                        '<a href="{}?producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            p.id,
                            p.short_profile_name.replace(" ", "&nbsp;"),
                        )
                    )
            if len(link) > 0:
                msg_html = '<div class="wrap-text">{}</div>'.format(", ".join(link))
            else:
                msg_html = '<div class="wrap-text">{}</div>'.format(_("No offer"))
        elif self.status == PERMANENCE_PRE_OPEN:
            link = []
            for p in self.producers.all():
                link.append(
                    "{} ({})".format(p.short_profile_name, p.get_phone1()).replace(
                        " ", "&nbsp;"
                    )
                )
            msg_html = '<div class="wrap-text">{}</div>'.format(", ".join(link))
        elif self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
            close_offeritem_changelist_url = reverse(
                "admin:repanier_offeritemclosed_changelist"
            )

            link = []
            if self.contract and len(self.contract.producers.all()) > 0:
                link_unicode = "{} ".format(LINK_UNICODE)
            else:
                link_unicode = EMPTY_STRING
            for p in self.producers.all().only("id"):
                pi = (
                    ProducerInvoice.objects.filter(
                        producer_id=p.id, permanence_id=self.id
                    )
                    .order_by("?")
                    .first()
                )
                if pi is not None:
                    if pi.status == PERMANENCE_OPENED:
                        label = (
                            "{}{} ({}) ".format(
                                link_unicode,
                                p.short_profile_name,
                                pi.get_total_price_with_tax(),
                            )
                        ).replace(" ", "&nbsp;")
                        offeritem_changelist_url = close_offeritem_changelist_url
                    else:
                        label = (
                            "{}{} ({}) {}".format(
                                link_unicode,
                                p.short_profile_name,
                                pi.get_total_price_with_tax(),
                                settings.LOCK_UNICODE,
                            )
                        ).replace(" ", "&nbsp;")
                        offeritem_changelist_url = close_offeritem_changelist_url
                else:
                    label = (
                        "{}{} ".format(link_unicode, p.short_profile_name)
                    ).replace(" ", "&nbsp;")
                    offeritem_changelist_url = close_offeritem_changelist_url
                link.append(
                    '<a href="{}?permanence={}&producer={}">{}</a>'.format(
                        offeritem_changelist_url, self.id, p.id, label
                    )
                )
            msg_html = '<div class="wrap-text">{}</div>'.format(", ".join(link))

        elif self.status in [PERMANENCE_SEND, PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            if self.contract and len(self.contract.producers.all()) > 0:
                link_unicode = "{} ".format(LINK_UNICODE)
            else:
                link_unicode = EMPTY_STRING
            send_offeritem_changelist_url = reverse(
                "admin:repanier_offeritemsend_changelist"
            )
            send_customer_changelist_url = reverse(
                "admin:repanier_customersend_changelist"
            )
            link = []
            at_least_one_permanence_send = False
            for pi in (
                ProducerInvoice.objects.filter(permanence_id=self.id)
                .select_related("producer")
                .order_by("producer")
            ):
                if pi.status == PERMANENCE_SEND:
                    at_least_one_permanence_send = True
                    if pi.producer.invoice_by_basket:
                        changelist_url = send_customer_changelist_url
                    else:
                        changelist_url = send_offeritem_changelist_url
                    # Important : no target="_blank"
                    label = "{}{} ({})".format(
                        link_unicode,
                        pi.producer.short_profile_name,
                        pi.get_total_price_with_tax(),
                    )
                    link.append(
                        '<a href="{}?permanence={}&producer={}">&nbsp;{}</a>'.format(
                            changelist_url,
                            self.id,
                            pi.producer_id,
                            label.replace(" ", "&nbsp;"),
                        )
                    )
                else:
                    if pi.invoice_reference:
                        if (
                            pi.to_be_invoiced_balance != DECIMAL_ZERO
                            or pi.total_price_with_tax != DECIMAL_ZERO
                        ):
                            label = "{}{} ({} - {})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance,
                                cap(pi.invoice_reference, 15),
                            )
                        else:
                            label = "{}{} ({})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                cap(pi.invoice_reference, 15),
                            )
                    else:
                        if (
                            pi.to_be_invoiced_balance != DECIMAL_ZERO
                            or pi.total_price_with_tax != DECIMAL_ZERO
                        ):
                            label = "{}{} ({})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance,
                            )
                        else:
                            continue
                    # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                    # Such that they can be accessed by the producer and by the staff
                    link.append(
                        '<a href="{}?producer={}" target="_blank">{}</a>'.format(
                            reverse("producer_invoice_view", args=(pi.id,)),
                            pi.producer_id,
                            label.replace(" ", "&nbsp;"),
                        )
                    )

            producers = ", ".join(link)
            if at_least_one_permanence_send:
                msg_html = '<div class="wrap-text">{}</div>'.format(producers)
            else:
                msg_html = """
                    <div class="wrap-text"><button
                    onclick="django.jQuery('#id_get_producers_{}').toggle();
                        if(django.jQuery(this).html()=='{}'){{
                            django.jQuery(this).html('{}')
                        }}else{{
                            django.jQuery(this).html('{}')
                        }};
                        return false;"
                    >{}</button>
                    <div id="id_get_producers_{}" style="display:none;">{}</div></div>
                """.format(
                    self.id,
                    _("Show"),
                    _("Hide"),
                    _("Show"),
                    _("Show"),
                    self.id,
                    producers,
                )
        else:
            msg_html = '<div class="wrap-text">{}</div>'.format(
                ", ".join(
                    [
                        p.short_profile_name
                        for p in Producer.objects.filter(
                            producerinvoice__permanence_id=self.id
                        ).only("short_profile_name")
                    ]
                )
            )
        return mark_safe(msg_html)

    get_producers.short_description = _("Offers from")

    @cached_property
    def get_customers(self):
        if self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            changelist_url = reverse("admin:repanier_purchase_changelist")
            link = []
            delivery_save = None
            for ci in (
                CustomerInvoice.objects.filter(permanence_id=self.id)
                .select_related("customer")
                .order_by("delivery", "customer")
            ):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        link.append("<br><br>--")
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
                link.append(
                    '<a href="{}?permanence={}&customer={}">{}</a>'.format(
                        changelist_url,
                        self.id,
                        ci.customer_id,
                        label.replace(" ", "&nbsp;"),
                    )
                )
            customers = ", ".join(link)
        elif self.status in [PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            link = []
            delivery_save = None
            for ci in (
                CustomerInvoice.objects.filter(permanence_id=self.id)
                .select_related("customer")
                .order_by("delivery", "customer")
            ):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append(
                            "<br><b>{}</b>".format(ci.delivery.get_delivery_display())
                        )
                    else:
                        link.append("<br><br>--")
                total_price_with_tax = ci.get_total_price_with_tax(
                    customer_charged=True
                )
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-"
                    if total_price_with_tax == DECIMAL_ZERO
                    else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                # Such that they can be accessed by the customer and by the staff
                link.append(
                    '<a href="{}?customer={}" target="_blank">{}</a>'.format(
                        reverse("customer_invoice_view", args=(ci.id,)),
                        ci.customer_id,
                        label.replace(" ", "&nbsp;"),
                    )
                )
            customers = ", ".join(link)
        else:
            customers = ", ".join(
                [
                    c.short_basket_name
                    for c in Customer.objects.filter(
                        customerinvoice__permanence_id=self.id
                    ).only("short_basket_name")
                ]
            )
        if len(customers) > 0:
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_customers_{}').toggle();
                    if(django.jQuery(this).html()=='{}'){{
                        django.jQuery(this).html('{}')
                    }}else{{
                        django.jQuery(this).html('{}')
                    }};
                    return false;"
                >{}</button>
                <div id="id_get_customers_{}" style="display:none;">{}</div></div>
            """.format(
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, customers
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No purchase")))

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
        first_board = True
        board = EMPTY_STRING
        if permanenceboard_set:
            for permanenceboard_row in permanenceboard_set:
                r_link = EMPTY_STRING
                r = permanenceboard_row.permanence_role
                if r:
                    r_url = reverse(
                        "admin:repanier_lut_permanencerole_change", args=(r.id,)
                    )
                    r_link = (
                        '<a href="'
                        + r_url
                        + '" target="_blank">'
                        + r.short_name.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                c_link = EMPTY_STRING
                c = permanenceboard_row.customer
                if c:
                    c_url = reverse("admin:repanier_customer_change", args=(c.id,))
                    c_link = (
                        '&nbsp;->&nbsp;<a href="'
                        + c_url
                        + '" target="_blank">'
                        + c.short_basket_name.replace(" ", "&nbsp;")
                        + "</a>"
                    )
                if not first_board:
                    board += "<br>"
                board += r_link + c_link
                first_board = False
        if not first_board:
            # At least one role is defined in the permanence board
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_board_{}').toggle();
                    if(django.jQuery(this).html()=='{}'){{
                        django.jQuery(this).html('{}')
                    }}else{{
                        django.jQuery(this).html('{}')
                    }};
                    return false;"
                >{}</button>
                <div id="id_get_board_{}" style="display:none;">{}</div></div>
            """.format(
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, board
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">{}</div>'.format(_("No task")))

    get_board.short_description = _("Tasks")

    @transaction.atomic
    @debug_parameters
    def set_status(
        self,
        old_status=(),
        new_status=None,
        everything=True,
        deliveries_id=(),
        update_payment_date=False,
        payment_date=None,
    ):
        if everything:
            permanence = (
                Permanence.objects.select_for_update()
                .filter(id=self.id, status__in=old_status)
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
            qs = (
                DeliveryBoard.objects.filter(permanence_id=self.id)
                .exclude(status=new_status)
                .order_by("?")
            )
            if not everything:
                qs = qs.filter(id__in=deliveries_id)
            for delivery_point in qs:
                delivery_point.set_status(new_status)
            if everything:
                ProducerInvoice.objects.filter(permanence_id=self.id).order_by(
                    "?"
                ).update(status=new_status)
        else:
            from repanier.models.purchase import PurchaseWoReceiver

            PurchaseWoReceiver.objects.filter(permanence_id=self.id).exclude(
                status=new_status
            ).order_by("?").update(status=new_status)
            CustomerInvoice.objects.filter(permanence_id=self.id).order_by("?").update(
                status=new_status
            )
            ProducerInvoice.objects.filter(permanence_id=self.id).order_by("?").update(
                status=new_status
            )
        if everything:
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
            OfferItemWoReceiver.objects.filter(permanence_id=self.id, may_order=True)
            .order_by()
            .distinct("producer_id")
        ):
            self.producers.add(offer_item.producer_id)
        OfferItemWoReceiver.objects.filter(permanence_id=self.id).update(
            may_order=False
        )

    @transaction.atomic
    def close_order(self, everything, deliveries_id=()):
        from repanier.apps import (
            REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION,
            REPANIER_SETTINGS_MEMBERSHIP_FEE,
        )

        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            # Cancel unconfirmed purchases whichever the producer is
            customer_invoice_qs = CustomerInvoice.objects.filter(
                permanence_id=self.id, is_order_confirm_send=False, status=self.status
            ).order_by("?")
            if self.with_delivery_point:
                customer_invoice_qs = customer_invoice_qs.filter(
                    delivery_id__in=deliveries_id
                )
            for customer_invoice in customer_invoice_qs:
                customer_invoice.cancel_if_unconfirmed(self)
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
                        permanence_id=self.id, customer_charged_id=F("customer_id")
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
                    if not customer.represent_this_buyinggroup:
                        # Should pay a membership fee
                        if customer.membership_fee_valid_until < self.permanence_date:
                            membership_fee_offer_item = membership_fee_product.get_or_create_offer_item(
                                self
                            )
                            self.producers.add(membership_fee_offer_item.producer_id)
                            create_or_update_one_purchase(
                                customer_id=customer.id,
                                offer_item=membership_fee_offer_item,
                                status=PERMANENCE_OPENED,
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
                customerinvoice__permanence_id=self.id,
                represent_this_buyinggroup=False,
            ).order_by("?")
            if self.with_delivery_point:
                customer_qs = customer_qs.filter(
                    customerinvoice__delivery_id__in=deliveries_id
                )
            for customer in customer_qs:
                offer_item_qs = OfferItem.objects.filter(
                    permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_DEPOSIT
                ).order_by("?")
                # if not everything:
                #     offer_item_qs = offer_item_qs.filter(producer_id__in=producers_id)
                for offer_item in offer_item_qs:
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=PERMANENCE_OPENED,
                        q_order=1,
                        batch_job=True,
                        is_box_content=False,
                        comment=EMPTY_STRING,
                    )
                    create_or_update_one_purchase(
                        customer_id=customer.id,
                        offer_item=offer_item,
                        status=PERMANENCE_OPENED,
                        q_order=0,
                        batch_job=True,
                        is_box_content=False,
                        comment=EMPTY_STRING,
                    )
        if everything:
            # Round to multiple producer_order_by_quantity
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=self.id,
                may_order=True,
                order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,
                producer_order_by_quantity__gt=1,
                quantity_invoiced__gt=0,
            ).order_by("?")
            for offer_item in offer_item_qs:
                # It's possible to round the ordered qty even If we do not manage stock
                if offer_item.manage_replenishment:
                    needed = offer_item.quantity_invoiced - offer_item.stock
                else:
                    needed = offer_item.quantity_invoiced
                if needed > DECIMAL_ZERO:
                    offer_item.add_2_stock = offer_item.producer_order_by_quantity - (
                        needed % offer_item.producer_order_by_quantity
                    )
                    offer_item.save()
            # Add Transport
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_TRANSPORTATION
            ).order_by("?")
            group_id = Customer.get_or_create_group().id
            for offer_item in offer_item_qs:
                create_or_update_one_purchase(
                    customer_id=group_id,
                    offer_item=offer_item,
                    status=PERMANENCE_OPENED,
                    q_order=1,
                    batch_job=True,
                    is_box_content=False,
                    comment=EMPTY_STRING,
                )

    @transaction.atomic
    def invoice(self, payment_date):
        from repanier.models.purchase import PurchaseWoReceiver

        self.set_status(
            old_status=(PERMANENCE_SEND,), new_status=PERMANENCE_WAIT_FOR_INVOICED
        )
        bank_account = (
            BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL)
            .order_by("?")
            .first()
        )
        producer_buyinggroup = Producer.get_or_create_group()
        customer_buyinggroup = Customer.get_or_create_group()
        if (
            bank_account is None
            or producer_buyinggroup is None
            or customer_buyinggroup is None
        ):
            return
        customer_invoice_buyinggroup = (
            CustomerInvoice.objects.filter(
                customer_id=customer_buyinggroup.id, permanence_id=self.id
            )
            .order_by("?")
            .first()
        )
        if customer_invoice_buyinggroup is None:
            customer_invoice_buyinggroup = CustomerInvoice.objects.create(
                customer_id=customer_buyinggroup.id,
                permanence_id=self.id,
                date_previous_balance=customer_buyinggroup.date_balance,
                previous_balance=customer_buyinggroup.balance,
                date_balance=payment_date,
                balance=customer_buyinggroup.balance,
                customer_charged_id=customer_buyinggroup.id,
                transport=DECIMAL_ZERO,
                min_transport=DECIMAL_ZERO,
                price_list_multiplier=DECIMAL_ONE,
            )
        old_bank_latest_total = (
            bank_account.bank_amount_in.amount - bank_account.bank_amount_out.amount
        )
        permanence_partially_invoiced = (
            ProducerInvoice.objects.filter(
                permanence_id=self.id, invoice_sort_order__isnull=True, to_be_paid=False
            )
            .order_by("?")
            .exists()
        )
        if permanence_partially_invoiced:
            # Move the producers not invoiced into a new permanence
            producers_to_keep = list(
                Producer.objects.filter(
                    producerinvoice__permanence_id=self.id,
                    producerinvoice__invoice_sort_order__isnull=True,
                    producerinvoice__to_be_paid=True,
                )
                .values_list("id", flat=True)
                .order_by("?")
            )
            self.producers.clear()
            self.producers.add(*producers_to_keep)
            producers_to_move = list(
                Producer.objects.filter(
                    producerinvoice__permanence_id=self.id,
                    producerinvoice__invoice_sort_order__isnull=True,
                    producerinvoice__to_be_paid=False,
                )
                .values_list("id", flat=True)
                .order_by("?")
            )
            new_permanence = self.create_child(PERMANENCE_SEND)
            new_permanence.producers.add(*producers_to_move)
            ProducerInvoice.objects.filter(
                permanence_id=self.id, producer_id__in=producers_to_move
            ).order_by("?").update(
                permanence_id=new_permanence.id, status=PERMANENCE_SEND
            )
            CustomerProducerInvoice.objects.filter(
                permanence_id=self.id, producer_id__in=producers_to_move
            ).order_by("?").update(permanence_id=new_permanence.id)
            OfferItemWoReceiver.objects.filter(
                permanence_id=self.id, producer_id__in=producers_to_move
            ).order_by("?").update(permanence_id=new_permanence.id)

            customer_invoice_id_to_create = list(
                PurchaseWoReceiver.objects.filter(
                    permanence_id=self.id, producer_id__in=producers_to_move
                )
                .order_by("customer_invoice_id")
                .distinct("customer_invoice")
                .values_list("customer_invoice", flat=True)
            )
            for customer_invoice_id in customer_invoice_id_to_create:
                customer_invoice = (
                    CustomerInvoice.objects.filter(id=customer_invoice_id)
                    .order_by("?")
                    .first()
                )
                new_customer_invoice = customer_invoice.create_child(
                    new_permanence=new_permanence
                )
                new_customer_invoice.set_order_delivery(customer_invoice.delivery)
                new_customer_invoice.calculate_order_price()
                # Save new_customer_invoice before reference it when updating the purchases
                new_customer_invoice.save()
                # Important : The purchase customer charged must be calculated before calculate_and_save_delta_buyinggroup
                PurchaseWoReceiver.objects.filter(
                    customer_invoice_id=customer_invoice.id,
                    producer_id__in=producers_to_move,
                ).order_by("?").update(
                    permanence_id=new_permanence.id,
                    customer_invoice_id=new_customer_invoice.id,
                    status=PERMANENCE_SEND,
                )

            new_permanence.recalculate_order_amount(re_init=True)
            new_permanence.save()

        self.save()

        for customer_invoice in CustomerInvoice.objects.filter(permanence_id=self.id):
            customer_invoice.balance = (
                customer_invoice.previous_balance
            ) = customer_invoice.customer.balance
            customer_invoice.date_previous_balance = (
                customer_invoice.customer.date_balance
            )
            customer_invoice.date_balance = payment_date

            if customer_invoice.customer_id == customer_invoice.customer_charged_id:
                # ajuster sa balance
                # il a droit aux réductions
                total_price_with_tax = (
                    customer_invoice.get_total_price_with_tax().amount
                )
                customer_invoice.balance.amount -= total_price_with_tax
                Customer.objects.filter(id=customer_invoice.customer_id).update(
                    date_balance=payment_date,
                    balance=F("balance") - total_price_with_tax,
                )
            else:
                # ne pas modifier sa balance
                # ajuster la balance de celui qui paye
                # celui qui paye a droit aux réductions
                Customer.objects.filter(id=customer_invoice.customer_id).update(
                    date_balance=payment_date
                )
            customer_invoice.save()

        # Claculate new stock
        for offer_item in OfferItem.objects.filter(
            is_active=True, manage_replenishment=True, permanence_id=self.id
        ).order_by("?"):
            invoiced_qty, taken_from_stock, customer_qty = (
                offer_item.get_producer_qty_stock_invoiced()
            )
            if taken_from_stock != DECIMAL_ZERO:
                if (
                    offer_item.price_list_multiplier < DECIMAL_ONE
                ):  # or offer_item.is_resale_price_fixed:
                    unit_price = offer_item.customer_unit_price.amount
                    unit_vat = offer_item.customer_vat.amount
                else:
                    unit_price = offer_item.producer_unit_price.amount
                    unit_vat = offer_item.producer_vat.amount
                delta_price_with_tax = (
                    (unit_price + offer_item.unit_deposit.amount) * taken_from_stock
                ).quantize(TWO_DECIMALS)
                delta_vat = unit_vat * taken_from_stock
                delta_deposit = offer_item.unit_deposit.amount * taken_from_stock
                producer_invoice = ProducerInvoice.objects.get(
                    producer_id=offer_item.producer_id, permanence_id=self.id
                )
                producer_invoice.delta_stock_with_tax.amount -= delta_price_with_tax
                producer_invoice.delta_stock_vat.amount -= delta_vat
                producer_invoice.delta_stock_deposit.amount -= delta_deposit
                producer_invoice.save(
                    update_fields=[
                        "delta_stock_with_tax",
                        "delta_stock_vat",
                        "delta_stock_deposit",
                    ]
                )

            # Update new_stock even if no order
            # // xslx_stock and task_invoice
            offer_item.new_stock = (
                offer_item.stock - taken_from_stock + offer_item.add_2_stock
            )
            if offer_item.new_stock < DECIMAL_ZERO:
                offer_item.new_stock = DECIMAL_ZERO
            offer_item.previous_add_2_stock = offer_item.add_2_stock
            offer_item.previous_producer_unit_price = offer_item.producer_unit_price
            offer_item.previous_unit_deposit = offer_item.unit_deposit
            if self.highest_status <= PERMANENCE_SEND:
                # Asked by Bees-Coop : Do not update stock when canceling
                new_stock = (
                    offer_item.stock
                    if offer_item.stock > DECIMAL_ZERO
                    else DECIMAL_ZERO
                )
                Product.objects.filter(
                    id=offer_item.product_id, stock=new_stock
                ).update(stock=offer_item.new_stock)
            offer_item.save()

        for producer_invoice in ProducerInvoice.objects.filter(permanence_id=self.id):
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

        result_set = (
            PurchaseWoReceiver.objects.filter(
                permanence_id=self.id,
                is_box_content=False,
                offer_item__price_list_multiplier__gte=DECIMAL_ONE,
                producer__represent_this_buyinggroup=False,
            )
            .order_by("?")
            .aggregate(
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
                producer_vat=Sum(
                    "producer_vat",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                    ),
                ),
                customer_vat=Sum(
                    "customer_vat",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=4, default=DECIMAL_ZERO
                    ),
                ),
            )
        )

        total_purchase_price_with_tax = (
            result_set["purchase_price"]
            if result_set["purchase_price"] is not None
            else DECIMAL_ZERO
        )
        total_selling_price_with_tax = (
            result_set["selling_price"]
            if result_set["selling_price"] is not None
            else DECIMAL_ZERO
        )
        total_customer_vat = (
            result_set["customer_vat"]
            if result_set["customer_vat"] is not None
            else DECIMAL_ZERO
        )
        total_producer_vat = (
            result_set["producer_vat"]
            if result_set["producer_vat"] is not None
            else DECIMAL_ZERO
        )

        purchases_delta_vat = total_customer_vat - total_producer_vat
        purchases_delta_price_with_tax = (
            total_selling_price_with_tax - total_purchase_price_with_tax
        )

        purchases_delta_price_wo_tax = (
            purchases_delta_price_with_tax - purchases_delta_vat
        )

        if purchases_delta_price_wo_tax != DECIMAL_ZERO:
            BankAccount.objects.create(
                permanence_id=self.id,
                producer=None,
                customer_id=customer_buyinggroup.id,
                operation_date=payment_date,
                operation_status=BANK_PROFIT,
                operation_comment=_("Profit")
                if purchases_delta_price_wo_tax >= DECIMAL_ZERO
                else _("Lost"),
                bank_amount_out=-purchases_delta_price_wo_tax
                if purchases_delta_price_wo_tax < DECIMAL_ZERO
                else DECIMAL_ZERO,
                bank_amount_in=purchases_delta_price_wo_tax
                if purchases_delta_price_wo_tax > DECIMAL_ZERO
                else DECIMAL_ZERO,
                customer_invoice_id=None,
                producer_invoice=None,
            )
        if purchases_delta_vat != DECIMAL_ZERO:
            BankAccount.objects.create(
                permanence_id=self.id,
                producer=None,
                customer_id=customer_buyinggroup.id,
                operation_date=payment_date,
                operation_status=BANK_TAX,
                operation_comment=_("VAT to pay to the tax authorities")
                if purchases_delta_vat >= DECIMAL_ZERO
                else _("VAT to receive from the tax authorities"),
                bank_amount_out=-purchases_delta_vat
                if purchases_delta_vat < DECIMAL_ZERO
                else DECIMAL_ZERO,
                bank_amount_in=purchases_delta_vat
                if purchases_delta_vat > DECIMAL_ZERO
                else DECIMAL_ZERO,
                customer_invoice_id=None,
                producer_invoice=None,
            )

        for customer_invoice in CustomerInvoice.objects.filter(
            permanence_id=self.id
        ).exclude(customer_id=customer_buyinggroup.id, delta_transport=DECIMAL_ZERO):
            if customer_invoice.delta_transport != DECIMAL_ZERO:
                # --> This bank movement is not a real entry
                # customer_invoice_id=customer_invoice_buyinggroup.id
                # making this, it will not be counted into the customer_buyinggroup movements twice
                # because Repanier will see it has already been counted into the customer_buyinggroup movements
                BankAccount.objects.create(
                    permanence_id=self.id,
                    producer=None,
                    customer_id=customer_buyinggroup.id,
                    operation_date=payment_date,
                    operation_status=BANK_PROFIT,
                    operation_comment="{} : {}".format(
                        _("Shipping"), customer_invoice.customer.short_basket_name
                    ),
                    bank_amount_in=customer_invoice.delta_transport,
                    bank_amount_out=DECIMAL_ZERO,
                    customer_invoice_id=customer_invoice_buyinggroup.id,
                    producer_invoice=None,
                )

        # generate bank account movements
        self.generate_bank_account_movement(payment_date=payment_date)

        new_bank_latest_total = old_bank_latest_total

        # Calculate new current balance : Bank
        for bank_account in (
            BankAccount.objects.select_for_update()
            .filter(
                customer_invoice__isnull=True,
                producer_invoice__isnull=True,
                operation_status__in=[BANK_PROFIT, BANK_TAX],
                customer_id=customer_buyinggroup.id,
                operation_date__lte=payment_date,
            )
            .order_by("?")
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

            customer_invoice = (
                CustomerInvoice.objects.filter(
                    customer_id=bank_account.customer_id, permanence_id=self.id
                )
                .order_by("?")
                .first()
            )
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

            producer_invoice = (
                ProducerInvoice.objects.filter(
                    producer_id=bank_account.producer_id, permanence_id=self.id
                )
                .order_by("?")
                .first()
            )
            if producer_invoice is None:
                producer_invoice = ProducerInvoice.objects.create(
                    producer=bank_account.producer,
                    permanence_id=self.id,
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

        BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by(
            "?"
        ).update(operation_status=BANK_NOT_LATEST_TOTAL)
        # Important : Create a new bank total for this permanence even if there is no bank movement
        bank_account = BankAccount.objects.create(
            permanence_id=self.id,
            producer=None,
            customer=None,
            operation_date=payment_date,
            operation_status=BANK_LATEST_TOTAL,
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
        Permanence.objects.filter(id=self.id).update(invoice_sort_order=bank_account.id)

        new_status = (
            PERMANENCE_INVOICED
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING
            else PERMANENCE_ARCHIVED
        )
        self.set_status(
            old_status=(PERMANENCE_WAIT_FOR_INVOICED,),
            new_status=new_status,
            update_payment_date=True,
            payment_date=payment_date,
        )

    @transaction.atomic
    def cancel_invoice(self, last_bank_account_total):
        self.set_status(
            old_status=(PERMANENCE_INVOICED,),
            new_status=PERMANENCE_WAIT_FOR_CANCEL_INVOICE,
        )
        CustomerInvoice.objects.filter(permanence_id=self.id).update(
            bank_amount_in=DECIMAL_ZERO,
            bank_amount_out=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )
        for customer_invoice in CustomerInvoice.objects.filter(
            permanence_id=self.id
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
            delta_deposit=DECIMAL_ZERO,
            delta_stock_with_tax=DECIMAL_ZERO,
            delta_stock_vat=DECIMAL_ZERO,
            delta_stock_deposit=DECIMAL_ZERO,
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
            delta_stock_with_tax=DECIMAL_ZERO,
            delta_stock_vat=DECIMAL_ZERO,
            delta_stock_deposit=DECIMAL_ZERO,
            balance=F("previous_balance"),
            date_balance=F("date_previous_balance"),
            invoice_sort_order=None,
        )

        for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=self.id
        ).order_by("?"):
            Producer.objects.filter(id=producer_invoice.producer_id).order_by(
                "?"
            ).update(
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
            bank_account.operation_status = BANK_LATEST_TOTAL
            bank_account.save()
        # Delete also all payments recorded to producers, bank profit, bank tax
        # Delete also all compensation recorded to producers
        BankAccount.objects.filter(
            permanence_id=self.id,
            operation_status__in=[
                BANK_CALCULATED_INVOICE,
                BANK_PROFIT,
                BANK_TAX,
                BANK_MEMBERSHIP_FEE,
                BANK_COMPENSATION,  # BANK_COMPENSATION may occurs in previous release of Repanier
            ],
        ).order_by("?").delete()
        Permanence.objects.filter(id=self.id).update(invoice_sort_order=None)
        self.set_status(
            old_status=(PERMANENCE_WAIT_FOR_CANCEL_INVOICE,), new_status=PERMANENCE_SEND
        )

    @transaction.atomic
    def cancel_delivery(self):
        self.set_status(old_status=(PERMANENCE_SEND,), new_status=PERMANENCE_CANCELLED)
        bank_account = BankAccount.get_closest_to(self.permanence_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    @transaction.atomic
    def archive(self):
        self.set_status(old_status=(PERMANENCE_SEND,), new_status=PERMANENCE_ARCHIVED)
        bank_account = BankAccount.get_closest_to(self.permanence_date)
        if bank_account is not None:
            self.invoice_sort_order = bank_account.id
            self.save(update_fields=["invoice_sort_order"])

    def duplicate(self, dates):
        creation_counter = 0
        short_name = self.safe_translation_getter(
            "short_name", any_language=True, default=EMPTY_STRING
        )
        cur_language = translation.get_language()
        for date in dates[:56]:
            # Limit to 56 weeks
            if short_name != EMPTY_STRING:
                # Mandatory because of Parler
                already_exists = Permanence.objects.filter(
                    permanence_date=date,
                    translations__language_code=cur_language,
                    translations__short_name=short_name,
                ).exists()
            else:
                already_exists = False
                for existing_permanence in Permanence.objects.filter(
                    permanence_date=date
                ):
                    try:
                        short_name = existing_permanence.short_name
                        already_exists = short_name == EMPTY_STRING
                    except TranslationDoesNotExist:
                        already_exists = True
                    if already_exists:
                        break
            if not already_exists:
                creation_counter += 1
                new_permanence = Permanence.objects.create(permanence_date=date)
                self.duplicate_short_name(
                    new_permanence, cur_language=translation.get_language()
                )
                for permanence_board in PermanenceBoard.objects.filter(permanence=self):
                    PermanenceBoard.objects.create(
                        permanence=new_permanence,
                        permanence_role=permanence_board.permanence_role,
                    )
                for delivery_board in DeliveryBoard.objects.filter(permanence=self):
                    new_delivery_board = DeliveryBoard.objects.create(
                        permanence=new_permanence,
                        delivery_point=delivery_board.delivery_point,
                    )
                    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                        language_code = language["code"]
                        translation.activate(language_code)
                        new_delivery_board.set_current_language(language_code)
                        delivery_board.set_current_language(language_code)
                        try:
                            new_delivery_board.delivery_comment = (
                                delivery_board.delivery_comment
                            )
                            new_delivery_board.save_translations()
                        except TranslationDoesNotExist:
                            pass
                    translation.activate(cur_language)
                for a_producer in self.producers.all():
                    new_permanence.producers.add(a_producer)
        return creation_counter

    def generate_bank_account_movement(self, payment_date):

        for producer_invoice in ProducerInvoice.objects.filter(
            permanence_id=self.id, invoice_sort_order__isnull=True, to_be_paid=True
        ).select_related("producer"):
            # We have to pay something
            producer = producer_invoice.producer
            result_set = (
                BankAccount.objects.filter(
                    producer_id=producer.id, producer_invoice__isnull=True
                )
                .order_by("?")
                .aggregate(
                    bank_amount_in=Sum(
                        "bank_amount_in",
                        output_field=DecimalField(
                            max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                        ),
                    ),
                    bank_amount_out=Sum(
                        "bank_amount_out",
                        output_field=DecimalField(
                            max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                        ),
                    ),
                )
            )

            total_bank_amount_in = (
                result_set["bank_amount_in"]
                if result_set["bank_amount_in"] is not None
                else DECIMAL_ZERO
            )
            total_bank_amount_out = (
                result_set["bank_amount_out"]
                if result_set["bank_amount_out"] is not None
                else DECIMAL_ZERO
            )
            bank_not_invoiced = total_bank_amount_out - total_bank_amount_in

            if (
                producer.balance.amount != DECIMAL_ZERO
                or producer_invoice.to_be_invoiced_balance.amount != DECIMAL_ZERO
                or bank_not_invoiced != DECIMAL_ZERO
            ):

                delta = (
                    producer_invoice.to_be_invoiced_balance.amount - bank_not_invoiced
                ).quantize(TWO_DECIMALS)

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
                        operation_status=BANK_CALCULATED_INVOICE,
                        operation_comment=cap(operation_comment, 100),
                        bank_amount_out=delta,
                        customer_invoice=None,
                        producer_invoice=None,
                    )

            delta = (
                producer.balance.amount - producer_invoice.to_be_invoiced_balance.amount
            ).quantize(TWO_DECIMALS)
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
                    operation_status=BANK_PROFIT,
                    operation_comment=cap(operation_comment, 100),
                    bank_amount_in=delta if delta > DECIMAL_ZERO else DECIMAL_ZERO,
                    bank_amount_out=-delta if delta < DECIMAL_ZERO else DECIMAL_ZERO,
                    customer_invoice_id=None,
                    producer_invoice=None,
                )
            producer_invoice.balance.amount -= delta
            producer_invoice.save(update_fields=["balance"])
            producer.balance.amount -= delta
            producer.save(update_fields=["balance"])

        return

    def duplicate_short_name(self, new_permanence, cur_language):
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            translation.activate(language_code)
            new_permanence.set_current_language(language_code)
            self.set_current_language(language_code)
            try:
                new_permanence.short_name = self.safe_translation_getter(
                    "short_name", any_language=True
                )
                new_permanence.save_translations()
            except TranslationDoesNotExist:
                pass
        translation.activate(cur_language)
        return new_permanence

    def create_child(self, status):
        child_permanence = Permanence.objects.create(
            permanence_date=self.permanence_date,
            master_permanence_id=self.id,
            status=status,
        )
        return self.duplicate_short_name(
            child_permanence, cur_language=translation.get_language()
        )

    def recalculate_order_amount(
        self, offer_item_qs=None, re_init=False, send_to_producer=False
    ):
        from repanier.models.purchase import Purchase

        if send_to_producer or re_init:
            assert (
                offer_item_qs is None
            ), "offer_item_qs must be set to None when send_to_producer or re_init"
            ProducerInvoice.objects.filter(permanence_id=self.id).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            CustomerInvoice.objects.filter(permanence_id=self.id).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            CustomerProducerInvoice.objects.filter(permanence_id=self.id).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO,
            )
            OfferItemWoReceiver.objects.filter(permanence_id=self.id).update(
                quantity_invoiced=DECIMAL_ZERO,
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO,
            )
            for offer_item in (
                OfferItem.objects.filter(
                    permanence_id=self.id, is_active=True, manage_replenishment=True
                )
                .exclude(add_2_stock=DECIMAL_ZERO)
                .order_by("?")
            ):
                # Recalculate the total_price_with_tax of ProducerInvoice and
                # the total_purchase_with_tax of OfferItem
                # taking into account "add_2_stock"
                offer_item.previous_add_2_stock = DECIMAL_ZERO
                offer_item.save()

        purchase_set = Purchase.objects.filter(permanence_id=self.id).order_by("?")
        if offer_item_qs is not None:
            purchase_set = purchase_set.filter(offer_item__in=offer_item_qs)

        for a_purchase in purchase_set.select_related("offer_item", "customer_invoice"):
            # Recalculate the total_price_with_tax of ProducerInvoice,
            # the total_price_with_tax of CustomerInvoice,
            # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
            # and quantity_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
            if send_to_producer or re_init:
                a_purchase.previous_quantity_ordered = DECIMAL_ZERO
                a_purchase.previous_quantity_invoiced = DECIMAL_ZERO
                a_purchase.previous_purchase_price = DECIMAL_ZERO
                a_purchase.previous_selling_price = DECIMAL_ZERO
                a_purchase.previous_producer_vat = DECIMAL_ZERO
                a_purchase.previous_customer_vat = DECIMAL_ZERO
                a_purchase.previous_deposit = DECIMAL_ZERO
                if send_to_producer and a_purchase.status == PERMANENCE_WAIT_FOR_SEND:
                    offer_item = a_purchase.offer_item
                    if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                        a_purchase.quantity_invoiced = (
                            a_purchase.quantity_ordered
                            * offer_item.order_average_weight
                        ).quantize(FOUR_DECIMALS)
                    else:
                        a_purchase.quantity_invoiced = a_purchase.quantity_ordered
            a_purchase.save()

        if send_to_producer:
            OfferItemWoReceiver.objects.filter(
                permanence_id=self.id, order_unit=PRODUCT_ORDER_UNIT_PC_KG
            ).order_by("?").update(use_order_unit_converted=True)
        self.save()

    @cached_property
    def get_new_products(self):
        assert self.status < PERMANENCE_SEND
        result = []
        for a_producer in self.producers.all():
            current_products = list(
                OfferItemWoReceiver.objects.filter(
                    is_active=True,
                    may_order=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                    permanence_id=self.id,
                    producer=a_producer,
                )
                .values_list("product", flat=True)
                .order_by("?")
            )
            six_months_ago = timezone.now().date() - datetime.timedelta(days=6 * 30)
            previous_permanence = (
                Permanence.objects.filter(
                    status__gte=PERMANENCE_SEND,
                    producers=a_producer,
                    permanence_date__gte=six_months_ago,
                )
                .order_by("-permanence_date", "status")
                .first()
            )
            if previous_permanence is not None:
                previous_products = list(
                    OfferItemWoReceiver.objects.filter(
                        is_active=True,
                        may_order=True,
                        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                        permanence_id=previous_permanence.id,
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
                permanence_id=self.id,
                product__in=new_products,
                translations__language_code=translation.get_language(),
            ).order_by("translations__order_sort_order")
            department_for_customer_save = None
            for o in qs:
                if department_for_customer_save != o.department_for_customer:
                    if department_for_customer_save is not None:
                        result.append("</ul></li>")
                    department_for_customer_save = o.department_for_customer
                    result.append("<li>{}<ul>".format(department_for_customer_save))
                result.append(
                    "<li>{}</li>".format(o.get_long_name_with_producer(is_html=True))
                )
            if department_for_customer_save is not None:
                result.append("</ul>")
        if result:
            return mark_safe("<ul>{}</ul>".format(EMPTY_STRING.join(result)))
        return EMPTY_STRING

    def get_html_status_display(self, force_refresh=True):
        need_to_refresh_status = force_refresh or self.status in refresh_status
        if self.with_delivery_point and self.status < PERMANENCE_INVOICED:
            status_list = []
            status = None
            status_counter = 0
            for delivery in DeliveryBoard.objects.filter(
                permanence_id=self.id
            ).order_by("status", "id"):
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
            url = reverse("display_status", args=(self.id,))
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
        short_name = self.safe_translation_getter("short_name", any_language=True)
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

    get_permanence_admin_display.short_description = _("Offers")

    def get_html_permanence_title_display(self):
        return self.get_html_permanence_display(align="vertical-align: bottom; ")

    def get_html_permanence_display(self, align=EMPTY_STRING):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
            if self.status == PERMANENCE_OPENED:
                return "{} - {}".format(
                    self.get_permanence_display(), self.get_status_display()
                )
            else:
                return "{} - {}".format(
                    self.get_permanence_display(), _("Orders closed")
                )
        else:
            if self.status == PERMANENCE_OPENED:
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
                    href=reverse("order_view", args=(self.id,)),
                    title=self.get_html_permanence_display(),
                    offer_description=offer_description.words(30, html=True),
                )
            )
        return EMPTY_STRING

    def get_html_board_composition(self):
        from repanier.models.permanenceboard import PermanenceBoard

        board_composition = []
        for permanenceboard in PermanenceBoard.objects.filter(
            permanence_id=self.id
        ).order_by("permanence_role__tree_id", "permanence_role__lft"):
            member = permanenceboard.get_html_board_member()
            if member is not None:
                board_composition.append(member)

        return mark_safe("<br>".join(board_composition))

    def __str__(self):
        return self.get_permanence_display()

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

        index_together = [["permanence_date"]]


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("Offer in preparation")
        verbose_name_plural = _("Offers in preparation")


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("Billing offer")
        verbose_name_plural = _("Billing offers")
