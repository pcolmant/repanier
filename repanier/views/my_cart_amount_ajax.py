# -*- coding: utf-8

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.invoice import CustomerInvoice
from repanier.tools import my_basket


@never_cache
@require_GET
@login_required
def my_cart_amount_ajax(request, permanence_id):
    if not request.is_ajax():
        raise Http404
    user = request.user
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id,
        customer__user_id=user.id
    ).order_by('?').first()
    if customer_invoice is None:
        raise Http404
    to_json = []
    my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(), to_json)
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
