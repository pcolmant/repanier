# -*- coding: utf-8 -*-

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import EMPTY_STRING, PERMANENCE_CLOSED, DECIMAL_ZERO, PERMANENCE_OPENED
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import sint, display_selected_value, display_selected_box_value

register = template.Library()


@register.simple_tag(takes_context=False)
def repanier_home(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_HOME_SITE
    return REPANIER_SETTINGS_HOME_SITE


@register.simple_tag(takes_context=False)
def repanier_group_name(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
    return REPANIER_SETTINGS_GROUP_NAME


@register.simple_tag(takes_context=True)
def repanier_user(context, *args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_INVOICE, REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    request = context["request"]
    user = request.user
    nodes = []
    if user.is_authenticated:
        if not user.is_staff:
            nodes = ["""
                <li id="li_my_name" class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown"><span class="glyphicon glyphicon-user" aria-hidden="true"></span> {} {}<b class="caret"></b></a>
                <ul class="dropdown-menu">
                """.format(
                _('Welkom'),
                user.username or '<span id = "my_name"></ span>'
            )]
            customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
            if customer_is_active:

                nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                    reverse('send_mail_to_coordinators_view'),
                    _('Send mail to coordinators')
                ))
                if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
                    nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                        reverse('send_mail_to_all_members_view'),
                        _('Send mail to all members')
                    ))
                    nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                        reverse('who_is_who_view'),
                        _('Who is who')
                    ))
                nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                    reverse('my_profile_view'),
                    _('My profile')
                ))
                if REPANIER_SETTINGS_INVOICE:
                    last_customer_invoice = CustomerInvoice.objects.filter(
                        customer__user_id=request.user.id,
                        invoice_sort_order__isnull=False) \
                        .only("balance", "date_balance") \
                        .order_by('-invoice_sort_order').first()
                    if last_customer_invoice is not None:
                        if last_customer_invoice.balance < DECIMAL_ZERO:
                            my_balance = _('My balance : <font color="red">%(balance)s</font> at %(date)s') % {
                                'balance': last_customer_invoice.balance,
                                'date'   : last_customer_invoice.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                        else:
                            my_balance = _('My balance : <font color="green">%(balance)s</font> at %(date)s') % {
                                'balance': last_customer_invoice.balance,
                                'date'   : last_customer_invoice.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                    else:
                        my_balance = _('My balance')
                    nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                        reverse("customer_invoice_view", args=(0,)),
                        my_balance
                    ))
                nodes.append('<li class="divider"></li>')
            nodes.append("<li><a href=\"{}\">{}</a></li>".format(
                reverse("logout_form"), _("Logout")
            ))
            nodes.append("</ul></li>")
            p_permanence_id = sint(kwargs.get("permanence_id", 0))
            if p_permanence_id > 0:
                nodes.append("<li id=\"li_my_basket\" style=\"display:none;\" class=\"dropdown\">")
                nodes.append("<a href=\"{}?is_basket=yes\" class=\"btn btn-info\"><span id=\"my_basket\"></span></a>".format(
                    reverse("order_view", args=(p_permanence_id,)))
                )
                nodes.append('</li>')
    else:
        p_offer_uuid = kwargs.get("offer_uuid", None)
        if len(p_offer_uuid) == 36:
            producer = Producer.objects.filter(offer_uuid=p_offer_uuid).only("long_profile_name").order_by('?').first()
            if producer is not None:
                nodes = ["<li><a href=\"#\">{} {}</a></li>".format(
                    _('Welkom'),
                    producer.long_profile_name
                )]
        else:
            nodes = ["<li class=\"dropdown\"><a href=\"{}\">{}</a></li>".format(
                    reverse("login_form"),
                    _("Login")
            )]

    return mark_safe("".join(nodes))


@register.simple_tag(takes_context=False)
def repanier_display_languages(*args, **kwargs):
    from django.conf import settings
    if len(settings.LANGUAGES) > 1:
        return "yes"
    return


@register.simple_tag(takes_context=False)
def repanier_display_task(*args, **kwargs):
    result = EMPTY_STRING
    p_task_id = sint(kwargs.get('task_id', 0))
    if p_task_id > 0:
        permanence_board = PermanenceBoard.objects.filter(id=p_task_id).select_related(
            "permanence_role"
        ).order_by('?').first()
        if permanence_board is not None:
            if permanence_board.permanence_role.customers_may_register:
                result = permanence_board.permanence_role
            else:
                result = "<p><b>{}</b></p>".format(permanence_board.permanence_role)
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_task(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if customer_is_active:
        p_task_id = sint(kwargs.get('task_id', 0))
        if p_task_id > 0:
            permanence_board = PermanenceBoard.objects.filter(id=p_task_id).select_related(
                "customer", "permanence_role", "permanence"
            ).order_by('?').first()
            if permanence_board is not None:
                if permanence_board.customer is not None:
                    if permanence_board.customer.user_id == user.id and permanence_board.permanence.status <= PERMANENCE_CLOSED:
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
                            long_basket_name=user.customer.long_basket_name
                        )
                    else:
                        result = """
                        <select name="value" id="task{task_id}"
                        class="form-control">
                        <option value="0" selected>{long_basket_name}</option>
                        </select>
                        """.format(
                            task_id=permanence_board.id,
                            long_basket_name=permanence_board.customer.long_basket_name
                        )
                else:
                    if permanence_board.permanence_role.customers_may_register:
                        if permanence_board.permanence.status <= PERMANENCE_CLOSED:
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
                                long_basket_name=user.customer.long_basket_name
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
    request = context['request']
    user = request.user
    offer_item = kwargs.get('offer_item')
    date = kwargs.get('date', EMPTY_STRING)
    result = []
    if offer_item.may_order:
        # Important : offer_item.permanences_dates_order is used to
        # group together offer item's of the same product of a contract
        # with different purchases dates on the order form
        # 0   : No group needed
        # 1   : Master of a group
        # > 1 : Displayed with the master of the group (filtered in order_class.py)
        select_offer_item(offer_item, result, user)
        if offer_item.permanences_dates_order == 1 and date == "all":
            for sub_offer_item in OfferItemWoReceiver.objects.filter(
                permanence_id=offer_item.permanence_id,
                product_id=offer_item.product_id,
                permanences_dates_order__gt=1
            ).order_by("permanences_dates_order"):
                select_offer_item(sub_offer_item, result, user)
    if offer_item.is_box_content:
        box_purchase = PurchaseWoReceiver.objects.filter(
            customer_id=user.customer,
            offer_item_id=offer_item.id,
            is_box_content=True
        ).order_by('?').only('quantity_ordered').first()
        if box_purchase is None:
            quantity_ordered = DECIMAL_ZERO
        else:
            quantity_ordered = box_purchase.quantity_ordered
        option_dict = display_selected_box_value(offer_item, quantity_ordered)
        result.append("<select id=\"box_offer_item{id}\" name=\"box_offer_item{id}\" disabled class=\"form-control\">{option}</select>".format(
            result=result,
            id=offer_item.id,
            option=option_dict['html']
        ))
    return mark_safe(EMPTY_STRING.join(result))


def select_offer_item(offer_item, result, user):
    purchase = PurchaseWoReceiver.objects.filter(
        customer_id=user.customer,
        offer_item_id=offer_item.id,
        is_box_content=False
    ).order_by('?').only('quantity_ordered').first()
    if purchase is not None:
        is_open = purchase.status == PERMANENCE_OPENED
        option_dict = display_selected_value(
            offer_item,
            purchase.quantity_ordered,
            is_open=is_open
        )
    else:
        is_open = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item.id,
            producer__offeritem=offer_item.id,
            status=PERMANENCE_OPENED
        ).order_by('?').exists()
        option_dict = display_selected_value(
            offer_item,
            DECIMAL_ZERO,
            is_open=is_open
        )
    if offer_item.permanences_dates_counter > 0:
        permanences_date = offer_item.get_html_permanences_dates
    else:
        permanences_date = EMPTY_STRING
    if is_open:
        result.append(
            "{dates}<select name=\"offer_item{id}\" id=\"offer_item{id}\" onchange=\"order_ajax({id})\" onmouseover=\"show_select_order_list_ajax({id})\" class=\"form-control\">{option}</select>".format(
                dates=permanences_date,
                id=offer_item.id,
                option=option_dict['html']
            ))
    else:
        result.append(
            "{dates}<select name=\"offer_item{id}\" id=\"offer_item{id}\" class=\"form-control\">{option}</select>".format(
                dates=permanences_date,
                id=offer_item.id,
                option=option_dict['html']
            ))


@register.simple_tag(takes_context=True)
def repanier_btn_like(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if customer_is_active:
        offer_item = kwargs.get('offer_item', None)
        str_id = str(offer_item.id)
        result = "<br><span class=\"btn_like{str_id}\" style=\"cursor: pointer;\">{html}</span>".format(
            str_id=str_id,
            html=offer_item.get_like(user)
        )
    return mark_safe(result)