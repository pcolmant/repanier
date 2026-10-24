"""
Façade d'accès pour les exports Excel des commandes Repanier.
Garantit une rétrocompatibilité exacte avec le reste de l'application.
"""

from django.utils.translation import gettext_lazy as _
from repanier.xlsx.export_tools import format_worksheet_title
from repanier.xlsx.xlsx_order_customer import (
    export_abstract,
    export_customer_label,
    export_preparation,
    export_customer,
)
from repanier.xlsx.xlsx_order_producer import (
    export_producer_by_product,
    export_producer_by_customer,
)
from repanier.xlsx.xlsx_stock import export_permanence_stock


def generate_customer_xlsx(
    permanence, deliveries_id=(), customer_invoice=None, group=False
):
    """
    Génère le classeur Excel complet pour les commandes clients.
    """
    if customer_invoice is not None:
        wb = export_customer(
            permanence=permanence,
            customer_invoice=customer_invoice,
            xlsx_formula=False,
            wb=None,
        )
        return wb, None
    else:
        wb = export_abstract(
            permanence=permanence, deliveries_id=deliveries_id, group=group, wb=None
        )
        if wb is not None:
            abstract_ws = wb.active
            ws_preparation_title = format_worksheet_title(_("Preparation"))
            ws_customer_title = format_worksheet_title(_("Basket control"))
            wb = export_customer_label(
                permanence=permanence, deliveries_id=deliveries_id, wb=wb
            )
            wb = export_preparation(
                permanence=permanence, deliveries_id=deliveries_id, wb=wb
            )
            wb = export_customer(
                permanence=permanence, deliveries_id=deliveries_id, deposit=True, wb=wb
            )
            wb = export_customer(
                permanence=permanence,
                deliveries_id=deliveries_id,
                deposit=False,
                wb=wb,
                ws_preparation_title=ws_preparation_title,
            )
            wb = export_permanence_stock(
                permanence=permanence,
                deliveries_id=deliveries_id,
                customer_price=True,
                wb=wb,
                ws_customer_title=ws_customer_title,
            )
            return wb, abstract_ws
        else:
            return


def generate_producer_xlsx(permanence, producer=None, wb=None):
    """
    Génère le classeur Excel complet pour un producteur.
    """
    wb = export_producer_by_product(permanence=permanence, producer=producer, wb=wb)
    if wb is not None:
        wb = export_producer_by_customer(
            permanence=permanence, producer=producer, wb=wb
        )
    return wb