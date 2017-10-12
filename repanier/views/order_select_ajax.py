# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.utils import translation
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, PERMANENCE_SEND, LIMIT_ORDER_QTY_ITEM, DECIMAL_ZERO, \
    EMPTY_STRING
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice, CustomerInvoice
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import sint, display_selected_value


@never_cache
@require_GET
@login_required
def order_select_ajax(request):
    if not request.is_ajax():
        raise Http404
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True) \
        .only("id", "vat_id", "language").order_by('?').first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    offer_item_id = sint(request.GET.get('offer_item', 0))
    offer_item = OfferItemWoReceiver.objects.filter(
        id=offer_item_id
    ).order_by('?').first()
    if offer_item is None:
        raise Http404
    to_json = []
    # Select one purchase
    purchase = PurchaseWoReceiver.objects.filter(
        customer_id=customer.id,
        offer_item_id=offer_item_id,
        is_box_content=False
    ).order_by('?').only('quantity_ordered').first()
    producer_invocie = ProducerInvoice.objects.filter(
        permanence_id=offer_item.permanence_id,
        producer_id=offer_item.producer_id,
        status=PERMANENCE_OPENED
    ).order_by('?')
    if producer_invocie.exists():
        # The orders are opened for this producer and this permanence
        if offer_item.is_active:
            # This offer_item may be ordered
            customer_invoice = CustomerInvoice.objects.filter(
                permanence_id=offer_item.permanence_id,
                customer_id=customer.id).only("status").order_by('?').first()
            if customer_invoice is not None:
                status = customer_invoice.status
                if PERMANENCE_OPENED <= status <= PERMANENCE_SEND:
                    a_price = offer_item.customer_unit_price.amount + offer_item.unit_deposit.amount
                    q_min = offer_item.customer_minimum_order_quantity
                    if purchase is not None:
                        q_previous_order = purchase.quantity_ordered
                    else:
                        q_previous_order = DECIMAL_ZERO
                    if status == PERMANENCE_OPENED and offer_item.limit_order_quantity_to_stock:
                        q_alert = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
                        if q_alert < DECIMAL_ZERO:
                            q_alert = DECIMAL_ZERO
                    else:
                        q_alert = offer_item.customer_alert_order_quantity
                    q_step = offer_item.customer_increment_order_quantity
                    q_order_is_displayed = False
                    q_select_id = 0
                    selected = EMPTY_STRING
                    if q_previous_order <= 0:
                        q_order_is_displayed = True
                        selected = "selected"

                    q_valid = q_min
                    if q_valid <= q_alert:
                        if (status == PERMANENCE_OPENED or
                                (status <= PERMANENCE_SEND and selected == "selected")):
                            option_dict = {'value': '0', 'selected': selected, 'label': '---'}
                            to_json.append(option_dict)
                    else:
                        if (status == PERMANENCE_OPENED or
                                (status <= PERMANENCE_SEND and selected == "selected")):
                            sold_out = _("Sold out")
                            option_dict = {'value': '0', 'selected': selected, 'label': sold_out}
                            to_json.append(option_dict)
                    q_counter = 0  # Limit to avoid too long selection list
                    while q_valid <= q_alert and q_counter <= LIMIT_ORDER_QTY_ITEM:
                        q_select_id += 1
                        q_counter += 1
                        selected = EMPTY_STRING
                        if not q_order_is_displayed:
                            if q_previous_order <= q_valid:
                                q_order_is_displayed = True
                                selected = "selected"
                        if (status == PERMANENCE_OPENED or
                                (status <= PERMANENCE_SEND and selected == "selected")):
                            display = offer_item.get_display(
                                qty=q_valid,
                                order_unit=offer_item.order_unit,
                                unit_price_amount=a_price,
                                for_order_select=True
                            )
                            option_dict = {'value': str(q_select_id), 'selected': selected,
                                           'label': display}
                            to_json.append(option_dict)
                        if q_valid < q_step:
                            # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                            # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                            q_valid = q_step
                        else:
                            # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                            # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                            q_valid = q_valid + q_step

                    if not q_order_is_displayed:
                        # An custom order_qty > q_alert
                        q_select_id += 1
                        selected = "selected"
                        display = offer_item.get_display(
                            qty=q_previous_order,
                            order_unit=offer_item.order_unit,
                            unit_price_amount=a_price,
                            for_order_select=True
                        )
                        option_dict = {'value': str(q_select_id), 'selected': selected,
                                       'label': display}
                        to_json.append(option_dict)
                    if status == PERMANENCE_OPENED:
                        # _not_lazy string are not placed in the "django.po"
                        other = _("Other qty")
                        option_dict = {'value': 'other_qty', 'selected': EMPTY_STRING, 'label': other}
                        to_json.append(option_dict)
                else:
                    option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                    to_json.append(option_dict)
            else:
                option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                to_json.append(option_dict)
        else:
            option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
            to_json.append(option_dict)
    else:
        if purchase is not None and purchase.quantity_ordered != DECIMAL_ZERO:
            option_dict = display_selected_value(offer_item, purchase.quantity_ordered, is_open=True)
            to_json.append(option_dict)
        else:
            closed = _("Closed")
            option_dict = {'value': '0', 'selected': 'selected', 'label': '%s' % closed}
            to_json.append(option_dict)

    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
