"""
Excel export for product prices list.

This module provides:
- export_product_prices(): Export product prices (producer or customer) to Excel
"""
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from openpyxl.styles import Border, Side
from openpyxl.styles.numbers import FORMAT_TEXT

from repanier.const import EMPTY_STRING
from repanier.models.product import Product
from repanier.tools import next_row
from repanier.xlsx.export_tools import new_landscape_a4_sheet, worksheet_set_header

def export_product_prices(producer_qs, wb=None, producer_prices=True):
    """
    Export product prices list to Excel.

    Args:
        producer_qs: QuerySet of producers to include
        wb: Existing workbook to append to (optional)
        producer_prices: If True, export producer prices; otherwise customer prices

    Returns:
        Workbook: Excel workbook with product prices
    """
    now = timezone.now()
    title = _("Producer prices list") if producer_prices else _("Customer prices list")
    subtitle = now.strftime(settings.DJANGO_SETTINGS_DATETIME)

    wb, ws = new_landscape_a4_sheet(wb, title, subtitle)

    # Get active products from selected producers
    products = (
        Product.objects
        .filter(
            is_active=True,
            is_into_offer=True,
            producer__in=producer_qs
        )
        .order_by(
            "department_for_customer",
            "long_name_v2",
            "order_average_weight",
        )
        .select_related("producer", "department_for_customer")
        .iterator()
    )

    current_product = next_row(products)

    if current_product is None:
        return wb

    # Build and write header from first product
    header = [
        (_("Reference"), 10),          # Col A - Product reference
        (_("Department"), 15),        # Col B - Department name
        (_("Wrapped"), 7),             # Col C - Wrapped status
        (_("Producer"), 15),           # Col D - Producer name
        (_("Long name"), 60),          # Col E - Product long name
        (_("VAT"), 10),                # Col F - VAT rate
    ]

    worksheet_set_header(ws, header)
    current_row = 2  # Move to first data row after header

    # Process each product
    while current_product is not None:
        # Prepare cell values
        reference = (
            current_product.reference
            if len(current_product.reference) < 36
            else EMPTY_STRING
        )

        department = (
            current_product.department_for_customer.short_name_v2
            if current_product.department_for_customer is not None
            else " "
        )

        wrapped = "{}".format(_("Yes") if current_product.wrapped else _("No"))

        # --- COLUMN A: Reference ---
        cell = ws.cell(row=current_row, column=1, value=reference)
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        # --- COLUMN B: Department ---
        cell = ws.cell(row=current_row, column=2, value=department)
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        # --- COLUMN C: Wrapped ---
        cell = ws.cell(row=current_row, column=3, value=wrapped)
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        # --- COLUMN D: Producer ---
        cell = ws.cell(row=current_row, column=4, value=current_product.producer.short_profile_name)
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        # --- COLUMN E: Long name ---
        cell = ws.cell(row=current_row, column=5, value=current_product.get_long_name_with_customer_price())
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        # --- COLUMN F: VAT ---
        cell = ws.cell(row=current_row, column=6, value=current_product.get_vat_level_display())
        cell.number_format = FORMAT_TEXT
        cell.border = Border(bottom=Side(style='hair'))

        current_row += 1
        current_product = next_row(products)

    return wb