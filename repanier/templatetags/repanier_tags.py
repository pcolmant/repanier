# -*- coding: utf-8 -*-
from django.conf import settings
from django import template
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.utils.formats import number_format

from repanier.const import *
from repanier.tools import *
from repanier.models import OfferItem
from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import PermanenceBoard

register = template.Library()

# <select name="{{ offer_item.id }}">
# <option value="1" selected>1</option>
# </select>

@register.simple_tag(takes_context=True)
def repanier_select_qty(context, *args, **kwargs):
    request = context['request']
    result = "N/A1"
    user = request.user
    # try:
    customer = Customer.objects.filter(
        user_id=user.id, is_active=True, may_order=True).order_by().first()
    if customer:
        # The user is an active customer
        p_offer_item_id = kwargs['offer_item_id']
        offer_item = OfferItem.objects.get(id=p_offer_item_id)
        if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
            # The offer_item belong to a open permanence
            q_order = 0
            q_average_weight = offer_item.product.order_average_weight
            pruchase_set = list(Purchase.objects.filter(product_id=offer_item.product_id,
                                                        permanence_id=offer_item.permanence_id,
                                                        customer_id=customer.id).order_by()[:1])
            if pruchase_set:
                purchase = pruchase_set[0]
                q_order = purchase.quantity if purchase.permanence.status < PERMANENCE_SEND else purchase.quantity_send_to_producer
            # The q_order is either the purchased quantity or 0

            q_min = offer_item.product.customer_minimum_order_quantity
            # do not use offer_item.product.customer_alert_order_quantity
            # but Limit to available qty
            q_alert = offer_item.customer_alert_order_quantity
            q_step = offer_item.product.customer_increment_order_quantity
            # The q_min cannot be 0. In this case try to replace q_min by q_step.
            # In last ressort by q_alert.
            # result = '<select name="value" id="offer_item' + str(offer_item.id) + '" onchange="order_ajax(' + str(offer_item.id) + ')" data-refresh="'+ str(offer_item.limit_to_alert_order_quantity) + '" class="form-control">'
            result = '<select name="value" id="offer_item' + str(offer_item.id) + '" onchange="order_ajax(' + str(
                offer_item.id) + ')" class="form-control">'
            q_order_is_displayed = False
            if q_step <= 0:
                q_step = q_min
            if q_min <= 0:
                q_min = q_step
            if q_min <= 0:
                q_min = q_alert
                q_step = q_alert
            if (q_min <= 0 and offer_item.permanence.status == PERMANENCE_OPENED) or (q_order <= 0):
                q_order_is_displayed = True
                result += '<option value="0" selected>---</option>'
            else:
                q_select_id = 0
                q_valid = q_min
                q_counter = 0  # Limit to avoid too long selection list
                while q_valid <= q_alert and q_counter <= 20 and q_order_is_displayed == False:
                    q_select_id += 1
                    q_counter += 1
                    if q_order <= q_valid:
                        q_order_is_displayed = True
                        qty_display = get_qty_display(
                            q_valid,
                            q_average_weight,
                            offer_item.product.order_unit
                        )
                        result += '<option value="' + str(q_select_id) + '" selected>' + qty_display + '</option>'
                    if q_valid < q_step:
                        # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                        # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                        q_valid = q_step
                    else:
                        # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                        # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                        q_valid = q_valid + q_step
                if q_order_is_displayed == False:
                    # An custom order_qty > q_alert
                    q_select_id = q_select_id + 1
                    qty_display = get_qty_display(
                        q_order,
                        q_average_weight,
                        offer_item.product.order_unit
                    )
                    result += '<option value="' + str(q_select_id) + '" selected>' + qty_display + '</option>'
            result += '</select>'
            if q_order > 0:
                # display it in bold il not null
                result = '<b>' + result + '</b>'
        else:
            result = "N/A4"
    else:
        result = "N/A3"
    # except:
    # 	# user.customer doesn't exist -> the user is not a customer.
    # 	result = "N/A2"
    return result


@register.simple_tag(takes_context=True)
def repanier_select_permanence(context, *args, **kwargs):
    request = context['request']
    result = "N/A1"
    user = request.user
    p_permanence_board_id = kwargs['permanence_board_id']
    if p_permanence_board_id:
        permanence_board = PermanenceBoard.objects.get(id=p_permanence_board_id)
        result = ""
        if permanence_board.customer:
            if permanence_board.customer.user.id == user.id:
                result += "<b><i>"
                result += '<select name="value" id="permanence_board' + str(
                    permanence_board.id) + '" onchange="permanence_board_ajax(' + str(
                    permanence_board.id) + ')" class="form-control">'
                result += '<option value="0">---</option>'
                result += '<option value="1" selected>' + request.user.customer.long_basket_name + '</option>'
                result += '</select>'
                result += "</b></i>"
            else:
                result += '<select name="value" id="permanence_board' + str(
                    permanence_board.id) + '" onchange="permanence_board_ajax(' + str(
                    permanence_board.id) + ')" class="form-control">'
                result += '<option value="0" selected>' + permanence_board.customer.long_basket_name + '</option>'
                result += '</select>'
        else:
            result += "<b><i>"
            result += '<select name="value" id="permanence_board' + str(
                permanence_board.id) + '" onchange="permanence_board_ajax(' + str(
                permanence_board.id) + ')" class="form-control">'
            result += '<option value="0" selected>---</option>'
            result += '<option value="1">' + request.user.customer.long_basket_name + '</option>'
            result += '</select>'
            result += "</b></i>"
    return result

