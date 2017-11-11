# -*- coding: utf-8

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.tools import sint, sboolean, my_basket


@never_cache
@require_GET
@login_required
def delivery_ajax(request):
    if not request.is_ajax():
        raise Http404
    user = request.user
    permanence_id = sint(request.GET.get('permanence', 0))
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
    to_json = []
    # if (customer_invoice.status == PERMANENCE_OPENED and not customer_invoice.is_order_confirm_send) \
    #         or (customer_invoice.total_price_with_tax == DECIMAL_ZERO):
    #     customer_invoice.status = PERMANENCE_OPENED
    #     customer_invoice.set_delivery(delivery)
    #     customer_invoice.save()
    #     # IMPORTANT : Set the status of the may be already existing purchase to "Open" so that
    #     # the total_price_with_tax will be correctly calculated on the customer order screen.
    #     Purchase.objects.filter(customer_invoice=customer_invoice).order_by('?').update(status=PERMANENCE_OPENED)
    if customer_invoice.status == PERMANENCE_OPENED:
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
                    delivery_point__customer_responsible__isnull=True,
                    status=PERMANENCE_OPENED
                )
            ).order_by('?')
        else:
            qs = DeliveryBoard.objects.filter(
                id=delivery_id,
                permanence_id=permanence_id,
                delivery_point__customer_responsible__isnull=True,
                status=PERMANENCE_OPENED
            ).order_by('?')
        delivery = qs.first()
        if delivery is None:
            raise Http404
        if customer_invoice.delivery != delivery:
            from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS

            if customer_invoice.delivery is not None:
                status_changed = customer_invoice.cancel_confirm_order()
                my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(),
                          to_json)
            else:
                status_changed = False
            customer_invoice.set_delivery(delivery)
            customer_invoice.save()
            if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS and status_changed:
                html = render_to_string(
                    'repanier/communication_confirm_order.html')
                option_dict = {'id': "#communication", 'html': html}
                to_json.append(option_dict)

    is_basket = sboolean(request.GET.get('is_basket', False))
    customer_invoice.my_order_confirmation(
        permanence=permanence,
        is_basket=is_basket,
        to_json=to_json
    )
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")

