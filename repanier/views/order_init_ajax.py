# -*- coding: utf-8
from __future__ import unicode_literals

import datetime
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, PERMANENCE_WAIT_FOR_DONE, PERMANENCE_OPENED, DECIMAL_ONE, \
    PERMANENCE_CLOSED, REPANIER_MONEY_ZERO, EMPTY_STRING
from repanier.models import Customer, Permanence, CustomerInvoice, PermanenceBoard, Staff, OfferItem, \
    ProducerInvoice, Purchase
from repanier.tools import sboolean, sint, display_selected_value, \
    display_selected_box_value, my_basket, my_order_confirmation, calc_basket_message


@never_cache
@require_GET
def order_init_ajax(request):
    if request.is_ajax():
        # construct a list which will contain all of the data for the response
        permanence_id = sint(request.GET.get('pe', 0))
        permanence_qs = Permanence.objects.filter(id=permanence_id) \
            .only("id", "status", "with_delivery_point").order_by('?')
        if not permanence_qs.exists():
            raise Http404
        user = request.user
        to_json = []
        if user.is_authenticated():
            permanence = permanence_qs.prefetch_related("producers").first()
            customer = Customer.objects.filter(
                user_id=user.id, is_active=True
            ).only(
                "id", "vat_id", "short_basket_name", "email2", "delivery_point",
                "balance", "date_balance", "may_order"
            ).order_by('?').first()
            if customer is None:
                my_basket(False, REPANIER_MONEY_ZERO, to_json)
            else:
                customer_invoice = CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    customer_id=customer.id
                ).order_by('?').first()
                if customer_invoice is None:
                    customer_invoice = CustomerInvoice.objects.create(
                        permanence_id=permanence.id,
                        customer_id=customer.id,
                        status=permanence.status,
                        customer_who_pays_id=customer.id,
                    )
                    customer_invoice.set_delivery(delivery=None)
                    customer_invoice.save()
                if customer_invoice is None:
                    raise Http404
                my_basket(customer_invoice.is_order_confirm_send, customer_invoice.get_total_price_with_tax(), to_json)
                if customer.balance.amount < 0:
                    my_balance = _('My balance : <font color="red">%(balance)s</font> at %(date)s') % {
                        'balance': customer.balance,
                        'date'   : customer.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                else:
                    my_balance = _('My balance : <font color="green">%(balance)s</font> at %(date)s') % {
                        'balance': customer.balance,
                        'date'   : customer.date_balance.strftime(settings.DJANGO_SETTINGS_DATE)}
                option_dict = {'id': "#my_balance", 'html': my_balance}
                to_json.append(option_dict)
                basket = sboolean(request.GET.get('ba', False))
                from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, \
                    REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM, \
                    REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION
                if basket or (REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
                              and customer_invoice.is_order_confirm_send):
                    if customer_invoice.status <= PERMANENCE_OPENED:
                        basket_message = calc_basket_message(customer, permanence, customer_invoice.status)
                    else:
                        if customer_invoice.delivery is not None:
                            basket_message = EMPTY_STRING
                        else:
                            basket_message = "%s" % (
                                _('The orders are closed.'),
                            )
                    my_order_confirmation(
                        permanence=permanence,
                        customer_invoice=customer_invoice,
                        is_basket=basket,
                        basket_message=basket_message,
                        to_json=to_json
                    )
                else:
                    if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                        my_order_confirmation(
                            permanence=permanence,
                            customer_invoice=customer_invoice,
                            is_basket=basket,
                            to_json=to_json
                        )
                if customer.may_order:
                    if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
                        for producer in permanence.producers.all():
                            producer_invoice = ProducerInvoice.objects.filter(
                                producer_id=producer.id, permanence_id=permanence.id
                            ).only(
                                "total_price_with_tax", "status"
                            ).order_by('?').first()
                            if producer_invoice is None:
                                producer_invoice = ProducerInvoice.objects.create(
                                    permanence_id=permanence.id,
                                    producer_id=producer.id,
                                    status=permanence.status
                                )
                            if producer.minimum_order_value.amount > DECIMAL_ZERO:
                                if producer_invoice is None:
                                    ratio = 0
                                else:
                                    ratio = producer_invoice.total_price_with_tax.amount / producer.minimum_order_value.amount
                                    if ratio >= DECIMAL_ONE:
                                        ratio = 100
                                    else:
                                        ratio *= 100
                                option_dict = {'id'  : "#order_procent%d" % producer.id,
                                               'html': "%s%%" % number_format(ratio, 0)}
                                to_json.append(option_dict)
                            if producer_invoice.status != PERMANENCE_OPENED:
                                option_dict = {'id'  : "#order_closed%d" % producer.id,
                                               'html': '&nbsp;<span class="glyphicon glyphicon-ban-circle" aria-hidden="true"></span>'}
                                to_json.append(option_dict)
                    communication = sboolean(request.GET.get('co', False))
                    if communication \
                            and customer_invoice.total_price_with_tax == DECIMAL_ZERO \
                            and not customer_invoice.is_order_confirm_send:
                        now = timezone.now()
                        permanence_boards = PermanenceBoard.objects.filter(
                            customer_id=customer.id, permanence_date__gte=now,
                            permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
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
                                'repanier/communication.html',
                                {'permanence_boards': permanence_boards, 'count_activity': count_activity})
                            option_dict = {'id': "#communication", 'html': html}
                            to_json.append(option_dict)
                else:
                    option_dict = {'id': "#may_not_order", 'html': '1'}
                    to_json.append(option_dict)
        else:
            customer = None
            my_basket(False, REPANIER_MONEY_ZERO, to_json)
        request_offer_items = request.GET.getlist('oi')
        for request_offer_item in request_offer_items:
            offer_item_id = sint(request_offer_item)
            if user.is_authenticated() and customer is not None:
                # No need to check customer.may_order.
                # Select one purchase
                purchase = Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item_id,
                    is_box_content=False
                ).select_related(
                    "offer_item"
                ).order_by('?').first()
                if purchase is not None:
                    offer_item = purchase.offer_item
                    if offer_item is not None:
                        option_dict = display_selected_value(
                            offer_item,
                            purchase.quantity_ordered)
                        to_json.append(option_dict)
                else:
                    offer_item = OfferItem.objects.filter(
                        id=offer_item_id
                    ).order_by('?').first()
                    if offer_item is not None:
                        option_dict = display_selected_value(
                            offer_item,
                            DECIMAL_ZERO)
                        to_json.append(option_dict)
                box_purchase = Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=offer_item_id,
                    is_box_content=True
                ).select_related(
                    "offer_item"
                ).order_by('?').first()
                if box_purchase is not None:
                    offer_item = box_purchase.offer_item
                    if offer_item is not None:
                        option_dict = display_selected_box_value(customer, offer_item, box_purchase)
                        to_json.append(option_dict)
                option_dict = {'id': ".btn_like%s" % offer_item_id, 'html': offer_item.get_like(user)}
                to_json.append(option_dict)
            else:
                option_dict = {'id'  : "#offer_item%s" % offer_item_id,
                               'html': '<option value="0" selected>---</option>'}
                to_json.append(option_dict)
                msg_html = '<span class="glyphicon glyphicon-heart-empty"></span>'
                option_dict = {'id': ".btn_like%s" % offer_item_id, 'html': msg_html}
                to_json.append(option_dict)
    else:
        raise Http404
    return HttpResponse(json.dumps(to_json, cls=DjangoJSONEncoder), content_type="application/json")
