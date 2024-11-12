from django.http import Http404, JsonResponse
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from repanier.email.email_order import export_order_2_1_customer
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.tools import (
    sint,
    my_basket,
    get_html_basket_message,
    permanence_ok_or_404,
)


@require_GET
def btn_confirm_order_ajax(request):
    customer_id = request.user.customer_id
    customer = Customer.can_place_an_order.filter(id=customer_id).first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence_id = sint(request.GET.get("permanence", 0))
    permanence = Permanence.objects.filter(id=permanence_id).first()
    permanence_ok_or_404(permanence)
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id,
        customer_id=customer_id,
        is_order_confirm_send=False,
        is_group=False,
    ).first()
    if customer_invoice is None:
        raise Http404
    # customer_invoice.calculate_order_amount()
    customer_invoice.confirm_order()
    customer_invoice.save()

    filename = "{}-{}.xlsx".format(_("Order"), permanence)
    export_order_2_1_customer(customer, filename, permanence)

    json_dict = my_basket(
        customer_invoice.is_order_confirm_send,
        customer_invoice.get_total_price_with_tax(),
    )
    if customer_invoice.delivery is not None:
        status = customer_invoice.delivery.status
    else:
        status = customer_invoice.status
    delivery_message = customer_invoice.get_html_select_delivery_point(
        permanence, status
    )
    basket_message = get_html_basket_message(
        customer, permanence, status, customer_invoice
    )
    json_dict.update(
        customer_invoice.get_html_my_order_confirmation(
            permanence=permanence,
            is_basket=True,
            delivery_message=delivery_message,
            basket_message=basket_message,
        )
    )
    return JsonResponse(json_dict)
