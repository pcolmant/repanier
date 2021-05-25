from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
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
    user = request.user
    permanence_id = sint(request.GET.get("permanence", 0))
    permanence = (
        Permanence.objects.filter(id=permanence_id)
        .only("id", "status")
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
    if customer_invoice.status == PERMANENCE_OPENED:
        delivery_id = sint(request.GET.get("delivery", 0))
        if customer.delivery_point is not None:
            # The customer is member of a group
            qs = DeliveryBoard.objects.filter(
                Q(
                    id=delivery_id,
                    permanence_id=permanence_id,
                    delivery_point_id=customer.delivery_point_id,
                    status=PERMANENCE_OPENED,
                )
                | Q(
                    id=delivery_id,
                    permanence_id=permanence_id,
                    delivery_point__group__isnull=True,
                    status=PERMANENCE_OPENED,
                )
            )
        else:
            qs = DeliveryBoard.objects.filter(
                id=delivery_id,
                permanence_id=permanence_id,
                delivery_point__group__isnull=True,
                status=PERMANENCE_OPENED,
            )
        delivery = qs.first()
        if delivery is None:
            raise Http404
        if customer_invoice.delivery != delivery:
            customer_invoice.set_order_delivery(delivery)
            customer_invoice.calculate_order_price()
            invoice_confirm_status_is_changed = customer_invoice.cancel_confirm_order()
            customer_invoice.save()
            if (
                settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER
                and invoice_confirm_status_is_changed
            ):
                html = render_to_string(template_communication_confirm_order)
                json_dict["#communicationModal"] = mark_safe(html)

            json_dict.update(
                my_basket(
                    customer_invoice.is_order_confirm_send,
                    customer_invoice.get_total_price_with_tax(),
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
