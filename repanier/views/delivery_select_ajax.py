# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.deliveryboard import DeliveryBoard
from repanier.tools import sint


@never_cache
@require_GET
@login_required
def delivery_select_ajax(request):
    if not request.is_ajax():
        raise Http404
    # construct a list which will contain all of the data for the response
    user = request.user
    to_json = []
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True) \
        .only("id", "language", "delivery_point").order_by('?').first()
    if customer is not None:
        translation.activate(customer.language)
        permanence_id = sint(request.GET.get('permanence', 0))
        customer_invoice = CustomerInvoice.objects.filter(
            customer_id=customer.id,
            permanence_id=permanence_id,
        ).order_by('?').only("delivery_id", ).first()
        if customer.delivery_point is not None:
            qs = DeliveryBoard.objects.filter(
                Q(
                    permanence_id=permanence_id,
                    delivery_point_id=customer.delivery_point_id,
                ) | Q(
                    permanence_id=permanence_id,
                    delivery_point__closed_group=False
                )
            ).order_by("id")
        else:
            qs = DeliveryBoard.objects.filter(
                permanence_id=permanence_id,
                delivery_point__closed_group=False
            ).order_by("id")
        selected = False
        delivery_counter = 0
        # IMPORTANT : Do not limit to delivery.status=PERMANENCE_OPENED to include potentialy closed
        # delivery already selected by the customer
        for delivery in qs:
            if customer_invoice is not None and delivery.id == customer_invoice.delivery_id:
                option_dict = {'value': delivery.id, 'selected': 'selected',
                               'label': delivery.get_delivery_customer_display()}
                to_json.append(option_dict)
                selected = True
            elif delivery.status == PERMANENCE_OPENED and customer_invoice.status == PERMANENCE_OPENED:
                delivery_counter += 1
                option_dict = {'value': delivery.id, 'selected': '',
                               'label': delivery.get_delivery_customer_display()}
                to_json.append(option_dict)
        if not selected:
            if delivery_counter == 0:
                label = "%s" % _('No delivery point is open for you. You can not place order.')
            else:
                label = "%s" % _('Please, select a delivery point')
            option_dict = {'value': -1, 'selected': 'selected',
                           'label': label}
            to_json.insert(0, option_dict)
    else:
        option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
        to_json.append(option_dict)
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
