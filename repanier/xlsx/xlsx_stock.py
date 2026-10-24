"""
Excel export for permanence stock verification.

This module generates an Excel sheet detailing:
- Available products per producer
- Requested quantities, initial stock, used stock, and remaining stock
- Unit prices (producer or customer based on parameter)
- Totals per producer and grand total
"""

from django.utils.translation import gettext_lazy as _
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment
from openpyxl.styles.numbers import FORMAT_TEXT
from openpyxl.utils import get_column_letter

from repanier.const import DECIMAL_ZERO, EMPTY_STRING, OrderUnit
from repanier.models.offeritem import OfferItemReadOnly
import repanier.apps
from repanier.tools import next_row
from repanier.xlsx.export_tools import (
    new_landscape_a4_sheet,
    format_worksheet_title,
)
from repanier.xlsx.xlsx_styles import (
    FILL_YELLOW,
    BORDER_BOTTOM_THIN,
    BORDER_BOTTOM_MEDIUM_DASHED,
    FONT_BOLD,
    FONT_BOLD_ITALIC,
    FONT_GRAY,
)


def export_permanence_stock(
    permanence,
    deliveries_id=(),
    customer_price=False,
    wb=None,
    ws_customer_title=None
):
    """
    Export permanence stock to an Excel file.

    Args:
        permanence: The permanence to export stock for
        deliveries_id: Tuple of delivery IDs for quantity calculations
        customer_price: If True, use customer prices; otherwise use producer prices
        wb: Existing workbook (optional). If None, creates a new one
        ws_customer_title: Customer worksheet title for references

    Returns:
        Workbook: The Excel workbook with stock sheet added
    """
    if wb is None:
        return None

    header = [
        (_("Id"), 5),                                  # Col A - Producer ID (hidden)
        (_("OfferItem"), 5),                           # Col B - OfferItem ID (hidden)
        (_("Reference"), 20),                          # Col C - Product reference
        (_("Product"), 60),                            # Col D - Product name
        (_("Customer unit price") if customer_price else _("Producer unit price"), 10),  # Col E
        (_("Deposit"), 10),                            # Col F - Deposit
        (_("Asked"), 10),                              # Col G - Requested quantity
        (_("Quantity ordered"), 10),                   # Col H - Ordered quantity (calculated)
        (_("Initial stock"), 10),                      # Col I - Initial stock
        (repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, 15),  # Col J - Initial stock value
        (_("Stock used"), 10),                         # Col K - Used stock
        (_("Additional"), 10),                         # Col L - Additional
        (_("Remaining stock"), 10),                    # Col M - Remaining stock
        (repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, 15),  # Col N - Remaining stock value
    ]

    offer_items = (
        OfferItemReadOnly.objects
        .filter(
            permanence_id=permanence.id,
            producer__checking_stock=True,
        )
        .order_by("producer", "long_name_v2", "order_average_weight")
        .select_related("producer", "department_for_customer")
        .iterator()
    )

    wb, ws = new_landscape_a4_sheet(wb, _("Stock check"), permanence, header)

    formula_main_total_a = []
    formula_main_total_b = []
    show_column_reference = False
    show_column_qty_ordered = False
    show_column_add2stock = False
    current_row = 2

    deliveries_ws = []
    if deliveries_id:
        for delivery_idx, delivery_id in enumerate(deliveries_id):
            ws_name = format_worksheet_title(f"{delivery_idx}-{ws_customer_title}")
            if any(ws_name == sheet.title for sheet in wb.worksheets):
                deliveries_ws.append(ws_name)
    elif ws_customer_title:
        ws_name = format_worksheet_title(ws_customer_title)
        if any(ws_name == sheet.title for sheet in wb.worksheets):
            deliveries_ws.append(ws_name)

    offer_item = next_row(offer_items)
    while offer_item is not None:
        current_producer = offer_item.producer
        producer_start_row = current_row

        cell = ws.cell(row=current_row, column=3)
        cell.value = current_producer.short_profile_name
        cell.font = FONT_BOLD_ITALIC

        while offer_item is not None and current_producer.id == offer_item.producer_id:
            current_department_id = offer_item.department_for_customer_id
            current_department_name = (
                offer_item.department_for_customer.short_name_v2
                if offer_item.department_for_customer
                else None
            )

            while (offer_item is not None and
                   current_producer.id == offer_item.producer_id and
                   current_department_id == offer_item.department_for_customer_id):

                if offer_item.order_unit < OrderUnit.DEPOSIT:
                    asked_qty = offer_item.get_producer_quantity(permanence.status)
                    initial_stock = offer_item.stock
                    unit_deposit = offer_item.unit_deposit.amount
                    unit_price = (
                        offer_item.customer_unit_price.amount
                        if customer_price
                        else offer_item.producer_unit_price.amount
                    )
                    price_with_deposit = unit_price + unit_deposit

                    ws.cell(row=current_row, column=1, value=offer_item.producer_id)
                    ws.cell(row=current_row, column=2, value=offer_item.id)

                    ref = offer_item.reference
                    if len(ref) < 36:
                        if ref.isdigit():
                            ref = f"[{ref}]"
                        show_column_reference = True
                    else:
                        ref = EMPTY_STRING

                    cell = ws.cell(row=current_row, column=3, value=ref)
                    cell.number_format = FORMAT_TEXT
                    cell.border = BORDER_BOTTOM_THIN

                    product_name = offer_item.get_long_name_with_customer_price()
                    if current_department_name:
                        product_name = f"{product_name} - {current_department_name}"

                    cell = ws.cell(row=current_row, column=4, value=product_name)
                    cell.number_format = FORMAT_TEXT
                    cell.alignment = Alignment(wrap_text=True)
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(row=current_row, column=5, value=unit_price)
                    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(row=current_row, column=6, value=unit_deposit)
                    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(row=current_row, column=7)
                    if ws_customer_title is None:
                        cell.value = asked_qty
                    else:
                        if deliveries_ws:
                            sum_formula = "+".join(
                                f"SUMIF('{dw}'!B:B,B{current_row},'{dw}'!F:F)"
                                for dw in deliveries_ws
                            )
                            cell.value = f"={sum_formula}"
                        else:
                            cell.value = DECIMAL_ZERO
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(
                        row=current_row,
                        column=8,
                        value=f"=G{current_row}-K{current_row}+L{current_row}"
                    )
                    if (asked_qty - min(asked_qty, initial_stock)) > 0:
                        show_column_qty_ordered = True
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(row=current_row, column=9, value=initial_stock)
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN
                    cell.font = FONT_GRAY

                    ws.conditional_formatting.add(
                        f"{get_column_letter(9)}{current_row}",
                        CellIsRule(
                            operator="notEqual",
                            formula=[str(initial_stock)],
                            fill=FILL_YELLOW,
                        ),
                    )

                    cell = ws.cell(
                        row=current_row,
                        column=10,
                        value=f"=ROUND(I{current_row}*{price_with_deposit},2)"
                    )
                    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(
                        row=current_row,
                        column=11,
                        value=f"=MIN(G{current_row},I{current_row})"
                    )
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(row=current_row, column=12, value=DECIMAL_ZERO)
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN

                    cell = ws.cell(
                        row=current_row,
                        column=13,
                        value=f"=I{current_row}-K{current_row}+L{current_row}"
                    )
                    cell.number_format = "#,##0.???"
                    cell.border = BORDER_BOTTOM_THIN
                    cell.font = FONT_BOLD

                    cell = ws.cell(
                        row=current_row,
                        column=14,
                        value=f"=ROUND(M{current_row}*{price_with_deposit},2)"
                    )
                    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
                    cell.border = BORDER_BOTTOM_THIN

                    current_row += 1

                offer_item = next_row(offer_items)

        cell = ws.cell(row=current_row, column=4)
        cell.value = f"{_('Total price')} {current_producer.short_profile_name}"
        cell.number_format = FORMAT_TEXT
        cell.font = FONT_BOLD
        cell.alignment = Alignment(horizontal="right")

        formula_j = f"SUM(J{producer_start_row}:J{current_row - 1})"
        cell = ws.cell(row=current_row, column=10, value=f"={formula_j}")
        cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
        cell.font = FONT_BOLD
        formula_main_total_a.append(formula_j)

        formula_n = f"SUM(N{producer_start_row}:N{current_row - 1})"
        cell = ws.cell(row=current_row, column=14, value=f"={formula_n}")
        cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
        cell.font = FONT_BOLD
        formula_main_total_b.append(formula_n)

        if offer_items is not None:
            current_row += 1
            for col in range(16):
                ws.cell(row=current_row, column=col + 1).border = BORDER_BOTTOM_MEDIUM_DASHED
            current_row += 2

    cell = ws.cell(row=current_row, column=4)
    cell.value = str(_("Total price"))
    cell.number_format = FORMAT_TEXT
    cell.font = FONT_BOLD
    cell.alignment = Alignment(horizontal="right")

    cell = ws.cell(
        row=current_row,
        column=10,
        value=f"={'+'.join(formula_main_total_a)}"
    )
    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
    cell.font = FONT_BOLD

    cell = ws.cell(
        row=current_row,
        column=14,
        value=f"={'+'.join(formula_main_total_b)}"
    )
    cell.number_format = repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX
    cell.font = FONT_BOLD

    current_row += 1
    for col in range(16):
        ws.cell(row=current_row, column=col + 1).border = BORDER_BOTTOM_MEDIUM_DASHED

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