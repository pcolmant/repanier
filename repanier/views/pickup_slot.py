from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.distribution import PickupSlot
from repanier.models.invoice import CustomerInvoice


@never_cache
@login_required
@require_POST
@transaction.atomic
def select_pickup_slot(request):
    customer = Customer.can_place_an_order.filter(user=request.user).first()
    if customer is None:
        raise Http404
    try:
        permanence_id = int(request.POST.get("permanence", ""))
        slot_id = int(request.POST.get("pickup_slot", ""))
    except (TypeError, ValueError):
        raise Http404
    invoice = CustomerInvoice.objects.select_for_update().filter(
        customer=customer, permanence_id=permanence_id,
        status=SaleStatus.OPENED, permanence__status=SaleStatus.OPENED,
        is_group=False,
    ).first()
    slot = PickupSlot.objects.filter(
        pk=slot_id, distribution_event__permanence_id=permanence_id
    ).first()
    if invoice is None or slot is None:
        raise Http404
    if invoice.pickup_slot_id != slot.id:
        invoice.set_pickup_slot(slot)
        if invoice.cancel_confirm_order():
            invoice.save(update_fields=["is_order_confirm_send"])
    return JsonResponse({"selected": slot.id})
