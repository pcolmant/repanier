# -*- coding: utf-8 -*-
from const import *
from django.utils.translation import ugettext_lazy as _
from repanier.models import Customer
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_ProductionMode
from repanier.models import Producer


def get_header(worksheet):
    header = []
    if worksheet:
        row_num = 0
        col_num = 0
        c = worksheet.cell(row=row_num, column=col_num)
        while (c.value != None ) and (col_num < 50):
            header.append(c.value)
            col_num += 1
            c = worksheet.cell(row=row_num, column=col_num)
    return header


def get_row(worksheet, header, row_num):
    row = {}
    if worksheet:
        # last_row is a row with all cells empty
        last_row = True
        for col_num, col_header in enumerate(header):
            c = worksheet.cell(row=row_num, column=col_num)
            # Important c.value==0 : Python (or Python lib) mix 0 and None
            if c.value or c.value == 0:
                last_row = False
            row[col_header] = None if c.data_type == c.TYPE_FORMULA else c.value
        if last_row:
            row = {}
    return row


def get_customer_2_id_dict():
    customer_2_id_dict = {}
    represent_this_buyinggroup = None
    customer_set = Customer.objects.filter(is_active=True).order_by()
    for customer in customer_set:
        customer_2_id_dict[customer.short_basket_name] = customer.id
        if customer.represent_this_buyinggroup:
            represent_this_buyinggroup = customer.id
    return represent_this_buyinggroup, customer_2_id_dict


def get_customer_2_vat_id_dict():
    id_2_customer_vat_id_dict = {}
    customer_set = Customer.objects.filter(is_active=True).order_by()
    for customer in customer_set:
        id_2_customer_vat_id_dict[customer.id] = None if customer.vat_id == None or len(
            customer.vat_id) <= 0 else customer.vat_id
    return id_2_customer_vat_id_dict


def get_producer_2_id_dict():
    producer_2_id_dict = {}
    represent_this_buyinggroup = None
    producer_set = Producer.objects.filter(is_active=True).order_by()
    for producer in producer_set:
        producer_2_id_dict[producer.short_profile_name] = producer.id
        if producer.represent_this_buyinggroup:
            represent_this_buyinggroup = producer.id
    return represent_this_buyinggroup, producer_2_id_dict


def get_id_2_producer_vat_level_dict():
    id_2_producer_vat_level_dict = {}
    producer_set = Producer.objects.filter(is_active=True).order_by()
    for producer in producer_set:
        id_2_producer_vat_level_dict[producer.id] = producer.vat_level
    return id_2_producer_vat_level_dict


def get_id_2_producer_price_list_multiplier_dict():
    id_2_producer_price_list_multiplier_dict = {}
    producer_set = Producer.objects.filter(is_active=True).order_by()
    for producer in producer_set:
        id_2_producer_price_list_multiplier_dict[producer.id] = producer.price_list_multiplier
    return id_2_producer_price_list_multiplier_dict


def get_department_for_customer_2_id_dict():
    department_for_customer_2_id_dict = {}
    department_for_customer_set = LUT_DepartmentForCustomer.objects.filter(is_active=True).order_by()
    for department_for_customer in department_for_customer_set:
        department_for_customer_2_id_dict[department_for_customer.short_name] = department_for_customer.id
    return department_for_customer_2_id_dict


def get_production_mode_2_id_dict():
    production_mode_2_id_dict = {}
    production_mode_set = LUT_ProductionMode.objects.filter(is_active=True).order_by()
    for production_mode in production_mode_set:
        production_mode_2_id_dict[production_mode.short_name] = production_mode.id
    return production_mode_2_id_dict


