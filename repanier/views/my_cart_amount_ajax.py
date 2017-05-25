# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO
from repanier.email.email_order import export_order_2_1_customer
from repanier.models import Customer, CustomerInvoice, Permanence
from repanier.tools import sint, get_signature, my_basket, my_order_confirmation, calc_basket_message


@never_cache
@require_GET
@login_required
def my_cart_amount_ajax(request, permanence_id):
    if not request.is_ajax():
        raise Http404
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True).order_by('?').first()
    if customer is None:
        raise Http404
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id,
        customer_id=customer.id
    ).order_by('?').first()
    if customer_invoice is None:
        raise Http404
    to_json = []
    my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(), to_json)
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
