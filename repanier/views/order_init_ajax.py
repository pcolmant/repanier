# -*- coding: utf-8

import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, PERMANENCE_WAIT_FOR_INVOICED, PERMANENCE_OPENED, \
    EMPTY_STRING
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard
from repanier.tools import sboolean, sint, \
    permanence_ok_or_404, my_basket, get_html_basket_message, get_repanier_template_name


@never_cache
@require_GET
@login_required
def order_init_ajax(request):
    if not request.is_ajax():
        raise Http404
    permanence_id = sint(request.GET.get('pe', 0))
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    permanence_ok_or_404(permanence)
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, may_order=True
    ).only(
        "id", "vat_id", "short_basket_name", "email2", "delivery_point",
        "balance", "date_balance", "may_order"
    ).order_by('?').first()
    if customer is None:
        raise Http404
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
        customer_invoice.set_order_delivery(delivery=None)
        customer_invoice.calculate_order_price()
        customer_invoice.save()

    if customer_invoice is None:
        raise Http404

    basket = sboolean(request.GET.get('ba', False))

    if customer_invoice.delivery is not None:
        status = customer_invoice.delivery.status
    else:
        status = customer_invoice.status
    if status <= PERMANENCE_OPENED:
        basket_message = get_html_basket_message(customer, permanence, status)
    else:
        if customer_invoice.delivery is not None:
            basket_message = EMPTY_STRING
        else:
            basket_message = "{}".format(
                _('The orders are closed.')
            )
    if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
        json_dict = customer_invoice.get_html_my_order_confirmation(
            permanence=permanence,
            is_basket=basket,
            basket_message=basket_message
        )
    else:
        json_dict = {}
    if customer.may_order:
        if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
            for producer_invoice in ProducerInvoice.objects.filter(
                    permanence_id=permanence.id
            ).only(
                "total_price_with_tax", "status"
            ).order_by('?'):
                json_dict.update(producer_invoice.get_order_json())
        communication = sboolean(request.GET.get('co', False))
        if communication:
            now = timezone.now()
            permanence_boards = PermanenceBoard.objects.filter(
                customer_id=customer.id,
                permanence_date__gte=now,
                permanence__status__lte=PERMANENCE_WAIT_FOR_INVOICED
            ).order_by("permanence_date")[:2]
            from repanier.apps import REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION
            if REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION > DECIMAL_ZERO or len(permanence_boards) > 0:
                if len(permanence_boards) == 0:
                    count_activity = PermanenceBoard.objects.filter(
                        customer_id=customer.id, permanence_date__lt=now,
                        permanence_date__gte=now - datetime.timedelta(
                            days=float(REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION) * 7
                        )
                    ).count()
                else:
                    count_activity = None
                template_name = get_repanier_template_name("communication_permanence_board.html")
                html = render_to_string(
                    template_name,
                    {'permanence_boards': permanence_boards, 'count_activity': count_activity}
                )
                json_dict["#communicationModal"] = mark_safe(html)
    json_dict.update(my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax()))
    return JsonResponse(json_dict)
