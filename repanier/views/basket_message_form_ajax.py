# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import EMPTY_STRING
from repanier.models import Customer
from repanier.tools import on_hold_movement_message


@never_cache
@require_GET
def basket_message_form_ajax(request, customer_id):
    if request.is_ajax():
        user = request.user
        if user.is_anonymous:
            return HttpResponse(EMPTY_STRING)
        to_json = []
        if request.user.is_staff:
            customer = Customer.objects.filter(id=customer_id).order_by('?').first()
        else:
            customer = request.user.customer
        customer_on_hold_movement = on_hold_movement_message(customer)
        basket_message = mark_safe(customer_on_hold_movement)
        option_dict = {'id': "#basket_message", 'html': basket_message}
        to_json.append(option_dict)
        return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404
