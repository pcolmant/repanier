# -*- coding: utf-8 -*-
from const import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils.formats import number_format

from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import OfferItem
from repanier.models import CustomerOrder

def get_user_order_amount(permanence, user=None):
	order_amount = 0
	if user!= None:
		customer_order_set= CustomerOrder.objects.all().filter(
      permanence = permanence.id,
			customer__user=user.id)[:1]
		if customer_order_set:
			order_amount = customer_order_set[0].order_amount
	return order_amount

def get_order_amount(permanence, customer=None):
  order_amount = 0
  if customer!= None:
    customer_order_set= CustomerOrder.objects.all().filter(
      permanence = permanence.id,
      customer=customer.id)[:1]
    if customer_order_set:
      order_amount = customer_order_set[0].order_amount
  return order_amount

def save_order_amount(permanence_id, customer_id, a_order):
  customer_order_set= CustomerOrder.objects.all().filter(
    permanence = permanence_id,
    customer = customer_id)[:1]
  if customer_order_set:
    customer_order = customer_order_set[0]
    customer_order.order_amount = a_order
    customer_order.save()
  else:
    CustomerOrder.objects.create(
      permanence_id = permanence_id,
      customer_id = customer_id,
      order_amount = a_order
			)
  return a_order

def save_order_delta_amount(permanence_id, customer, a_previous_order, a_order):
  order_amount = 0
  customer_order_set= CustomerOrder.objects.all().filter(
    permanence=permanence_id,
    customer=customer.id)[:1]
  if customer_order_set:
    customer_order = customer_order_set[0]
    customer_order.order_amount += (a_order - a_previous_order)
    order_amount = customer_order.order_amount
    customer_order.save()
  else:
    CustomerOrder.objects.create(
      permanence_id = permanence_id,
      customer_id = customer.id,
      order_amount = a_order
      )
    order_amount = a_order
  return order_amount

def recalculate_order_amount(permanence_id):
  customer_save_id = None
  order_amount = 0
  for purchase in Purchase.objects.filter(
      permanence=permanence_id
    ).exclude(order_quantity=0).order_by('customer'):
    if customer_save_id != purchase.customer.id:
      if customer_save_id != None:
        save_order_amount(permanence_id, customer_save_id, order_amount)
      order_amount = 0
      customer_save_id = purchase.customer.id
    qty = purchase.order_quantity
    if purchase.product.order_by_piece_pay_by_kg:
      order_amount += qty * purchase.product.producer_unit_price * purchase.product.order_average_weight
    else:
      order_amount += qty * purchase.product.producer_unit_price
  if customer_save_id != None:
    save_order_amount(permanence_id, customer_save_id, order_amount)

def find_customer(user=None, customer_id = None):
  customer = None
  try:
    customer_set = None
    if user:
      customer_set = Customer.objects.filter(
        id = user.customer.id).active().may_order().order_by()[:1]
    if customer_id:
      customer_set = Customer.objects.filter(
        id = customer_id).active().may_order().order_by()[:1]
    if customer_set:
      customer = customer_set[0]
  except:
    # user.customer doesn't exist -> the user is not a customer.
    pass
  return customer

def update_or_create_purchase(user=None, p_offer_item_id=None, p_value_id = None, customer_id = None, customer = None):
  result = "ko"
  if p_offer_item_id and p_value_id:
    # try:
    if user or customer_id:
      customer = find_customer(user=user, customer_id=customer_id)
    if customer:
      # The user is an active customer
      offer_item = OfferItem.objects.get(id=p_offer_item_id)
      if offer_item.permanence.status == PERMANENCE_OPENED:
        # The offer_item belong to a open permanence
        q_order = 0
        pruchase_set = Purchase.objects.filter(
          offer_item_id = offer_item.id,
          permanence_id = offer_item.permanence.id,
          customer_id = customer.id).order_by()[:1]
        purchase = None
        # q_previous_order must be set here to None
        q_previous_order = None
        if pruchase_set:
          purchase = pruchase_set[0]
          q_previous_order = purchase.order_quantity
          a_previous_order = purchase.order_amount
        # The q_order is either the purchased quantity or 0
        q_min = offer_item.product.customer_minimum_order_quantity
        q_alert = offer_item.product.customer_alert_order_quantity
        q_step = offer_item.product.customer_increment_order_quantity
        p_value_id = abs(int(p_value_id[0:3]))
        if p_value_id == 0:
          q_order = 0
        elif p_value_id == 1:
          q_order = q_min
        else:
          q_order = q_min + q_step * ( p_value_id - 1 )
        if q_order > q_alert:
          # This occurs if the costomer has personaly asked it -> let it be
          if q_order != q_previous_order:
            q_order = q_previous_order
            result = "not ok"
        if q_previous_order != q_order:
          a_order = 0
          a_previous_order = 0
          if offer_item.product.order_by_piece_pay_by_kg:
            a_order = q_order * offer_item.product.producer_unit_price * offer_item.product.order_average_weight
          else:
            a_order = q_order * offer_item.product.producer_unit_price
          if purchase:
            a_previous_order = purchase.order_amount
            purchase.order_quantity = q_order
            purchase.order_amount = a_order
            purchase.save()
          else:
            purchase = Purchase.objects.create( 
              permanence = offer_item.permanence,
              distribution_date = offer_item.permanence.distribution_date,
              product = offer_item.product,
              offer_item = offer_item,
              producer = offer_item.product.producer,
              customer = customer,
              order_quantity = q_order,
              order_amount = a_order,
              is_to_be_prepared = (offer_item.product.automatically_added == ADD_PORDUCT_MANUALY)
              )

          if result=="ko":
            order_amount = save_order_delta_amount(
              offer_item.permanence.id,
              customer,
              a_previous_order,
              a_order
            )
            if -0.00001 <= order_amount <= 0.00001:
              result = "ok0"
            else:
              result = "ok" + number_format(order_amount, 2)

    # except:
    #   # user.customer doesn't exist -> the user is not a customer.
    #   pass
  return result

def get_qty_display(qty=0, order_average_weight=0, order_by_kg_pay_by_kg=False, order_by_piece_pay_by_kg=False):
  unit = unicode(_(' pieces'))
  magnitude = 1
  if order_by_kg_pay_by_kg:
    if qty < 1:
      unit = unicode(_(' gr'))
      magnitude = 1000
    else:
      unit = unicode(_(' kg'))
  elif order_by_piece_pay_by_kg:
    average_weight = order_average_weight * qty
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
    if qty < 2:
      unit = unicode(_(' piece = ~ ')) + number_format(average_weight, decimal) + average_weight_unit
    else:
      unit = unicode(_(' pieces = ~ ')) + number_format(average_weight, decimal) + average_weight_unit
  else:
    if qty < 2:
      unit = unicode(_(' piece'))
  qty *= magnitude
  decimal = 3
  if qty == int(qty):
    decimal = 0
  elif qty * 10 == int(qty * 10):
    decimal = 1
  elif qty * 100 == int(qty * 100):
    decimal = 2 
  return number_format(qty, decimal) + unit
