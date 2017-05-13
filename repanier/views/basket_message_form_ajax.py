# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Producer
from repanier.models import Customer


@never_cache
@require_GET
def customer_basket_message_form_ajax(request, pk):
    if request.is_ajax():
        user = request.user
        if user.is_anonymous:
            raise Http404
        to_json = []
        if request.user.is_staff:
            customer = Customer.objects.filter(id=pk).order_by('?').first()
        else:
            customer = request.user.customer
        option_dict = {'id': "#basket_message", 'html': customer.get_on_hold_movement_html()}
        to_json.append(option_dict)
        return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404


@never_cache
@require_GET
def producer_basket_message_form_ajax(request, pk, uuid):
    if request.is_ajax():
        user = request.user
        if not (user.is_anonymous or request.user.is_staff):
            raise Http404
        producer = Producer.objects.filter(id=pk, uuid=uuid).order_by('?').first()
        if producer is None:
            raise Http404
        to_json = []
        producer.on_hold_movement_json(to_json)
        return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404
