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

register = template.Library()

    # <select name="{{ offer_item.id }}">
    #     <option value="1" selected>1</option>    
    # </select>

@register.simple_tag(takes_context=True)
def repanier_select_qty(context, *args, **kwargs):
	request = context['request']
	result = "N/A1"
	user = request.user
	# try:
	customer_set = list(Customer.objects.filter(
		user_id = user.id).active()[:1])
	if customer_set:
		customer = customer_set[0]
		# The user is an active customer
		p_offer_item_id = kwargs['offer_item_id']
		offer_item = OfferItem.objects.get(id=p_offer_item_id)
		if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
			# The offer_item belong to a open permanence
			q_order = 0
			q_average_weight = offer_item.product.order_average_weight
			pruchase_set = list(Purchase.objects.all().product(
				offer_item.product).permanence(offer_item.permanence).customer(
				customer)[:1])
			if pruchase_set:
				pruchase = pruchase_set[0]
				if offer_item.permanence.status < PERMANENCE_SEND:
					q_order = pruchase.order_quantity
				else:
					q_order = pruchase.prepared_quantity
					q_average_weight = 1
			# The q_order is either the purchased quantity or 0

			q_min = offer_item.product.customer_minimum_order_quantity
			q_alert = offer_item.product.customer_alert_order_quantity
			q_step = offer_item.product.customer_increment_order_quantity
			# The q_min cannot be 0. In this case try to replace q_min by q_step.
			# In last ressort by q_alert.
			result = '<input hidden name="offer_item" value="' + str(
				offer_item.id
				) + '"/><select name="value" id="offer_item' + str(offer_item.id) + '" onchange="order_ajax(' + str(offer_item.id) + ')" class="form-control">'
			q_order_is_displayed = False
			if q_step <= 0:
				q_step = q_min
			if q_min <= 0:
				q_min = q_step
			if q_min <= 0:
				q_min = q_alert
				q_step = q_alert
			if q_min <= 0 and offer_item.permanence.status == PERMANENCE_OPENED:
				q_order_is_displayed = True
				result += '<option value="0" selected>---</option>'
			else:
				q_select_id = 0
				selected = ""
				if q_order <= 0:
					q_order_is_displayed = True
					selected = "selected"
				if( offer_item.permanence.status == PERMANENCE_OPENED or
					(PERMANENCE_SEND <= offer_item.permanence.status and selected == "selected")):
					result += '<option value="0" '+ selected + '>---</option>'
				q_valid = q_min
				q_counter = 0 # Limit to avoid too long selection list
				while q_valid <= q_alert and q_counter <= 20:
					q_select_id += 1
					q_counter += 1
					selected = ""
					if q_order_is_displayed == False:
						if q_order <= q_valid:
							q_order_is_displayed = True
							selected = "selected"
					if( offer_item.permanence.status == PERMANENCE_OPENED or
						(PERMANENCE_SEND <= offer_item.permanence.status and selected == "selected")):
						qty_display = get_qty_display(
							q_valid,
						 	q_average_weight,
							offer_item.product.order_by_kg_pay_by_kg,
						 	offer_item.product.order_by_piece_pay_by_kg
						)
						result += '<option value="'+ str(q_select_id) + '" '+ selected + '>'+ qty_display +'</option>'
					q_valid = q_valid + q_step
				if q_order_is_displayed == False:
					# An custom order_qty > q_alert
					q_select_id = q_select_id + 1
					selected = "selected"
					qty_display = get_qty_display(
						q_order,
					 	q_average_weight,
						offer_item.product.order_by_kg_pay_by_kg,
					 	offer_item.product.order_by_piece_pay_by_kg
					)
					result += '<option value="'+ str(q_select_id) + '" '+ selected + '>'+ qty_display +'</option>'
			result += '</select>'
		else:
			result = "N/A4"
	else:
		result = "N/A3"
	# except:
	# 	# user.customer doesn't exist -> the user is not a customer.
	# 	result = "N/A2"
	return result