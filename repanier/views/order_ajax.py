# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO, EMPTY_STRING
from repanier.models.box import BoxContent
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice, CustomerInvoice
from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.purchase import Purchase
from repanier.tools import create_or_update_one_cart_item, sint, sboolean, display_selected_value, \
    calc_basket_message, my_basket, display_selected_box_value


@never_cache
@require_GET
@login_required
def order_ajax(request):
    if not request.is_ajax():
        raise Http404
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True
    ).order_by('?').first()
    if customer is None:
        raise Http404
    offer_item_id = sint(request.GET.get('offer_item', 0))
    value_id = sint(request.GET.get('value', 0))
    is_basket = sboolean(request.GET.get('is_basket', False))
    qs = CustomerInvoice.objects.filter(
        permanence__offeritem=offer_item_id,
        customer_id=customer.id,
        status=PERMANENCE_OPENED).order_by('?')
    to_json = []
    if qs.exists():
        qs = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item_id,
            producer__offeritem=offer_item_id,
            status=PERMANENCE_OPENED
        ).order_by('?')
        if qs.exists():
            from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, \
                REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
            purchase, updated = create_or_update_one_cart_item(
                customer=customer,
                offer_item_id=offer_item_id,
                value_id=value_id,
                is_basket=is_basket,
                batch_job=False
            )
            offer_item = OfferItemWoReceiver.objects.filter(
                id=offer_item_id
            ).order_by('?').first()
            if purchase is None:
                if offer_item.is_box:
                    sold_out = _("Sold out")
                    option_dict = {
                        'id'  : "#offer_item%d" % offer_item.id,
                        'html': '<option value="0" selected>%s</option>' % sold_out
                    }
                else:
                    option_dict = display_selected_value(offer_item, DECIMAL_ZERO, is_open=True)
                to_json.append(option_dict)
            else:
                if offer_item is not None:
                    option_dict = display_selected_value(offer_item, purchase.quantity_ordered, is_open=True)
                    to_json.append(option_dict)
            if updated and offer_item.is_box:
                # update the content
                for content in BoxContent.objects.filter(
                        box=offer_item.product_id
                ).only(
                    "product_id"
                ).order_by('?'):
                    box_offer_item = OfferItem.objects.filter(
                        product_id=content.product_id,
                        permanence_id=offer_item.permanence_id
                    ).order_by('?').first()
                    if box_offer_item is not None:
                        # Select one purchase
                        purchase = Purchase.objects.filter(
                            customer_id=customer.id,
                            offer_item_id=box_offer_item.id,
                            is_box_content=False
                        ).order_by('?').first()
                        option_dict = display_selected_value(
                            box_offer_item,
                            purchase.quantity_ordered if purchase is not None else DECIMAL_ZERO,
                            is_open=True
                        )
                        to_json.append(option_dict)
                        box_purchase = Purchase.objects.filter(
                            customer_id=customer.id,
                            offer_item_id=box_offer_item.id,
                            is_box_content=True
                        ).order_by('?').first()
                        option_dict = display_selected_box_value(box_offer_item, box_purchase)
                        to_json.append(option_dict)


            if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
                producer_invoice = ProducerInvoice.objects.filter(
                    producer_id=offer_item.producer_id, permanence_id=offer_item.permanence_id
                ).only("total_price_with_tax").order_by('?').first()
                producer_invoice.get_order_json(to_json)

            customer_invoice = CustomerInvoice.objects.filter(
                permanence_id=offer_item.permanence_id,
                customer_id=customer.id
            ).order_by('?').first()
            status_changed = customer_invoice.cancel_confirm_order()
            if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS and status_changed:
                html = render_to_string(
                    'repanier/communication_confirm_order.html')
                option_dict = {'id': "#communication", 'html': html}
                to_json.append(option_dict)
            customer_invoice.save()
            my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(),
                      to_json)
            permanence = Permanence.objects.filter(
                id=offer_item.permanence_id
            ).order_by('?').first()

            if is_basket:
                basket_message = calc_basket_message(customer, permanence, PERMANENCE_OPENED)
            else:
                basket_message = EMPTY_STRING
            customer_invoice.my_order_confirmation(
                permanence=permanence,
                is_basket=is_basket,
                basket_message=basket_message,
                to_json=to_json
            )
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
