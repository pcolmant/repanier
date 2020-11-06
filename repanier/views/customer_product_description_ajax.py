from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, PERMANENCE_SEND
from repanier.models.offeritem import OfferItem
from repanier.tools import permanence_ok_or_404, sint, get_repanier_template_name

template_order_product_description = get_repanier_template_name(
    "order_product_description.html"
)


@require_GET
def customer_product_description_ajax(request):
    if request.is_ajax():
        offer_item_id = sint(request.GET.get("offer_item", 0))
        offer_item = get_object_or_404(OfferItem, id=offer_item_id)
        permanence = offer_item.permanence
        permanence_ok_or_404(permanence)
        if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
            html = render_to_string(
                template_order_product_description,
                {"offer": offer_item, "MEDIA_URL": settings.MEDIA_URL},
            )
            return JsonResponse({"#orderModal": mark_safe(html)})
    raise Http404
