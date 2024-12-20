from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from repanier.models import Customer
from repanier.models.offeritem import OfferItemReadOnly
from repanier.tools import sint


@require_GET
def like_ajax(request):
    user_id = request.user.id
    offer_item_id = sint(request.GET.get("offer_item", 0))
    offer_item = OfferItemReadOnly.objects.filter(id=offer_item_id).first()
    if offer_item is not None and offer_item.product_id is not None:
        product = offer_item.product
        json_dict = {}
        if product.likes.filter(id=user_id).exists():
            # user has already liked this company
            # remove like/user
            product.likes.remove(user_id)
        else:
            # add a new like for a company
            product.likes.add(user_id)
        like_html = offer_item.get_html_like(user_id=user_id)
        json_dict[".btn_like{}".format(offer_item.id)] = like_html
        return JsonResponse(json_dict)
    raise Http404
