from django.contrib.auth.decorators import login_required

from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.offeritem import OfferItemWoReceiver
from repanier.tools import sint


@never_cache
@require_GET
@login_required
def like_ajax(request):
    user = request.user
    if user.is_authenticated:
        offer_item_id = sint(request.GET.get("offer_item", 0))
        offer_item = (
            OfferItemWoReceiver.objects.filter(id=offer_item_id)
            .order_by("?")
            .first()
        )
        if offer_item is not None and offer_item.product_id is not None:
            product = offer_item.product
            json_dict = {}
            if product.likes.filter(id=user.id).exists():
                # user has already liked this company
                # remove like/user
                product.likes.remove(user)
            else:
                # add a new like for a company
                product.likes.add(user)
            like_html = offer_item.get_html_like(user)
            json_dict[".btn_like{}".format(offer_item.id)] = like_html
            return JsonResponse(json_dict)
    raise Http404
