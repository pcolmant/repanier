from repanier.models.customer import Customer
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.producer import Producer


def get_header(worksheet):
    header = []
    if worksheet is not None:
        row_num = 0
        col_num = 0
        c = worksheet.cell(row=row_num, column=col_num)
        while (c.value is not None) and (col_num < 50):
            header.append(c.value)
            col_num += 1
            c = worksheet.cell(row=row_num, column=col_num)
    return header


def get_row(worksheet, header, row_num):
    row = {}
    if worksheet is not None:
        # last_row is a row with all cells empty
        last_row = True
        i = 0
        while last_row and i < 10:
            for col_num, col_header in enumerate(header):
                c = worksheet.cell(row=row_num, column=col_num)
                # Important c.value==0 : Python (or Python lib) mix 0 and None
                if c.value is not None or c.value == 0:
                    last_row = False
                row[col_header] = None if c.data_type == c.TYPE_FORMULA else c.value
            row_num += 1
            i += 1
        if last_row:
            row = {}
    return row


def get_customer_2_id_dict():
    customer_2_id_dict = {}
    represent_this_buyinggroup = None
    customer_set = Customer.objects.filter(is_active=True).order_by("?")
    for customer in customer_set:
        customer_2_id_dict[customer.short_basket_name] = customer.id
        if customer.represent_this_buyinggroup:
            represent_this_buyinggroup = customer.id
    return represent_this_buyinggroup, customer_2_id_dict


def get_customer_email_2_id_dict():
    customer_2_id_dict = {}
    customer_set = Customer.objects.filter(is_active=True).order_by("?")
    for customer in customer_set:
        customer_2_id_dict[customer.user.email] = customer.id
    return customer_2_id_dict


def get_producer_2_id_dict():
    producer_2_id_dict = {}
    represent_this_buyinggroup = None
    producer_set = Producer.objects.filter(is_active=True).order_by("?")
    for producer in producer_set:
        producer_2_id_dict[producer.short_profile_name] = producer.id
        if producer.represent_this_buyinggroup:
            represent_this_buyinggroup = producer.id
    return represent_this_buyinggroup, producer_2_id_dict


def get_department_for_customer_2_id_dict():
    department_for_customer_2_id_dict = {}
    department_for_customer_set = LUT_DepartmentForCustomer.objects.filter(
        is_active=True
    ).order_by("?")
    for department_for_customer in department_for_customer_set:
        department_for_customer_2_id_dict[
            department_for_customer.short_name_v2
        ] = department_for_customer.id
    return department_for_customer_2_id_dict
