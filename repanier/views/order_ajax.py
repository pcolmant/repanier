# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO
from repanier.models import Customer, ProducerInvoice, CustomerInvoice, Purchase, OfferItem
from repanier.tools import update_or_create_purchase, sint, sboolean, display_selected_value


@never_cache
@require_GET
def order_ajax(request):
    if not request.is_ajax():
        raise Http404
    user = request.user
    if not user.is_authenticated:
        raise Http404
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True
    ).order_by('?').first()
    if customer is None:
        raise Http404
    offer_item_id = sint(request.GET.get('offer_item', 0))
    value_id = sint(request.GET.get('value', 0))
    basket = sboolean(request.GET.get('basket', False))
    qs = CustomerInvoice.objects.filter(
        permanence__offeritem=offer_item_id,
        customer_id=customer.id,
        status=PERMANENCE_OPENED).order_by('?')
    result = None
    if qs.exists():
        qs = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item_id,
            producer__offeritem=offer_item_id,
            status=PERMANENCE_OPENED
        ).order_by('?')
        if qs.exists():
            result = update_or_create_purchase(
                customer=customer,
                offer_item_id=offer_item_id,
                value_id=value_id,
                basket=basket,
                batch_job=False
            )
    if result is None:
        # Select one purchase
        purchase = Purchase.objects.filter(
            customer_id=customer.id,
            offer_item_id=offer_item_id,
            is_box_content=False
        ).select_related(
            "offer_item"
        ).order_by('?').first()
        to_json = []
        if purchase is not None:
            option_dict = display_selected_value(
                purchase.offer_item,
                purchase.quantity_ordered)
            to_json.append(option_dict)
        else:
            offer_item = OfferItem.objects.filter(
                id=offer_item_id
            ).select_related(
                "product"
            ).order_by('?').first()
            option_dict = display_selected_value(
                offer_item,
                DECIMAL_ZERO)
            to_json.append(option_dict)
        result = json.dumps(to_json, cls=DjangoJSONEncoder)
    return HttpResponse(result, content_type="application/json")
