"""
Export Excel des données d'achat pour vérification comptable.
"""

from django.utils.translation import gettext_lazy as _
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment
from openpyxl.styles.numbers import FORMAT_TEXT, FORMAT_DATE_DMYSLASH
from openpyxl.utils import get_column_letter

from repanier.apps import REPANIER_SETTINGS_CURRENCY_XLSX
from repanier.const import DECIMAL_ZERO, EMPTY_STRING, OrderUnit, RoundUpTo, SaleStatus
from repanier.models.purchase import Purchase
from repanier.models.producer import Producer
from repanier.tools import next_row, cap
from repanier.xlsx.export_tools import new_landscape_a4_sheet
from repanier.xlsx.xlsx_styles import (
    FILL_YELLOW,
    FONT_BLUE,
    FONT_GRAY,
    FONT_BOLD,
    BORDER_TOP_THIN,
    BORDER_BOTTOM_MEDIUM_DASHED,
)


def next_purchase(purchases):
    """
    Récupère l'achat valide suivant dans l'itérateur, en sautant les quantités nulles et les articles de type consigne.
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
    Exporte les données d'achat vers Excel pour vérification comptable.
    """
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
    current_row = 2
    count_all_purchase = 0
    purchase_price_all_purchase = []
    tax_all_purchase = []

    while current_producer is not None:
        producer_price = DECIMAL_ZERO
        producer_start_row = current_row

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
                                unit_price = current_purchase.get_producer_unit_price()
                                deposit = current_purchase.offer_item.unit_deposit.amount
                                price_with_deposit = unit_price + deposit
                                customer_vat = current_purchase.offer_item.customer_vat.amount

                                format_marker = "A" if customer_item_count == 0 else "B"
                                ws.cell(row=current_row, column=1, value=format_marker)

                                if customer_item_count == 0:
                                    if count_permanence_purchase == 0:
                                        ws.cell(row=current_row, column=4).font = FONT_BOLD
                                        permanence_start_row = current_row
                                    ws.cell(row=current_row, column=1).font = FONT_BOLD

                                ws.cell(row=current_row, column=2, value=current_purchase.id)

                                cell = ws.cell(row=current_row, column=3, value=current_permanence.permanence_date)
                                cell.number_format = FORMAT_DATE_DMYSLASH

                                ws.cell(row=current_row, column=4, value=current_producer.short_profile_name).number_format = FORMAT_TEXT

                                product_name = current_purchase.get_long_name_with_customer_price()
                                if department_name:
                                    product_name = f"{product_name} - {department_name}"
                                cell = ws.cell(row=current_row, column=5, value=product_name)
                                cell.number_format = FORMAT_TEXT

                                cell = ws.cell(row=current_row, column=6, value=current_customer.short_basket_name)
                                cell.number_format = FORMAT_TEXT
                                if customer_item_count == 0 and customer is None:
                                    cell.font = FONT_BOLD

                                cell = ws.cell(row=current_row, column=7, value=current_purchase.quantity_invoiced)
                                cell.number_format = "#,##0.????"

                                if year is None:
                                    cell.font = FONT_BLUE
                                    ws.conditional_formatting.add(
                                        f"{get_column_letter(7)}{current_row}",
                                        CellIsRule(
                                            operator="notEqual",
                                            formula=[str(current_purchase.quantity_invoiced)],
                                            fill=FILL_YELLOW,
                                        ),
                                    )

                                cell = ws.cell(row=current_row, column=8, value=unit_price)
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                cell = ws.cell(row=current_row, column=9, value=deposit)
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                cell = ws.cell(row=current_row, column=10)
                                cell.value = f"=ROUND(G{current_row}*(H{current_row}+I{current_row}),2)"
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                if year is None:
                                    calculated_price = (current_purchase.quantity_invoiced * price_with_deposit).quantize(RoundUpTo.TWO_DECIMALS)
                                    cell.font = FONT_BLUE
                                    ws.conditional_formatting.add(
                                        f"{get_column_letter(10)}{current_row}",
                                        CellIsRule(
                                            operator="notEqual",
                                            formula=[str(calculated_price)],
                                            fill=FILL_YELLOW,
                                        ),
                                    )
                                    customer_total_price += calculated_price

                                cell = ws.cell(row=current_row, column=11)
                                cell.value = f"=G{current_row}*{customer_vat}"
                                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                                ws.cell(row=current_row, column=12, value=EMPTY_STRING)
                                ws.cell(row=current_row, column=13, value=cap(current_purchase.comment, 100)).number_format = FORMAT_TEXT
                                ws.cell(row=current_row, column=14, value=current_purchase.offer_item.get_vat_level_display()).number_format = FORMAT_TEXT
                                ws.cell(row=current_row, column=15, value=current_purchase.customer.user.email).number_format = FORMAT_TEXT

                                if format_marker == "A":
                                    ws.cell(row=current_row, column=5).border = BORDER_TOP_THIN

                                customer_item_count += 1
                                count_permanence_purchase += 1

                            current_purchase = next_purchase(purchases)
                            current_row += 1

                        if year is None and customer_item_count > 1:
                            current_row -= 1
                            cell = ws.cell(row=current_row, column=12)
                            cell.value = f"=SUM(J{customer_start_row}:J{current_row})"
                            cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                            cell.font = FONT_BLUE
                            ws.conditional_formatting.add(
                                f"{get_column_letter(12)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(customer_total_price)],
                                    fill=FILL_YELLOW,
                                ),
                            )
                            ws.cell(row=current_row, column=1, value="C")
                            current_row += 1

                    producer_price += customer_total_price

                else:
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

                        unit_price = current_purchase.get_producer_unit_price()
                        deposit = current_purchase.offer_item.unit_deposit.amount
                        price_with_deposit = unit_price + deposit
                        customer_vat = current_purchase.offer_item.customer_vat.amount

                        format_marker = "A" if count_offer_item == 0 else "B"
                        ws.cell(row=current_row, column=1, value=format_marker)

                        if count_offer_item == 0:
                            if count_permanence_purchase == 0:
                                ws.cell(row=current_row, column=4).font = FONT_BOLD
                                permanence_start_row = current_row
                            ws.cell(row=current_row, column=1).font = FONT_BOLD

                        ws.cell(row=current_row, column=2, value=current_purchase.id)

                        cell = ws.cell(row=current_row, column=3, value=current_permanence.permanence_date)
                        cell.number_format = FORMAT_DATE_DMYSLASH

                        ws.cell(row=current_row, column=4, value=current_producer.short_profile_name).number_format = FORMAT_TEXT

                        product_name = current_purchase.get_long_name_with_customer_price()
                        if department_name:
                            product_name = f"{product_name} - {department_name}"
                        cell = ws.cell(row=current_row, column=5, value=product_name)
                        cell.number_format = FORMAT_TEXT
                        if count_offer_item > 0:
                            cell.font = FONT_GRAY

                        cell = ws.cell(row=current_row, column=6, value=current_purchase.customer.short_basket_name)
                        cell.number_format = FORMAT_TEXT

                        cell = ws.cell(row=current_row, column=7, value=current_purchase.quantity_invoiced)
                        cell.number_format = "#,##0.????"

                        if year is None:
                            cell.font = FONT_BLUE
                            ws.conditional_formatting.add(
                                f"{get_column_letter(7)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(current_purchase.quantity_invoiced)],
                                    fill=FILL_YELLOW,
                                ),
                            )

                        cell = ws.cell(row=current_row, column=8)

                        if count_offer_item == 0:
                            cell.value = unit_price
                            if year is None:
                                cell.font = FONT_BLUE
                                ws.conditional_formatting.add(
                                    f"{get_column_letter(8)}{current_row}",
                                    CellIsRule(
                                        operator="notEqual",
                                        formula=[str(unit_price)],
                                        fill=FILL_YELLOW,
                                    ),
                                )
                        else:
                            cell.value = f"=H{offer_item_start_row}"

                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        cell = ws.cell(row=current_row, column=9, value=deposit)
                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

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
                                cell.font = FONT_BLUE
                            ws.conditional_formatting.add(
                                f"{get_column_letter(10)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(item_price)],
                                    fill=FILL_YELLOW,
                                ),
                            )

                        cell = ws.cell(row=current_row, column=11)
                        cell.value = f"=G{current_row}*{customer_vat}"
                        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                        ws.cell(row=current_row, column=12, value=EMPTY_STRING)
                        ws.cell(row=current_row, column=13, value=cap(current_purchase.comment, 100)).number_format = FORMAT_TEXT
                        ws.cell(row=current_row, column=14, value=current_purchase.offer_item.get_vat_level_display()).number_format = FORMAT_TEXT
                        ws.cell(row=current_row, column=15, value=current_purchase.customer.user.email).number_format = FORMAT_TEXT

                        if format_marker == "A":
                            ws.cell(row=current_row, column=5).border = BORDER_TOP_THIN

                        count_offer_item += 1
                        count_permanence_purchase += 1

                        current_purchase = next_purchase(purchases)
                        current_row += 1

                    if year is None and count_offer_item > 1:
                        if (not current_offer_item.wrapped and
                            current_offer_item.order_unit in [OrderUnit.KG, OrderUnit.PC_KG, OrderUnit.LT]):
                            current_row -= 1
                            cell = ws.cell(row=current_row, column=12)
                            cell.value = f"=SUM(J{offer_item_start_row}:J{current_row})"
                            cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                            cell.font = FONT_BLUE
                            ws.conditional_formatting.add(
                                f"{get_column_letter(12)}{current_row}",
                                CellIsRule(
                                    operator="notEqual",
                                    formula=[str(offer_item_total_price)],
                                    fill=FILL_YELLOW,
                                ),
                            )
                            ws.cell(row=current_row, column=1, value="D")
                            ws.cell(row=current_row, column=5).border = None
                            current_row += 1

                    producer_price += offer_item_total_price

            if count_permanence_purchase > 0:
                count_all_purchase += count_permanence_purchase

                price_formula = f"ROUND(SUM(J{permanence_start_row}:J{current_row - 1}),2)"
                purchase_price_all_purchase.append(price_formula)

                tax_formula = f"SUM(K{permanence_start_row}:K{current_row - 1})"
                tax_all_purchase.append(tax_formula)

                cell = ws.cell(row=current_row, column=9)
                cell.value = f"{_('Total')} : {current_producer.short_profile_name} {current_permanence}"
                cell.number_format = FORMAT_TEXT
                cell.font = FONT_BOLD
                cell.alignment = Alignment(horizontal="right")

                cell = ws.cell(row=current_row, column=10)
                cell.value = f"={price_formula}"
                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
                cell.font = FONT_BOLD

                if year is None:
                    ws.conditional_formatting.add(
                        f"{get_column_letter(10)}{current_row}",
                        CellIsRule(
                            operator="notEqual",
                            formula=[str(producer_price)],
                            fill=FILL_YELLOW,
                        ),
                    )

                cell = ws.cell(row=current_row, column=11)
                cell.value = f"={tax_formula}"
                cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

                current_row += 1
                for col in range(14):
                    ws.cell(row=current_row, column=col + 1).border = BORDER_BOTTOM_MEDIUM_DASHED
                current_row += 1

        current_producer = next_row(producers)

    if count_all_purchase > 0:
        cell = ws.cell(row=current_row, column=9)
        cell.value = f"{_('Total')} : {title1}"
        cell.number_format = FORMAT_TEXT
        cell.font = FONT_BOLD
        cell.alignment = Alignment(horizontal="right")

        cell = ws.cell(row=current_row, column=10)
        cell.value = f"={'+'.join(purchase_price_all_purchase)}"
        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX
        cell.font = FONT_BOLD

        cell = ws.cell(row=current_row, column=11)
        cell.value = f"={'+'.join(tax_all_purchase)}"
        cell.number_format = REPANIER_SETTINGS_CURRENCY_XLSX

        current_row += 1
        for col in range(14):
            ws.cell(row=current_row, column=col + 1).border = BORDER_BOTTOM_MEDIUM_DASHED

    ws.column_dimensions[get_column_letter(1)].hidden = True
    ws.column_dimensions[get_column_letter(2)].hidden = True
    ws.column_dimensions[get_column_letter(8)].hidden = True
    ws.column_dimensions[get_column_letter(15)].hidden = True

    return wb