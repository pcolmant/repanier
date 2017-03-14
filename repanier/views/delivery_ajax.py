# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO
from repanier.models import Customer, DeliveryBoard, CustomerInvoice, Purchase, Permanence
from repanier.tools import sint, sboolean, calc_basket_message, my_order_confirmation


@never_cache
@require_GET
def delivery_ajax(request):
    if request.is_ajax():
        user = request.user
        if user.is_authenticated:
            permanence_id = sint(request.GET.get('permanence', 0))
            basket = sboolean(request.GET.get('basket', False))
            permanence = Permanence.objects.filter(
                id=permanence_id
            ).only("id", "status").order_by('?').first()
            if permanence is None:
                raise Http404
            customer = Customer.objects.filter(
                user_id=user.id, is_active=True, may_order=True
            ).only(
                "id", "delivery_point", "balance"
            ).order_by('?').first()
            if customer is None:
                raise Http404
            customer_invoice = CustomerInvoice.objects.filter(
                customer_id=customer.id,
                permanence_id=permanence_id
            ).order_by('?').first()
            if customer_invoice is None:
                raise Http404
            delivery_id = sint(request.GET.get('delivery', 0))
            if customer.delivery_point is not None:
                qs = DeliveryBoard.objects.filter(
                    Q(
                        id=delivery_id,
                        permanence_id=permanence_id,
                        delivery_point_id=customer.delivery_point_id,
                        # delivery_point__closed_group=True, -> This is always the case
                        # when delivery_point_id == customer.delivery_point_id
                        status=PERMANENCE_OPENED
                    ) | Q(
                        id=delivery_id,
                        permanence_id=permanence_id,
                        delivery_point__closed_group=False,
                        status=PERMANENCE_OPENED
                    )
                ).order_by('?')
            else:
                qs = DeliveryBoard.objects.filter(
                    id=delivery_id,
                    permanence_id=permanence_id,
                    delivery_point__closed_group=False,
                    status=PERMANENCE_OPENED
                ).order_by('?')
            delivery = qs.first()
            if delivery is not None:
                to_json = []
                if (customer_invoice.status == PERMANENCE_OPENED and not customer_invoice.is_order_confirm_send) \
                        or (customer_invoice.total_price_with_tax == DECIMAL_ZERO):
                    customer_invoice.status = PERMANENCE_OPENED
                    customer_invoice.set_delivery(delivery)
                    customer_invoice.save()
                    # IMPORTANT : Set the status of the may be already existing purchase to "Open" so that
                    # the total_price_with_tax will be correctly calculated on the customer order screen.
                    Purchase.objects.filter(customer_invoice=customer_invoice).order_by('?').update(status=PERMANENCE_OPENED)
                basket_message = calc_basket_message(
                    customer, permanence, PERMANENCE_OPENED
                )
                my_order_confirmation(
                    permanence=permanence,
                    customer_invoice=customer_invoice,
                    is_basket=basket,
                    basket_message=basket_message,
                    to_json=to_json
                )
                return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
    raise Http404

