# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.datavalidation import DataValidation, ValidationType
from openpyxl.style import Border
from openpyxl.style import Fill
from openpyxl.style import NumberFormat
from openpyxl.workbook import Workbook
from django.contrib.sites.models import Site

from export_tools import *
from import_tools import *
from repanier.const import *
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import Producer
from repanier.models import Purchase
from repanier.models import Customer
from repanier.tools import cap
from views import import_xslx_view


def export(permanence, wb=None):
    if wb is None:
        wb = Workbook()
        ws = wb.get_active_sheet()
    else:
        ws = wb.create_sheet()

    yellowFill = Fill()
    yellowFill.start_color.index = 'FFEEEE11'
    yellowFill.end_color.index = 'FFEEEE11'
    yellowFill.fill_type = Fill.FILL_SOLID

    last_permanence_name = worksheet_setup_landscape_a4(ws, unicode(permanence), unicode(_('invoices')))
    producer_valid_values = []
    customer_valid_values = []

    row_num = 0

    producer_set = Producer.objects.filter(is_active=True)
    for producer in producer_set:

        if producer.invoice_by_basket:
            purchase_set = Purchase.objects.filter(
                permanence_id=permanence.id,
                producer_id=producer.id
            ).order_by(
                "customer__short_basket_name",  # "product__placement",
                "department_for_customer",
                "long_name"
            )
        else:
            # Using quantity_for_preparation_order the order is by customer__short_basket_name if the product
            # is to be distributed by piece, otherwise by lower qty first.
            purchase_set = Purchase.objects.filter(
                permanence_id=permanence.id,
                producer_id=producer.id
            ).order_by(  # "product__placement",
                         "department_for_customer",
                         "long_name",
                         "quantity_for_preparation_order",
                         "customer__short_basket_name"
            )

        sum_on = None
        sum_counter = 0
        sum_original_price = 0
        sum_quantity = 0

        for purchase in purchase_set:
            customer_short_basket_name = purchase.customer.short_basket_name
            producer_short_profile_name = purchase.producer.short_profile_name
            product_long_name = purchase.long_name
            if producer_short_profile_name not in producer_valid_values:
                producer_valid_values.append(producer_short_profile_name)
            if customer_short_basket_name not in customer_valid_values:
                customer_valid_values.append(customer_short_basket_name)

            if producer.invoice_by_basket:
                if sum_on != customer_short_basket_name:
                    if sum_on is not None:
                        if sum_counter > 1:
                            c = ws.cell(row=row_num - 1, column=8)
                            c.value = sum_original_price
                            c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                            ws.conditional_formatting.addCellIs(get_column_letter(9) + str(row_num), 'notEqual',
                                                                [get_column_letter(1) + str(row_num + 1)], True, wb,
                                                                None, None, yellowFill)
                            c.style.font.bold = True
                        else:
                            c = ws.cell(row=row_num - 1, column=7)
                            c.style.font.bold = True
                        c = ws.cell(row=row_num, column=0)
                        c.value = sum_original_price
                        c = ws.cell(row=row_num - 1, column=1)
                        c.style.font.bold = True
                        c = ws.cell(row=row_num - 1, column=4)
                        c.style.font.bold = True
                        for col_num in xrange(12):
                            c = ws.cell(row=row_num - 1, column=col_num)
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                        row_num += 1
                        ws.row_dimensions[row_num].visible = False
                    sum_on = customer_short_basket_name
                    sum_original_price = 0
                    sum_quantity = 0
                    sum_counter = 0
            else:
                if sum_on != product_long_name:
                    if sum_on is not None:
                        if sum_counter > 1:
                            c = ws.cell(row=row_num - 1, column=8)
                            # c.value = sum_quantity
                            c.value = sum_original_price
                            # c.style.number_format.format_code = '#,##0.????'
                            c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                            ws.conditional_formatting.addCellIs(get_column_letter(9) + str(row_num), 'notEqual',
                                                                [get_column_letter(1) + str(row_num + 1)], True, wb,
                                                                None, None, yellowFill)
                            c.style.font.bold = True
                        else:
                            c = ws.cell(row=row_num - 1, column=7)
                            c.style.font.bold = True
                        c = ws.cell(row=row_num, column=0)
                        # c.value = sum_quantity
                        c.value = sum_original_price
                        c = ws.cell(row=row_num - 1, column=1)
                        c.style.font.bold = True
                        c = ws.cell(row=row_num - 1, column=3)
                        c.style.font.bold = True
                        for col_num in xrange(12):
                            c = ws.cell(row=row_num - 1, column=col_num)
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                        row_num += 1
                        ws.row_dimensions[row_num].visible = False
                    sum_on = product_long_name
                    sum_original_price = 0
                    sum_quantity = 0
                    sum_counter = 0
                else:
                    if purchase.wrapped:
                        # Don't display the sum_quantity of wrapped products
                        sum_counter = 0
                        c = ws.cell(row=row_num - 1, column=7)
                        c.style.font.bold = True

            sum_original_price += purchase.original_price
            sum_quantity += purchase.quantity
            sum_counter += 1

            row = [
                (unicode(_("Id")), 10, purchase.id, '#,##0', False),
                (unicode(_("producer")), 15, producer_short_profile_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("Department")), 15,
                 "" if purchase.department_for_customer is None else purchase.department_for_customer.short_name,
                 NumberFormat.FORMAT_TEXT, False),
                (unicode(_("product")), 60, product_long_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("customer")), 15, customer_short_basket_name, NumberFormat.FORMAT_TEXT, False),
                (unicode(_("quantity")), 10, purchase.quantity, '#,##0.????',
                 True if purchase.order_unit == PRODUCT_ORDER_UNIT_PC_KG else False),
                (unicode(_("original unit price")), 10, purchase.original_unit_price,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
                (unicode(_("original row price")), 10, purchase.original_price,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
                (unicode(_("invoiced without deposit")), 10, "", NumberFormat.FORMAT_TEXT, False),
                (unicode(_("invoiced deposit")), 10, purchase.quantity_deposit * purchase.unit_deposit,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
                (unicode(_("comment")), 30, cap(purchase.comment, 100), NumberFormat.FORMAT_TEXT, False),
                (unicode(_("vat or compensation")), 10, purchase.get_vat_level_display(), NumberFormat.FORMAT_TEXT,
                 False),
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
                    if c.style.borders.bottom.border_style != Border.BORDER_THIN:
                        c.style.borders.bottom.border_style = Border.BORDER_HAIR
                if col_num in [0, 5, 6, 7, 9]:
                    ws.conditional_formatting.addCellIs(get_column_letter(col_num + 1) + str(row_num + 1), 'notEqual',
                                                        [str(row[col_num][ROW_VALUE])], True, wb, None, None,
                                                        yellowFill)
            row_num += 1
        if sum_on is not None:
            c = ws.cell(row=row_num - 1, column=8)
            if producer.invoice_by_basket:
                if sum_counter > 1:
                    c.value = sum_original_price
                    c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                    c.style.font.bold = True
                    ws.conditional_formatting.addCellIs(get_column_letter(9) + str(row_num), 'notEqual',
                                                        [get_column_letter(1) + str(row_num + 1)], True, wb, None, None,
                                                        yellowFill)
                else:
                    c = ws.cell(row=row_num - 1, column=7)
                    c.style.font.bold = True
                c = ws.cell(row=row_num, column=0)
                c.value = sum_original_price
                c = ws.cell(row=row_num - 1, column=1)
                c.style.font.bold = True
                c = ws.cell(row=row_num - 1, column=4)
                c.style.font.bold = True
            else:
                if sum_counter > 1:
                    # c.value = sum_quantity
                    c.value = sum_original_price
                    # c.style.number_format.format_code = '#,##0.????'
                    c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                    c.style.font.bold = True
                    ws.conditional_formatting.addCellIs(get_column_letter(9) + str(row_num), 'notEqual',
                                                        [get_column_letter(1) + str(row_num + 1)], True, wb, None, None,
                                                        yellowFill)
                else:
                    c = ws.cell(row=row_num - 1, column=7)
                    c.style.font.bold = True
                c = ws.cell(row=row_num, column=0)
                # c.value = sum_quantity
                c.value = sum_original_price
                c = ws.cell(row=row_num - 1, column=1)
                c.style.font.bold = True
                c = ws.cell(row=row_num - 1, column=3)
                c.style.font.bold = True
            for col_num in xrange(12):
                c = ws.cell(row=row_num - 1, column=col_num)
                c.style.borders.bottom.border_style = Border.BORDER_THIN
            row_num += 1

    # Data validation Producer
    # List of Producer
    valid_values = []
    producer_set = Producer.objects.filter(is_active=True).order_by()
    for producer in producer_set:
        valid_values.append(producer.short_profile_name)
    valid_values.sort()
    dv = DataValidation(ValidationType.LIST, formula1=get_validation_formula(wb=wb, valid_values=valid_values),
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.ranges.append('B2:B5000')
    # Data validation Departement for customer
    # list of Departement for customer
    valid_values = []
    department_for_customer_set = LUT_DepartmentForCustomer.objects.filter(is_active=True).order_by()
    for department_for_customer in department_for_customer_set:
        valid_values.append(department_for_customer.short_name)
    valid_values.sort()
    dv = DataValidation(ValidationType.LIST, formula1=get_validation_formula(wb=wb, valid_values=valid_values),
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.ranges.append('C2:C5000')
    # Data validation Customer
    # list of Customer
    valid_values = []
    customer_set = Customer.objects.filter(is_active=True).order_by()
    for customer in customer_set:
        valid_values.append(customer.short_basket_name)
    valid_values.sort()
    dv = DataValidation(ValidationType.LIST, formula1=get_validation_formula(wb=wb, valid_values=valid_values),
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.ranges.append('E2:E5000')
    # Data validation Vat or Compensation
    # List of Vat or Compensation
    valid_values = []
    for record in LUT_VAT:
        valid_values.append(unicode(record[1]))
    dv = DataValidation(ValidationType.LIST, formula1=get_validation_formula(wb=wb, valid_values=valid_values),
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.ranges.append('L2:L5000')
    # End of data validation

    # use a new ws if needed for another permanence
    ws = None

    ws = wb.create_sheet()
    worksheet_setup_landscape_a4(ws, unicode(_('Account summary')), unicode(permanence))
    row_num = 0

    row = [
        (unicode(_("Who")), 15, u"", NumberFormat.FORMAT_TEXT),
        (unicode(_("Bank_amount_in")), 12, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
        (unicode(_("Bank_amount_out")), 12, u"", u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
        (unicode(_("Operation_comment")), 60, u"", NumberFormat.FORMAT_TEXT),
    ]

    worksheet_set_header(ws, row_num, row)
    row_num += 1

    current_site_name = Site.objects.get_current().name
    producer_valid_values.sort()
    for v in producer_valid_values:
        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            if col_num == 0:
                c.value = v
            if col_num == 2:
                c.value = "=SUMIF('" + last_permanence_name + "'!$B$2:$B$5000,A" + str(
                    row_num + 1) + ",'" + last_permanence_name + "'!$H$2:$H$5000)"
            if col_num == 3:
                c.value = unicode(
                    _('Delivery')) + " " + current_site_name + " - " + last_permanence_name + ". " + unicode(
                    _('Thanks!'))
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]

        row_num += 1

    customer_valid_values.sort()
    for v in customer_valid_values:
        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            if col_num == 0:
                c.value = v
            if col_num == 1:
                c.value = "=SUMIF('" + last_permanence_name + "'!$E$2:$E$5000,A" + str(
                    row_num + 1) + ",'" + last_permanence_name + "'!$H$2:$H$5000)"
            if col_num == 3:
                c.value = unicode(_('Delivery')) + " - " + last_permanence_name + "."
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]

        row_num += 1
    wb.worksheets.reverse()
    return wb


def admin_export(request, queryset):
    permanence = queryset.first()
    response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = (unicode(_("invoices")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1',
                                                                                              errors='ignore')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    wb = export(permanence=permanence, wb=None)
    if wb is not None:
        wb.save(response)
    return response


def import_purchase_sheet(worksheet, permanence=None, db_write=False,
                          customer_2_id_dict=None,
                          id_2_customer_vat_id_dict=None,
                          producer_2_id_dict=None,
                          id_2_producer_price_list_multiplier_dict=None
):
    vat_level_dict = dict(LUT_VAT_REVERSE)
    error = False
    error_msg = None
    header = get_header(worksheet)
    if header:
        row_num = 1
        array_purchase = []
        new_invoiced = None
        row = get_row(worksheet, header, row_num)
        while row and not error:
            # print(str(row[_('Id')]))
            try:
                if row[_('producer')] is None and row[_('product')] is None and row[_('customer')] is None:
                    if db_write:
                        max_purchase_counter = len(array_purchase)
                        if max_purchase_counter > 1:
                            producer_id = None
                            actual_invoice = DECIMAL_ZERO
                            for i, purchase in enumerate(array_purchase):
                                if i == 0:
                                    producer_id = purchase.producer_id
                                actual_invoice += purchase.original_price

                            if new_invoiced is not None:
                                ratio = DECIMAL_ONE
                                # print "Ratio", ratio
                                if actual_invoice != DECIMAL_ZERO:
                                    ratio = new_invoiced / actual_invoice
                                else:
                                    if new_invoiced == DECIMAL_ZERO:
                                        ratio = DECIMAL_ZERO
                                    else:
                                        ratio = DECIMAL_ONE
                                # print "Ratio", ratio, "new_invoiced", new_invoiced, "actual_invoice", actual_invoice
                                # Rule of 3
                                if ratio != DECIMAL_ONE:
                                    adjusted_invoice = 0
                                    for i, purchase in enumerate(array_purchase, start=1):
                                        if i == max_purchase_counter:
                                            purchase.original_price = new_invoiced - adjusted_invoice
                                            if purchase.original_unit_price != DECIMAL_ZERO:
                                                purchase.quantity = purchase.original_price / purchase.original_unit_price
                                        else:
                                            purchase.original_price *= ratio
                                            purchase.original_price = purchase.original_price.quantize(TWO_DECIMALS)
                                            adjusted_invoice += purchase.original_price
                                            if purchase.original_unit_price != DECIMAL_ZERO:
                                                purchase.quantity = purchase.original_price / purchase.original_unit_price
                        # Adjust tax and save updated purchase
                        price_list_multiplier = 1
                        if producer_id in id_2_producer_price_list_multiplier_dict:
                            price_list_multiplier = id_2_producer_price_list_multiplier_dict[producer_id]
                        for purchase in array_purchase:
                            original_price = purchase.original_price
                            if price_list_multiplier != 1:
                                original_price = (original_price * price_list_multiplier).quantize(TWO_DECIMALS)
                            purchase.price_with_compensation = purchase.price_with_vat = original_price
                            if purchase.vat_level == VAT_200:
                                purchase.price_with_compensation *= DECIMAL_1_02
                            elif purchase.vat_level == VAT_300:
                                purchase.price_with_compensation *= DECIMAL_1_06
                            # RoundUp
                            purchase.price_with_vat = purchase.price_with_vat.quantize(TWO_DECIMALS)
                            purchase.price_with_compensation = purchase.price_with_compensation.quantize(TWO_DECIMALS)
                            purchase.invoiced_price_with_compensation = False
                            if (purchase.vat_level in [VAT_200, VAT_300]) and (
                                        id_2_customer_vat_id_dict[purchase.customer_id] is not None):
                                purchase.invoiced_price_with_compensation = True
                            purchase.save()

                    array_purchase = []
                    new_invoiced = None
                else:
                    if row[_('Id')] is None:
                        error = True
                        error_msg = _("Row %(row_num)d : No purchase id given.") % {'row_num': row_num + 1}
                        break
                    row_id = Decimal(row[_('Id')])

                    purchase_set = Purchase.objects.filter(id=row_id).order_by()[:1]
                    if purchase_set:
                        purchase = purchase_set[0]
                    else:
                        error = True
                        error_msg = _("Row %(row_num)d : No purchase corresponding to the given purchase id.") % {
                            'row_num': row_num + 1}
                        break
                    if purchase.permanence_id != permanence.id:
                        error = True
                        error_msg = _("Row %(row_num)d : The given permanence doesn't own the given purchase id.") % {
                            'row_num': row_num + 1}
                        break
                    producer_id = None
                    if row[_('producer')] in producer_2_id_dict:
                        producer_id = producer_2_id_dict[row[_('producer')]]
                    if producer_id != purchase.producer_id:
                        error = True
                        error_msg = _("Row %(row_num)d : No valid producer.") % {'row_num': row_num + 1}
                        break
                    customer_id = None
                    if row[_('customer')] in customer_2_id_dict:
                        customer_id = customer_2_id_dict[row[_('customer')]]
                    if customer_id != purchase.customer_id:
                        error = True
                        error_msg = _("Row %(row_num)d : No valid customer") % {'row_num': row_num + 1}
                        break
                    if row[_("vat or compensation")] in vat_level_dict:
                        vat_level = vat_level_dict[row[_("vat or compensation")]]
                    else:
                        error = True
                        error_msg = _("Row %(row_num)d : No valid vat or compensation level") % {'row_num': row_num + 1}
                        break

                    # Q
                    quantity = DECIMAL_ZERO if row[_('quantity')] is None else Decimal(row[_('quantity')]).quantize(
                        FOUR_DECIMALS)
                    # PU
                    original_unit_price = DECIMAL_ZERO if row[_('original unit price')] is None else Decimal(
                        row[_('original unit price')]).quantize(TWO_DECIMALS)
                    # PL
                    original_price = DECIMAL_ZERO if row[_('original row price')] is None else Decimal(
                        row[_('original row price')]).quantize(TWO_DECIMALS)
                    new_invoiced = None if row[_('invoiced without deposit')] in [None, " "] else Decimal(
                        row[_('invoiced without deposit')]).quantize(TWO_DECIMALS)

                    comment = cap(row[_('comment')], 100)

                    if db_write:

                        quantity_modified = quantity != purchase.quantity
                        original_unit_price_modified = original_unit_price != purchase.original_unit_price
                        # unit_deposit_modified = unit_deposit != purchase.unit_deposit
                        original_price_modified = original_price != purchase.original_price

                        # print("---------------------------------------")
                        # print quantity, original_unit_price, unit_deposit, original_price
                        # A1	if (PU + C) != 0 then: Q = PL / (PU + C) else: Q = 1, PU = PL - C
                        # A2	if Q != 0 then: PU = ( PL / Q ) - C else: PL = 0
                        # A3	if Q != 0 then: C = ( PL / Q ) - PU else: PL = 0
                        # A4	if (PU + C) != 0 then: Q = PL / (PU + C) else: Q = 1, C = PL - PU
                        # A5	PL = Q * ( PU + C )
                        # A6	Nothing

                        if original_price_modified:
                            if quantity_modified:
                                if original_unit_price_modified:
                                    # print("A3-3")
                                    # A3
                                    if quantity == DECIMAL_ZERO:
                                        original_price = DECIMAL_ZERO
                                else:
                                    # print("A2-4")
                                    # A2
                                    if quantity != DECIMAL_ZERO:
                                        original_unit_price = ( original_price / quantity )
                                        original_unit_price = original_unit_price.quantize(TWO_DECIMALS)
                                    else:
                                        original_price = DECIMAL_ZERO
                            else:
                                if original_unit_price_modified:
                                    # print("A4-5")
                                    # A4
                                    if original_unit_price != DECIMAL_ZERO:
                                        quantity = original_price / original_unit_price
                                        quantity = quantity.quantize(FOUR_DECIMALS)
                                    else:
                                        quantity = DECIMAL_ONE
                                        original_unit_price = original_price - original_unit_price
                                else:
                                    # A1
                                    # print("A1-6")
                                    if original_unit_price != DECIMAL_ZERO:
                                        quantity = original_price / original_unit_price
                                        quantity = quantity.quantize(FOUR_DECIMALS)
                                    else:
                                        quantity = DECIMAL_ONE
                                        original_unit_price = original_price
                        else:
                            if quantity_modified or original_unit_price_modified:
                                # A5
                                # print("A5-7")
                                original_price = quantity * original_unit_price
                                original_price = original_price.quantize(TWO_DECIMALS)
                            else:
                                # A6
                                # print("A6-8")
                                pass

                        # print quantity, original_unit_price, unit_deposit, original_price

                        purchase.quantity = quantity
                        purchase.original_unit_price = original_unit_price
                        # purchase.unit_deposit = unit_deposit
                        purchase.original_price = original_price
                        purchase.vat_level = vat_level
                        purchase.comment = comment
                        array_purchase.append(purchase)

                row_num += 1
                row = get_row(worksheet, header, row_num)

            except KeyError, e:
                # Missing field
                error = True
                error_msg = _("Row %(row_num)d : A required column is missing %(error_msg)s.") % {
                    'row_num': row_num + 1, 'error_msg': str(e)}
            except Exception, e:
                error = True
                error_msg = _("Row %(row_num)d : %(error_msg)s.") % {'row_num': row_num + 1, 'error_msg': str(e)}
    return error, error_msg


def handle_uploaded_file(request, queryset, file_to_import):
    error = False
    error_msg = None
    wb = load_workbook(file_to_import)
    # dict for performance optimisation purpose : read the DB only once
    customer_buyinggroup_id, customer_2_id_dict = get_customer_2_id_dict()
    id_2_customer_vat_id_dict = get_customer_2_vat_id_dict()
    producer_buyinggroup_id, producer_2_id_dict = get_producer_2_id_dict()
    id_2_producer_vat_level_dict = get_id_2_producer_vat_level_dict()
    id_2_producer_price_list_multiplier_dict = get_id_2_producer_price_list_multiplier_dict()
    if customer_buyinggroup_id is None:
        error = True
        error_msg = _("At least one customer must represent the buying group.")
    else:
        if producer_buyinggroup_id is None:
            error = True
            error_msg = _("At least one producer must represent the buying group.")

    if not error:
        for permanence in queryset:
            if permanence.status == PERMANENCE_SEND:
                ws = wb.get_sheet_by_name(unicode(cap(permanence.__unicode__(), 31), "utf8"))
                if ws:
                    error, error_msg = import_purchase_sheet(ws, permanence=permanence, db_write=False,
                                                             customer_2_id_dict=customer_2_id_dict,
                                                             id_2_customer_vat_id_dict=id_2_customer_vat_id_dict,
                                                             producer_2_id_dict=producer_2_id_dict,
                                                             id_2_producer_price_list_multiplier_dict=id_2_producer_price_list_multiplier_dict
                    )
                    if error:
                        error_msg = cap(permanence.__unicode__(), 31) + " > " + error_msg
                        break
            else:
                error = True
                error_msg = _("At least one of the permanences has already been invoiced.")
                break

    if not error:
        for permanence in queryset:
            ws = wb.get_sheet_by_name(cap(permanence.__unicode__(), 31))
            if ws:
                error, error_msg = import_purchase_sheet(ws, permanence=permanence, db_write=True,
                                                         customer_2_id_dict=customer_2_id_dict,
                                                         id_2_customer_vat_id_dict=id_2_customer_vat_id_dict,
                                                         producer_2_id_dict=producer_2_id_dict,
                                                         id_2_producer_price_list_multiplier_dict=id_2_producer_price_list_multiplier_dict
                )
                if error:
                    error_msg = cap(permanence.__unicode__(), 31) + " > " + error_msg
                    break

    return error, error_msg


def admin_import(permanence, admin, request, queryset):
    return import_xslx_view(permanence, admin, request, queryset, handle_uploaded_file)
