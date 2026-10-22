from django.utils.translation import gettext_lazy as _
from openpyxl.styles.numbers import FORMAT_TEXT

import repanier.apps
from repanier.const import DECIMAL_ZERO
from repanier.const import LIMIT_ORDER_QTY_ITEM, SaleStatus, EMPTY_STRING
from repanier.models.offeritem import OfferItem
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.xlsx.export_tools import *


def export_offer(permanence, wb=None):
    wb, ws = new_landscape_a4_sheet(wb, permanence, permanence)
    row_num = 0

    if permanence.status == SaleStatus.PLANNED.value:
        producers_in_this_permanence = Producer.objects.filter(
            permanence=permanence, is_active=True
        )

        for product in (
            Product.objects.prefetch_related("producer", "department_for_customer")
            .filter(
                producer__in=producers_in_this_permanence,
                is_into_offer=True,
            )
            .order_by(
                "producer__short_profile_name",
                "department_for_customer",
                "long_name_v2",
                "order_average_weight",
            )
        ):
            row_num = export_offer_row(product, row_num, ws)
        # for product in (
        #     Product.objects.prefetch_related("producer", "department_for_customer")
        #     .filter(is_into_offer=True)
        #     .order_by("customer_unit_price", "unit_deposit", "long_name_v2")
        # ):
        #     row_num = export_offer_row(product, row_num, ws)

    elif permanence.status == SaleStatus.OPENED.value:
        for offer_item in (
            OfferItem.objects.prefetch_related("producer", "department_for_customer")
            .filter(
                permanence_id=permanence.id,
                is_active=True,
            )
            .order_by(
                "order_sort_order_v2",
            )
        ):
            row_num = export_offer_row(offer_item, row_num, ws)

    return wb


def export_offer_row(product, row_num, ws):
    row = [
        (
            _("Producer"),
            15,
            product.producer.short_profile_name,
            FORMAT_TEXT,
        ),
        (
            _("Department"),
            15,
            product.department_for_customer.short_name_v2
            if product.department_for_customer is not None
            else EMPTY_STRING,
            FORMAT_TEXT,
        ),
        (
            _("Product"),
            60,
            product.get_long_name_with_customer_price(),
            FORMAT_TEXT,
        ),
        (
            _("Producer unit price"),
            10,
            product.producer_unit_price.amount
            if product.producer_unit_price < product.customer_unit_price
            else DECIMAL_ZERO,
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX,
        ),
        (
            _("Customer unit price"),
            10,
            product.customer_unit_price.amount,
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX,
        ),
        (
            _("Deposit"),
            10,
            product.unit_deposit.amount,
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX,
        ),
    ]
    if row_num == 0:
        worksheet_set_header(ws, row)
        row_num += 1
    for col_num in range(len(row)):
        c = ws.cell(row=row_num + 1, column=col_num +1)
        c.value = row[col_num][ROW_VALUE]
        c.number_format = row[col_num][ROW_FORMAT]
    col_num = len(row)
    q_min = product.customer_minimum_order_quantity
    q_alert = product.get_q_alert()
    q_step = product.customer_increment_order_quantity
    # The q_min cannot be 0. In this case try to replace q_min by q_step.
    # In last ressort by q_alert.
    c = ws.cell(row=row_num + 1, column=col_num)
    c.value = "---"
    ws.column_dimensions[get_column_letter(col_num + 1)].width = 2.3
    c.number_format = FORMAT_TEXT
    col_num += 1
    q_valid = q_min
    q_counter = 0  # Limit to avoid too long selection list
    while q_valid <= q_alert and q_counter <= LIMIT_ORDER_QTY_ITEM:
        q_counter += 1
        c = ws.cell(row=row_num +1, column=col_num+1)
        c.value = product.get_display(
            qty=q_valid,
            order_unit=product.order_unit,
            unit_price_amount=product.customer_unit_price.amount,
        )
        ws.column_dimensions[get_column_letter(col_num + 1)].width = 20
        c.number_format = FORMAT_TEXT
        col_num += 1
        if q_valid < q_step:
            # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
            # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
            q_valid = q_step
        else:
            # 1; 2; 3; 4 ... q_min = 1; q_step = 1
            # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
            q_valid = q_valid + q_step
    row_num += 1
    return row_num
