from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from repanier.const import (
    EMPTY_STRING,
    DECIMAL_ZERO,
    RoundUpTo,
    SaleStatus,
)
from repanier.models import Permanence
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import (
    sint,
    get_html_selected_value,
)

register = template.Library()


@register.simple_tag(takes_context=False)
def repanier_admins(*args, **kwargs):
    return mark_safe(
        ", ".join(
            [
                '{0} <a href="mailto:{1}">{1}</a>'.format(admin[0], admin[1])
                for admin in settings.ADMINS
            ]
        )
    )


@register.simple_tag(takes_context=False)
def repanier_notification(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_NOTIFICATION

    return REPANIER_SETTINGS_NOTIFICATION.get_html_notification_card_display()


@register.simple_tag(takes_context=False)
def repanier_permanences(*args, **kwargs):
    permanences_cards = []
    for permanence in (
        Permanence.objects.filter(status=SaleStatus.OPENED)
        .only("id", "permanence_date", "with_delivery_point")
        .order_by("permanence_date", "id")
    ):
        permanences_cards.append(permanence.get_html_permanence_card_display())

    displayed_permanence_counter = 0
    for permanence in (
        Permanence.objects.filter(
            status__in=[SaleStatus.CLOSED, SaleStatus.SEND],
            master_permanence__isnull=True,
        )
        .only("id", "permanence_date")
        .order_by("-permanence_date")
    ):
        displayed_permanence_counter += 1
        permanences_cards.append(permanence.get_html_permanence_card_display())
        if displayed_permanence_counter > 4:
            break

    return mark_safe(
        """
        <div class="container">
            <div class="row">
                <div class="col">
                    <div class="card container-activities">
                        <div class="card-header">
                            <h2 class="card-title">{card_title}</h2>
                        </div>
                        {html}
                    </div>
                </div>
            </div>
        </div>
        """.format(
            card_title=("No offer to display")
            if len(permanences_cards) == 0
            else _("Sale")
            if len(permanences_cards) == 1
            else _("Sales"),
            html='<div class="dropdown-divider"></div>'.join(permanences_cards),
        )
    )


@register.simple_tag(takes_context=True)
def repanier_user_bs3(context, *args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    request = context["request"]
    user = request.user
    nodes = []
    if user.is_authenticated:
        p_permanence_id = sint(kwargs.get("permanence_id", 0))
        if p_permanence_id > 0:
            nodes.append(
                '<li id="li_my_basket" style="display:none;" class="dropdown">'
            )
            nodes.append(
                '<a href="{}?is_basket=yes" class="btn btn-info"><span id="my_basket"></span></a>'.format(
                    reverse("repanier:order_view", args=(p_permanence_id,))
                )
            )
            nodes.append("</li>")
        nodes.append(
            """
            <li id="li_my_name" class="dropdown">
            <a href="#" class="dropdown-toggle" data-toggle="dropdown"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> {}<b class="caret"></b></a>
            <ul class="dropdown-menu">
            """.format(
                # _('Welkom'),
                user.username
                or '<span id = "my_name"></ span>'
            )
        )
        nodes.append(
            '<li><a href="{}">{}</a></li>'.format(
                reverse("repanier:send_mail_to_coordinators_view"), _("Inform")
            )
        )
        if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
            nodes.append(
                '<li><a href="{}">{}</a></li>'.format(
                    reverse("repanier:who_is_who_view"), _("Who's who")
                )
            )
        if user.customer_id is not None:
            nodes.append(
                '<li><a href="{}">{}</a></li>'.format(
                    reverse("repanier:my_profile_view"), _("My profile")
                )
            )
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                nodes.append(
                    '<li><a href="{}">{}</a></li>'.format(
                        reverse("repanier:customer_history_view", args=(user.customer_id,)),
                        _("History"),
                    )
                )
            nodes.append('<li class="divider"></li>')
        nodes.append(
            '<li><a href="{}">{}</a></li>'.format(
                reverse("repanier:logout"), _("Logout")
            )
        )
        nodes.append("</ul></li>")
    else:
        nodes = [
            '<li class="dropdown"><a href="{}?{}" class="btn btn-info"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> {}</a></li>'.format(
                reverse("repanier:login_form"), urlencode({'next': request.get_full_path()}), _("Sign in")
            )
        ]
    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=True)
def repanier_user_bs5(context, *args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    request = context["request"]
    user = request.user
    nodes = []
    if user.is_authenticated:
        p_permanence_id = sint(kwargs.get("permanence_id", 0))
        if p_permanence_id > 0:
            nodes.append(
                '<li id="li_my_basket" style="display:none;" class="dropdown">'
            )
            nodes.append(
                '<a href="{}?is_basket=yes" class="btn btn-info"><span id="my_basket"></span></a>'.format(
                    reverse("repanier:order_view", args=(p_permanence_id,))
                )
            )
            nodes.append("</li>")
        nodes.append(
            """
            <li id="li_my_name" class="dropdown">
            <a href="#" class="dropdown-toggle" data-toggle="dropdown"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> {}<b class="caret"></b></a>
            <ul class="dropdown-menu">
            """.format(
                # _('Welkom'),
                user.username
                or '<span id = "my_name"></ span>'
            )
        )
        nodes.append(
            '<li><a href="{}">{}</a></li>'.format(
                reverse("repanier:send_mail_to_coordinators_view"), _("Inform")
            )
        )
        if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
            nodes.append(
                '<li><a href="{}">{}</a></li>'.format(
                    reverse("repanier:who_is_who_view"), _("Who's who")
                )
            )
        if user.customer_id is not None:
            nodes.append(
                '<li><a href="{}">{}</a></li>'.format(
                    reverse("repanier:my_profile_view"), _("My profile")
                )
            )
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                last_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer__user_id=request.user.id,
                        invoice_sort_order__isnull=False,
                        status__lte=SaleStatus.INVOICED,
                    )
                    .only("balance", "date_balance")
                    .order_by("-invoice_sort_order")
                    .first()
                )
                if last_customer_invoice is not None:
                    if last_customer_invoice.balance < DECIMAL_ZERO:
                        my_balance = _(
                            'My balance : <font color="red">%(balance)s</font> at %(date)s'
                        ) % {
                            "balance": last_customer_invoice.balance,
                            "date": last_customer_invoice.date_balance.strftime(
                                settings.DJANGO_SETTINGS_DATE
                            ),
                        }
                    else:
                        my_balance = _(
                            'My balance : <font color="green">%(balance)s</font> at %(date)s'
                        ) % {
                            "balance": last_customer_invoice.balance,
                            "date": last_customer_invoice.date_balance.strftime(
                                settings.DJANGO_SETTINGS_DATE
                            ),
                        }
                else:
                    my_balance = _("My balance")
                nodes.append(
                    '<li><a href="{}">{}</a></li>'.format(
                        reverse("repanier:customer_invoice_view", args=(0,user.customer_id,)), my_balance
                    )
                )
            nodes.append('<li class="divider"></li>')
        nodes.append(
            '<li><a href="{}">{}</a></li>'.format(
                reverse("repanier:logout"), _("Logout")
            )
        )
        nodes.append("</ul></li>")
    else:
        nodes = [
            '<li class="dropdown"><a href="{}" class="btn btn-info"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> {}</a></li>'.format(
                reverse("repanier:login_form"), _("Sign in")
            )
        ]

    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=False)
def repanier_permanence_title(*args, **kwargs):
    result = EMPTY_STRING
    p_permanence_id = sint(kwargs.get("permanence_id", 0))
    if p_permanence_id > 0:
        permanence = Permanence.objects.filter(id=p_permanence_id).first()
        if permanence is not None:
            result = permanence.get_permanence_display()
        else:
            result = EMPTY_STRING
    return result


@register.simple_tag(takes_context=False)
def repanier_html_permanence_title(*args, **kwargs):
    result = EMPTY_STRING
    p_permanence_id = sint(kwargs.get("permanence_id", 0))
    if p_permanence_id > 0:
        permanence = Permanence.objects.filter(id=p_permanence_id).first()
        if permanence is not None:
            result = permanence.get_html_permanence_title_display()
        else:
            result = EMPTY_STRING
    return result


@register.simple_tag(takes_context=False)
def repanier_display_task(*args, **kwargs):
    result = EMPTY_STRING
    p_task_id = sint(kwargs.get("task_id", 0))
    if p_task_id > 0:
        permanence_board = (
            PermanenceBoard.objects.filter(id=p_task_id)
            .select_related("permanence_role")
            .first()
        )
        if permanence_board is not None:
            if permanence_board.permanence_role.customers_may_register:
                result = permanence_board.permanence_role
            else:
                result = "<p><b>{}</b></p>".format(permanence_board.permanence_role)
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_task(context, *args, **kwargs):
    request = context["request"]
    user = request.user
    result = EMPTY_STRING
    customer = Customer.objects.filter(id=user.customer_id, may_order=True).first()
    if customer is not None:
        p_task_id = sint(kwargs.get("task_id", 0))
        if p_task_id > 0:
            permanence_board = (
                PermanenceBoard.objects.filter(id=p_task_id)
                .select_related("customer", "permanence_role", "permanence")
                .first()
            )
            if permanence_board is not None:
                if permanence_board.customer is not None:
                    if (
                        permanence_board.customer_id == customer.id
                        and permanence_board.permanence.status <= SaleStatus.CLOSED
                    ):
                        result = """
                        <b><i>
                        <select name="value" id="task{task_id}"
                        onchange="task_ajax({task_id})" class="form-control">
                        <option value="0">---</option>
                        <option value="1" selected>{long_basket_name}</option>
                        </select>
                        </i></b>
                        """.format(
                            task_id=permanence_board.id,
                            long_basket_name=customer.long_basket_name,
                        )
                    else:
                        result = """
                        <select name="value" id="task{task_id}"
                        class="form-control">
                        <option value="0" selected>{long_basket_name}</option>
                        </select>
                        """.format(
                            task_id=permanence_board.id,
                            long_basket_name=permanence_board.customer.long_basket_name,
                        )
                else:
                    if permanence_board.permanence_role.customers_may_register:
                        if permanence_board.permanence.status <= SaleStatus.CLOSED:
                            result = """
                            <b><i>
                            <select name="value" id="task{task_id}"
                            onchange="task_ajax({task_id})" class="form-control">
                            <option value="0" selected>---</option>
                            <option value="1">{long_basket_name}</option>
                            </select>
                            </i></b>
                            """.format(
                                task_id=permanence_board.id,
                                long_basket_name=customer.long_basket_name,
                            )
                        else:
                            result = """
                            <select name="value" id="task{task_id}"
                            class="form-control">
                            <option value="0" selected>---</option>
                            </select>
                            """.format(
                                task_id=permanence_board.id
                            )
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_offer_item(context, *args, **kwargs):
    request = context["request"]
    user = request.user
    offer_item = kwargs.get("offer_item")
    result = []
    if offer_item.may_order:
        select_offer_item(offer_item, result, user)
    return mark_safe(EMPTY_STRING.join(result))


def select_offer_item(offer_item, result, user):
    purchase = (
        PurchaseWoReceiver.objects.filter(
            customer_id=user.customer_id,
            offer_item_id=offer_item.id,
        )
        .only("quantity_ordered")
        .first()
    )
    if purchase is not None:
        is_open = purchase.status == SaleStatus.OPENED
        offer_item = purchase.offer_item
        price_list_multiplier = offer_item.get_price_list_multiplier(
            purchase.customer_invoice
        )
        customer_unit_price = offer_item.get_customer_unit_price(price_list_multiplier)
        unit_deposit = offer_item.get_unit_deposit()
        unit_price_amount = (customer_unit_price + unit_deposit).quantize(
            RoundUpTo.TWO_DECIMALS
        )
        html = get_html_selected_value(
            offer_item,
            purchase.quantity_ordered,
            unit_price_amount=unit_price_amount,
            is_open=is_open,
        )
    else:
        is_open = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item.id,
            producer__offeritem=offer_item.id,
            status=SaleStatus.OPENED,
        ).exists()
        html = get_html_selected_value(
            offer_item, DECIMAL_ZERO, DECIMAL_ZERO, is_open=is_open
        )
    if is_open:
        result.append(
            '<select name="offer_item{id}" id="offer_item{id}" onchange="order_ajax({id})" onmouseover="show_select_order_list_ajax({id})" onmouseout="clear_select_order_list_ajax()" class="form-control">{option}</select>'.format(
                id=offer_item.id, option=html
            )
        )
    else:
        result.append(
            '<select name="offer_item{id}" id="offer_item{id}" class="form-control">{option}</select>'.format(
                id=offer_item.id, option=html
            )
        )


@register.simple_tag(takes_context=True)
def repanier_btn_like(context, *args, **kwargs):
    request = context["request"]
    user_id = request.user.id
    offer_item = kwargs.get("offer_item", None)
    str_id = str(offer_item.id)
    result = '<br><span class="btn_like{str_id}" style="cursor: pointer;">{html}</span>'.format(
        str_id=str_id, html=offer_item.get_html_like(user_id)
    )
    return mark_safe(result)
