"""
Excel export and import for purchase accounting.

This module provides:
- export_purchase(): Export purchase data to Excel for accounting verification
- import_purchase_sheet(): Import purchase data from Excel
- handle_uploaded_purchase(): Handle file upload and validation
"""
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from openpyxl.formatting.rule import CellIsRule
from openpyxl.reader.excel import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.styles.numbers import FORMAT_TEXT, FORMAT_DATE_DMYSLASH
from openpyxl.utils import get_column_letter

from repanier.apps import REPANIER_SETTINGS_CURRENCY_XLSX
from repanier.const import DECIMAL_ZERO, EMPTY_STRING, OrderUnit, RoundUpTo, SaleStatus, DECIMAL_ONE
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.purchase import Purchase
from repanier.models.producer import Producer
from repanier.tools import next_row, cap
from repanier.xlsx.export_tools import new_landscape_a4_sheet, format_worksheet_title
from repanier.xlsx.import_tools import get_header, get_row, get_customer_2_id_dict, get_producer_2_id_dict

def next_purchase(purchases):
    """
    Get next valid purchase from iterator, skipping zero-quantity and deposit items.

    Args:
        purchases: Iterator of Purchase objects

    Returns:
        Next valid Purchase object or None
    """
    purchase = next_row(purchases)
    while (
        purchase is not None
        and purchase.quantity_invoiced <= DECIMAL_ZERO
        and purchase.offer_item.order_unit < OrderUnit.DEPOSIT
    ):
        purchase = next_row(purchases)
    return purchase

def export_purchase(permanence=None, year=None, producer=None, customer=None, wb=None):
    """
    Export purchase data to Excel for accounting verification.

    Args:
        permanence: Permanence to export (optional)
        year: Year to filter by (optional)
        producer: Specific producer to export (optional)
        customer: Specific customer to filter by (optional)
        wb: Existing workbook to append to (optional)

    Returns:
        Workbook: Excel workbook with purchase data
    """
    # Style configurations
    yellow_fill = PatternFill(fill_type="solid", start_color="FFFF00", end_color="FFFF00")
    blue_font = Font(color="FF0000FF")
    gray_font = Font(color="FF939393")
    thin_border = Border(top=Side(style="thin"))
    medium_dashed_border = Border(top=Side(style="mediumDashed"))

    # Column definitions
    header = [
        (_("Format"), 5),              # Col A - Format marker (A, B, C, D)
        (_("Id"), 10),                 # Col B - Purchase ID (hidden)
        (_("Date"), 15),               # Col C - Permanence date
        (_("Producer"), 15),           # Col D - Producer name
        (_("Product"), 60),            # Col E - Product name
        (_("Customer"), 15),           # Col F - Customer name
        (_("Quantity accounted for"), 10),  # Col G - Invoiced quantity
        (_("Producer unit price"), 10),    # Col H - Unit price
        (_("Deposit"), 10),            # Col I - Deposit amount
        (_("Purchase price"), 10),     # Col J - Total purchase price
        (_("VAT"), 10),                # Col K - VAT amount
        (_("Rule of 3"), 10),          # Col L - Rule of 3 value
        (_("Comment"), 30),            # Col M - Comment
        (_("VAT rate"), 10),           # Col N - VAT rate
        (_("CustId_01"), 10),          # Col O - Customer email (hidden)
    ]

    # Determine producers to export
    if producer is None:
        if permanence is not None:
            producers_query = Producer.objects.filter(
                producerinvoice__permanence_id=permanence.id
            ).distinct()

            if customer is not None:
                title1 = f"{customer.short_basket_name}-{permanence}"
            else:
                title1 = f"{permanence}"
        else:
            producers_query = Producer.objects.filter(
                producerinvoice__permanence__permanence_date__year=year
            ).distinct()
            title1 = f"{customer.short_basket_name}-{year}"
    else:
        producers_query = Producer.objects.filter(id=producer.id)
        title1 = f"{producer.short_profile_name}-{year}"

    producers = producers_query.iterator()
    current_producer = next_row(producers)

    if current_producer is None:
        return wb

    wb, ws = new_landscape_a4_sheet(wb, title1, _("Accounting entries"), header)
    current_row = 2  # Start after header at row 1
    count_all_purchase = 0
    purchase_price_all_purchase = []
    tax_all_purchase = []

    while current_producer is not None:
        producer_price = DECIMAL_ZERO
        producer_start_row = current_row

        # Get purchases for this producer
        if year is None:
            base_filters = {
                'permanence_id': permanence.id,
                'producer_id': current_producer.id,
            }
            if customer is not None:
                base_filters['customer_id'] = customer.id

            if current_producer.invoice_by_basket:
                order_by = [
                    "customer__short_basket_name",
                    "offer_item__preparation_sort_order_v2",
                ]
            else:
                order_by = [
                    "offer_item__preparation_sort_order_v2",
                    "quantity_for_preparation_sort_order",
                    "customer__short_basket_name",
                ]
        else:
            base_filters = {
                'permanence__status__gte': SaleStatus.INVOICED,
                'permanence__permanence_date__year': year,
                'producer_id': current_producer.id,
            }
            if customer is not None:
                base_filters['customer_id'] = customer.id

            if current_producer.invoice_by_basket:
                order_by = [
                    "permanence_id",
                    "customer__short_basket_name",
                    "offer_item__preparation_sort_order_v2",
                ]
            else:
                order_by = [
                    "permanence_id",
                    "offer_item__preparation_sort_order_v2",
                    "quantity_for_preparation_sort_order",
                    "customer__short_basket_name",
                ]

        purchases = Purchase.objects.filter(**base_filters).order_by(*order_by).iterator()
        current_purchase = next_purchase(purchases)

        while current_purchase is not None:
            current_permanence = current_purchase.permanence
            count_permanence_purchase = 0
            permanence_start_row = current_row

            while current_purchase is not None and current_permanence.id == current_purchase.permanence_id:
                if current_producer.invoice_by_basket:
                    # =========================================================================
                    # MODE 1: invoice_by_basket = True
                    # Group by: Producer > Permanence > Customer > Department
                    # =========================================================================
                    current_customer = current_purchase.customer
                    count_customer_purchase = 0
                    customer_start_row = current_row
                    customer_total_price = DECIMAL_ZERO

                    while (current_purchase is not None and
                           current_permanence.id == current_purchase.permanence_id and
                           current_customer.id == current_purchase.customer_id):

                        current_department = current_purchase.offer_item.department_for_customer
                        department_name = (
                            current_department.short_name_v2
                            if current_department is not None
                            else EMPTY_STRING
                        )

                        customer_item_count = 0
                        while (current_purchase is not None and
                               current_permanence.id == current_purchase.permanence_id and
                               current_customer.id == current_purchase.customer_id and
                               current_department == current_purchase.offer_item.department_for_customer):

                            if current_purchase.offer_item.order_unit < OrderUnit.DEPOSIT:
                                # Pre-calculate values
                                unit_price = current_purchase.get_producer_unit_price()
                                deposit = current_purchase.offer_item.unit_deposit.amount
                                price_with_deposit = unit_price + deposit
                                customer_vat = current_purchase.offer_item.customer_vat.amount

                                # --- COLUMN A: Format marker ---
                                format_marker = "A" if customer_item_count == 0 else "B"
                                ws.cell(row=current_row, column=1, value=format_marker)

                                if customer_item_count == 0:
                                    if count_permanence_purchase == 0:
                                        ws.cell(row=current_row, column=4).font = Font(bold=True)
                                        permanence_start_row = current_row
                                    ws.cell(row=current_row, column=1).font = Font(bold=True)

                                # --- COLUMN B: Purchase ID (hidden) ---
                                ws.cell(row=current_row, column=2, value=current_purchase.id)

                                # --- COLUMN C: Date ---
                                cell = ws.cell(row=current_row, column=3, value=current_permanence.permanence_date)
                                cell.number_format = FORMAT_DATE_DMYSLASH

                                # --- COLUMN D: Producer ---
                                ws.cell(row=current_row, column=4, value=current_producer.short_profile_name).number_format = FORMAT_TEXT

                                # --- COLUMN E: Product name ---
                                product_name = current_purchase.get_long_name_with_customer_price()
                                if department_name:
                                    product_name = f"{product_name} - {department_name}"
                                cell = ws.cell(row=current_row, column=5, value=product_name)
                                cell.number_format = FORMAT_TEXT

                                # --- COLUMN F: Customer ---
                                cell = ws.cell(row=current_row, column=6, value=current_customer.short_basket_name)
                                cell.number_format = FORMAT_TEXT
                                if customer_item_count == 0 and customer is None:
                                    cell.font = Font(bold=True)

                                # --- COLUMN G: Quantity accounted for ---
                                cell = ws.cell(row=current_row, column=7, value=current_purchase.quantity_invoiced)
                                cell.number_format = "#,##0.????"

                                if year is None:
                                    cell.font = blue_font
                                    ws.conditional_formatting.add(
                                        f"{get_column_letter(7)}{current_row}",
                                        CellIsRule(
                                            operator="notEqual",
                                            formula=[str(current_purchase.quantity_invoiced)],
                                            fill=yellow_fill,
                                        ),
                                    )

                                # --- COLUMN H: Producer unit price ---
                                cell = ws.cell(row=current_row, column=8, value=unit_price)
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                # --- COLUMN I: Deposit ---
                                cell = ws.cell(row=current_row, column=9, value=deposit)
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                # --- COLUMN J: Purchase price (Quantity * (Unit price + Deposit)) ---
                                cell = ws.cell(row=current_row, column=10)
                                cell.value = f"=ROUND(G{current_row}*(H{current_row}+I{current_row}),2)"
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                if year is None:
                                    calculated_price = (current_purchase.quantity_invoiced * price_with_deposit).quantize(RoundUpTo.TWO_DECIMALS)
                                    cell.font = blue_font
                                    ws.conditional_formatting.add(
                                        f"{get_column_letter(10)}{current_row}",
                                        CellIsRule(
                                            operator="notEqual",
                                            formula=[str(calculated_price)],
                                            fill=yellow_fill,
                                        ),
                                    )
                                    customer_total_price += calculated_price

                                # --- COLUMN K: VAT (Quantity * VAT rate) ---
                                cell = ws.cell(row=current_row, column=11)
                                cell.value = f"=G{current_row}*{customer_vat}"
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                # --- COLUMN L: Rule of 3 (placeholder) ---
                                ws.cell(row=current_row, column=12, value=EMPTY_STRING)

                                # --- COLUMN M: Comment ---
                                ws.cell(row=current_row, column=13, value=cap(current_purchase.comment, 100)).number_format = FORMAT_TEXT

                                # --- COLUMN N: VAT rate ---
                                ws.cell(row=current_row, column=14, value=current_purchase.offer_item.get_vat_level_display()).number_format = FORMAT_TEXT

                                # --- COLUMN O: Customer email (hidden) ---
                                ws.cell(row=current_row, column=15, value=current_purchase.customer.user.email).number_format = FORMAT_TEXT

                                # Add top border to first 5 columns
                                if format_marker == "A":
                                    ws.cell(row=current_row, column=5).border = thin_border

                                customer_item_count += 1
                                count_permanence_purchase += 1

                            current_purchase = next_purchase(purchases)
                            current_row += 1

                        # Write subtotal for customer if multiple items
                        if year is None and customer_item_count > 1:
                            # Same row as the latest product of the "rule group"
                            current_row -= 1
                            cell = ws.cell(row=current_row, column=12)
                            cell.value = f"=SUM(J{customer_start_row}:J{current_row})"
                            cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                            cell.font = blue_font
                            ws.conditional_formatting.add(
                                f"{get_column_letter(12)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(customer_total_price)],
                                    fill=yellow_fill,
                                ),
                            )
                            ws.cell(row=current_row, column=1, value="C")
                            current_row += 1

                    producer_price += customer_total_price

                else:
                    # =========================================================================
                    # MODE 2: invoice_by_basket = False
                    # Group by: Producer > Permanence > OfferItem
                    # =========================================================================
                    current_offer_item = current_purchase.offer_item
                    current_department = current_offer_item.department_for_customer
                    department_name = (
                        current_department.short_name_v2
                        if current_department is not None
                        else EMPTY_STRING
                    )
                    count_offer_item = 0
                    offer_item_start_row = current_row
                    offer_item_total_price = DECIMAL_ZERO

                    while (current_purchase is not None and
                           current_permanence.id == current_purchase.permanence_id and
                           current_offer_item == current_purchase.offer_item):

                        # Pre-calculate values
                        unit_price = current_purchase.get_producer_unit_price()
                        deposit = current_purchase.offer_item.unit_deposit.amount
                        price_with_deposit = unit_price + deposit
                        customer_vat = current_purchase.offer_item.customer_vat.amount

                        # --- COLUMN A: Format marker ---
                        format_marker = "A" if count_offer_item == 0 else "B"
                        ws.cell(row=current_row, column=1, value=format_marker)

                        if count_offer_item == 0:
                            if count_permanence_purchase == 0:
                                ws.cell(row=current_row, column=4).font = Font(bold=True)
                                permanence_start_row = current_row
                            ws.cell(row=current_row, column=1).font = Font(bold=True)

                        # --- COLUMN B: Purchase ID (hidden) ---
                        ws.cell(row=current_row, column=2, value=current_purchase.id)

                        # --- COLUMN C: Date ---
                        cell = ws.cell(row=current_row, column=3, value=current_permanence.permanence_date)
                        cell.number_format = FORMAT_DATE_DMYSLASH

                        # --- COLUMN D: Producer ---
                        ws.cell(row=current_row, column=4, value=current_producer.short_profile_name).number_format = FORMAT_TEXT

                        # --- COLUMN E: Product name ---
                        product_name = current_purchase.get_long_name_with_customer_price()
                        if department_name:
                            product_name = f"{product_name} - {department_name}"
                        cell = ws.cell(row=current_row, column=5, value=product_name)
                        cell.number_format = FORMAT_TEXT
                        if count_offer_item > 0:
                            cell.font = gray_font

                        # --- COLUMN F: Customer ---
                        cell = ws.cell(row=current_row, column=6, value=current_purchase.customer.short_basket_name)
                        cell.number_format = FORMAT_TEXT

                        # --- COLUMN G: Quantity accounted for ---
                        cell = ws.cell(row=current_row, column=7, value=current_purchase.quantity_invoiced)
                        cell.number_format = "#,##0.????"

                        if year is None:
                            cell.font = blue_font
                            ws.conditional_formatting.add(
                                f"{get_column_letter(7)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(current_purchase.quantity_invoiced)],
                                    fill=yellow_fill,
                                ),
                            )

                        # --- COLUMN H: Producer unit price ---
                        cell = ws.cell(row=current_row, column=8)

                        if count_offer_item == 0:
                            cell.value = unit_price
                            if year is None:
                                cell.font = blue_font
                                ws.conditional_formatting.add(
                                    f"{get_column_letter(8)}{current_row}",
                                    CellIsRule(
                                        operator="notEqual",
                                        formula=[str(unit_price)],
                                        fill=yellow_fill,
                                    ),
                                )
                        else:
                            cell.value = f"=H{offer_item_start_row}"

                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        # --- COLUMN I: Deposit ---
                        cell = ws.cell(row=current_row, column=9, value=deposit)
                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        # --- COLUMN J: Purchase price ---
                        if count_offer_item == 0:
                            cell = ws.cell(row=current_row, column=10)
                            cell.value = f"=ROUND(G{current_row}*(H{current_row}+I{current_row}),2)"
                        else:
                            cell = ws.cell(row=current_row, column=10)
                            cell.value = f"=ROUND(G{current_row}*(H{offer_item_start_row}+I{current_row}),2)"
                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        if year is None:
                            item_price = (current_purchase.quantity_invoiced * price_with_deposit).quantize(RoundUpTo.TWO_DECIMALS)
                            offer_item_total_price += item_price

                            if current_offer_item.order_unit in [OrderUnit.KG, OrderUnit.PC_KG, OrderUnit.LT]:
                                cell.font = blue_font
                            ws.conditional_formatting.add(
                                f"{get_column_letter(10)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(item_price)],
                                    fill=yellow_fill,
                                ),
                            )

                        # --- COLUMN K: VAT ---
                        cell = ws.cell(row=current_row, column=11)
                        cell.value = f"=G{current_row}*{customer_vat}"
                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        # --- COLUMN L: Rule of 3 (placeholder) ---
                        ws.cell(row=current_row, column=12, value=EMPTY_STRING)

                        # --- COLUMN M: Comment ---
                        ws.cell(row=current_row, column=13, value=cap(current_purchase.comment, 100)).number_format = FORMAT_TEXT

                        # --- COLUMN N: VAT rate ---
                        ws.cell(row=current_row, column=14, value=current_purchase.offer_item.get_vat_level_display()).number_format = FORMAT_TEXT

                        # --- COLUMN O: Customer email (hidden) ---
                        ws.cell(row=current_row, column=15, value=current_purchase.customer.user.email).number_format = FORMAT_TEXT

                        # Add top border to first 5 columns
                        if format_marker == "A":
                            ws.cell(row=current_row, column=5).border = thin_border

                        count_offer_item += 1
                        count_permanence_purchase += 1

                        current_purchase = next_purchase(purchases)
                        current_row += 1

                    # Write subtotal for offer_item if multiple weighted items
                    if year is None and count_offer_item > 1:
                        if (not current_offer_item.wrapped and
                            current_offer_item.order_unit in [OrderUnit.KG, OrderUnit.PC_KG, OrderUnit.LT]):
                            # Same row as the latest product of the "rule group"
                            current_row -= 1
                            cell = ws.cell(row=current_row, column=12)
                            cell.value = f"=SUM(J{offer_item_start_row}:J{current_row})"
                            cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                            cell.font = blue_font
                            ws.conditional_formatting.add(
                                f"{get_column_letter(12)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(offer_item_total_price)],
                                    fill=yellow_fill,
                                ),
                            )
                            ws.cell(row=current_row, column=1, value="D")
                            ws.cell(row=current_row, column=5).border = None
                            current_row += 1

                    producer_price += offer_item_total_price

            # Write total for permanence
            if count_permanence_purchase > 0:
                count_all_purchase += count_permanence_purchase

                # Calculate formulas for grand total
                price_formula = f"ROUND(SUM(J{permanence_start_row}:J{current_row - 1}),2)"
                purchase_price_all_purchase.append(price_formula)

                tax_formula = f"SUM(K{permanence_start_row}:K{current_row - 1})"
                tax_all_purchase.append(tax_formula)

                # Write total row
                cell = ws.cell(row=current_row, column=9)
                cell.value = f"{_('Total')} : {current_producer.short_profile_name} {current_permanence}"
                cell.number_format = FORMAT_TEXT
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="right")

                cell = ws.cell(row=current_row, column=10)
                cell.value = f"={price_formula}"
                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                cell.font = Font(bold=True)

                if year is None:
                    ws.conditional_formatting.add(
                        f"{get_column_letter(10)}{current_row}",
                        CellIsRule(
                            operator="notEqual",
                            formula=[str(producer_price)],
                            fill=yellow_fill,
                        ),
                    )

                cell = ws.cell(row=current_row, column=11)
                cell.value = f"={tax_formula}"
                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                current_row += 1
                for col in range(14):
                    ws.cell(row=current_row, column=col + 1).border = medium_dashed_border
                current_row += 1

        current_producer = next_row(producers)

    # Grand total row
    if count_all_purchase > 0:
        cell = ws.cell(row=current_row, column=9)
        cell.value = f"{_('Total')} : {title1}"
        cell.number_format = FORMAT_TEXT
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="right")

        cell = ws.cell(row=current_row, column=10)
        cell.value = f"={'+'.join(purchase_price_all_purchase)}"
        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
        cell.font = Font(bold=True)

        cell = ws.cell(row=current_row, column=11)
        cell.value = f"={'+'.join(tax_all_purchase)}"
        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

        current_row += 1
        for col in range(14):
            ws.cell(row=current_row, column=col + 1).border = medium_dashed_border

    ws.column_dimensions[get_column_letter(1)].hidden = True  # A: Format
    ws.column_dimensions[get_column_letter(2)].hidden = True  # B: Purchase ID
    ws.column_dimensions[get_column_letter(8)].hidden = True  # H: Unit price
    ws.column_dimensions[get_column_letter(15)].hidden = True  # O: Customer email

    return wb

@transaction.atomic
def import_purchase_sheet(
    worksheet, permanence=None, customer_2_id_dict=None, producer_2_id_dict=None
):
    """
    Import purchase data from Excel worksheet.

    Args:
        worksheet: Excel worksheet to import
        permanence: Permanence to import for
        customer_2_id_dict: Dictionary mapping customer names to IDs
        producer_2_id_dict: Dictionary mapping producer names to IDs

    Returns:
        tuple: (error: bool, error_msg: str)
    """
    error = False
    error_msg = None
    import_counter = 0
    header = get_header(worksheet)

    if not header:
        return True, _("No valid header found")

    current_row = 2
    array_purchase = []
    rule_of_3_source = DECIMAL_ZERO
    row = get_row(worksheet, header, current_row)

    while row and not error:
        try:
            row_format = row[_("Format")]
            if row_format in ["A", "B", "C", "D"]:
                import_counter += 1

                # Validate and get purchase
                if row[_("Id")] is None:
                    error = True
                    error_msg = _("Row %(row_num)d : No purchase id given.") % {"row_num": current_row}
                    break

                purchase_id = Decimal(row[_("Id")])
                purchase = Purchase.objects.filter(id=purchase_id).first()

                if purchase is None:
                    error = True
                    error_msg = _("Row %(row_num)d : No purchase corresponding to the given purchase id.") % {"row_num": current_row}
                    break

                if purchase.permanence_id != permanence.id:
                    error = True
                    error_msg = _("Row %(row_num)d : The given permanence doesn't own the given purchase id.") % {"row_num": current_row}
                    break

                offer_item = OfferItemReadOnly.objects.filter(id=purchase.offer_item_id).first()
                if offer_item is None:
                    error = True
                    error_msg = _("Row %(row_num)d : No offer_item corresponding to the given purchase id.") % {"row_num": current_row}
                    break

                # Validate producer
                producer_id = producer_2_id_dict.get(row[_("Producer")])
                if producer_id != purchase.producer_id:
                    error = True
                    error_msg = _("Row %(row_num)d : No valid producer.") % {"row_num": current_row}
                    break

                # Validate customer
                customer_name = str(row[_("Customer")])
                customer_id = customer_2_id_dict.get(customer_name)
                if customer_id != purchase.customer_id:
                    error = True
                    error_msg = _("Row %(row_num)d : No valid customer.") % {"row_num": current_row}
                    break

                comment = cap(row[_("Comment")] or EMPTY_STRING, 100)
                quantity_has_been_modified = False

                # Handle purchase price update
                producer_row_price = row[_("Purchase price")]
                if producer_row_price is not None:
                    producer_row_price = Decimal(producer_row_price).quantize(RoundUpTo.TWO_DECIMALS)
                    if purchase.purchase_price.amount != producer_row_price:
                        quantity_has_been_modified = True
                        producer_unit_price = (
                            offer_item.producer_unit_price.amount
                            + offer_item.unit_deposit.amount
                        ).quantize(RoundUpTo.TWO_DECIMALS)

                        if producer_unit_price != DECIMAL_ZERO:
                            purchase.quantity_invoiced = (producer_row_price / producer_unit_price).quantize(RoundUpTo.FOUR_DECIMALS)
                        else:
                            purchase.quantity_invoiced = DECIMAL_ZERO

                # Handle quantity update
                if not quantity_has_been_modified:
                    quantity_invoiced = (
                        DECIMAL_ZERO
                        if row[_("Quantity accounted for")] is None
                        else Decimal(row[_("Quantity accounted for")]).quantize(RoundUpTo.FOUR_DECIMALS)
                    )
                    if purchase.quantity_invoiced != quantity_invoiced:
                        purchase.quantity_invoiced = quantity_invoiced

                # Handle format A (start of group)
                if row_format == "A":
                    array_purchase = []
                    rule_of_3_source = DECIMAL_ZERO
                    producer_unit_price = row[_("Producer unit price")]
                    if producer_unit_price is not None and not purchase.producer.invoice_by_basket:
                        previous_price = purchase.get_producer_unit_price()
                        if producer_unit_price != previous_price:
                            offer_item.producer_unit_price = producer_unit_price
                            offer_item.save()

                # Save purchase
                purchase.comment = comment
                purchase.save()
                rule_of_3_source += purchase.purchase_price.amount
                array_purchase.append(purchase)

            # Handle rule of 3 for formats C and D
            if row_format in ["C", "D"]:
                rule_of_3_target = row[_("Rule of 3")]
                if rule_of_3_target is not None:
                    rule_of_3_target = Decimal(rule_of_3_target).quantize(RoundUpTo.TWO_DECIMALS)
                    if rule_of_3_target != rule_of_3_source:
                        max_purchase_counter = len(array_purchase)
                        if max_purchase_counter <= 1:
                            error = True
                            error_msg = _("Row %(row_num)d : Rule of 3 target in wrong context.") % {"row_num": current_row}
                            return error, error_msg

                        ratio = rule_of_3_target / rule_of_3_source if rule_of_3_source != DECIMAL_ZERO else (DECIMAL_ZERO if rule_of_3_target == DECIMAL_ZERO else DECIMAL_ONE)

                        # Apply rule of 3
                        if ratio != DECIMAL_ONE:
                            adjusted_invoice = DECIMAL_ZERO
                            for i, purchase_item in enumerate(array_purchase, start=1):
                                producer_unit_price = purchase_item.offer_item.producer_unit_price.amount

                                if i == max_purchase_counter:
                                    delta = rule_of_3_target - adjusted_invoice
                                    purchase_item.quantity_invoiced = (delta / producer_unit_price).quantize(RoundUpTo.FOUR_DECIMALS) if producer_unit_price != DECIMAL_ZERO else DECIMAL_ZERO
                                else:
                                    purchase_item.quantity_invoiced = (purchase_item.quantity_invoiced * ratio).quantize(RoundUpTo.FOUR_DECIMALS)
                                    adjusted_invoice += (purchase_item.quantity_invoiced * producer_unit_price).quantize(RoundUpTo.TWO_DECIMALS)

                                purchase_item.save()

            current_row += 1
            row = get_row(worksheet, header, current_row)

        except KeyError as e:
            error = True
            error_msg = _("Row %(row_num)d : A required column is missing %(error_msg)s.") % {"row_num": current_row, "error_msg": str(e)}
        except Exception as e:
            error = True
            error_msg = _("Row %(row_num)d : %(error_msg)s.") % {"row_num": current_row, "error_msg": str(e)}

    if import_counter == 0:
        error = True
        error_msg = _("Nothing to import.")

    return error, error_msg

def handle_uploaded_purchase(request, permanence, file_to_import, *args):
    """
    Handle uploaded purchase file.

    Args:
        request: HTTP request
        permanence: Permanence to import for
        file_to_import: Uploaded file
        *args: Additional arguments

    Returns:
        tuple: (error: bool, error_msg: str)
    """
    error = False
    error_msg = None

    wb = load_workbook(file_to_import)
    customer_buyinggroup_id, customer_2_id_dict = get_customer_2_id_dict()
    producer_buyinggroup_id, producer_2_id_dict = get_producer_2_id_dict()

    if customer_buyinggroup_id is None:
        error = True
        error_msg = _("At least one customer must represent the buying group.")
    elif producer_buyinggroup_id is None:
        error = True
        error_msg = _("At least one producer must represent the buying group.")

    if not error:
        if permanence is not None:
            if permanence.status == SaleStatus.SEND:
                ws_name = format_worksheet_title(permanence)
                if ws_name in wb.sheetnames:
                    ws = wb[ws_name]
                    error, error_msg = import_purchase_sheet(
                        ws,
                        permanence=permanence,
                        customer_2_id_dict=customer_2_id_dict,
                        producer_2_id_dict=producer_2_id_dict,
                    )
                    if error:
                        error_msg = f"{ws_name} > {error_msg}"
                else:
                    error = True
                    error_msg = _("The permanence doesn't exist.")
            else:
                error = True
                error_msg = _("The accounting has already been done")
        else:
            error = True
            error_msg = _("The permanence doesn't exist.")

    return error, error_msg