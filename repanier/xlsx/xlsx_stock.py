import repanier.apps
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.models.offeritem import OfferItemReadOnly
from repanier.packages.openpyxl.style import Fill
from repanier.packages.openpyxl.styles import Color
from repanier.tools import next_row
from repanier.xlsx.export_tools import *


def export_permanence_stock(
    permanence, deliveries_id=(), customer_price=False, wb=None, ws_customer_title=None
):
    if wb is not None:
        yellowFill = Fill()
        yellowFill.start_color.index = "FFEEEE11"
        yellowFill.end_color.index = "FFEEEE11"
        yellowFill.fill_type = Fill.FILL_SOLID

        header = [
            (_("Id"), 5),
            (_("OfferItem"), 5),
            (_("Reference"), 20),
            (_("Product"), 60),
            (
                _("Customer unit price")
                if customer_price
                else _("Producer unit price"),
                10,
            ),
            (_("Deposit"), 10),
            (_("Asked"), 10),
            (_("Quantity ordered"), 10),
            (_("Initial stock"), 10),
            (repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, 15),
            (_("Stock used"), 10),
            (_("Additional"), 10),
            (_("Remaining stock"), 10),
            (repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, 15),
        ]
        offer_items = (
            OfferItemReadOnly.objects.filter(
                permanence_id=permanence.id,
                producer__checking_stock=True,
            )
            .order_by("producer", "long_name_v2", "order_average_weight")
            .select_related("producer", "department_for_customer")
            .iterator()
        )
        offer_item = next_row(offer_items)
        if offer_item is not None:
            # Check if there are deliveries_ws
            deliveries_ws = []
            if len(deliveries_id) > 0:
                for delivery_cpt, delivery_id in enumerate(deliveries_id):
                    ws_sc_name = format_worksheet_title(
                        "{}-{}".format(delivery_cpt, ws_customer_title)
                    )
                    for sheet in wb.worksheets:
                        if ws_sc_name == sheet.title:
                            deliveries_ws.append(ws_sc_name)
                            break
            else:
                ws_sc_name = format_worksheet_title(ws_customer_title)
                for sheet in wb.worksheets:
                    if ws_sc_name == sheet.title:
                        deliveries_ws.append(ws_sc_name)
                        break
            wb, ws = new_landscape_a4_sheet(wb, _("Stock check"), permanence, header)
            formula_main_total_a = []
            formula_main_total_b = []
            show_column_reference = False
            show_column_qty_ordered = False
            show_column_add2stock = False
            row_num = 1
            while offer_item is not None:
                producer_save = offer_item.producer
                row_start_producer = row_num + 1
                c = ws.cell(row=row_num, column=2)
                c.value = "{}".format(producer_save.short_profile_name)
                c.style.font.bold = True
                c.style.font.italic = True
                while (
                    offer_item is not None
                    and producer_save.id == offer_item.producer_id
                ):
                    department_for_customer_save__id = (
                        offer_item.department_for_customer_id
                    )
                    department_for_customer_save__short_name = (
                        offer_item.department_for_customer.short_name_v2
                        if offer_item.department_for_customer is not None
                        else None
                    )
                    while (
                        offer_item is not None
                        and producer_save.id == offer_item.producer_id
                        and department_for_customer_save__id
                        == offer_item.department_for_customer_id
                    ):
                        if len(offer_item.reference) < 36:
                            if offer_item.reference.isdigit():
                                # Avoid display of exponent by Excel
                                offer_item_reference = "[{}]".format(
                                    offer_item.reference
                                )
                            else:
                                offer_item_reference = offer_item.reference
                            show_column_reference = True
                        else:
                            offer_item_reference = EMPTY_STRING
                        if offer_item.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:

                            asked = offer_item.quantity_invoiced
                            stock = offer_item.stock
                            c = ws.cell(row=row_num, column=0)
                            c.value = offer_item.producer_id
                            c = ws.cell(row=row_num, column=1)
                            c.value = offer_item.id
                            c = ws.cell(row=row_num, column=2)
                            c.value = "{}".format(offer_item_reference)
                            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=3)
                            if department_for_customer_save__short_name is not None:
                                c.value = "{} - {}".format(
                                    offer_item.get_long_name_with_customer_price(),
                                    department_for_customer_save__short_name,
                                )
                            else:
                                c.value = "{}".format(
                                    offer_item.get_long_name_with_customer_price()
                                )
                            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
                            c.style.alignment.wrap_text = True
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=4)
                            unit_price = (
                                offer_item.customer_unit_price
                                if customer_price
                                else offer_item.producer_unit_price
                            )
                            c.value = unit_price.amount
                            c.style.number_format.format_code = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=5)
                            c.value = offer_item.unit_deposit.amount
                            c.style.number_format.format_code = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=6)
                            if ws_customer_title is None:
                                c.value = asked
                            else:
                                if len(deliveries_ws) > 0:
                                    sum_value = "+".join(
                                        "SUMIF('{}'!B:B,B{},'{}'!F:F)".format(
                                            delivery_ws, row_num + 1, delivery_ws
                                        )
                                        for delivery_ws in deliveries_ws
                                    )
                                    c.value = "={}".format(sum_value)
                                else:
                                    c.value = DECIMAL_ZERO
                            c.style.number_format.format_code = "#,##0.???"
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=7)
                            c.value = "=G{}-K{}+L{}".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            if not show_column_qty_ordered:
                                show_column_qty_ordered = (
                                    asked - min(asked, stock)
                                ) > 0
                            c.style.number_format.format_code = "#,##0.???"
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=8)
                            c.value = stock
                            c.style.number_format.format_code = "#,##0.???"
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c.style.font.color = Color(Color.BLUE)
                            ws.conditional_formatting.addCellIs(
                                get_column_letter(9) + str(row_num + 1),
                                "notEqual",
                                [str(stock)],
                                True,
                                wb,
                                None,
                                None,
                                yellowFill,
                            )
                            c = ws.cell(row=row_num, column=9)
                            c.value = "=ROUND(I{}*(E{}+F{}),2)".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.style.number_format.format_code = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=10)
                            c.value = "=MIN(G{},I{})".format(row_num + 1, row_num + 1)
                            c.style.number_format.format_code = "#,##0.???"
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c = ws.cell(row=row_num, column=12)
                            c.value = "=I{}-K{}+L{}".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.style.number_format.format_code = "#,##0.???"
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            c.style.font.bold = True
                            c = ws.cell(row=row_num, column=13)
                            c.value = "=ROUND(M{}*(E{}+F{}),2)".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.style.number_format.format_code = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.style.borders.bottom.border_style = Border.BORDER_THIN
                            row_num += 1
                        offer_item = next_row(offer_items)
                row_num += 1
                c = ws.cell(row=row_num, column=3)
                c.value = "{} {}".format(
                    _("Total price"), producer_save.short_profile_name
                )
                c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
                c.style.font.bold = True
                c.style.alignment.horizontal = c.style.alignment.HORIZONTAL_RIGHT
                c = ws.cell(row=row_num, column=9)
                formula = "SUM(J{}:J{})".format(row_start_producer, row_num)
                c.value = "=" + formula
                c.style.number_format.format_code = (
                    repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                )
                c.style.font.bold = True
                formula_main_total_a.append(formula)
                c = ws.cell(row=row_num, column=13)
                formula = "SUM(N{}:N{})".format(row_start_producer, row_num)
                c.value = "=" + formula
                c.style.number_format.format_code = (
                    repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                )
                c.style.font.bold = True
                formula_main_total_b.append(formula)

                if offer_items is not None:
                    # Display a separator line between producers
                    row_num += 1
                    for col_num in range(16):
                        c = ws.cell(row=row_num, column=col_num)
                        c.style.borders.bottom.border_style = Border.BORDER_MEDIUMDASHED
                    row_num += 2

            c = ws.cell(row=row_num, column=3)
            c.value = "{}".format(_("Total price"))
            c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
            c.style.font.bold = True
            c.style.alignment.horizontal = c.style.alignment.HORIZONTAL_RIGHT
            c = ws.cell(row=row_num, column=9)
            c.value = "=" + "+".join(formula_main_total_a)
            c.style.number_format.format_code = (
                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
            )
            c.style.font.bold = True
            c = ws.cell(row=row_num, column=13)
            c.value = "=" + "+".join(formula_main_total_b)
            c.style.number_format.format_code = (
                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
            )
            c.style.font.bold = True

            row_num += 1
            for col_num in range(16):
                c = ws.cell(row=row_num, column=col_num)
                c.style.borders.bottom.border_style = Border.BORDER_MEDIUMDASHED

            ws.column_dimensions[get_column_letter(1)].visible = False
            ws.column_dimensions[get_column_letter(2)].visible = False
            ws.column_dimensions[get_column_letter(11)].visible = False
            if not show_column_reference:
                ws.column_dimensions[get_column_letter(3)].visible = False
            if not show_column_qty_ordered:
                ws.column_dimensions[get_column_letter(8)].visible = False
            if not show_column_add2stock:
                ws.column_dimensions[get_column_letter(12)].visible = False
    return wb


# @transaction.atomic
# def import_stock_sheet(worksheet, permanence=None):
#     error = False
#     error_msg = None
#     if permanence.status < PERMANENCE_DONE:
#         header = get_header(worksheet)
#         if header:
#             row_num = 1
#             row = get_row(worksheet, header, row_num)
#             while row and not error:
#                 try:
#                     # with transaction.atomic():
#                     stock = None if row[_('Initial stock')] is None else Decimal(row[_('Initial stock')]).quantize(THREE_DECIMALS)
#                     if stock is not None:
#                         producer_id = None if row[_('Id')] is None else Decimal(row[_('Id')])
#                         offer_item_id = None if row[_('OfferItem')] is None else Decimal(row[_('OfferItem')])
#                         offer_item = OfferItem.objects.filter(
#                             id=offer_item_id,
#                             permanence_id=permanence.id,
#                             producer_id=producer_id
#                         ).order_by('?').first()
#                         if offer_item is not None \
#                                 and (offer_item.stock != stock):
#                             offer_item.stock = stock
#                             offer_item.save()
#                             Product.objects.filter(
#                                 id=offer_item.product_id,
#                                 producer_id=producer_id
#                             ).update(stock=stock)
#                     row_num += 1
#                     row = get_row(worksheet, header, row_num)
#                 except KeyError, e:
#                     # Missing field
#                     error = True
#                     error_msg = _("Row %(row_num)d : A required column is missing.") % {'row_num': row_num + 1}
#                 except Exception, e:
#                     error = True
#                     error_msg = _("Row %(row_num)d : %(error_msg)s.") % {'row_num': row_num + 1, 'error_msg': str(e)}
#     else:
#         error = True
#         error_msg = _("The status of this permanence prohibit you to update the stock.")
#     return error, error_msg


# def export_producer_stock(producers, customer_price=False, wb=None):
#     yellowFill = Fill()
#     yellowFill.start_color.index = "FFEEEE11"
#     yellowFill.end_color.index = "FFEEEE11"
#     yellowFill.fill_type = Fill.FILL_SOLID
#
#     header = [
#         (_("Id"), 5),
#         (_("Producer"), 60),
#         (_("Reference"), 20),
#         (_("Product"), 60),
#         (_("Customer unit price") if customer_price else _("Producer unit price"), 10),
#         (_("Deposit"), 10),
#         (_("Maximum quantity"), 10),
#         (repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, 15),
#     ]
#     producers = producers.iterator()
#     producer = next_row(producers)
#     wb, ws = new_landscape_a4_sheet(wb, _("Maximum quantity"), _("Maximum quantity"), header)
#     show_column_reference = False
#     row_num = 1
#     while producer is not None:
#         products = (
#             Product.objects.filter(
#                 producer_id=producer.id,
#                 is_active=True,
#             )
#             .order_by("long_name_v2", "order_average_weight")
#             .select_related("producer", "department_for_customer")
#             .iterator()
#         )
#         product = next_row(products)
#         while product is not None:
#             if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
#                 c = ws.cell(row=row_num, column=0)
#                 c.value = product.id
#                 c = ws.cell(row=row_num, column=1)
#                 c.value = "{}".format(product.producer)
#                 if len(product.reference) < 36:
#                     if product.reference.isdigit():
#                         # Avoid display of exponent by Excel
#                         product_reference = "[{}]".format(product.reference)
#                     else:
#                         product_reference = product.reference
#                     show_column_reference = True
#                 else:
#                     product_reference = EMPTY_STRING
#                 c = ws.cell(row=row_num, column=2)
#                 c.value = "{}".format(product_reference)
#                 c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 c = ws.cell(row=row_num, column=3)
#                 if product.department_for_customer is not None:
#                     c.value = "{} - {}".format(
#                         product.department_for_customer.short_name_v2,
#                         product.get_long_name_with_customer_price(),
#                     )
#                 else:
#                     c.value = product.get_long_name_with_customer_price()
#                 c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
#                 c.style.alignment.wrap_text = True
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 c = ws.cell(row=row_num, column=4)
#                 unit_price = (
#                     product.customer_unit_price
#                     if customer_price
#                     else product.producer_unit_price
#                 )
#                 c.value = unit_price.amount
#                 c.style.number_format.format_code = (
#                     repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
#                 )
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 c = ws.cell(row=row_num, column=5)
#                 c.value = product.unit_deposit.amount
#                 c.style.number_format.format_code = (
#                     repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
#                 )
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 c = ws.cell(row=row_num, column=6)
#                 c.value = product.stock
#                 c.style.number_format.format_code = (
#                     '_ * #,##0.00_ ;_ * -#,##0.00_ ;_ * "-"??_ ;_ @_ '
#                 )
#                 c.style.font.color = Color(Color.BLUE)
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 c = ws.cell(row=row_num, column=7)
#                 c.value = "=ROUND((E{}+F{})*G{},2)".format(
#                     row_num + 1, row_num + 1, row_num + 1
#                 )
#                 c.style.number_format.format_code = (
#                     repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
#                 )
#                 ws.conditional_formatting.addCellIs(
#                     get_column_letter(8) + str(row_num + 1),
#                     "notEqual",
#                     [
#                         str(
#                             (
#                                 (unit_price.amount + product.unit_deposit.amount)
#                                 * product.stock
#                             ).quantize(TWO_DECIMALS)
#                         )
#                     ],
#                     True,
#                     wb,
#                     None,
#                     None,
#                     yellowFill,
#                 )
#                 c.style.borders.bottom.border_style = Border.BORDER_THIN
#                 row_num += 1
#             product = next_row(products)
#         row_num += 1
#         c = ws.cell(row=row_num, column=4)
#         c.value = "{}".format(_("Total"))
#         c.style.number_format.format_code = NumberFormat.FORMAT_TEXT
#         c.style.font.bold = True
#         c.style.alignment.horizontal = c.style.alignment.HORIZONTAL_RIGHT
#         c = ws.cell(row=row_num, column=7)
#         formula = "SUM(H{}:H{})".format(2, row_num)
#         c.value = "=" + formula
#         c.style.number_format.format_code = (
#             repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
#         )
#         c.style.font.bold = True
#
#         ws.column_dimensions[get_column_letter(1)].visible = False
#         if not show_column_reference:
#             ws.column_dimensions[get_column_letter(3)].visible = False
#         producer = next_row(producers)
#     return wb


# @transaction.atomic
# def import_producer_stock(worksheet):
#     error = False
#     error_msg = None
#     header = get_header(worksheet)
#     if header:
#         row_num = 1
#         row = get_row(worksheet, header, row_num)
#         while row and not error:
#             try:
#                 # with transaction.atomic():
#                 product_id = None if row[_("Id")] is None else Decimal(row[_("Id")])
#                 if product_id is not None:
#                     stock = (
#                         DECIMAL_ZERO
#                         if row[_("Maximum quantity")] is None
#                         else Decimal(row[_("Maximum quantity")]).quantize(THREE_DECIMALS)
#                     )
#                     stock = stock if stock >= DECIMAL_ZERO else DECIMAL_ZERO
#                     Product.objects.filter(id=product_id).update(stock=stock)
#                 update_offer_item(product_id=product_id)
#                 row_num += 1
#                 row = get_row(worksheet, header, row_num)
#             except KeyError as e:
#                 # Missing field
#                 error = True
#                 error_msg = _("Row %(row_num)d : A required column is missing.") % {
#                     "row_num": row_num + 1
#                 }
#             except Exception as e:
#                 error = True
#                 error_msg = _("Row %(row_num)d : %(error_msg)s.") % {
#                     "row_num": row_num + 1,
#                     "error_msg": str(e),
#                 }
#     return error, error_msg


# def handle_uploaded_stock(request, producers, file_to_import, *args):
#     error = False
#     error_msg = None
#     wb = load_workbook(file_to_import)
#     if wb is not None:
#         ws = wb.get_sheet_by_name(format_worksheet_title(_("Maximum quantity")))
#         if ws is not None:
#             error, error_msg = import_producer_stock(ws, producers=producers)
#             if error:
#                 error_msg = format_worksheet_title(_("Maximum quantity")) + " > " + error_msg
#     return error, error_msg
