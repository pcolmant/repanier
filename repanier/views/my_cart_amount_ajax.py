from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.invoice import CustomerInvoice
from repanier.tools import my_basket


@never_cache
@require_GET
@login_required
def my_cart_amount_ajax(request, permanence_id):
    user = request.user
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id, customer_id=user.customer_id
    ).first()
    if customer_invoice is None:
        raise Http404
    json_dict = my_basket(
        customer_invoice.is_order_confirm_send,
        customer_invoice.get_total_price_with_tax(),
    )
    return JsonResponse(json_dict)
