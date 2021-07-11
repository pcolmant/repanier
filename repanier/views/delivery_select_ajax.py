from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, EMPTY_STRING
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.tools import sint


@never_cache
@require_GET
@login_required
def delivery_select_ajax(request):
    # construct a list which will contain all of the data for the response
    user = request.user
    customer = Customer.objects.filter(user_id=user.id, may_order=True).first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence_id = sint(request.GET.get("permanence", 0))
    customer_invoice = (
        CustomerInvoice.objects.filter(
            customer_id=customer.id, permanence_id=permanence_id
        )
        .first()
    )
    if customer_invoice is None:
        raise Http404
    if customer.group is not None:
        qs = DeliveryBoard.objects.filter(
            Q(
                permanence_id=permanence_id,
                delivery_point__group_id=customer.group_id,
                status=PERMANENCE_OPENED,
            )
            | Q(
                permanence_id=permanence_id,
                delivery_point__group__isnull=True,
                status=PERMANENCE_OPENED,
            )
        )
    else:
        qs = DeliveryBoard.objects.filter(
            permanence_id=permanence_id,
            delivery_point__group__isnull=True,
            status=PERMANENCE_OPENED,
        )
    is_selected = False
    delivery_counter = 0
    html = EMPTY_STRING
    # IMPORTANT : Do not limit to delivery.status=PERMANENCE_OPENED to include potentialy closed
    # delivery already selected by the customer
    for delivery in qs:
        if delivery.id == customer_invoice.delivery_id:
            is_selected = True
            html += '<option value="{}" selected>{}</option>'.format(
                delivery.id, delivery.get_delivery_customer_display()
            )
        elif (
            delivery.status == PERMANENCE_OPENED
            and customer_invoice.status == PERMANENCE_OPENED
        ):
            delivery_counter += 1
            html += '<option value="{}">{}</option>'.format(
                delivery.id, delivery.get_delivery_customer_display()
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
