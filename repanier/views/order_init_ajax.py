# -*- coding: utf-8
from __future__ import unicode_literals

import datetime
import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, PERMANENCE_WAIT_FOR_INVOICED, PERMANENCE_OPENED, \
    EMPTY_STRING
from repanier.models.customer import Customer
from repanier.models.permanence import Permanence
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.staff import Staff
from repanier.tools import sboolean, sint, \
        calc_basket_message, permanence_ok_or_404, my_basket


@never_cache
@require_GET
@login_required
def order_init_ajax(request):
    if not request.is_ajax():
        raise Http404
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True
    ).only(
        "id", "vat_id", "short_basket_name", "email2", "delivery_point",
        "balance", "date_balance", "may_order"
    ).order_by('?').first()
    if customer is None:
        raise Http404

    permanence_id = sint(request.GET.get('pe', 0))
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    permanence_ok_or_404(permanence)
    to_json = []
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence.id,
        customer_id=customer.id
    ).order_by('?').first()
    if customer_invoice is None:
        customer_invoice = CustomerInvoice.objects.create(
            permanence_id=permanence.id,
            customer_id=customer.id,
            status=permanence.status,
            customer_charged_id=customer.id,
        )
        customer_invoice.set_delivery(delivery=None)
        customer_invoice.save()

    if customer_invoice is None:
        raise Http404

    basket = sboolean(request.GET.get('ba', False))
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM, \
        REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION
    if customer_invoice.delivery is not None:
        status = customer_invoice.delivery.status
    else:
        status = customer_invoice.status
    if status <= PERMANENCE_OPENED:
        basket_message = calc_basket_message(customer, permanence, status)
    else:
        if customer_invoice.delivery is not None:
            basket_message = EMPTY_STRING
        else:
            basket_message = "%s" % (
                _('The orders are closed.'),
            )
    customer_invoice.my_order_confirmation(
        permanence=permanence,
        is_basket=basket,
        basket_message=basket_message,
        to_json=to_json
    )
    if customer.may_order:
        if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
            for producer_invoice in ProducerInvoice.objects.filter(
                permanence_id=permanence.id
            ).only(
                "total_price_with_tax", "status"
            ).order_by('?'):
                producer_invoice.get_order_json(to_json)
        communication = sboolean(request.GET.get('co', False))
        if communication \
                and customer_invoice.total_price_with_tax == DECIMAL_ZERO \
                and not customer_invoice.is_order_confirm_send:
            now = timezone.now()
            permanence_boards = PermanenceBoard.objects.filter(
                customer_id=customer.id,
                permanence_date__gte=now,
                permanence__status__lte=PERMANENCE_WAIT_FOR_INVOICED
            ).order_by("permanence_date")[:2]
            is_staff = Staff.objects.filter(
                customer_responsible_id=customer.id
            ).order_by('?').exists()
            if (not is_staff and REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION > DECIMAL_ZERO) \
                    or len(permanence_boards) > 0:
                if len(permanence_boards) == 0:
                    count_activity = PermanenceBoard.objects.filter(
                        customer_id=customer.id, permanence_date__lt=now,
                        permanence_date__gte=now - datetime.timedelta(
                            days=float(REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION) * 7
                        )
                    ).count()
                else:
                    count_activity = None
                html = render_to_string(
                    'repanier/communication_permanence_board.html',
                    {'permanence_boards': permanence_boards, 'count_activity': count_activity})
                option_dict = {'id': "#communication", 'html': html}
                to_json.append(option_dict)
    my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(), to_json)
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
