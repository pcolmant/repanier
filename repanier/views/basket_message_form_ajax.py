# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Producer
from repanier.models import Customer
from repanier.tools import customer_on_hold_movement_message, producer_on_hold_movement_message


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
        customer_on_hold_movement = customer_on_hold_movement_message(customer)
        basket_message = mark_safe(customer_on_hold_movement)
        option_dict = {'id': "#basket_message", 'html': basket_message}
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
        producer_on_hold_movement = producer_on_hold_movement_message(producer)
        basket_message = mark_safe(producer_on_hold_movement)
        option_dict = {'id': "#basket_message", 'html': basket_message}
        to_json.append(option_dict)
        return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404
