from django.utils.translation import gettext_lazy as _
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.styles.numbers import FORMAT_TEXT

import repanier.apps
from repanier.const import *
from repanier.models.offeritem import OfferItemReadOnly
from repanier.tools import next_row
from repanier.xlsx.export_tools import *


def export_permanence_stock(
    permanence, deliveries_id=(), customer_price=False, wb=None, ws_customer_title=None
):
    if wb is not None:
        yellow_fill = PatternFill(fill_type="solid", start_color="FFFF00", end_color="FFFF00")

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
                c = ws.cell(row=row_num + 1, column=2 + 1)
                c.value = "{}".format(producer_save.short_profile_name)
                c.font = Font(bold=True, italic=True)
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
                        if offer_item.order_unit < OrderUnit.DEPOSIT:

                            asked = offer_item.get_producer_quantity(permanence.status)
                            stock = offer_item.stock
                            c = ws.cell(row=row_num + 1, column=0 + 1)
                            c.value = offer_item.producer_id
                            c = ws.cell(row=row_num + 1, column=1 + 1)
                            c.value = offer_item.id
                            c = ws.cell(row=row_num + 1, column=2 + 1)
                            c.value = "{}".format(offer_item_reference)
                            c.number_format = FORMAT_TEXT
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=3 + 1)
                            if department_for_customer_save__short_name is not None:
                                c.value = "{} - {}".format(
                                    offer_item.get_long_name_with_customer_price(),
                                    department_for_customer_save__short_name,
                                )
                            else:
                                c.value = "{}".format(
                                    offer_item.get_long_name_with_customer_price()
                                )
                            c.number_format = FORMAT_TEXT
                            c.alignment = Alignment(wrap_text=True)
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=4 + 1)
                            unit_price = (
                                offer_item.customer_unit_price
                                if customer_price
                                else offer_item.producer_unit_price
                            )
                            c.value = unit_price.amount
                            c.number_format = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=5 + 1)
                            c.value = offer_item.unit_deposit.amount
                            c.number_format = (
                                repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            )
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=6 + 1)
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
                            c.number_format = "#,##0.???"
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=7 + 1)
                            c.value = "=G{}-K{}+L{}".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            if not show_column_qty_ordered:
                                show_column_qty_ordered = (
                                    asked - min(asked, stock)
                                ) > 0
                            c.number_format = "#,##0.???"
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=8 + 1)
                            c.value = stock
                            c.number_format = "#,##0.???"
                            c.border = Border(bottom=Side(style="thin"))
                            c.font = Font(color="FF939393")
                            ws.conditional_formatting.add(
                                f"{get_column_letter(9)}{row_num + 1}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(stock)],
                                    fill=yellow_fill,
                                ),
                            )
                            c = ws.cell(row=row_num + 1, column=9 + 1)
                            c.value = "=ROUND(I{}*(E{}+F{}),2)".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=10 + 1)
                            c.value = "=MIN(G{},I{})".format(row_num + 1, row_num + 1)
                            c.number_format = "#,##0.???"
                            c.border = Border(bottom=Side(style="thin"))
                            c = ws.cell(row=row_num + 1, column=12 + 1)
                            c.value = "=I{}-K{}+L{}".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.number_format = "#,##0.???"
                            c.border = Border(bottom=Side(style="thin"))
                            c.font = Font(bold=True)
                            c = ws.cell(row=row_num + 1, column=13 + 1)
                            c.value = "=ROUND(M{}*(E{}+F{}),2)".format(
                                row_num + 1, row_num + 1, row_num + 1
                            )
                            c.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                            c.border = Border(bottom=Side(style="thin"))
                            row_num += 1
                        offer_item = next_row(offer_items)
                row_num += 1
                c = ws.cell(row=row_num + 1, column=3 + 1)
                c.value = "{} {}".format(
                    _("Total price"), producer_save.short_profile_name
                )
                c.number_format = FORMAT_TEXT
                c.font = Font(bold=True)
                c.alignment = Alignment(horizontal="right")
                c = ws.cell(row=row_num + 1, column=9 + 1)
                formula = "SUM(J{}:J{})".format(row_start_producer, row_num)
                c.value = "=" + formula
                c.number_format = (
                    repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                )
                c.font = Font(bold=True)
                formula_main_total_a.append(formula)
                c = ws.cell(row=row_num + 1, column=13 + 1)
                formula = "SUM(N{}:N{})".format(row_start_producer, row_num)
                c.value = "=" + formula
                c.number_format = (
                    repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                )
                c.font = Font(bold=True)
                formula_main_total_b.append(formula)

                if offer_items is not None:
                    # Display a separator line between producers
                    row_num += 1
                    for col_num in range(16):
                        c = ws.cell(row=row_num + 1, column=col_num + 1)
                        c.border = Border(bottom=Side(style="mediumDashed"))
                    row_num += 2

            c = ws.cell(row=row_num + 1, column=3 + 1)
            c.value = "{}".format(_("Total price"))
            c.number_format = FORMAT_TEXT
            c.font = Font(bold=True)
            c.alignment = Alignment(horizontal="right")
            c = ws.cell(row=row_num + 1, column=9 + 1)
            c.value = "=" + "+".join(formula_main_total_a)
            c.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
            c.font = Font(bold=True)
            c = ws.cell(row=row_num + 1, column=13 + 1)
            c.value = "=" + "+".join(formula_main_total_b)
            c.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
            c.font = Font(bold=True)

            row_num += 1
            for col_num in range(16):
                c = ws.cell(row=row_num + 1, column=col_num + 1)
                c.border = Border(bottom=Side(style="mediumDashed"))

            ws.column_dimensions[get_column_letter(1)].hidden = True
            ws.column_dimensions[get_column_letter(2)].hidden = True
            ws.column_dimensions[get_column_letter(11)].hidden = True
            if not show_column_reference:
                ws.column_dimensions[get_column_letter(3)].hidden = True
            if not show_column_qty_ordered:
                ws.column_dimensions[get_column_letter(8)].hidden = True
            if not show_column_add2stock:
                ws.column_dimensions[get_column_letter(12)].hidden = True
    return wb
