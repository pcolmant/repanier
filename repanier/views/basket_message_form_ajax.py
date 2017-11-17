# -*- coding: utf-8

from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.customer import Customer
from repanier.models.producer import Producer


@never_cache
@require_GET
def customer_basket_message_form_ajax(request, pk):
    if request.is_ajax():
        user = request.user
        if user.is_anonymous:
            raise Http404
        if request.user.is_staff:
            customer = Customer.objects.filter(id=pk).order_by('?').first()
        else:
            customer = request.user.customer
        json = {"#basket_message", customer.get_on_hold_movement_html()}
        return JsonResponse(json)
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
        json = {"#basket_message", producer.get_on_hold_movement_html()}
        return JsonResponse(json)
    raise Http404
