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
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence
from repanier.tools import sint, get_signature, my_basket, calc_basket_message


@never_cache
@require_GET
@login_required
def btn_confirm_order_ajax(request):
    if not request.is_ajax():
        raise Http404
    permanence_id = sint(request.GET.get('permanence', 0))
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True).order_by('?').first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    if permanence is None:
        raise Http404
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id,
        customer_id=customer.id,
        is_order_confirm_send=False,
        is_group=False,
        # total_price_with_tax__gt=DECIMAL_ZERO
        purchase__quantity_ordered__gt = DECIMAL_ZERO,
    ).order_by('?')
    if not customer_invoice.exists():
        raise Http404
    filename = "{0}-{1}.xlsx".format(
        _("Order"),
        permanence
    )
    sender_email, sender_function, signature, cc_email_staff = get_signature(
        is_reply_to_order_email=True)
    export_order_2_1_customer(
        customer, filename, permanence, sender_email,
        sender_function, signature
    )
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence_id,
        customer_id=customer.id
    ).order_by('?').first()
    customer_invoice.confirm_order()
    customer_invoice.save()
    to_json = []
    my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(), to_json)
    if customer_invoice.delivery is not None:
        status = customer_invoice.delivery.status
    else:
        status = customer_invoice.status
    basket_message = calc_basket_message(
        customer,
        permanence,
        status
    )
    customer_invoice.my_order_confirmation(
        permanence=permanence,
        is_basket=True,
        basket_message=basket_message,
        to_json=to_json
    )
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
