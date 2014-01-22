# -*- coding: utf-8 -*-
from django.conf import settings
from django import template
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from repanier.const import *
from repanier.models import OfferItem
from repanier.models import Purchase
from repanier.models import SiteCustomer

register = template.Library()

    # <select name="{{ offer_item.id }}">
    #     <option value="1" selected>1</option>    
    # </select>

@register.simple_tag(takes_context=True)
def repanier_select_qty(context, *args, **kwargs):
	request = context['request']
	result = "N/A1"
	user = request.user
	try:
		site_customer_set = list(SiteCustomer.objects.filter(
			site_id = settings.SITE_ID,
			customer_id = user.customer).active()[:1])
		if site_customer_set:
			site_customer = site_customer_set[0]
			# The user is an active customer of this site
			p_offer_item_id = kwargs['offer_item_id']
			offer_item = OfferItem.objects.get(id=p_offer_item_id)
			if(offer_item.permanence.status == PERMANENCE_OPEN and 
				offer_item.permanence.site_id == settings.SITE_ID):
				# The offer_item belong to a open permanence of this site
				q_order = 0
				pruchase_set = list(Purchase.objects.all().product(
					offer_item.product).permanence(offer_item.permanence).site_customer(
					site_customer)[:1])
				if pruchase_set:
					pruchase = pruchase_set[0]
					q_order = pruchase.order_quantity
				# The q_order is either the purchased quantity or 0
				q_min = offer_item.product.customer_minimum_order_quantity
				q_alert = offer_item.product.customer_alert_order_quantity
				q_step = offer_item.product.customer_increment_order_quantity
				select_id = 0
				if q_order >= q_min:
					q_order = q_order - q_min
					if q_order <= 0:
						select_id = 1
						q_order = 0
					elif q_step > 0:
						select_id = ( q_order / q_step ) + 1
				select_step = 0
				if q_step > 0:
					select_step = ( ( ( q_alert - q_min ) / q_step ) + 1 ) * 3 + 1
					# Why 3 ? why not ? It define the q_max = 3 * q_alert
				result = '<input hidden name="offer_item" value="' + str(offer_item.id) + '"/><select name="value">'
				for i in range(select_step):
					selected = ""
					if i == select_id:
						selected = "selected"
					if i == 0:
						result = result + '<option value="0" '+ selected + '>---</option>'
					else:
						unit = ""
						if offer_item.product.order_by_kg_pay_by_kg:
							unit = _(' kg')
						elif offer_item.product.order_by_piece_pay_by_kg:
							unit = _(' piece = ~ ') + '%.2f' % (offer_item.product.order_average_weight * i) + _(' kg')
						else:
							unit = _(' piece')
						if i == 1:
							result = result + '<option value="1" '+ selected + '>'+str(q_min)+ unit +'</option>'
						else:
							result = result + '<option value="'+ str(i) + '" '+ selected + '>'+str(q_min+(i-1)*q_step) + unit +'</option>'
				result = result + '</select>'
			else:
				result = "N/A4"
		else:
			result = "N/A3"
	except:
		# user.customer doesn't exist -> the user is not a customer.
		result = "N/A2"
	return result