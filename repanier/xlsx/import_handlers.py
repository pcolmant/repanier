"""
Generic handlers for processing uploaded Excel files.
Centralizes common logic for loading, validating, and importing Excel data.
"""

from openpyxl import load_workbook
from django.utils.translation import gettext_lazy as _


def process_uploaded_excel(
    file_to_import,
    pre_validation_func=None,
    sheet_getter_func=None,
    import_func=None,
    max_file_size=1_000_000,  # 1 MB in bytes
    **kwargs
):
    """
    Generic processing of an uploaded Excel file.

    Args:
        file_to_import: Django UploadedFile object.
        pre_validation_func: Business validation function (returns (error: bool, error_msg: str)).
        sheet_getter_func: Function to select the worksheet (returns worksheet or None).
        import_func: Import function (returns (error: bool, error_msg: str)).
        max_file_size: Maximum allowed file size in bytes.
        **kwargs: Additional arguments passed to helper functions (e.g., producer, permanence).

    Returns:
        tuple: (error: bool, error_msg: str) where error_msg is None if no error occurred.
    """
    # 1. Basic file validation (size and extension)
    if file_to_import.size > max_file_size:
        return True, _("File size must be <= 1MB.")
    # Accept both .xlsx and .xls extensions
    if not (file_to_import.name.lower().endswith('.xlsx') or file_to_import.name.lower().endswith('.xls')):
        return True, _("File must have .xlsx or .xls extension.")

    # 2. Business-specific validation (optional)
    if pre_validation_func:
        error, error_msg = pre_validation_func(**kwargs)
        if error:
            return error, error_msg

    # 3. Load the workbook
    try:
        wb = load_workbook(file_to_import)
    except Exception as e:
        return True, _("Invalid Excel file: {}").format(str(e))

    # 4. Select the worksheet
    if sheet_getter_func:
        ws = sheet_getter_func(wb, **kwargs)
        if ws is None:
            return True, _("Required worksheet not found.")
    else:
        ws = wb.worksheets[0]  # Default: use first sheet

    # 5. Call the specialized import function
    return import_func(ws, **kwargs)


# --- Business validation functions ---

def validate_invoice_upload(producer, **_):
    """
    Validate invoice upload: a producer is required.

    Args:
        producer: Producer model instance or None.

    Returns:
        tuple: (error: bool, error_msg: str)
    """
    if producer is None:
        return True, _("A producer must be given.")
    return False, None


def validate_purchase_upload(permanence, **_):
    """
    Validate purchase upload: permanence must exist and be in SEND status.

    Args:
        permanence: Permanence model instance or None.

    Returns:
        tuple: (error: bool, error_msg: str)
    """
    from repanier.const import SaleStatus
    if permanence is None:
        return True, _("The permanence doesn't exist.")
    if permanence.status != SaleStatus.SEND:
        return True, _("The accounting has already been done.")
    return False, None


# --- Worksheet selection functions ---

def get_first_sheet(wb, **_):
    """
    Always return the first worksheet in the workbook.

    Args:
        wb: OpenPyXL workbook object.

    Returns:
        Worksheet: First worksheet.
    """
    return wb.worksheets[0]


def get_permanence_sheet(wb, permanence, **_):
    """
    Return the worksheet corresponding to a permanence.

    Args:
        wb: OpenPyXL workbook object.
        permanence: Permanence model instance.

    Returns:
        Worksheet or None: The worksheet if found, None otherwise.
    """
    from repanier.xlsx.export_tools import format_worksheet_title
    ws_name = format_worksheet_title(permanence)
    return wb[ws_name] if ws_name in wb.sheetnames else None
