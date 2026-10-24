"""
Importation de factures d'achat à partir de fichiers Excel.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from openpyxl import load_workbook

from repanier.const import EMPTY_STRING, SaleStatus, DICT_ALL_VAT_REVERSE
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.tools import (
    get_reverse_invoice_unit,
    create_or_update_one_purchase,
    reorder_offer_items,
    reorder_purchases,
    round_tva,
)
from repanier.xlsx.import_tools import get_customer_email_2_id_dict, get_header, get_row


def import_invoice_sheet(
    worksheet, invoice_reference=EMPTY_STRING, customer_2_id_dict=None, producer=None
):
    """
    Lit une feuille de facturation Excel et crée/met à jour la permanence, les produits et les achats correspondants.
    """
    error = False
    error_msg = None
    header = get_header(worksheet)
    if header:
        now = timezone.now().date()
        import_counter = 0
        row_num = 2
        column_name = EMPTY_STRING
        sid = transaction.savepoint()
        try:

            permanence = Permanence.objects.create(
                permanence_date=now,
                short_name_v2=invoice_reference,
                status=SaleStatus.SEND,
                highest_status=SaleStatus.SEND,
            )
            permanence.producers.add(producer)
            row = get_row(worksheet, header, row_num)
            while row and not error:
                column_name = _("Customer")
                customer_name = row[column_name]
                if customer_name:
                    if customer_name in customer_2_id_dict:
                        customer_id = customer_2_id_dict[customer_name]
                    else:
                        error = True
                        error_msg = _("Row %(row_num)d : No valid customer.") % {
                            "row_num": row_num + 1
                        }
                        break
                    column_name = _("Reference")
                    product_reference = row[column_name] or EMPTY_STRING
                    column_name = _("Unit")
                    unit = row[column_name]
                    order_unit = get_reverse_invoice_unit(unit)
                    column_name = _("VAT rate")
                    vat = row[column_name]
                    vat_level = DICT_ALL_VAT_REVERSE[round_tva(Decimal(vat))]
                    product = Product.objects.filter(
                        producer_id=producer.id, reference=product_reference
                    ).first()
                    if product is None:
                        product = Product.objects.create(
                            producer=producer, reference=product_reference
                        )
                    column_name = _("Product")
                    long_name = row[column_name]
                    column_name = _("Customer unit price")
                    product.producer_unit_price = row[column_name]
                    column_name = _("Deposit")
                    product.unit_deposit = row[column_name]
                    product.order_unit = order_unit
                    product.vat_level = vat_level
                    column_name = _("Wrapped")
                    product.wrapped = row[column_name]
                    qty_and_price_display = product.get_qty_and_price_display(
                        customer_price=False
                    ).lstrip()
                    if long_name.endswith(qty_and_price_display):
                        long_name = long_name[: -len(qty_and_price_display)]
                    product.long_name_v2 = long_name[:100]
                    product.save()
                    offer_item = product.get_or_create_offer_item(permanence)
                    column_name = _("Quantity")
                    qty = row[column_name]
                    column_name = _("Comment")
                    comment = row[column_name]
                    create_or_update_one_purchase(
                        customer_id=customer_id,
                        offer_item=offer_item,
                        status=SaleStatus.SEND,
                        q_order=Decimal(qty),
                        batch_job=True,
                        comment=comment or EMPTY_STRING,
                    )
                    import_counter += 1

                row_num += 1
                row = get_row(worksheet, header, row_num)
            reorder_offer_items(permanence.id)
            reorder_purchases(permanence.id)

        except KeyError as e:
            error = True
            error_msg = _(
                "Row %(row_num)d : A required column %(column_name)s is missing %(error_msg)s."
            ) % {
                "row_num": row_num + 1,
                "column_name": column_name,
                "error_msg": str(e),
            }
        except Exception as e:
            error = True
            error_msg = _("Row %(row_num)d : %(error_msg)s.") % {
                "row_num": row_num + 1,
                "error_msg": str(e),
            }
        if not error and import_counter == 0:
            error = True
            error_msg = "{}".format(_("Nothing to import."))
        if error:
            transaction.savepoint_rollback(sid)
        else:
            transaction.savepoint_commit(sid)
    return error, error_msg


def handle_uploaded_invoice(
    request, permanences, file_to_import, producer, invoice_reference
):
    """
    Point d'entrée pour traiter un fichier Excel de facturation téléversé.
    """
    if producer is None:
        error = True
        error_msg = _("A producer must be given.")
    else:
        wb = load_workbook(file_to_import)
        customer_2_id_dict = get_customer_email_2_id_dict()
        ws = wb.worksheets[0]
        error, error_msg = import_invoice_sheet(
            ws,
            invoice_reference=invoice_reference,
            customer_2_id_dict=customer_2_id_dict,
            producer=producer,
        )
    return error, error_msg