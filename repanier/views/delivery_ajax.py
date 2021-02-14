from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.middleware import is_ajax
from repanier.const import SALE_OPENED
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.tools import (
    sint,
    sboolean,
    my_basket,
    get_repanier_template_name,
    get_html_basket_message,
)

template_communication_confirm_order = get_repanier_template_name(
    "communication_confirm_order.html"
)


@never_cache
@require_GET
@login_required
def delivery_ajax(request):
    if not is_ajax():
        raise Http404
    user = request.user
    permanence_id = sint(request.GET.get("permanence", 0))
    permanence = (
        Permanence.objects.filter(id=permanence_id, with_delivery_point=True)
        .order_by("?")
        .first()
    )
    if permanence is None:
        raise Http404
    customer = (
        Customer.objects.filter(user_id=user.id, may_order=True).order_by("?").first()
    )
    if customer is None:
        raise Http404
    customer_invoice = (
        CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence_id=permanence_id
        )
        .order_by("?")
        .first()
    )
    if customer_invoice is None:
        raise Http404
    json_dict = {}
    if customer_invoice.status == SALE_OPENED:
        delivery_board_id = sint(request.GET.get("delivery", 0))
        qs = customer.get_available_deliveries_qs(
            permanence_id=permanence_id, delivery_board_id=delivery_board_id
        )
        delivery_board = qs.first()
        if delivery_board is None:
            raise Http404
        if customer_invoice.delivery != delivery_board:
            customer_invoice.set_delivery_context(delivery_board=delivery_board)
            customer_invoice.set_total()
            invoice_confirm_status_is_changed = customer_invoice.cancel_confirm_order()
            customer_invoice.save()

            if invoice_confirm_status_is_changed:
                html = render_to_string(template_communication_confirm_order)
                json_dict["#communicationModal"] = mark_safe(html)

            json_dict.update(
                my_basket(
                    customer_invoice.is_order_confirm_send,
                    customer_invoice.balance_calculated,
                )
            )

    is_basket = sboolean(request.GET.get("is_basket", False))
    if customer_invoice.delivery is not None:
        status = customer_invoice.delivery.status
    else:
        status = customer_invoice.status
    basket_message = get_html_basket_message(customer, permanence, status)
    json_dict.update(
        customer_invoice.get_html_my_order_confirmation(
            permanence=permanence, is_basket=is_basket, basket_message=basket_message
        )
    )
    return JsonResponse(json_dict)
