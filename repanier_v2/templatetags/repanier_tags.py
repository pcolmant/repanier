from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier_v2.const import (
    EMPTY_STRING,
    ORDER_CLOSED,
    DECIMAL_ZERO,
    ORDER_OPENED,
    ORDER_SEND,
)
from repanier_v2.models import Permanence
from repanier_v2.models.customer import Customer
from repanier_v2.models.invoice import CustomerInvoice, ProducerInvoice
from repanier_v2.models.permanenceboard import PermanenceBoard
from repanier_v2.models.purchase import PurchaseWoReceiver
from repanier_v2.tools import (
    sint,
    get_html_selected_value,
    get_html_selected_box_value,
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
    from repanier_v2.globals import REPANIER_SETTINGS_NOTIFICATION

    return REPANIER_SETTINGS_NOTIFICATION.get_html_notification_card_display()


@register.simple_tag(takes_context=False)
def repanier_permanences(*args, **kwargs):
    permanences_cards = []
    for permanence in (
        Permanence.objects.filter(status=ORDER_OPENED)
        .only("id", "permanence_date", "with_delivery_point")
        .order_by("permanence_date", "id")
    ):
        permanences_cards.append(permanence.get_html_permanence_card_display())

    displayed_permanence_counter = 0
    for permanence in (
        Permanence.objects.filter(
            status__in=[ORDER_CLOSED, ORDER_SEND],
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
            else _("Offer")
            if len(permanences_cards) == 1
            else _("Offers"),
            html='<div class="dropdown-divider"></div>'.join(permanences_cards),
        )
    )


@register.simple_tag(takes_context=True)
def repanier_user_bs3(context, *args, **kwargs):
    from repanier_v2.globals import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    request = context["request"]
    user = request.user
    nodes = []
    if user.is_authenticated:
        if not user.is_staff:
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
                    reverse("repanier_v2:send_mail_to_coordinators_view"), _("Inform")
                )
            )
            if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
                nodes.append(
                    '<li><a href="{}">{}</a></li>'.format(
                        reverse("repanier_v2:who_is_who_view"), _("Who's who")
                    )
                )
            if user.customer_id is not None:
                nodes.append(
                    '<li><a href="{}">{}</a></li>'.format(
                        reverse(
                            "repanier_v2:published_customer_view",
                            kwargs={"customer_id": user.customer_id},
                        ),
                        _("My profile"),
                    )
                )
                if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                    last_customer_invoice = (
                        CustomerInvoice.objects.filter(
                            customer__user_id=request.user.id,
                            invoice_sort_order__isnull=False,
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
                            reverse(
                                "repanier_v2:customer_invoice_view",
                                args=(0, user.customer_id),
                            ),
                            my_balance,
                        )
                    )
                nodes.append('<li class="divider"></li>')
            nodes.append(
                '<li><a href="{}">{}</a></li>'.format(
                    reverse("repanier_v2:logout"), _("Logout")
                )
            )
            nodes.append("</ul></li>")

    else:
        nodes = [
            '<li class="dropdown"><a href="{}">{}</a></li>'.format(
                reverse("repanier_v2:login_form"), _("Login")
            )
        ]

    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=False)
def repanier_permanence_basket_bs3(*args, **kwargs):
    p_permanence_id = sint(kwargs.get("permanence_id", 0))
    nodes = []
    if p_permanence_id > 0:
        nodes.append('<li id="li_my_basket" style="display:none;" class="dropdown">')
        nodes.append(
            '<a href="{}?is_basket=yes" class="btn btn-info"><span id="my_basket"></span></a>'.format(
                reverse("repanier_v2:order_view", args=(p_permanence_id,))
            )
        )
        nodes.append("</li>")
    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=False)
def repanier_permanence_title(*args, **kwargs):
    result = EMPTY_STRING
    p_permanence_id = sint(kwargs.get("permanence_id", 0))
    if p_permanence_id > 0:
        permanence = Permanence.objects.filter(id=p_permanence_id).order_by("?").first()
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
        permanence = Permanence.objects.filter(id=p_permanence_id).order_by("?").first()
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
            .order_by("?")
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
    customer_is_active = (
        Customer.objects.filter(user_id=user.id, is_active=True).order_by("?").exists()
    )
    if customer_is_active:
        p_task_id = sint(kwargs.get("task_id", 0))
        if p_task_id > 0:
            permanence_board = (
                PermanenceBoard.objects.filter(id=p_task_id)
                .select_related("customer", "permanence_role", "permanence")
                .order_by("?")
                .first()
            )
            if permanence_board is not None:
                if permanence_board.customer is not None:
                    if (
                        permanence_board.customer.user_id == user.id
                        and permanence_board.permanence.status <= ORDER_CLOSED
                    ):
                        result = """
                        <b><i>
                        <select name="value" id="task{task_id}"
                        onchange="task_ajax({task_id})" class="form-control">
                        <option value="0">---</option>
                        <option value="1" selected>{long_name}</option>
                        </select>
                        </i></b>
                        """.format(
                            task_id=permanence_board.id,
                            long_name=user.customer.long_name,
                        )
                    else:
                        result = """
                        <select name="value" id="task{task_id}"
                        class="form-control">
                        <option value="0" selected>{long_name}</option>
                        </select>
                        """.format(
                            task_id=permanence_board.id,
                            long_name=permanence_board.customer.long_name,
                        )
                else:
                    if permanence_board.permanence_role.customers_may_register:
                        if permanence_board.permanence.status <= ORDER_CLOSED:
                            result = """
                            <b><i>
                            <select name="value" id="task{task_id}"
                            onchange="task_ajax({task_id})" class="form-control">
                            <option value="0" selected>---</option>
                            <option value="1">{long_name}</option>
                            </select>
                            </i></b>
                            """.format(
                                task_id=permanence_board.id,
                                long_name=user.customer.long_name,
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
    date = kwargs.get("date", EMPTY_STRING)
    result = []
    if offer_item.may_order:
        select_offer_item(offer_item, result, user)
    if offer_item.is_box_content:
        box_purchase = (
            PurchaseWoReceiver.objects.filter(
                customer_id=user.customer,
                offer_item_id=offer_item.id,
                is_box_content=True,
            )
            .order_by("?")
            .only("qty")
            .first()
        )
        if box_purchase is None:
            qty = DECIMAL_ZERO
        else:
            qty = box_purchase.qty
        html = get_html_selected_box_value(offer_item, qty)
        result.append(
            '<select id="box_offer_item{id}" name="box_offer_item{id}" disabled class="form-control">{option}</select>'.format(
                result=result, id=offer_item.id, option=html
            )
        )
    return mark_safe(EMPTY_STRING.join(result))


def select_offer_item(offer_item, result, user):
    purchase = (
        PurchaseWoReceiver.objects.filter(
            customer_id=user.customer, offer_item_id=offer_item.id, is_box_content=False
        )
        .only("qty")
        .first()
    )
    if purchase is not None:
        is_open = purchase.status == ORDER_OPENED
        html = get_html_selected_value(offer_item, purchase.qty, is_open=is_open)
    else:
        is_open = Permanence.objects.filter(
            id=offer_item.permanence_id, status=ORDER_OPENED
        ).exists()
        html = get_html_selected_value(offer_item, DECIMAL_ZERO, is_open=is_open)
    if is_open:
        result.append(
            '<select name="offer_item{id}" id="offer_item{id}" onchange="order_ajax({id})" onmouseover="show_select_order_list_ajax({id})" class="form-control">{option}</select>'.format(
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
    user = request.user
    result = EMPTY_STRING
    customer_is_active = (
        Customer.objects.filter(user_id=user.id, is_active=True).order_by("?").exists()
    )
    if customer_is_active:
        offer_item = kwargs.get("offer_item", None)
        str_id = str(offer_item.id)
        result = '<br><span class="btn_like{str_id}" style="cursor: pointer;">{html}</span>'.format(
            str_id=str_id, html=offer_item.get_html_like(user)
        )
    return mark_safe(result)
