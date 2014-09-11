# -*- coding: utf-8 -*-
from django import template
from django.utils.translation import ugettext_lazy as _

from repanier.tools import *
from repanier.models import OfferItem
from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import PermanenceBoard
import uuid

register = template.Library()

# <select name="{{ offer_item.id }}">
# <option value="1" selected>1</option>
# </select>

# @register.simple_tag(takes_context=True)
# def repanier_select_qty(context, *args, **kwargs):
#     request = context['request']
#     result = "N/A1"
#     user = request.user
#     # try:
#     customer = Customer.objects.filter(
#         user_id=user.id, is_active=True, may_order=True).order_by().first()
#     if customer:
#         # The user is an active customer
#         p_offer_item_id = kwargs['offer_item_id']
#         offer_item = OfferItem.objects.get(id=p_offer_item_id)
#         if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
#             # The offer_item belong to a open permanence
#             q_order = 0
#             if offer_item.product.vat_level in [VAT_200, VAT_300] and customer.vat_id is not None and len(
#                 customer.vat_id) > 0:
#                 a_price = offer_item.product.unit_price_with_compensation
#             else:
#                 a_price = offer_item.product.unit_price_with_vat
#             q_average_weight = offer_item.product.order_average_weight
#             # result = '<select name="value" id="offer_item' + str(offer_item.id) + '" onchange="order_ajax(' + str(
#             #     offer_item.id) + ')" class="form-control">'
#             purchase = Purchase.objects.filter(product_id=offer_item.product_id,
#                                                         permanence_id=offer_item.permanence_id,
#                                                         customer_id=customer.id).order_by().first()
#             if purchase:
#                 q_order = purchase.quantity if purchase.permanence.status < PERMANENCE_SEND else purchase.quantity_send_to_producer
#             if q_order<=0:
#                 result = '<option value="0" selected>---</option>'
#             else:
#                 qty_display = get_qty_display(
#                     q_order,
#                     q_average_weight,
#                     offer_item.product.order_unit,
#                     a_price
#                 )
#                 result = '<option value="' + str(q_order) + '" selected>' + qty_display + '</option>'
#             # result += '</select>'
#         else:
#             result = "N/A4"
#     else:
#         result = "N/A3"
#     # except:
#     # # user.customer doesn't exist -> the user is not a customer.
#     # result = "N/A2"
#     return result

@register.simple_tag(takes_context=False)
def repanier_uuid(*args, **kwargs):
    return uuid.uuid4()

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

@register.simple_tag(takes_context=False)
def repanier_product_content_unit(*args, **kwargs):
    result = ""
    p_offer_item_id = kwargs['offer_item_id']
    offer_item = OfferItem.objects.get(id=p_offer_item_id)
    order_unit = offer_item.product.order_unit
    if order_unit in [PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_KG]:
        average_weight = offer_item.product.order_average_weight
        if average_weight < 1:
            average_weight_unit = unicode(_(' gr'))
            average_weight *= 1000
        else:
            average_weight_unit = unicode(_(' kg'))
        decimal = 3
        if average_weight == int(average_weight):
            decimal = 0
        elif average_weight * 10 == int(average_weight * 10):
            decimal = 1
        elif average_weight * 100 == int(average_weight * 100):
            decimal = 2
        tilde = ''
        if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            tilde = '~'
        result = ' (' + tilde + number_format(average_weight, decimal) + average_weight_unit + ')'
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
        average_weight = offer_item.product.order_average_weight
        if average_weight < 1:
            average_weight_unit = unicode(_(' cl'))
            average_weight *= 100
        else:
            average_weight_unit = unicode(_(' l'))
        decimal = 3
        if average_weight == int(average_weight):
            decimal = 0
        elif average_weight * 10 == int(average_weight * 10):
            decimal = 1
        elif average_weight * 100 == int(average_weight * 100):
            decimal = 2
        result = ' (' + number_format(average_weight, decimal) + average_weight_unit + ')'
    elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
        average_weight = offer_item.product.order_average_weight
        if average_weight > 2:
            result = ' (' + number_format(average_weight, 0) + unicode(_(' pcs')) + ')'
    return result
