# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.http import HttpResponse
from openpyxl.style import Border
from openpyxl.style import NumberFormat
from openpyxl.workbook import Workbook
from django.contrib.sites.models import Site

from export_tools import *
from repanier.const import *
from repanier.models import Customer
from repanier.models import Permanence
from repanier.models import PermanenceBoard
from repanier.models import Producer
from repanier.models import Purchase
from repanier.models import Staff
from repanier.tools import get_producer_unit
from repanier.tools import get_display


def export(permanence, wb=None):
    translation.activate(settings.LANGUAGES[0][0])
    if wb is None:
        wb = Workbook()
        ws = wb.get_active_sheet()
    else:
        ws = wb.create_sheet()

    # Customer info
    worksheet_setup_portait_a4(ws, unicode(permanence), '')

    header = [
        (unicode(_("Basket")), 20),
        (unicode(_('Family')), 35),
        (unicode(_('Phone1')), 15),
        (unicode(_('Phone2')), 15),
    ]
    row_num = 0
    worksheet_set_header(ws, row_num, header)
    row_num += 1
    customer_set = Customer.objects.filter(
        purchase__permanence_id=permanence.id, represent_this_buyinggroup=False).distinct()
    for customer in customer_set:
        row = [
            customer.short_basket_name,
            customer.long_basket_name,
            customer.phone1,
            customer.phone2
        ]
        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = row[col_num]
            c.style.alignment.wrap_text = True
        row_num += 1
    c = ws.cell(row=row_num, column=1)
    c.value = unicode(_('Permanence Board Member List'))
    c.style.alignment.wrap_text = False
    c.style.font.bold = True
    row_num += 1
    distribution_date_save = None
    next_permanence_set = Permanence.objects.filter(distribution_date__gte=permanence.distribution_date).order_by(
        "distribution_date")[:3]
    for next_permanence in next_permanence_set:
        for permanenceboard in PermanenceBoard.objects.filter(
                permanence_id=next_permanence.id):
            c = permanenceboard.customer
            if c is not None:
                row = [
                    next_permanence.distribution_date,
                    c.long_basket_name,
                    c.phone1,
                    c.phone2,
                    permanenceboard.permanence_role.short_name
                ]
                for col_num in xrange(len(row)):
                    c = ws.cell(row=row_num, column=col_num)
                    c.value = row[col_num]
                    c.style.alignment.wrap_text = False
                    if distribution_date_save != next_permanence.distribution_date:
                        c.style.font.bold = True
                        distribution_date_save = next_permanence.distribution_date
                row_num += 1
    c = ws.cell(row=row_num, column=1)
    c.value = unicode(_('Staff Member List'))
    c.style.alignment.wrap_text = False
    c.style.font.bold = True
    row_num += 1
    for staff in Staff.objects.filter(is_active=True).order_by():
        c = staff.customer_responsible
        if c is not None:
            row = [
                staff.long_name,
                c.long_basket_name,
                c.phone1,
                c.phone2
            ]
            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num]
                c.style.alignment.wrap_text = True
            row_num += 1

    c = ws.cell(row=row_num, column=1)
    c.value = unicode(_('producers'))
    c.style.alignment.wrap_text = False
    c.style.font.bold = True
    row_num += 1
    for producer in Producer.objects.filter(permanence=permanence).order_by("short_profile_name"):
        row = [
            producer.short_profile_name,
            producer.long_profile_name,
            producer.phone1,
            producer.phone2
        ]
        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = row[col_num]
            c.style.alignment.wrap_text = True
        row_num += 1

    if PERMANENCE_WAIT_FOR_SEND <= permanence.status <= PERMANENCE_SEND:
        # Customer label
        ws = wb.create_sheet()
        worksheet_setup_portait_a4(ws, unicode(_('Label')), unicode(permanence))
        row_num = 0
        customer_set = Customer.objects.filter(
            purchase__permanence_id=permanence.id, represent_this_buyinggroup=False).distinct()
        for customer in customer_set:
            c = ws.cell(row=row_num, column=0)
            c.value = customer.short_basket_name
            c.style.font.size = 36
            c.style.alignment.wrap_text = False
            c.style.borders.top.border_style = Border.BORDER_THIN
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            c.style.borders.left.border_style = Border.BORDER_THIN
            c.style.borders.right.border_style = Border.BORDER_THIN
            c.style.alignment.vertical = 'center'
            c.style.alignment.horizontal = 'center'
            row_num += 1
            ws.row_dimensions[row_num].height = 60
        if row_num > 0:
            ws.column_dimensions[get_column_letter(1)].width = 120

    if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
        # Basket check list, by customer
        wb = export_customer(permanence, wb=wb)

    if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
    #     # Order adressed to our producers,
        producer_set = Producer.objects.filter(permanence=permanence).order_by("short_profile_name")
        for producer in producer_set:
            wb = export_producer(permanence=permanence, producer=producer, wb=wb)


    return wb


def export_producer(permanence, producer, wb=None):
    ws = None
    row_num = 0
    current_site_name = Site.objects.get_current().name

    department_for_customer_save = None
    department_for_customer_short_name_save = None
    qty_sum = 0
    long_name_save = None
    unit_price_save = 0
    unit_deposit_save = 0
    row_start_sum_sum = 0
    formula_sum_sum_sum = []
    hide_column_short_basket_name = True
    hide_column_unit_deposit = True
    unit_save = None

    translation.activate(producer.language)
    purchase_set = Purchase.objects.filter(
        permanence_id=permanence.id, producer_id=producer.id,
        order_unit__lte=PRODUCT_ORDER_UNIT_DEPOSIT,
        product__translations__language_code=translation.get_language()
    ).exclude(quantity=0
    ).order_by(
        "department_for_customer__tree_id",
        "department_for_customer__lft",
        "product__translations__long_name",
        "customer__short_basket_name"
    )
    for purchase in purchase_set:

        if ws is None:
            if wb is None:
                wb = Workbook()
                ws = wb.get_active_sheet()
            else:
                ws = wb.create_sheet()
            worksheet_setup_landscape_a4(ws, unicode(producer.short_profile_name) + unicode(_(" by product")),
                                         unicode(permanence))
        if long_name_save != purchase.long_name:
            product_bold = True
            row_start_sum = row_num
            if department_for_customer_save != purchase.department_for_customer_id:
                if department_for_customer_short_name_save is not None:
                    row_num += 1
                    for col_num in xrange(6):
                        c = ws.cell(row=row_num, column=col_num)
                        c.style.borders.bottom.border_style = Border.BORDER_THIN
                        if col_num == 2:
                            c.value = unicode(_("Total Price")) + " " + department_for_customer_short_name_save
                            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
                        if col_num == 5:
                            formula = 'SUM(F%s:F%s)' % (row_start_sum_sum + 3, row_num)
                            c.value = '=' + formula
                            formula_sum_sum_sum.append(formula)
                            c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                            c.style.font.bold = True
                row_start_sum_sum = row_num
                department_for_customer_save = purchase.department_for_customer_id
                if purchase.department_for_customer is not None:
                    department_for_customer_short_name_save = purchase.department_for_customer.short_name
                else:
                    department_for_customer_short_name_save = ""
                if long_name_save is not None:
                    row_num += 1
                    c = ws.cell(row=row_num, column=1)
                else:
                    c = ws.cell(row=1, column=1)
                c.value = department_for_customer_short_name_save
                c.style.font.bold = True

            long_name_save = purchase.long_name
            unit_price_save = purchase.original_unit_price
            unit_deposit_save = purchase.unit_deposit

            if unit_deposit_save != 0:
                hide_column_unit_deposit = False

            if purchase.wrapped:
                short_basket_name = purchase.customer.short_basket_name
                hide_column_short_basket_name = False
            else:
                short_basket_name = current_site_name

            qty_sum = 0
            row_inc = 1
        else:

            product_bold = False

            if unit_deposit_save != 0:
                hide_column_unit_deposit = False

            if purchase.wrapped:
                short_basket_name = purchase.customer.short_basket_name
                hide_column_short_basket_name = False
                qty_sum = 0
                row_inc = 1
            else:
                short_basket_name = current_site_name
                row_inc = 0

        qty = purchase.quantity if permanence.status < PERMANENCE_WAIT_FOR_SEND else purchase.quantity_send_to_producer
        qty_sum += qty
        a_price = (purchase.original_unit_price + purchase.unit_deposit) * qty_sum
        qty_display, price_display, price = get_display(
            qty_sum,
            purchase.order_average_weight,
            purchase.order_unit,
            a_price,
            False
        )
        if unit_save is None:
            unit_save = purchase.order_unit

        row = [
            (unicode(_("Basket")), 20, short_basket_name, NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Quantity")), 10, qty_sum, '#,##0.???', True),
            (unicode(_("Product")), 60, long_name_save + qty_display, NumberFormat.FORMAT_TEXT, product_bold),
            (unicode(_("Unit Price")), 10, unit_price_save, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ',
             False),
            (unicode(_("Deposit")), 10, unit_deposit_save, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ',
             False),
            (unicode(_("Total Price")), 12, a_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ',
             False)
        ]

        if row_num == 0:
            worksheet_set_header(ws, row_num, row)
            row_num += 1

        row_num += row_inc

        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = row[col_num][ROW_VALUE]
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]
            if row[col_num][ROW_BOX]:
                c.style.font.bold = True
            c.style.borders.bottom.border_style = Border.BORDER_THIN

    if ws is not None:
        if hide_column_unit_deposit:
            ws.column_dimensions[get_column_letter(5)].visible = False
        if hide_column_short_basket_name:
            ws.column_dimensions[get_column_letter(1)].visible = False
        row_num += 1
        for col_num in xrange(6):
            c = ws.cell(row=row_num, column=col_num)
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            if col_num == 2:
                if department_for_customer_short_name_save is not None:
                    c.value = unicode(_("Total Price")) + " " + department_for_customer_short_name_save
                else:
                    c.value = unicode(_("Total Price"))
                c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
            if col_num == 5:
                formula = 'SUM(F%s:F%s)' % (row_start_sum_sum + 3, row_num)
                c.value = '=' + formula
                formula_sum_sum_sum.append(formula)
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True
        row_num += 1
        for col_num in xrange(6):
            c = ws.cell(row=row_num, column=col_num)
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            if col_num == 1:
                c.value = unicode(_("Total Price")) + " " + current_site_name
                c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
            if col_num == 5:
                c.value = "=" + "+".join(formula_sum_sum_sum)
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True

    ws = None
    row_num = 0

    department_for_customer_save = None
    basket_save = None
    row_start_sum = 0
    formula_sum_sum = []
    hide_column_unit_deposit = True
    unit_save = None

    purchase_set = Purchase.objects.filter(
        permanence_id=permanence.id, producer_id=producer.id,
        order_unit__lte=PRODUCT_ORDER_UNIT_DEPOSIT,
        product__translations__language_code=translation.get_language()
    ).exclude(quantity=0
    ).order_by(
        "customer__short_basket_name",
        "department_for_customer__tree_id",
        "department_for_customer__lft",
        "product__translations__long_name"
    )
    for purchase in purchase_set:

        if ws is None:
            if wb is None:
                wb = Workbook()
                ws = wb.get_active_sheet()
            else:
                ws = wb.create_sheet()
            worksheet_setup_landscape_a4(ws, unicode(producer.short_profile_name) + unicode(_(" by basket")),
                                         unicode(permanence))

        if basket_save != purchase.customer.short_basket_name:
            basket_bold = True
            if basket_save is not None:
                c = ws.cell(row=row_num, column=2)
                c.value = unicode(_("Total Price")) + " " + basket_save
                c = ws.cell(row=row_num, column=5)
                formula = 'SUM(F%s:F%s)' % (row_start_sum + 2, row_num)
                c.value = '=' + formula
                formula_sum_sum.append(formula)
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True
                row_start_sum = row_num
                row_num += 1
            basket_save = purchase.customer.short_basket_name
        else:
            basket_bold = False

        if purchase.unit_deposit != 0:
            hide_column_unit_deposit = False

        qty = purchase.quantity if permanence.status < PERMANENCE_WAIT_FOR_SEND else purchase.quantity_send_to_producer

        a_price = ( purchase.original_unit_price + purchase.unit_deposit ) * qty
        qty_display, price_display, price = get_display(
            qty,
            purchase.order_average_weight,
            purchase.order_unit,
            0,
            False
        )

        if unit_save is None:
            unit_save = purchase.order_unit

        row = [
            (unicode(_("Basket")), 20, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, basket_bold),
            (unicode(_("Quantity")), 10, qty, '#,##0.???', True),
            (unicode(_("Product")), 60, purchase.long_name + qty_display, NumberFormat.FORMAT_TEXT, True),
            (unicode(_("Unit Price")), 10, purchase.original_unit_price,
             u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
            (unicode(_("Deposit")), 10, purchase.unit_deposit, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ',
             False),
            (unicode(_("Total Price")), 12, a_price, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ',
             False)
        ]

        if row_num == 0:
            worksheet_set_header(ws, row_num, row)
            row_num += 1

        if basket_bold:
            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.style.borders.top.border_style = Border.BORDER_THIN

        if basket_bold or (department_for_customer_save != purchase.department_for_customer):
            department_for_customer_save = purchase.department_for_customer
            if department_for_customer_save is not None:
                c = ws.cell(row=row_num, column=1)
                c.value = department_for_customer_save.short_name
                row_num += 1
                ws.row_dimensions[row_num].visible = False

        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = row[col_num][ROW_VALUE]
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]
            if row[col_num][ROW_BOX]:
                c.style.font.bold = True
            c.style.borders.bottom.border_style = Border.BORDER_THIN

        row_num += 1

    if ws is not None:
        if hide_column_unit_deposit:
            ws.column_dimensions[get_column_letter(5)].visible = False
        c = ws.cell(row=row_num, column=2)
        c.value = unicode(_("Total Price")) + " " + basket_save
        c = ws.cell(row=row_num, column=5)
        formula = 'SUM(F%s:F%s)' % (row_start_sum + 2, row_num)
        c.value = '=' + formula
        formula_sum_sum.append(formula)
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
        c.style.font.bold = True
        row_num += 1
        for col_num in xrange(6):
            c = ws.cell(row=row_num, column=col_num)
            c.style.borders.top.border_style = Border.BORDER_THIN
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            if col_num == 1:
                c.value = unicode(_("Total Price")) + " " + current_site_name
            if col_num == 5:
                c.value = "=" + "+".join(formula_sum_sum)
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True

    return wb


def export_customer(permanence, customer=None, wb=None):

    if customer is not None:
        translation.activate(customer.language)
        purchase_set = Purchase.objects.filter(
            permanence_id=permanence.id, customer_id=customer.id, producer__isnull=False,
            product__translations__language_code=translation.get_language()
        ).order_by(
            "product__placement",
            "product__department_for_customer__tree_id",
            "product__department_for_customer__lft",
            "producer__short_profile_name",
            "product__translations__long_name"
        )
    else:
        purchase_set = Purchase.objects.filter(
            permanence_id=permanence.id, producer__isnull=False,
            product__translations__language_code=translation.get_language()
        ).order_by(
            "customer__short_basket_name",
            "product__placement",
            "product__department_for_customer__tree_id",
            "product__department_for_customer__lft",
            "producer__short_profile_name",
            "product__translations__long_name"
        )

    if wb is None:
        wb = Workbook()
        ws = wb.get_active_sheet()
    else:
        ws = wb.create_sheet()

    # Customer check list
    worksheet_setup_landscape_a4(ws, unicode(_('Customer check')), unicode(permanence))

    row_num = 0
    department_for_customer_save = None
    customer_save = None
    hide_column_placement = True
    placement_save = None
    row_start_sum = None
    order_amount = 0

    for purchase in purchase_set:

        qty = purchase.quantity if permanence.status < PERMANENCE_WAIT_FOR_SEND else purchase.quantity_send_to_producer
        if qty != 0 or purchase.order_unit == PRODUCT_ORDER_UNIT_DEPOSIT:

            if placement_save is not None:
                if placement_save != purchase.product.placement:
                    hide_column_placement = False
            placement_save = purchase.product.placement
            # unit = get_customer_unit(order_unit=purchase.order_unit, qty=qty)
            if purchase.invoiced_price_with_compensation:
                a_price = purchase.product.unit_price_with_compensation
            else:
                a_price = purchase.product.unit_price_with_vat
            qty_display, price_display, price = get_display(
                qty,
                purchase.product.order_average_weight,
                purchase.product.order_unit,
                a_price
            )
            row_price = qty * purchase.unit_deposit + price
            order_amount += row_price

            row = [
                (unicode(_("Placement")), 15,
                 purchase.product.get_placement_display() if purchase.product is not None else "",
                 NumberFormat.FORMAT_TEXT),
                (unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT),
                (unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT),
                (unicode(_("Quantity")), 20, qty_display, NumberFormat.FORMAT_TEXT),
                (unicode(_("Unit Price")), 10, a_price,
                    u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_("deposit")), 10, purchase.unit_deposit,
                    u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_("Total invoiced price, deposit included")), 10, row_price,
                    u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                # (unicode(_("Quantity")), 10, qty, '#,##0.???'),
                # (unicode(_("Unit")), 12, unit, NumberFormat.FORMAT_TEXT),
                (unicode(_("Basket")), 20, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT),
            ]

            if row_num == 0:
                worksheet_set_header(ws, row_num, row)
                row_num += 1

            if customer_save != purchase.customer.id or department_for_customer_save != purchase.department_for_customer:
                if customer_save != purchase.customer.id:
                    if row_start_sum is not None:
                        c = ws.cell(row=row_num, column=5)
                        c.value = unicode(_("Total Price"))
                        c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
                        c.style.font.bold = True
                        c = ws.cell(row=row_num, column=6)
                        if row_start_sum == 1:
                            formula = 'SUM(G%s:G%s)' % (row_start_sum + 1, row_num)
                        else:
                            formula = 'SUM(G%s:G%s)' % (row_start_sum + 3, row_num)
                        c.value = '=' + formula
                        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                        c.style.font.bold = True
                    row_start_sum = row_num
                    # Add an empty line for the scissors.
                    if customer_save is not None:
                        row_num += 2
                c = ws.cell(row=row_num, column=2)
                c.style.borders.bottom.border_style = Border.BORDER_THIN
                c.style.alignment.horizontal = 'right'
                c.style.font.italic = True
                department_for_customer_save = purchase.department_for_customer
                if department_for_customer_save is not None:
                    c.value = department_for_customer_save.short_name
                else:
                    c.value = ""
                if customer_save != purchase.customer.id:
                    for col_num in xrange(len(row)):
                        c = ws.cell(row=row_num, column=col_num)
                        c.style.borders.top.border_style = Border.BORDER_THIN
                        if col_num == 7:
                            c.value = purchase.customer.short_basket_name
                            c.style.font.bold = True
                    # Force the display of the department for next customer
                    customer_save = purchase.customer.id
                else:
                    c = ws.cell(row=row_num, column=7)
                    c.value = purchase.customer.short_basket_name
                row_num += 1

            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num][ROW_VALUE]
                c.style.number_format.format_code = row[col_num][ROW_FORMAT]
                c.style.borders.bottom.border_style = Border.BORDER_HAIR

            row_num += 1

    if row_start_sum is not None:
        c = ws.cell(row=row_num, column=5)
        c.value = unicode(_("Total Price"))
        c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
        c.style.font.bold = True
        c = ws.cell(row=row_num, column=6)
        if row_start_sum == 1:
            formula = 'SUM(G%s:G%s)' % (row_start_sum + 1, row_num)
        else:
            formula = 'SUM(G%s:G%s)' % (row_start_sum + 3, row_num)
        c.value = '=' + formula
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
        c.style.font.bold = True

        if hide_column_placement:
            ws.column_dimensions[get_column_letter(1)].visible = False
    if customer is not None:
        return order_amount, wb
    else:
        return wb


def admin_export(request, queryset):
    permanence = queryset.filter(status__gte=PERMANENCE_OPENED).first()
    response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = (unicode(_("Check")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1', errors='ignore')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    wb = export(permanence=permanence, wb=None)
    if wb is not None:
        wb.save(response)
    return response