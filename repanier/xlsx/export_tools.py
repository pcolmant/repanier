import re

from django.contrib.sites.models import Site
from django.utils.translation import gettext_lazy as _
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from repanier.models.staff import Staff
from repanier.xlsx.const import *

INVALID_WORKSHEET_TITLE_CHARS = re.compile(r"[\\/*?:\[\]]")


def format_worksheet_title(title):
    """Return a valid Excel worksheet title while preserving Unicode text."""
    title = INVALID_WORKSHEET_TITLE_CHARS.sub("-", str(title)).strip()
    return title[:31] or "Sheet"


def _new_a4_sheet(
    workbook,
    title1,
    title2,
    orientation,
    header=None,
    add_print_title=True,
):
    """Create a worksheet and apply the settings shared by all A4 exports."""
    if workbook is None:
        workbook = Workbook()
        worksheet = workbook.active
    else:
        worksheet = workbook.create_sheet()

    worksheet.title = format_worksheet_title(title1)
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.page_setup.orientation = orientation
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToHeight = 0
    worksheet.page_setup.fitToWidth = 1
    worksheet.print_gridlines = True
    if add_print_title:
        worksheet.print_title_rows = "1:1"
        worksheet.freeze_panes = "A2"
    worksheet.oddHeader.left_header = worksheet.evenHeader.left_header = Site.objects.get_current().name
    worksheet.oddHeader.left_footer = worksheet.evenHeader.left_footer = "{}".format(title2)
    worksheet.oddHeader.center_footer = worksheet.evenHeader.center_footer = "{}".format(title1)
    worksheet.oddHeader.right_footer = worksheet.evenHeader.right_footer = "Page &[Page]/&[Pages]"
    order_responsible = Staff.get_or_create_order_responsible()
    invoice_responsible = Staff.get_or_create_invoice_responsible()
    separator = chr(10) + " "
    worksheet.oddHeader.right_header = worksheet.evenHeader.right_header = separator.join(
        (order_responsible["signature"], invoice_responsible["signature"])
    )

    if header is not None:
        worksheet_set_header(worksheet, header)

    return workbook, worksheet


def new_portrait_a4_sheet(workbook, title1, title2, header=None, add_print_title=True):
    """Create and configure a portrait-oriented A4 worksheet.

    A new workbook is created when ``workbook`` is ``None``. Otherwise, a new
    worksheet is appended to the supplied workbook. The optional header is
    written on the first row.
    """
    return _new_a4_sheet(
        workbook,
        title1,
        title2,
        orientation="portrait",
        header=header,
        add_print_title=add_print_title,
    )


def new_landscape_a4_sheet(workbook, title1, title2, header=None, add_print_title=True):
    """Create and configure a landscape-oriented A4 worksheet.

    A new workbook is created when ``workbook`` is ``None``. Otherwise, a new
    worksheet is appended to the supplied workbook. The optional header is
    written on the first row.
    """
    return _new_a4_sheet(
        workbook,
        title1,
        title2,
        orientation="landscape",
        header=header,
        add_print_title=add_print_title,
    )


def worksheet_set_header(worksheet, header):
    """Format the first worksheet row as column headers.

    Each header entry has the following structure::

        (title, width, value, format, boxed)

    The fields used here are identified by these constants::

        ROW_TITLE = 0
        ROW_WIDTH = 1
    """
    # Worksheet columns are one-based, while enumerate normally starts at zero.
    for column, item in enumerate(header, start=1):
        c = worksheet.cell(row=1, column=column)

        # Set the column title and format the header cell.
        c.value = "{}".format(item[ROW_TITLE])
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=False)
        c.border = Border(bottom=Side(style='thin'))

        # Apply the configured width to the corresponding worksheet column.
        dimensions = worksheet.column_dimensions[get_column_letter(column)]
        dimensions.width = item[ROW_WIDTH]

        # Keep identifiers in the export while hiding them from normal view.
        if item[ROW_TITLE] == _("Id"):
            dimensions.hidden = True
