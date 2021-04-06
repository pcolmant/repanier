from repanier_v2.models.customer import Customer
from repanier_v2.models.lut import LUT_DepartmentForCustomer
from repanier_v2.models.producer import Producer


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
    is_default_id = None
    customer_set = Customer.objects.filter(is_active=True).order_by("?")
    for customer in customer_set:
        customer_2_id_dict[customer.short_name] = customer.id
        if customer.is_default:
            is_default_id = customer.id
    return is_default_id, customer_2_id_dict


def get_customer_email_2_id_dict():
    customer_2_id_dict = {}
    customer_set = Customer.objects.filter(is_active=True).order_by("?")
    for customer in customer_set:
        customer_2_id_dict[customer.user.email] = customer.id
    return customer_2_id_dict


def get_producer_2_id_dict():
    producer_2_id_dict = {}
    is_default_id = None
    producer_set = Producer.objects.filter(is_active=True).order_by("?")
    for producer in producer_set:
        producer_2_id_dict[producer.short_name] = producer.id
        if producer.is_default:
            is_default_id = producer.id
    return is_default_id, producer_2_id_dict


def get_department_2_id_dict():
    department_2_id_dict = {}
    department_set = LUT_DepartmentForCustomer.objects.filter(is_active=True).order_by(
        "?"
    )
    for department in department_set:
        department_2_id_dict[department.short_name] = department.id
    return department_2_id_dict
