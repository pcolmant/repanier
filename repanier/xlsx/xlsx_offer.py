# -*- coding: utf-8

from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.const import PERMANENCE_PLANNED, PERMANENCE_OPENED, LIMIT_ORDER_QTY_ITEM
from repanier.models import ContractContent
from repanier.models.offeritem import OfferItem
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import *
from repanier.xlsx.export_tools import *


def export_offer(permanence, wb=None):
    wb, ws = new_landscape_a4_sheet(wb, permanence, permanence)
    row_num = 0

    if permanence.status == PERMANENCE_PLANNED:
        if permanence.contract is None:
            producers_in_this_permanence = Producer.objects.filter(
                permanence=permanence, is_active=True)

            for product in Product.objects.prefetch_related(
                    "producer", "department_for_customer").filter(
                producer__in=producers_in_this_permanence, is_into_offer=True,
                is_box=False,
                translations__language_code=translation.get_language()).order_by(
                "producer__short_profile_name",
                "department_for_customer",
                "translations__long_name",
                "order_average_weight"):
                row_num = export_offer_row(product, row_num, ws)
            for product in Product.objects.prefetch_related(
                    "producer", "department_for_customer").filter(
                is_into_offer=True,
                is_box=True,
                translations__language_code=translation.get_language()).order_by(
                "customer_unit_price",
                "unit_deposit",
                "translations__long_name"):
                row_num = export_offer_row(product, row_num, ws)
        else:
            for contract_content in ContractContent.objects.prefetch_related(
                    "product", "product__producer", "product__department_for_customer").filter(
                contract=permanence.contract,
                permanences_dates__isnull=False
            ):
                product = contract_content.product
                row_num = export_offer_row(
                    product, row_num, ws,
                    permanences_dates=contract_content.get_permanences_dates,
                    flexible_dates=contract_content.flexible_dates
                )

    elif permanence.status == PERMANENCE_OPENED:
        for offer_item in OfferItem.objects.prefetch_related(
                "producer", "department_for_customer"
        ).filter(
            permanence_id=permanence.id,
            is_active=True,
            product__translations__language_code=translation.get_language()).order_by(
            'translations__order_sort_order',
        ):
            row_num = export_offer_row(
                offer_item, row_num, ws,
                permanences_dates=offer_item.get_permanences_dates
            )

    return wb


def export_offer_row(product, row_num, ws, permanences_dates=EMPTY_STRING, flexible_dates=False):
    row = [
        (_("Producer"), 15, product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
        (_("Department"), 15,
         product.department_for_customer.short_name if product.department_for_customer is not None else EMPTY_STRING,
         NumberFormat.FORMAT_TEXT,
         False),
        (_("Product"), 60, product.get_long_name(), NumberFormat.FORMAT_TEXT, False),
        (_("Producer unit price"), 10,
         product.producer_unit_price if product.producer_unit_price < product.customer_unit_price and not product.is_box else EMPTY_STRING,
         repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX, False),
        (_("Customer unit price"), 10, product.customer_unit_price,
         repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX, False),
        (_("Deposit"), 10, product.unit_deposit,
         repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX, False),
    ]
    if permanences_dates:
        row += [
            (_("Permanences dates"), 60, permanences_dates, NumberFormat.FORMAT_TEXT, False),
            (_("Flexible dates of permanence"), 5, _("Yes") if flexible_dates else _("No"), NumberFormat.FORMAT_TEXT,
             False),
        ]
    if row_num == 0:
        worksheet_set_header(ws, row)
        row_num += 1
    for col_num in range(len(row)):
        c = ws.cell(row=row_num, column=col_num)
        c.value = "{}".format(row[col_num][ROW_VALUE])
        c.style.number_format.format_code = row[col_num][ROW_FORMAT]
        if row[col_num][ROW_BOX]:
            c.style.borders.top.border_style = Border.BORDER_THIN
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            c.style.borders.left.border_style = Border.BORDER_THIN
            c.style.borders.right.border_style = Border.BORDER_THIN
        else:
            c.style.borders.bottom.border_style = Border.BORDER_HAIR
    col_num = len(row)
    q_min = product.customer_minimum_order_quantity
    q_alert = product.customer_alert_order_quantity
    q_step = product.customer_increment_order_quantity
    # The q_min cannot be 0. In this case try to replace q_min by q_step.
    # In last ressort by q_alert.
    c = ws.cell(row=row_num, column=col_num)
    c.value = '---'
    ws.column_dimensions[get_column_letter(col_num + 1)].width = 2.3
    c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
    col_num += 1
    q_valid = q_min
    q_counter = 0  # Limit to avoid too long selection list
    while q_valid <= q_alert and q_counter <= LIMIT_ORDER_QTY_ITEM:
        q_counter += 1
        c = ws.cell(row=row_num, column=col_num)
        c.value = product.get_display(
            qty=q_valid,
            order_unit=product.order_unit,
            unit_price_amount=product.customer_unit_price.amount
        )
        ws.column_dimensions[get_column_letter(col_num + 1)].width = 20
        c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
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
