import codecs
import datetime
import json
import logging
import os
from functools import wraps
from urllib.parse import urljoin
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from repanier import apps
from repanier import const

logger = logging.getLogger(__name__)
reader = codecs.getreader("utf-8")


def sboolean(str_val, default_val=False):
    try:
        return bool(str_val)
    except:
        return default_val


def sint(str_val, default_val=0):
    try:
        return int(str_val)
    except:
        return default_val


if settings.DEBUG:

    def debug_parameters(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            logger.debug("__module__ %s", func_wrapper.__module__)
            logger.debug("__name__ %s", func_wrapper.__name__)
            logger.debug("Must-have arguments are: %s", list(args))
            logger.debug("Optional arguments are: %s", kwargs)
            return func(*args, **kwargs)

        return func_wrapper


else:

    def debug_parameters(func):
        def func_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return func_wrapper


def get_admin_template_name(template_name):
    return os.path.join(
        settings.REPANIER_SETTINGS_TEMPLATE, "admin", "repanier", template_name
    )


def get_repanier_template_name(template_name):
    return os.path.join(settings.REPANIER_SETTINGS_TEMPLATE, "repanier", template_name)


def get_repanier_static_name(template_name):
    return os.path.join("repanier", settings.REPANIER_SETTINGS_TEMPLATE, template_name)


def next_row(query_iterator):
    try:
        return next(query_iterator)
    except StopIteration:
        # No rows were found, so do nothing.
        return


def send_sms(sms_nr=None, sms_msg=None):
    try:
        if sms_nr is not None and sms_msg is not None:
            valid_nr = "0"
            i = 0
            while i < len(sms_nr) and not sms_nr[i] == "4":
                i += 1
            while i < len(sms_nr):
                if "0" <= sms_nr[i] <= "9":
                    valid_nr += sms_nr[i]
                i += 1
            if len(valid_nr) == 10:
                if settings.REPANIER_SETTINGS_SMS_GATEWAY_MAIL:
                    from repanier.email.email import RepanierEmail

                    # Send SMS with free gateway : Sms Gateway - Android.
                    email = RepanierEmail(
                        valid_nr,
                        html_body=sms_msg,
                        to=[settings.REPANIER_SETTINGS_SMS_GATEWAY_MAIL],
                    )
                    email.send_email()
    except:
        pass


def cap(s, l):
    if s is not None:
        if not isinstance(s, str):
            s = str(s)
        s = s if len(s) <= l else s[0 : l - 4] + "..."
        return s
    else:
        return


def permanence_ok_or_404(permanence):
    if permanence is None:
        raise Http404
    if permanence.status not in [
        const.PERMANENCE_OPENED,
        const.PERMANENCE_CLOSED,
        const.PERMANENCE_SEND,
    ]:
        if permanence.status in [const.PERMANENCE_INVOICED, const.PERMANENCE_ARCHIVED]:
            if (
                permanence.permanence_date
                < (
                    timezone.now()
                    - datetime.timedelta(weeks=const.LIMIT_DISPLAYED_PERMANENCE)
                ).date()
            ):
                raise Http404
        else:
            raise Http404


def get_invoice_unit(order_unit, qty=0):
    if order_unit in [const.PRODUCT_ORDER_UNIT_KG, const.PRODUCT_ORDER_UNIT_PC_KG]:
        unit = _("/ kg")
    elif order_unit == const.PRODUCT_ORDER_UNIT_LT:
        unit = _("/ l")
    else:
        if qty < 2:
            unit = _("/ piece")
        else:
            unit = _("/ pieces")
    return unit


def get_reverse_invoice_unit(unit):
    # reverse of tools get_invoice_unit
    if unit == _("/ kg"):
        order_unit = const.PRODUCT_ORDER_UNIT_KG
    elif unit == _("/ l"):
        order_unit = const.PRODUCT_ORDER_UNIT_LT
    else:
        order_unit = const.PRODUCT_ORDER_UNIT_PC
    return order_unit


def get_base_unit(order_unit, qty=0):
    if order_unit == const.PRODUCT_ORDER_UNIT_KG:
        if qty == const.DECIMAL_ZERO:
            base_unit = const.EMPTY_STRING
        else:
            base_unit = _("kg")
    elif order_unit == const.PRODUCT_ORDER_UNIT_LT:
        if qty == const.DECIMAL_ZERO:
            base_unit = const.EMPTY_STRING
        else:
            base_unit = _("l")
    else:
        if qty == const.DECIMAL_ZERO:
            base_unit = const.EMPTY_STRING
        elif qty < 2:
            base_unit = _("piece")
        else:
            base_unit = _("pieces")
    return base_unit


def payment_message(customer, permanence):
    from repanier.models.invoice import CustomerInvoice

    customer_invoice = (
        CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence_id=permanence.id
        )
        .first()
    )

    total_price_with_tax = customer_invoice.get_total_price_with_tax()
    customer_order_amount = _("The amount of your order is %(amount)s.") % {
        "amount": total_price_with_tax
    }
    if customer.balance.amount != const.DECIMAL_ZERO:
        if customer.balance.amount < const.DECIMAL_ZERO:
            balance = '<font color="#bd0926">{}</font>'.format(customer.balance)
        else:
            balance = "{}".format(customer.balance)
        customer_last_balance = _(
            "The balance of your account as of %(date)s is %(balance)s."
        ) % {
            "date": customer.date_balance.strftime(settings.DJANGO_SETTINGS_DATE),
            "balance": balance,
        }
    else:
        customer_last_balance = const.EMPTY_STRING

    if customer_invoice.customer_id != customer_invoice.customer_charged_id:
        customer_on_hold_movement = const.EMPTY_STRING
        customer_payment_needed = '<font color="#51a351">{}</font>'.format(
            _(
                "Invoices for this delivery point are sent to %(name)s who is responsible for collecting the payments."
            )
            % {"name": customer_invoice.customer_charged.long_basket_name}
        )
    else:
        bank_not_invoiced = customer.get_bank_not_invoiced()
        order_not_invoiced = customer.get_order_not_invoiced()

        customer_on_hold_movement = customer.get_html_on_hold_movement(
            bank_not_invoiced, order_not_invoiced, total_price_with_tax
        )
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            payment_needed = -(
                customer.balance - order_not_invoiced + bank_not_invoiced
            )
        else:
            payment_needed = total_price_with_tax

        bank_account_number = apps.REPANIER_SETTINGS_BANK_ACCOUNT
        if bank_account_number is not None:
            if payment_needed.amount > const.DECIMAL_ZERO:
                if permanence.short_name_v2:
                    communication = "{} ({})".format(
                        customer.short_basket_name, permanence.short_name_v2
                    )
                else:
                    communication = customer.short_basket_name
                group_name = settings.REPANIER_SETTINGS_GROUP_NAME
                customer_payment_needed = '<br><font color="#bd0926">{}</font>'.format(
                    _(
                        "Please pay a provision of %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s."
                    )
                    % {
                        "payment": payment_needed,
                        "name": group_name,
                        "number": bank_account_number,
                        "communication": communication,
                    }
                )

            else:
                if customer.balance.amount != const.DECIMAL_ZERO:
                    customer_payment_needed = (
                        '<br><font color="#51a351">{}.</font>'.format(
                            _("Your account balance is sufficient")
                        )
                    )
                else:
                    customer_payment_needed = const.EMPTY_STRING
        else:
            customer_payment_needed = const.EMPTY_STRING

    return (
        customer_last_balance,
        customer_on_hold_movement,
        customer_payment_needed,
        customer_order_amount,
    )


def get_html_selected_value(offer_item, quantity_ordered, is_open=True):
    if offer_item is not None and offer_item.may_order:
        if quantity_ordered <= const.DECIMAL_ZERO:
            if is_open:
                if offer_item.is_box:
                    label = _("Sold out")
                else:
                    q_min = offer_item.customer_minimum_order_quantity
                    if offer_item.stock > const.DECIMAL_ZERO:
                        q_alert = offer_item.stock - offer_item.quantity_invoiced
                        if q_alert < const.DECIMAL_ZERO:
                            q_alert = const.DECIMAL_ZERO
                    else:
                        q_alert = offer_item.customer_alert_order_quantity
                    if q_min <= q_alert:
                        label = "---"
                    else:
                        label = _("Sold out")
            else:
                label = _("Closed")
            html = '<option value="0" selected>{}</option>'.format(label)

        else:
            unit_price_amount = (
                offer_item.customer_unit_price.amount + offer_item.unit_deposit.amount
            )
            display = offer_item.get_display(
                qty=quantity_ordered,
                order_unit=offer_item.order_unit,
                unit_price_amount=unit_price_amount,
            )
            html = '<option value="{}" selected>{}</option>'.format(
                quantity_ordered, display
            )
    else:
        html = const.EMPTY_STRING
    return mark_safe(html)


def get_html_selected_box_value(offer_item, quantity_ordered):
    # Select one purchase
    if quantity_ordered > const.DECIMAL_ZERO:
        qty_display = offer_item.get_display(
            qty=quantity_ordered,
            order_unit=offer_item.order_unit,
            with_price_display=False,
        )
    else:
        qty_display = "---"
    return mark_safe(
        '<option value="0" selected>☑ {} {}</option>'.format(
            qty_display, const.BOX_UNICODE
        )
    )


def create_or_update_one_purchase(
    customer_id,
    offer_item,
    status,
    q_order=None,
    batch_job=False,
    is_box_content=False,
    comment=None,
):
    from repanier.models.purchase import Purchase
    from repanier.models.invoice import CustomerInvoice

    # The batch_job flag is used because we need to forbid
    # customers to add purchases during the close_orders_async or other batch_job process
    # when the status is PERMANENCE_WAIT_FOR_SEND
    purchase = (
        Purchase.objects.filter(
            customer_id=customer_id,
            offer_item_id=offer_item.id,
            is_box_content=is_box_content,
        )
        .first()
    )
    if batch_job:
        if purchase is None:
            purchase = Purchase.objects.create(
                permanence_id=offer_item.permanence_id,
                offer_item_id=offer_item.id,
                producer_id=offer_item.producer_id,
                customer_id=customer_id,
                quantity_ordered=q_order
                if status < const.PERMANENCE_SEND
                else const.DECIMAL_ZERO,
                quantity_invoiced=q_order
                if status >= const.PERMANENCE_SEND
                else const.DECIMAL_ZERO,
                is_box_content=is_box_content,
                status=status,
                comment=comment,
            )
        else:
            purchase.set_comment(comment)
            if status < const.PERMANENCE_SEND:
                purchase.quantity_ordered = q_order
            else:
                purchase.quantity_invoiced = q_order
            purchase.save()
            # if offer_item.is_box:
            #     purchase.save_box()
        return purchase, True
    else:
        permanence_is_opened = (
            CustomerInvoice.objects.filter(
                permanence_id=offer_item.permanence_id,
                customer_id=customer_id,
                status=status,
            )
            .exists()
        )
        if permanence_is_opened:
            if offer_item.stock > const.DECIMAL_ZERO:
                if purchase is not None:
                    q_previous_order = purchase.quantity_ordered
                else:
                    q_previous_order = const.DECIMAL_ZERO
                q_alert = (
                    offer_item.stock - offer_item.quantity_invoiced + q_previous_order
                )
                if is_box_content and q_alert < q_order:
                    # Select one purchase
                    non_box_purchase = (
                        Purchase.objects.filter(
                            customer_id=customer_id,
                            offer_item_id=offer_item.id,
                            is_box_content=False,
                        )
                        .first()
                    )
                    if non_box_purchase is not None:
                        tbd_qty = min(
                            q_order - q_alert, non_box_purchase.quantity_ordered
                        )
                        tbk_qty = non_box_purchase.quantity_ordered - tbd_qty
                        non_box_purchase.quantity_ordered = tbk_qty
                        non_box_purchase.save()
                        q_alert += tbd_qty
            else:
                if is_box_content:
                    q_alert = q_order
                else:
                    q_alert = offer_item.customer_alert_order_quantity
            if purchase is not None:
                purchase.set_comment(comment)
                if q_order <= q_alert:
                    if (
                        not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
                        or purchase.quantity_confirmed <= q_order
                    ):
                        purchase.quantity_ordered = q_order
                        purchase.save()
                    else:
                        purchase.quantity_ordered = purchase.quantity_confirmed
                        purchase.save()
                else:
                    return purchase, False
            else:
                purchase = Purchase.objects.create(
                    permanence_id=offer_item.permanence_id,
                    offer_item_id=offer_item.id,
                    producer_id=offer_item.producer_id,
                    customer_id=customer_id,
                    quantity_ordered=q_order,
                    quantity_invoiced=const.DECIMAL_ZERO,
                    is_box_content=is_box_content,
                    status=status,
                    comment=comment,
                )
            return purchase, True
        else:
            return purchase, False


@transaction.atomic
def create_or_update_one_cart_item(
    customer, offer_item_id, q_order=None, value_id=None, batch_job=False, comment=None
):
    from repanier.models.box import BoxContent
    from repanier.models.offeritem import OfferItem
    from repanier.models.purchase import Purchase

    offer_item = (
        OfferItem.objects.select_for_update(nowait=False)
        .filter(id=offer_item_id, is_active=True, may_order=True)
        .select_related("producer")
        .first()
    )
    if offer_item is not None:
        if q_order is None:
            # Transform value_id into a q_order.
            # This is done here and not in the order_ajax to avoid to access twice to offer_item
            q_min = offer_item.customer_minimum_order_quantity
            q_step = offer_item.customer_increment_order_quantity
            if value_id <= 0:
                q_order = const.DECIMAL_ZERO
            elif value_id == 1:
                q_order = q_min
            else:
                if q_min < q_step:
                    # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                    # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                    if value_id == 2:
                        q_order = q_step
                    else:
                        q_order = q_step * (value_id - 1)
                else:
                    # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                    # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                    q_order = q_min + q_step * (value_id - 1)
        if q_order < const.DECIMAL_ZERO:
            q_order = const.DECIMAL_ZERO
        is_box_updated = True
        if offer_item.is_box:
            # Select one purchase
            purchase = (
                Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item.id,
                    is_box_content=False,
                )
                .first()
            )
            if purchase is not None:
                delta_q_order = q_order - purchase.quantity_ordered
            else:
                delta_q_order = q_order
            with transaction.atomic():
                sid = transaction.savepoint()
                # This code executes inside a transaction.
                for content in (
                    BoxContent.objects.filter(box=offer_item.product_id)
                    .only("product_id", "content_quantity")
                ):
                    box_offer_item = (
                        OfferItem.objects.filter(
                            product_id=content.product_id,
                            permanence_id=offer_item.permanence_id,
                        )
                        .select_related("producer")
                        .first()
                    )
                    if box_offer_item is not None:
                        # Select one purchase
                        purchase = (
                            Purchase.objects.filter(
                                customer_id=customer.id,
                                offer_item_id=box_offer_item.id,
                                is_box_content=True,
                            )
                            .first()
                        )
                        if purchase is not None:
                            quantity_ordered = (
                                purchase.quantity_ordered
                                + delta_q_order * content.content_quantity
                            )
                        else:
                            quantity_ordered = delta_q_order * content.content_quantity
                        if quantity_ordered < const.DECIMAL_ZERO:
                            quantity_ordered = const.DECIMAL_ZERO
                        purchase, is_box_updated = create_or_update_one_purchase(
                            customer_id=customer.id,
                            offer_item=box_offer_item,
                            status=const.PERMANENCE_OPENED,
                            q_order=quantity_ordered,
                            batch_job=batch_job,
                            is_box_content=True,
                            comment=const.EMPTY_STRING,
                        )
                    else:
                        is_box_updated = False
                    if not is_box_updated:
                        break
                if is_box_updated:
                    transaction.savepoint_commit(sid)
                else:
                    transaction.savepoint_rollback(sid)
        if not offer_item.is_box or is_box_updated:
            return create_or_update_one_purchase(
                customer_id=customer.id,
                offer_item=offer_item,
                status=const.PERMANENCE_OPENED,
                q_order=q_order,
                batch_job=batch_job,
                is_box_content=False,
                comment=comment,
            )
        elif not batch_job:
            # Select one purchase
            purchase = (
                Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item.id,
                    is_box_content=False,
                )
                .first()
            )
            return purchase, False


def my_basket(is_order_confirm_send, order_amount):
    if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
        if (
            settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            and not is_order_confirm_send
        ):
            if order_amount.amount <= const.DECIMAL_ZERO:
                msg_confirm = const.EMPTY_STRING
            else:
                msg_confirm = '<span class="glyphicon glyphicon-exclamation-sign"></span>&nbsp;<span class="glyphicon glyphicon-floppy-remove"></span>'
            msg_html = "{order_amount}&nbsp;&nbsp;&nbsp;{msg_confirm}".format(
                order_amount=order_amount, msg_confirm=msg_confirm
            )
        else:
            if order_amount.amount <= const.DECIMAL_ZERO:
                msg_confirm = cart_content = const.EMPTY_STRING
            else:
                msg_confirm = '<span class="glyphicon glyphicon-ok"></span>'
                cart_content = (
                    '<div class="cart-line-3" style="background-color: #E5E9EA"></div>'
                )
            msg_html = """
            <div class="icon-cart" style="float: left">
                <div class="cart-line-1" style="background-color: #fff"></div>
                <div class="cart-line-2" style="background-color: #fff"></div>
                {cart_content}
                <div class="cart-wheel" style="background-color: #fff"></div>
            </div> {order_amount}&nbsp;&nbsp;&nbsp;
            {msg_confirm}
                """.format(
                cart_content=cart_content,
                order_amount=order_amount,
                msg_confirm=msg_confirm,
            )
        json_dict = {"#my_basket": msg_html}
        msg_html = "{order_amount}&nbsp;&nbsp;&nbsp;{msg_confirm}".format(
            order_amount=order_amount, msg_confirm=msg_confirm
        )
        json_dict["#prepared_amount_visible_xs"] = msg_html
    else:
        if (
            settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            and not is_order_confirm_send
        ):
            msg_html = """
            {order_amount} <span class="badge">{to_confirm}</span>
            """.format(
                order_amount=order_amount, to_confirm=_("to confirm")
            )
        else:
            msg_html = """
            {order_amount}
            """.format(
                order_amount=order_amount
            )
        json_dict = {"#my_basket": msg_html}
    return json_dict


def clean_offer_item(permanence, queryset):
    if permanence.status > const.PERMANENCE_SEND:
        # The purchases are already invoiced.
        # The offer item may not be modified any more
        raise ValueError(
            "Not offer item may be created when permanece status > PERMANENCE_SEND"
        )
    for offer_item in queryset.select_related("producer", "product"):
        product = offer_item.product
        producer = offer_item.producer

        offer_item.set_from(product)

        offer_item.manage_production = producer.represent_this_buyinggroup
        # Those offer_items not subjects to price modifications
        # product.is_box or product.is_box_content or product.order_unit >= const.PRODUCT_ORDER_UNIT_DEPOSIT
        offer_item.is_resale_price_fixed = (
            product.is_box or product.order_unit >= const.PRODUCT_ORDER_UNIT_DEPOSIT # TODO NEXT : or producer.is_resale_price_fixed
        )
        offer_item.price_list_multiplier = (
            const.DECIMAL_ONE
            if offer_item.is_resale_price_fixed
            else producer.price_list_multiplier
        )

        offer_item.may_order = False
        if offer_item.order_unit < const.PRODUCT_ORDER_UNIT_DEPOSIT:
            offer_item.may_order = product.is_into_offer

        # The group must pay the VAT, so it's easier to allways have
        # offer_item with VAT included
        if producer.producer_price_are_wo_vat:
            offer_item.producer_unit_price += offer_item.producer_vat
        offer_item.producer_price_are_wo_vat = False

        offer_item.save()

    # Now got everything to calculate the sort order of the order display screen
    template_cache_part_a = get_repanier_template_name("cache_part_a.html")
    template_cache_part_b = get_repanier_template_name("cache_part_b.html")

    for offer_item in queryset.select_related("producer", "department_for_customer"):
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


def reorder_purchases(permanence_id):
    from repanier.models.purchase import Purchase

    # Order the purchases such that lower quantity are before larger quantity
    Purchase.objects.filter(permanence_id=permanence_id).update(
        quantity_for_preparation_sort_order=const.DECIMAL_ZERO
    )
    Purchase.objects.filter(
        permanence_id=permanence_id,
        offer_item__wrapped=False,
        offer_item__order_unit__in=[
            const.PRODUCT_ORDER_UNIT_KG,
            const.PRODUCT_ORDER_UNIT_PC_KG,
        ],
    ).update(quantity_for_preparation_sort_order=F("quantity_invoiced"))


def reorder_offer_items(permanence_id):
    from repanier.models.offeritem import OfferItemReadOnly

    # calculate the sort order of the order display screen
    cur_language = translation.get_language()
    offer_item_qs = OfferItemReadOnly.objects.filter(
        permanence_id=permanence_id
    )

    i = 0
    reorder_queryset = offer_item_qs.filter(is_box=False,).order_by(
        "department_for_customer",
        "long_name_v2",
        "order_average_weight",
        "producer__short_profile_name",
    )
    for offer_item in reorder_queryset:
        offer_item.producer_sort_order_v2 = (
            offer_item.order_sort_order_v2
        ) = offer_item.preparation_sort_order_v2 = i
        offer_item.save()
        if i < 9999:
            i += 1
    # producer lists sort order : sort by reference if needed, otherwise sort by order_sort_order
    i = 9999
    reorder_queryset = offer_item_qs.filter(
        is_box=False,
        producer__sort_products_by_reference=True,
    ).order_by("department_for_customer", "reference")
    for offer_item in reorder_queryset:
        offer_item.producer_sort_order_v2 = i
        offer_item.save()
        if i < 19999:
            i += 1
    # preparation lists sort order
    i = -9999
    reorder_queryset = offer_item_qs.filter(is_box=True,).order_by(
        "customer_unit_price",
        # "department_for_customer__lft",
        "unit_deposit",
        "long_name_v2",
    )
    # 'TranslatableQuerySet' object has no attribute 'desc'
    for offer_item in reorder_queryset:
        # display box on top
        offer_item.producer_sort_order_v2 = (
            offer_item.order_sort_order_v2
        ) = offer_item.preparation_sort_order_v2 = i
        offer_item.save()
        if i < -1:
            i += 1


def update_offer_item(product_id=None, producer_id=None):
    from repanier.models.permanence import Permanence
    from repanier.models.offeritem import OfferItem

    # The user can modify the price of a product PERMANENCE_SEND via "rule_of_3_per_product"
    for permanence in Permanence.objects.filter(
        status__in=[
            const.PERMANENCE_PLANNED,
            const.PERMANENCE_OPENED,
            const.PERMANENCE_CLOSED,
            const.PERMANENCE_SEND,
        ]
    ):
        if producer_id is None:
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=permanence.id, product_id=product_id
            )
        else:
            offer_item_qs = OfferItem.objects.filter(
                permanence_id=permanence.id, producer_id=producer_id
            )
        clean_offer_item(permanence, offer_item_qs)
        permanence.recalculate_order_amount(offer_item_qs=offer_item_qs)
    cache.clear()


def web_services_activated(reference_site=None):
    activated = False
    version = None
    if reference_site:
        try:
            url = urljoin(reference_site, reverse("repanier:version_rest"))
            web_services = urlopen(url, timeout=0.5)
            rest_as_json = json.load(reader(web_services))
            if rest_as_json["version"] == "1":
                activated = True
                version = 1
        except:
            pass
    return activated, "Repanier", version


def get_html_basket_message(customer, permanence, status):
    invoice_msg = const.EMPTY_STRING
    payment_msg = const.EMPTY_STRING
    (
        customer_last_balance,
        customer_on_hold_movement,
        customer_payment_needed,
        customer_order_amount,
    ) = payment_message(customer, permanence)
    if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING and customer_last_balance:
        invoice_msg = "<br>{} {}".format(
            customer_last_balance, customer_on_hold_movement
        )
    if apps.REPANIER_SETTINGS_BANK_ACCOUNT is not None:
        payment_msg = "<br>{}".format(customer_payment_needed)

    if status == const.PERMANENCE_OPENED:
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            if permanence.with_delivery_point:
                you_can_change = _(
                    "You can increase the order quantities as long as the orders are open for your delivery point."
                )
            else:
                you_can_change = _(
                    "You can increase the order quantities as long as the orders are open."
                )
        else:
            if permanence.with_delivery_point:
                you_can_change = _(
                    "You can change the order quantities as long as the orders are open for your delivery point."
                )
            else:
                you_can_change = _(
                    "You can change the order quantities as long as the orders are open."
                )
    else:
        if permanence.with_delivery_point:
            you_can_change = _("The orders are closed for your delivery point.")
        else:
            you_can_change = _("The orders are closed.")

    basket_message = "{}{}{}<br>{}".format(
        customer_order_amount, invoice_msg, payment_msg, you_can_change
    )
    return mark_safe(basket_message)


def html_box_content(offer_item, user):
    from repanier.models.box import BoxContent
    from repanier.models.offeritem import OfferItemReadOnly

    box_id = offer_item.product_id
    box_products = list(
        BoxContent.objects.filter(box_id=box_id)
        .values_list("product_id", flat=True)
    )
    if len(box_products) > 0:
        box_offer_items_qs = (
            OfferItemReadOnly.objects.filter(
                permanence_id=offer_item.permanence_id,
                product_id__in=box_products,
            )
            .order_by("order_sort_order_v2")
            .select_related("producer")
        )
        box_products_description = []
        for box_offer_item in box_offer_items_qs:
            box_products_description.append(
                format_html(
                    '<li>{} * {}, {} <span class="btn_like{}" style="cursor: pointer;">{}</span></li>',
                    mark_safe(
                        box_offer_item.get_display(
                            qty=BoxContent.objects.filter(
                                box_id=box_id, product_id=box_offer_item.product_id
                            )
                            .only("content_quantity")
                            .first()
                            .content_quantity,
                            order_unit=box_offer_item.order_unit,
                            with_price_display=False,
                        )
                    ),
                    box_offer_item.long_name_v2,
                    box_offer_item.producer.short_profile_name,
                    box_offer_item.id,
                    mark_safe(box_offer_item.get_like(user)),
                )
            )
        return format_html(
            "<ul>{}</ul>", mark_safe(const.EMPTY_STRING.join(box_products_description))
        )
    return const.EMPTY_STRING


def rule_of_3_reload_purchase(
    customer, offer_item, purchase_form, purchase_form_instance
):
    from repanier.models.purchase import Purchase

    purchase_form.repanier_is_valid = True
    # Reload purchase, because it has maybe be deleted
    purchase = (
        Purchase.objects.filter(
            customer_id=customer.id, offer_item_id=offer_item.id, is_box_content=False
        )
        .first()
    )
    if purchase is None:
        # Doesn't exists ? Create one
        purchase = Purchase.objects.create(
            permanence=offer_item.permanence,
            offer_item=offer_item,
            producer=offer_item.producer,
            customer=customer,
            quantity_ordered=const.DECIMAL_ZERO,
            quantity_invoiced=const.DECIMAL_ZERO,
            comment=purchase_form_instance.comment,
            is_box_content=False,
            status=const.PERMANENCE_SEND,
        )
    # And set the form's values
    purchase.quantity_invoiced = purchase_form_instance.quantity_invoiced
    purchase.purchase_price = purchase_form_instance.purchase_price
    purchase.comment = purchase_form_instance.comment
    # Set it as new form instance
    purchase_form.instance = purchase
    return purchase


def get_recurrence_dates(first_date, recurrences):
    dates = []
    # d_start = first_date
    # dt_start = new_datetime(d_start)
    # dt_end = new_datetime(d_start + datetime.timedelta(days=const.ONE_YEAR))
    # occurrences = recurrences.between(dt_start, dt_end, dtstart=dt_start, inc=True)
    # occurrences = recurrences.occurrences()
    for occurrence in recurrences.occurrences():
        dates.append(occurrence.date())
    return dates


def round_gov_be(number):
    """Round according to Belgian market regulations
    http://economie.fgov.be/fr/entreprises/reglementation_de_marche/Pratiques_commerce/bienarrondir/
    If the total amount to be paid ends with 1 or 2 cents, it is rounded down to 0.00 euro.
    If the total amount to be paid ends with 3, 4, 6 or 7 cents, it is rounded to 0.05 euro.
    If the total amount to be paid ends with 8 or 9 cents, it is rounded up to 0.10 euro.
    """
    return (number / const.DECIMAL_0_05).quantize(
        const.DECIMAL_ONE, rounding=const.ROUND_HALF_UP
    ) * const.DECIMAL_0_05

def round_tva(number):
    return number.quantize(const.THREE_DECIMALS)
