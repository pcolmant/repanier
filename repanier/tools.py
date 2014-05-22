# -*- coding: utf-8 -*-
from const import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils.formats import number_format

from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import Producer
from repanier.models import OfferItem
from repanier.models import CustomerOrder
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_ProductionMode

LENGTH_BY_PREFIX = [
  (0xC0, 2), # first byte mask, total codepoint length
  (0xE0, 3), 
  (0xF0, 4),
  (0xF8, 5),
  (0xFC, 6),
]

def codepoint_length(first_byte):
    if first_byte < 128:
        return 1 # ASCII
    for mask, length in LENGTH_BY_PREFIX:
        if first_byte & 0xF0 == mask:
          return length
        elif first_byte & 0xF8 == 0xF8:
          return length
    assert False, 'Invalid byte %r' % first_byte

def cap_to_bytes_length(unicode_text, byte_limit):
    utf8_bytes = unicode_text.encode('UTF-8', 'replace')
    cut_index = 0
    previous_cut_index = cut_index
    while cut_index < len(utf8_bytes):
        step = codepoint_length(ord(utf8_bytes[cut_index]))
        if cut_index + step > byte_limit:
            # can't go a whole codepoint further, time to cut
            return utf8_bytes[:cut_index] + '...'
        else:
            previous_cut_index = cut_index
            previuos_step = step
            cprevious = utf8_bytes[cut_index]
            cut_index += step
            # ccurrent = utf8_bytes[cut_index]
    # length limit is longer than our bytes strung, so no cutting
    return utf8_bytes

def cap(s, l):
  if s != None:
    if not isinstance(s, basestring):
      s = str(s)
    if isinstance(s, unicode):
      s = cap_to_bytes_length(s, l - 4)
    else:
      s = s if len(s)<=l else s[0:l-4]+'...'
    return s
  else:
    return None

def get_unit(order_unit=PRODUCT_ORDER_UNIT_LOOSE_PC, qty=0):
  unit = None
  if order_unit in [PRODUCT_ORDER_UNIT_LOOSE_KG, PRODUCT_ORDER_UNIT_NAMED_KG]:
    unit = unicode(_("/ Kg"))
  elif order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC_KG, PRODUCT_ORDER_UNIT_NAMED_PC_KG]:
    if qty < 2:
      unit = unicode(_("/ piece -> Kg"))
    else:
      unit = unicode(_("/ pieces -> Kg"))
  else:
    if qty < 2:
      unit = unicode(_("/ piece"))
    else:
      unit = unicode(_("/ pieces"))
  return unit

def get_producer_unit(order_unit=PRODUCT_ORDER_UNIT_LOOSE_PC, qty=0):
  # Used when producing the orders send to the producers.
  unit = None
  if order_unit in [PRODUCT_ORDER_UNIT_LOOSE_KG, PRODUCT_ORDER_UNIT_NAMED_KG]:
    unit = unicode(_("/ Kg"))
  else:
    if qty < 2:
      unit = unicode(_("/ piece"))
    else:
      unit = unicode(_("/ pieces"))
  return unit

def get_user_order_amount(permanence, user=None):
  a_total_price_with_tax = 0
  if user!= None:
    customer_order_set= CustomerOrder.objects.all().filter(
      permanence = permanence.id,
      customer__user=user.id)[:1]
    if customer_order_set:
      a_total_price_with_tax = customer_order_set[0].total_price_with_tax
  return number_format(a_total_price_with_tax, 2)

def get_order_amount(permanence, customer=None):
  a_total_price_with_tax = 0
  if customer!= None:
    customer_order_set= CustomerOrder.objects.all().filter(
      permanence = permanence.id,
      customer=customer.id)[:1]
    if customer_order_set:
      a_total_price_with_tax = customer_order_set[0].total_price_with_tax
  return  number_format(a_total_price_with_tax, 2)

def save_order_amount(permanence_id, customer_id, a_total_price_with_tax):
  customer_order_set= CustomerOrder.objects.all().filter(
    permanence = permanence_id,
    customer = customer_id)[:1]
  if customer_order_set:
    customer_order = customer_order_set[0]
    customer_order.total_price_with_tax = a_total_price_with_tax
    customer_order.save(update_fields=[
      'total_price_with_tax' 
    ])
  else:
    CustomerOrder.objects.create(
      permanence_id = permanence_id,
      customer_id = customer_id,
      total_price_with_tax = a_total_price_with_tax
    )

def save_order_delta_amount(permanence_id, customer_id, 
              a_previous_total_price_with_tax,
              a_total_price_with_tax):
  a_new_total_price_with_tax = 0
  customer_order_set= CustomerOrder.objects.all().filter(
    permanence=permanence_id,
    customer=customer_id)[:1]
  if customer_order_set:
    customer_order = customer_order_set[0]
    customer_order.total_price_with_tax += (a_total_price_with_tax - a_previous_total_price_with_tax)
    a_new_total_price_with_tax = customer_order.total_price_with_tax
    customer_order.save(update_fields=[
      'total_price_with_tax'
      ])
  else:
    CustomerOrder.objects.create(
      permanence_id = permanence_id,
      customer_id = customer_id,
      total_price_with_tax = a_total_price_with_tax
    )
    a_new_total_price_with_tax = a_total_price_with_tax
  return a_new_total_price_with_tax

def recalculate_order_amount(permanence_id, send_to_producer=False):
  customer_save_id = None
  a_total_price_with_tax = 0
  for purchase in Purchase.objects.all().permanence(permanence_id).order_by('customer'):
    if customer_save_id != purchase.customer.id:
      if customer_save_id != None:
        save_order_amount(permanence_id, customer_save_id,a_total_price_with_tax)
      a_total_price_with_tax = 0
      customer_save_id = purchase.customer.id
    purchase.original_unit_price = purchase.product.original_unit_price
    purchase.original_price = purchase.quantity * purchase.original_unit_price
    purchase.producer = purchase.product.producer
    purchase.long_name = purchase.product.long_name
    purchase.department_for_customer = purchase.product.department_for_customer
    purchase.order_unit = purchase.product.order_unit
    purchase.price_with_vat = purchase.quantity * purchase.product.unit_price_with_vat
    purchase.price_with_compensation = purchase.quantity * purchase.product.unit_price_with_compensation
    purchase.invoiced_price_with_compensation = False
    if purchase.product.vat_level in [VAT_200, VAT_300] and purchase.customer.vat_id != None and len(purchase.customer.vat_id) > 0:
      purchase.invoiced_price_with_compensation = True
    if purchase.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC_KG, PRODUCT_ORDER_UNIT_NAMED_PC_KG]:
      purchase.original_price *= purchase.product.order_average_weight
      purchase.price_with_vat *= purchase.product.order_average_weight
      purchase.price_with_compensation *= purchase.product.order_average_weight
    # RoundUp
    purchase.original_price = purchase.original_price.quantize(Decimal('.01'), rounding=ROUND_UP)
    purchase.price_with_vat = purchase.price_with_vat.quantize(Decimal('.01'), rounding=ROUND_UP)
    purchase.price_with_compensation = purchase.price_with_compensation.quantize(Decimal('.01'), rounding=ROUND_UP)
    purchase.unit_deposit = purchase.product.unit_deposit
    if purchase.unit_deposit != 0:
      purchase.original_price += ( purchase.quantity * purchase.unit_deposit )
      purchase.price_with_vat += ( purchase.quantity * purchase.unit_deposit )
      purchase.price_with_compensation += ( purchase.quantity * purchase.unit_deposit )
    purchase.vat_level = purchase.product.vat_level
    purchase.quantity_for_preparation_order = purchase.quantity if purchase.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_KG] else 0
    if send_to_producer:
      purchase.quantity_send_to_producer = purchase.quantity
    purchase.save()
    if purchase.invoiced_price_with_compensation:
      a_total_price_with_tax += purchase.price_with_compensation
    else:
      a_total_price_with_tax += purchase.price_with_vat

  if customer_save_id != None:
    save_order_amount(permanence_id, customer_save_id,a_total_price_with_tax)

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

def update_or_create_purchase(user=None, customer=None, p_offer_item_id=None, p_value_id = None, close_orders=False):
  result = "ko"
  if p_offer_item_id and p_value_id:
    # try:
    if user:
      customer = find_customer(user=user)
    if customer:
      # The user is an active customer
      offer_item = OfferItem.objects.get(id=p_offer_item_id)
      # The close_orders flag is used because we need to forbid 
      # customers to add purchases during the close_orders_async process
      # when the status is PERMANENCE_WAIT_FOR_SEND
      if (offer_item.permanence.status == PERMANENCE_OPENED) or close_orders:
        # The offer_item belong to a open permanence
        q_order = 0
        pruchase_set = Purchase.objects.filter(
          offer_item_id = offer_item.id,
          permanence_id = offer_item.permanence.id,
          customer_id = customer.id).order_by()[:1]
        purchase = None
        # q_previous_order must be set here to None
        q_previous_order = None
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
          if q_min < q_step:
            # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
            # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
            if  p_value_id == 2:
              q_order = q_step
            else:
              q_order = q_step * ( p_value_id - 1 )
          else:
            # 1; 2; 3; 4 ... q_min = 1; q_step = 1
            # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
            q_order = q_min + q_step * ( p_value_id - 1 )
        if q_order > q_alert:
          # This occurs if the costomer has personaly asked it -> let it be
          if q_order != q_previous_order:
            q_order = q_previous_order
            result = "not ok"
        if q_previous_order != q_order:
          a_previous_total_price_with_tax = 0
          if pruchase_set:
            purchase = pruchase_set[0]
            if purchase.invoiced_price_with_compensation:
              a_previous_total_price_with_tax = purchase.price_with_compensation
            else:
              a_previous_total_price_with_tax = purchase.price_with_vat
          a_original_unit_price = offer_item.product.original_unit_price
          a_unit_deposit = offer_item.product.unit_deposit
          a_original_price =q_order * a_original_unit_price
          a_price_with_vat = q_order * offer_item.product.unit_price_with_vat
          a_price_with_compensation = q_order * offer_item.product.unit_price_with_compensation
          is_compensation = False
          if offer_item.product.vat_level in [VAT_200, VAT_300] and customer.vat_id != None and len(customer.vat_id) > 0:
            is_compensation = True
          if offer_item.product.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC_KG, PRODUCT_ORDER_UNIT_NAMED_PC_KG]:
            a_original_price *= offer_item.product.order_average_weight
            a_price_with_vat *= offer_item.product.order_average_weight
            a_price_with_compensation *= offer_item.product.order_average_weight
          a_original_price += ( q_order * a_unit_deposit )
          a_price_with_vat += ( q_order * a_unit_deposit )
          a_price_with_compensation += ( q_order * a_unit_deposit )
          if purchase:
            purchase.quantity = q_order
            purchase.original_unit_price = a_original_unit_price
            purchase.unit_deposit = a_unit_deposit
            purchase.original_price = a_original_price
            purchase.price_with_vat = a_price_with_vat
            purchase.price_with_compensation = a_price_with_compensation
            purchase.invoiced_price_with_compensation = is_compensation
            purchase.vat_level = offer_item.product.vat_level
            purchase.order_unit = offer_item.product.order_unit
            purchase.save(update_fields=[
              'quantity',
              'order_unit',
              'original_unit_price',
              'unit_deposit',
              'original_price',
              'price_with_vat',
              'price_with_compensation',
              'invoiced_price_with_compensation',
              'vat_level'
            ])
          else:
            purchase = Purchase.objects.create( 
              permanence = offer_item.permanence,
              distribution_date = offer_item.permanence.distribution_date,
              product = offer_item.product,
              department_for_customer = offer_item.product.department_for_customer,
              offer_item = offer_item,
              producer = offer_item.product.producer,
              customer = customer,
              quantity = q_order,
              long_name = offer_item.product.long_name,
              order_unit = offer_item.product.order_unit,
              original_unit_price = a_original_unit_price,
              unit_deposit = a_unit_deposit,
              original_price = a_original_price,
              price_with_vat = a_price_with_vat,
              price_with_compensation = a_price_with_compensation,
              invoiced_price_with_compensation = is_compensation,
              vat_level = offer_item.product.vat_level
              )
          if result=="ko":
            if purchase.invoiced_price_with_compensation:
              order_amount = save_order_delta_amount(
                offer_item.permanence.id,
                customer.id,
                a_previous_total_price_with_tax,
                purchase.price_with_compensation
              )
            else:
              order_amount = save_order_delta_amount(
                offer_item.permanence.id,
                customer.id,
                a_previous_total_price_with_tax,
                purchase.price_with_vat
              )

            if -0.00001 <= order_amount <= 0.00001:
              result = "ok0"
            else:
              result = "ok" + number_format(order_amount, 2)

    # except:
    #   # user.customer doesn't exist -> the user is not a customer.
    #   pass
  return result

def get_qty_display(qty=0, order_average_weight=0, order_unit=PRODUCT_ORDER_UNIT_LOOSE_PC):
  unit = unicode(_(' pieces'))
  magnitude = 1
  if order_unit in [PRODUCT_ORDER_UNIT_LOOSE_KG, PRODUCT_ORDER_UNIT_NAMED_KG]:
    if qty < 1:
      unit = unicode(_(' gr'))
      magnitude = 1000
    else:
      unit = unicode(_(' kg'))
  elif order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC_KG, PRODUCT_ORDER_UNIT_NAMED_PC_KG]:
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
      unit = unicode(_(' piece')) + ' (' + number_format(average_weight, decimal) + average_weight_unit + ')'
      # unit = unicode(_(' piece = ~ ')) + number_format(average_weight, decimal) + average_weight_unit
    else:
      unit = unicode(_(' pieces')) + ' (' + number_format(average_weight, decimal) + average_weight_unit + ')'
      # unit = unicode(_(' pieces = ~ ')) + number_format(average_weight, decimal) + average_weight_unit
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

def get_customer_2_id_dict():
  customer_2_id_dict={}
  represent_this_buyinggroup = None
  customer_set = Customer.objects.all().active().order_by()
  for customer in customer_set:
    customer_2_id_dict[customer.short_basket_name]=customer.id
    if customer.represent_this_buyinggroup:
      represent_this_buyinggroup = customer.id
  return represent_this_buyinggroup, customer_2_id_dict

def get_id_2_customer_dict():
  id_2_customer_dict={}
  customer_set = Customer.objects.all().active().order_by()
  for customer in customer_set:
    id_2_customer_dict[customer.id]=customer.short_basket_name
  return id_2_customer_dict

def get_customer_2_vat_id_dict():
  id_2_customer_vat_id_dict={}
  customer_set = Customer.objects.all().active().order_by()
  for customer in customer_set:
    id_2_customer_vat_id_dict[customer.id]=None if customer.vat_id == None or len(customer.vat_id) <= 0 else customer.vat_id
  return id_2_customer_vat_id_dict

def get_producer_2_id_dict():
  producer_2_id_dict={}
  represent_this_buyinggroup = None
  producer_set = Producer.objects.all().active().order_by()
  for producer in producer_set:
    producer_2_id_dict[producer.short_profile_name]=producer.id
    if producer.represent_this_buyinggroup:
      represent_this_buyinggroup = producer.id
  return represent_this_buyinggroup, producer_2_id_dict

def get_id_2_producer_dict():
  id_2_producer_dict={}
  producer_set = Producer.objects.all().active().order_by()
  for producer in producer_set:
    id_2_producer_dict[producer.id]=producer.short_profile_name
  return id_2_producer_dict

def get_id_2_producer_vat_level_dict():
  id_2_producer_vat_level_dict={}
  producer_set = Producer.objects.all().active().order_by()
  for producer in producer_set:
    id_2_producer_vat_level_dict[producer.id]=producer.vat_level
  return id_2_producer_vat_level_dict


def get_id_2_producer_price_list_multiplier_dict():
  id_2_producer_price_list_multiplier_dict={}
  producer_set = Producer.objects.all().active().order_by()
  for producer in producer_set:
    id_2_producer_price_list_multiplier_dict[producer.id]=producer.price_list_multiplier
  return id_2_producer_price_list_multiplier_dict

def get_department_for_customer_2_id_dict():
  department_for_customer_2_id_dict={}
  department_for_customer_set = LUT_DepartmentForCustomer.objects.all().active().order_by()
  for department_for_customer in department_for_customer_set:
    department_for_customer_2_id_dict[department_for_customer.short_name]=department_for_customer.id
  return department_for_customer_2_id_dict

def get_id_2_department_for_customer_dict():
  id_2_department_for_customer_dict={}
  department_for_customer_set = LUT_DepartmentForCustomer.objects.all().active().order_by()
  for department_for_customer in department_for_customer_set:
    id_2_department_for_customer_dict[department_for_customer.id]=department_for_customer.short_name
  return id_2_department_for_customer_dict

def get_production_mode_2_id_dict():
  production_mode_2_id_dict={}
  production_mode_set = LUT_ProductionMode.objects.all().active().order_by()
  for production_mode in production_mode_set:
    production_mode_2_id_dict[production_mode.short_name]=production_mode.id
  return production_mode_2_id_dict

def get_id_2_production_mode_dict():
  id_2_production_mode_dict={}
  production_mode_set = LUT_ProductionMode.objects.all().active().order_by()
  for production_mode in production_mode_set:
    id_2_production_mode_dict[production_mode.id]=production_mode.short_name
  return id_2_production_mode_dict