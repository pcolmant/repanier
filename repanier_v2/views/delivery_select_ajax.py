from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier_v2.middleware import is_ajax
from repanier_v2.const import ORDER_OPENED, EMPTY_STRING
from repanier_v2.models.customer import Customer
from repanier_v2.models.invoice import CustomerInvoice
from repanier_v2.tools import sint


@never_cache
@require_GET
@login_required
def delivery_select_ajax(request):
    if not is_ajax():
        raise Http404
    # construct a list which will contain all of the data for the response
    user = request.user
    customer = (
        Customer.objects.filter(user_id=user.id, may_order=True).order_by("?").first()
    )
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence_id = sint(request.GET.get("permanence", 0))
    customer_invoice = (
        CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence_id=permanence_id
        )
        .order_by("?")
        .first()
    )
    if customer_invoice is None:
        raise Http404
    qs = customer.get_available_deliveries_qs(permanence_id=permanence_id)
    is_selected = False
    delivery_counter = 0
    html = EMPTY_STRING
    # IMPORTANT : Do not limit to delivery.status=ORDER_OPENED to include potentialy closed
    # delivery already selected by the customer
    for delivery in qs:
        if delivery.id == customer_invoice.delivery_id:
            is_selected = True
            html += '<option value="{}" selected>{}</option>'.format(
                delivery.id, delivery.get_delivery_status_display()
            )
        elif delivery.status == ORDER_OPENED and customer_invoice.status == ORDER_OPENED:
            delivery_counter += 1
            html += '<option value="{}">{}</option>'.format(
                delivery.id, delivery.get_delivery_status_display()
            )
    if not is_selected:
        if delivery_counter == 0:
            label = "{}".format(
                _("No delivery point is open for you. You can not place order.")
            )
        else:
            label = "{}".format(_("Please, select a delivery point"))
        html = '<option value="-1" selected>{}</option>'.format(label) + html

    return JsonResponse({"#delivery": mark_safe(html)})
