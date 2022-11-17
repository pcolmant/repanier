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
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
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
        const.SaleStatus.OPENED,
        const.SaleStatus.CLOSED,
        const.SaleStatus.SEND,
    ]:
        if permanence.status in [const.SaleStatus.INVOICED, const.SaleStatus.ARCHIVED]:
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


def payment_message(customer, permanence, customer_invoice):
    customer_order_amount = _("The amount of your order is %(amount)s.") % {
        "amount": customer_invoice.get_total_price_with_tax()
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
        customer_payment_needed = "{}".format(
            _(
                "Invoices for this delivery point are sent to %(name)s who is responsible for collecting the payments."
            )
            % {"name": customer_invoice.customer_charged.long_basket_name}
        )
    else:
        if (
            not settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
            or customer_invoice.is_order_confirm_send
        ):
            bank_not_invoiced = customer.get_bank_not_invoiced()
            order_not_invoiced = customer.get_order_not_invoiced()

            customer_on_hold_movement = customer.get_html_on_hold_movement(
                bank_not_invoiced,
                order_not_invoiced,
                customer_invoice.get_total_price_with_tax(),
            )
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                payment_needed = -(
                    customer.balance - order_not_invoiced + bank_not_invoiced
                )
            else:
                payment_needed = customer_invoice.get_total_price_with_tax()

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
        else:
            customer_on_hold_movement = const.EMPTY_STRING
            customer_payment_needed = const.EMPTY_STRING

    return (
        customer_last_balance,
        customer_on_hold_movement,
        customer_payment_needed,
        customer_order_amount,
    )


def get_html_selected_value(
    offer_item, quantity_ordered, unit_price_amount, is_open=True
):
    if offer_item is not None:
        product = offer_item.product
        if quantity_ordered <= const.DECIMAL_ZERO:
            if is_open:
                q_min = product.customer_minimum_order_quantity
                q_alert = offer_item.get_q_alert()
                if q_min <= q_alert:
                    label = "---"
                else:
                    label = _("Sold out")
            else:
                label = _("Closed")
            html = '<option value="0" selected>{}</option>'.format(label)

        else:
            # unit_price_amount = (
            #     product.customer_unit_price.amount + product.unit_deposit.amount
            # )
            display = product.get_display(
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


def create_or_update_one_purchase(
    customer_id,
    offer_item,
    status,
    q_order=None,
    batch_job=False,
    comment=None,
):
    from repanier.models.purchase import Purchase
    from repanier.models.invoice import CustomerInvoice

    # The batch_job flag is used because we need to forbid
    # customers to add purchases during the close_orders_async or other batch_job process
    # when the status is PERMANENCE_WAIT_FOR_SEND
    purchase = Purchase.objects.filter(
        customer_id=customer_id,
        offer_item_id=offer_item.id,
    ).first()
    if batch_job:
        if purchase is None:
            purchase = Purchase.objects.create(
                permanence_id=offer_item.permanence_id,
                offer_item_id=offer_item.id,
                producer_id=offer_item.producer_id,
                customer_id=customer_id,
                quantity_ordered=q_order
                if status < const.SaleStatus.SEND
                else const.DECIMAL_ZERO,
                quantity_invoiced=q_order
                if status >= const.SaleStatus.SEND
                else const.DECIMAL_ZERO,
                status=status,
                comment=comment,
            )
        else:
            purchase.set_comment(comment)
            purchase.status = status
            if status < const.SaleStatus.SEND:
                purchase.quantity_ordered = q_order
            else:
                # purchase.quantity_ordered = q_order
                purchase.quantity_invoiced = q_order
            purchase.save()
        return purchase, True
    else:
        permanence_is_opened = CustomerInvoice.objects.filter(
            permanence_id=offer_item.permanence_id,
            customer_id=customer_id,
            status=status,
        ).exists()
        if permanence_is_opened:
            if offer_item.stock > const.DECIMAL_ZERO:
                if purchase is not None:
                    q_previous_order = purchase.quantity_ordered
                else:
                    q_previous_order = const.DECIMAL_ZERO
                q_alert = offer_item.get_q_alert(q_previous_order=q_previous_order)
                if q_previous_order > q_order:
                    # if the customer decreases the reserved quantity
                    # and the stock has been decreased in the management interface
                    # then adapt the quantity to accept the sale
                    if q_alert < q_order:
                        q_alert = q_order
            else:
                q_alert = offer_item.get_q_alert()
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
    from repanier.models.offeritem import OfferItem

    offer_item = (
        OfferItem.objects.select_for_update(nowait=False)
        .filter(id=offer_item_id, is_active=True, may_order=True)
        .select_related("producer", "product")
        .first()
    )
    if offer_item is None:
        return None, False
    if q_order is None:
        # Transform value_id into a q_order.
        # This is done here and not in the order_ajax to avoid to access twice to offer_item
        if value_id <= 0:
            q_order = const.DECIMAL_ZERO
        else:
            product = offer_item.product
            q_min = product.customer_minimum_order_quantity
            if value_id == 1:
                q_order = q_min
            else:
                q_step = product.customer_increment_order_quantity
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

    return create_or_update_one_purchase(
        customer_id=customer.id,
        offer_item=offer_item,
        status=const.SaleStatus.OPENED,
        q_order=q_order,
        batch_job=batch_job,
        comment=comment,
    )


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
    offer_item_qs = OfferItemReadOnly.objects.filter(permanence_id=permanence_id)

    i = 0
    reorder_queryset = offer_item_qs.order_by(
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
    i = 10000
    reorder_queryset = offer_item_qs.filter(
        producer__sort_products_by_reference=True,
    ).order_by("department_for_customer", "reference")
    for offer_item in reorder_queryset:
        offer_item.producer_sort_order_v2 = i
        offer_item.save()
        if i < 19999:
            i += 1


def update_offer_item(product=None, producer_id=None):
    from repanier.models.permanence import Permanence
    from repanier.models.offeritem import OfferItem

    # The user can also modify the price of a product PERMANENCE_SEND via "rule_of_3_per_product"
    for permanence in Permanence.objects.filter(
        status=const.SaleStatus.OPENED,
    ):
        if product is not None:
            offer_item_qs = OfferItem.objects.filter(product_id=product.id)
        else:
            offer_item_qs = OfferItem.objects.filter(producer_id=producer_id)
        permanence.clean_offer_item(offer_item_qs=offer_item_qs)
        permanence.update_offer_item(offer_item_qs=offer_item_qs)

    for permanence in Permanence.objects.filter(
        status=const.SaleStatus.SEND,
    ):
        if product is not None:
            if product.is_into_offer:
                offer_item = product.get_or_create_offer_item(permanence)
                offer_item_qs = OfferItem.objects.filter(id=offer_item.id)
                permanence.update_offer_item(offer_item_qs=offer_item_qs)
        else:
            offer_item_qs = OfferItem.objects.filter(
                producer_id=producer_id, product__is_into_offer=True
            )
            permanence.clean_offer_item(offer_item_qs=offer_item_qs)
            permanence.update_offer_item(offer_item_qs=offer_item_qs)
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


def get_html_basket_message(customer, permanence, status, customer_invoice):
    invoice_msg = const.EMPTY_STRING
    payment_msg = const.EMPTY_STRING
    (
        customer_last_balance,
        customer_on_hold_movement,
        customer_payment_needed,
        customer_order_amount,
    ) = payment_message(customer, permanence, customer_invoice)
    if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING and customer_last_balance:
        invoice_msg = "<br>{} {}".format(
            customer_last_balance, customer_on_hold_movement
        )
    if apps.REPANIER_SETTINGS_BANK_ACCOUNT is not None and customer_payment_needed:
        payment_msg = "<br>{}".format(customer_payment_needed)

    if status == const.SaleStatus.OPENED:
        if customer_invoice.is_order_confirm_send:
            if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                you_can_change = "<br>{}".format(
                    _(
                        "You can increase the order quantities as long as the orders are open."
                    )
                )
            else:
                you_can_change = "<br>{}".format(
                    _(
                        "You can change the order quantities as long as the orders are open."
                    )
                )
        else:
            you_can_change = const.EMPTY_STRING
    else:
        if permanence.with_delivery_point:
            you_can_change = "<br>{}".format(
                _("The orders are closed for your delivery point.")
            )
        else:
            you_can_change = "<br>{}".format(_("The orders are closed."))

    basket_message = "<b>{}</b>{}{}{}".format(
        customer_order_amount, invoice_msg, payment_msg, you_can_change
    )
    return mark_safe(basket_message)


def rule_of_3_reload_purchase(
    customer, offer_item, purchase_form, purchase_form_instance
):
    from repanier.models.purchase import Purchase

    purchase_form.repanier_is_valid = True
    # Reload purchase, because it has maybe be deleted
    purchase = Purchase.objects.filter(
        customer_id=customer.id, offer_item_id=offer_item.id
    ).first()
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
            status=const.SaleStatus.SEND,
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
    return number.quantize(const.RoundUpTo.THREE_DECIMALS)
