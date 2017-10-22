# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.offeritem import OfferItem
from repanier.tools import sint


@never_cache
@require_GET
def like_ajax(request):
    if request.is_ajax():
        user = request.user
        if user.is_authenticated:
            offer_item_id = sint(request.GET.get('offer_item', 0))
            offer_item = OfferItem.objects.filter(id=offer_item_id).order_by('?').first()
            if offer_item is not None and offer_item.product_id is not None:
                product = offer_item.product
                to_json = []
                if product.likes.filter(id=user.id).exists():
                    # user has already liked this company
                    # remove like/user
                    product.likes.remove(user)
                else:
                    # add a new like for a company
                    product.likes.add(user)
                option_dict = {'id': ".btn_like{}".format(offer_item_id), 'html': offer_item.get_like(user)}
                to_json.append(option_dict)
                return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404
