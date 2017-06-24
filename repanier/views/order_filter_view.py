# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils import translation
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET

from repanier.models.offeritem import OfferItem
from repanier.models.producer import Producer
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.const import EMPTY_STRING


@never_cache
@require_GET
@csrf_protect
def order_filter_view(request, permanence_id):
    if request.user.is_staff or request.user.is_superuser:
        raise Http404
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
    if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
        producer_set = Producer.objects.filter(permanence=permanence_id).only("id", "short_profile_name")
    else:
        producer_set = None
    is_basket = request.GET.get('is_basket', EMPTY_STRING)
    is_like = request.GET.get('is_like', EMPTY_STRING)
    producer_id = request.GET.get('producer', 'all')
    departementforcustomer_id = request.GET.get('departementforcustomer', 'all')
    box_id = request.GET.get('box', 'all')
    if box_id != 'all':
        is_box = True
        # Do not display "all department" as selected
        departementforcustomer_id = None
    else:
        is_box = False
    q = request.GET.get('q', None)
    departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
        offeritem__permanence_id=permanence_id,
        offeritem__is_active=True,
        offeritem__is_box=False) \
        .order_by("tree_id", "lft") \
        .distinct("id", "tree_id", "lft")
    if producer_id != 'all':
        departementforcustomer_set = departementforcustomer_set.filter(
            offeritem__producer_id=producer_id
        )
    return render(
        request, "repanier/order_filter.html",
        {
            'is_like': is_like,
            'is_basket': is_basket,
            'is_box': is_box,
            'q': q,
            'producer_set': producer_set,
            'producer_id': producer_id,
            'departementforcustomer_set': departementforcustomer_set,
            'departementforcustomer_id': departementforcustomer_id,
            'box_set':  OfferItem.objects.filter(
                            permanence_id=permanence_id,
                            is_box=True,
                            is_active=True,
                            may_order=True,
                            translations__language_code=translation.get_language()
                        ).order_by(
                            'customer_unit_price',
                            'unit_deposit',
                            'translations__long_name',
                        ),
            'box_id': box_id,
            'permanence_id': permanence_id,
            'may_order': True
        }
    )
