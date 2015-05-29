# -*- coding: utf-8 -*-
from django import template
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

# from repanier.tools import *
# from repanier.models import OfferItem
from repanier.models import PermanenceBoard
import uuid

register = template.Library()

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
                result += "</i></b>"
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
            result += "</i></b>"
    return result
