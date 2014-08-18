# -*- coding: utf-8 -*-
from const import *
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from export_tools import *
from openpyxl.datavalidation import DataValidation, ValidationType, ValidationOperator
from openpyxl.style import Border
from openpyxl.style import NumberFormat
from openpyxl.workbook import Workbook
from repanier.const import *
from repanier.models import OfferItem
from repanier.models import Producer
from repanier.models import Product
from repanier.tools import *


def export(permanence, wb=None):
    ws = None

    if wb == None:
        wb = Workbook()
        ws = wb.get_active_sheet()
    else:
        ws = wb.create_sheet()
    worksheet_setup_landscape_a4(ws, unicode(_("Planned")), unicode(permanence))
    row_num = 0

    if permanence.status == PERMANENCE_PLANNED:

        producers_in_this_permanence = Producer.objects.filter(
            permanence=permanence, is_active=True)

        for product in Product.objects.filter(
                producer__in=producers_in_this_permanence, is_active=True, is_into_offer=True).order_by(
                "producer__short_profile_name",
                "department_for_customer",
                "long_name"):
            row = [
                (unicode(_("Producer")), 15, product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("Department")), 15, product.department_for_customer.short_name, NumberFormat.FORMAT_TEXT,
                 False),
                (unicode(_("Product")), 60, product.long_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("Unit Price")), 10, product.original_unit_price,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
            ]

            if row_num == 0:
                worksheet_set_header(ws, row_num, row)
                row_num += 1

            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num][ROW_VALUE]
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
            if q_step <= 0:
                q_step = q_min
            if q_min <= 0:
                q_min = q_step
            if q_min <= 0:
                q_min = q_alert
                q_step = q_alert
            c = ws.cell(row=row_num, column=col_num)
            c.value = unicode('---')
            ws.column_dimensions[get_column_letter(col_num + 1)].width = 2.3
            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
            col_num += 1
            q_valid = q_min
            q_counter = 0  # Limit to avoid too long selection list
            while q_valid <= q_alert and q_counter <= 20:
                q_counter += 1
                c = ws.cell(row=row_num, column=col_num)
                c.value = get_qty_display(
                    q_valid,
                    product.order_average_weight,
                    product.order_unit
                )
                ws.column_dimensions[get_column_letter(col_num + 1)].width = 15
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

    if permanence.status == PERMANENCE_OPENED:

        for offer_item in OfferItem.objects.filter(permanence_id=permanence.id, is_active=True).order_by(
                'product__producer__short_profile_name',
                'product__department_for_customer',
                'product__long_name'):
            row = [
                (unicode(_("Producer")), 15, offer_item.product.producer.short_profile_name, NumberFormat.FORMAT_TEXT,
                 False),
                (unicode(_("Department")), 15, offer_item.product.department_for_customer.short_name,
                 NumberFormat.FORMAT_TEXT, False),
                (unicode(_("Product")), 60, offer_item.product.long_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("Unit Price")), 10, offer_item.product.original_unit_price,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
            ]

            if row_num == 0:
                worksheet_set_header(ws, row_num, row)
                row_num += 1

            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num][ROW_VALUE]
                c.style.number_format.format_code = row[col_num][ROW_FORMAT]
                if row[col_num][ROW_BOX]:
                    c.style.borders.top.border_style = Border.BORDER_THIN
                    c.style.borders.bottom.border_style = Border.BORDER_THIN
                    c.style.borders.left.border_style = Border.BORDER_THIN
                    c.style.borders.right.border_style = Border.BORDER_THIN
                else:
                    c.style.borders.bottom.border_style = Border.BORDER_HAIR

            col_num = len(row)
            q_min = offer_item.product.customer_minimum_order_quantity
            q_alert = offer_item.product.customer_alert_order_quantity
            q_step = offer_item.product.customer_increment_order_quantity
            # The q_min cannot be 0. In this case try to replace q_min by q_step.
            # In last ressort by q_alert.
            if q_step <= 0:
                q_step = q_min
            if q_min <= 0:
                q_min = q_step
            if q_min <= 0:
                q_min = q_alert
                q_step = q_alert
            c = ws.cell(row=row_num, column=col_num)
            c.value = unicode('---')
            ws.column_dimensions[get_column_letter(col_num + 1)].width = 2.3
            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
            col_num += 1
            q_valid = q_min
            q_counter = 0  # Limit to avoid too long selection list
            while q_valid <= q_alert and q_counter <= 20:
                q_counter += 1
                c = ws.cell(row=row_num, column=col_num)
                c.value = get_qty_display(
                    q_valid,
                    offer_item.product.order_average_weight,
                    offer_item.product.order_unit
                )
                ws.column_dimensions[get_column_letter(col_num + 1)].width = 15
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

    return wb


def admin_export(request, queryset):
    permanence = queryset.first()
    response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = (unicode(_("Preview")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1', errors='ignore')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    wb = export(permanence=permanence, wb=None)
    if wb != None:
        wb.save(response)
    return response