# -*- coding: utf-8 -*-
from const import *
from django.contrib.sites.models import get_current_site
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from export_tools import *
from openpyxl.datavalidation import DataValidation, ValidationType, ValidationOperator
from openpyxl.style import Border
from openpyxl.style import Fill
from openpyxl.style import NumberFormat
from openpyxl.workbook import Workbook
from repanier.const import *
from repanier.models import BankAccount
from repanier.models import Customer
from repanier.models import CustomerInvoice
from repanier.models import Producer
from repanier.models import ProducerInvoice
from repanier.models import Purchase
from repanier.tools import get_invoice_unit


def export(permanence, customer=None, producer=None, wb=None, sheet_name=""):
    ws = None
    # Detail of what has been prepared
    purchase_set = Purchase.objects.none()
    if customer == None and producer == None:
        if ws == None:
            if wb == None:
                wb = Workbook()
                ws = wb.get_active_sheet()
            else:
                ws = wb.create_sheet()
            worksheet_setup_landscape_a4(ws, unicode(_('Account summary')) + " " + unicode(sheet_name),
                                         unicode(permanence))

        row_num = 0

        max_customer_invoice_id = 0
        customer_invoice_set = CustomerInvoice.objects.filter(permanence=permanence).order_by("-id")[:1]
        if customer_invoice_set:
            max_customer_invoice_id = customer_invoice_set[0].id

        customer_set = Customer.objects.all()
        for customer in customer_set:
            balance_before = 0
            payment = 0
            prepared = 0
            balance_after = 0
            customer_invoice_set = CustomerInvoice.objects.filter(customer=customer,
                                                                  permanence=permanence
            ).order_by()[:1]
            if customer_invoice_set:
                customer_invoice = customer_invoice_set[0]
                balance_before = customer_invoice.previous_balance
                payment = customer_invoice.bank_amount_in - customer_invoice.bank_amount_out
                prepared = customer_invoice.total_price_with_tax
                balance_after = customer_invoice.balance
            else:
                customer_invoice_set = CustomerInvoice.objects.filter(customer=customer,
                                                                      # Do not filter on date_balance : You may close the permanences in any date order
                                                                      # date_balance__lte=permanence.distribution_date,
                                                                      id__lt=max_customer_invoice_id
                ).order_by("-id")[:1]
                if customer_invoice_set:
                    customer_invoice = customer_invoice_set[0]
                    balance_before = customer_invoice.balance
                    balance_after = customer_invoice.balance
                else:
                    # No invoice yet.
                    balance_before = customer.initial_balance
                    balance_after = customer.initial_balance
            row = [
                (unicode(_('Name')), 40, customer.long_basket_name, NumberFormat.FORMAT_TEXT),
                (unicode(_('Balance before')), 15, balance_before,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Payment')), 10, payment, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Prepared')), 10, prepared, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Balance after')), 15, balance_after,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Name')), 20, customer.short_basket_name, NumberFormat.FORMAT_TEXT),
            ]

            if row_num == 0:
                worksheet_set_header(ws, row_num, row)
                row_num += 1

            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num][ROW_VALUE]
                c.style.number_format.format_code = row[col_num][ROW_FORMAT]

            row_num += 1

        row_break = row_num
        row_num += 1

        max_producer_invoice_id = 0
        producer_invoice_set = ProducerInvoice.objects.filter(permanence=permanence).order_by("-id")[:1]
        if producer_invoice_set:
            max_producer_invoice_id = producer_invoice_set[0].id
        producer_set = Producer.objects.filter(is_active=True)
        for producer in producer_set:
            balance_before = 0
            payment = 0
            prepared = 0
            balance_after = 0
            producer_invoice_set = ProducerInvoice.objects.filter(producer=producer,
                                                                  permanence=permanence
            ).order_by()[:1]
            if producer_invoice_set:
                producer_invoice = producer_invoice_set[0]
                balance_before = -producer_invoice.previous_balance
                payment = producer_invoice.bank_amount_out - producer_invoice.bank_amount_in
                prepared = producer_invoice.total_price_with_tax
                balance_after = -producer_invoice.balance
            else:
                producer_invoice_set = ProducerInvoice.objects.filter(producer=producer,
                                                                      # Do not filter on date_balance : You may close the permanences in any date order
                                                                      # date_balance__lte=permanence.distribution_date,
                                                                      id__lt=max_producer_invoice_id
                ).order_by("-id")[:1]
                if producer_invoice_set:
                    producer_invoice = producer_invoice_set[0]
                    balance_before = -producer_invoice.balance
                    balance_after = -producer_invoice.balance

            row = [
                (unicode(_('Name')), 40, producer.long_profile_name, NumberFormat.FORMAT_TEXT),
                (unicode(_('Balance before')), 15, balance_before,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Payment')), 10, payment, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Prepared')), 10, prepared, u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Balance after')), 15, balance_after,
                 u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '),
                (unicode(_('Name')), 20, producer.short_profile_name, NumberFormat.FORMAT_TEXT),
            ]

            if row_num == 0:
                worksheet_set_header(ws, row_num, row)
                row_num += 1

            for col_num in xrange(len(row)):
                c = ws.cell(row=row_num, column=col_num)
                c.value = row[col_num][ROW_VALUE]
                c.style.number_format.format_code = row[col_num][ROW_FORMAT]

            row_num += 1

        initial_bank_amount = 0
        final_bank_amount = 0
        bank_account_set = BankAccount.objects.filter(permanence=permanence,
                                                      producer=None,
                                                      customer=None).order_by()[:1]
        if bank_account_set:
            final_bank_amount = bank_account_set[0].bank_amount_in - bank_account_set[0].bank_amount_out
            bank_account_set = BankAccount.objects.filter(id__lt=bank_account_set[0].id,
                                                          producer=None,
                                                          customer=None).order_by("-id")[:1]
            if bank_account_set:
                initial_bank_amount = bank_account_set[0].bank_amount_in - bank_account_set[0].bank_amount_out

        row_num += 1
        c = ws.cell(row=row_num, column=1)
        c.value = initial_bank_amount
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
        c = ws.cell(row=row_num, column=4)
        formula = 'B%s+SUM(C%s:C%s)-SUM(C%s:C%s)' % (row_num + 1, 2, row_break, row_break + 2, row_num - 1)
        c.value = '=' + formula
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '

        row_num += 1
        c = ws.cell(row=row_num, column=4)
        formula = 'SUM(E%s:E%s)-SUM(E%s:E%s)' % (2, row_break, row_break + 2, row_num - 2)
        c.value = '=' + formula
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '

        row_num += 1
        c = ws.cell(row=row_num, column=4)
        c.value = final_bank_amount
        c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '

        ws = None

        purchase_set = Purchase.objects.filter(
            permanence_id=permanence.id, producer__isnull=False, customer__isnull=False).order_by(
            "producer__short_profile_name",
            "department_for_customer",
            "long_name",
            "customer__short_basket_name"
        )
    elif customer != None:
        purchase_set = Purchase.objects.filter(
            permanence_id=permanence.id, producer__isnull=False, customer=customer).order_by(
            "producer__short_profile_name",
            "department_for_customer",
            "long_name",
            "customer__short_basket_name"
        )
    else:
        purchase_set = Purchase.objects.filter(
            permanence_id=permanence.id, producer=producer, customer__isnull=False).order_by(
            "producer__short_profile_name",
            "department_for_customer",
            "long_name",
            "customer__short_basket_name"
        )

    row_num = 0

    hidde_column_vat = True
    hidde_column_compensation = True

    for purchase in purchase_set:

        if ws == None:
            if wb == None:
                wb = Workbook()
                ws = wb.get_active_sheet()
            else:
                ws = wb.create_sheet()
            if producer != None:
                # To the producer we speak of "payment".
                # This is the detail of the paiment to the producer, i.e. received products
                worksheet_setup_landscape_a4(ws, unicode(_('Payment')) + " - " + unicode(sheet_name),
                                             unicode(permanence))
            else:
                # To the customer we speak of "invoice".
                # This is the detail of the invoice, i.e. sold products
                worksheet_setup_landscape_a4(ws, unicode(_('Invoice')) + " - " + unicode(sheet_name),
                                             unicode(permanence))

        qty = purchase.quantity
        # if (qty != 0):
        a_total_price = 0
        a_total_vat = 0
        a_total_compensation = 0
        a_total_deposit = purchase.unit_deposit * purchase.quantity_deposit
        if purchase.invoiced_price_with_compensation:
            a_total_price = purchase.price_with_compensation + a_total_deposit
            a_total_vat = 0
            a_total_compensation = purchase.price_with_compensation - purchase.price_with_vat
        else:
            a_total_price = purchase.price_with_vat + a_total_deposit
            a_total_vat = 0
            if purchase.vat_level == VAT_400:
                a_total_vat = (purchase.price_with_vat * DECIMAL_0_06).quantize(THREE_DECIMALS)
            elif purchase.vat_level == VAT_500:
                a_total_vat = (purchase.price_with_vat * DECIMAL_0_12).quantize(THREE_DECIMALS)
            elif purchase.vat_level == VAT_600:
                a_total_vat = (purchase.price_with_vat * DECIMAL_0_21).quantize(THREE_DECIMALS)
            a_total_compensation = 0

        if a_total_vat != 0:
            hidde_column_vat = False
        if a_total_compensation != 0:
            hidde_column_compensation = False
        a_unit_price = ( a_total_price / qty ).quantize(TWO_DECIMALS) if qty != 0 else 0

        unit = get_invoice_unit(order_unit=purchase.order_unit, qty=qty)
        row = [
            (unicode(_("Producer")), 15, purchase.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Basket")), 20, purchase.customer.short_basket_name, NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Department")), 15,
             purchase.product.department_for_customer.short_name if purchase.product != None else "",
             NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Product")), 60, purchase.long_name, NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Quantity")), 10, qty, '#,##0.????',
             True if purchase.order_unit in [PRODUCT_ORDER_UNIT_LOOSE_PC_KG,
                                             PRODUCT_ORDER_UNIT_NAMED_PC_KG] else False),
            (unicode(_("Unit")), 10, unit, NumberFormat.FORMAT_TEXT, False),
            (unicode(_("Unit invoided price, deposit included")), 10, a_unit_price,
             u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
            (unicode(_("Total invoiced price, deposit included")), 10, a_total_price,
             u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ ', False),
            (unicode(_("Vat")), 10, a_total_vat, u'_ € * #,##0.000_ ;_ € * -#,##0.000_ ;_ € * "-"??_ ;_ @_ ', False),
            (unicode(_("Compensation")), 10, a_total_compensation,
             u'_ € * #,##0.000_ ;_ € * -#,##0.000_ ;_ € * "-"??_ ;_ @_ ', False),
            (unicode(_("comment")), 30, purchase.comment, NumberFormat.FORMAT_TEXT, False),
        ]

        if row_num == 0:
            worksheet_set_header(ws, row_num, row)
            row_num += 1

        for col_num in xrange(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = row[col_num][ROW_VALUE]
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]
            if row[col_num][ROW_BOX]:
                c.style.borders.top.border_style = Border.BORDER_THIN
                c.style.borders.bottom.border_style = Border.BORDER_THIN
                c.style.borders.left.border_style = Border.BORDER_THIN
                c.style.borders.right.border_style = Border.BORDER_THIN
            else:
                c.style.borders.bottom.border_style = Border.BORDER_HAIR
            if col_num == 7:
                c.style.font.bold = True

        row_num += 1

    if wb != None:
        if hidde_column_vat:
            ws.column_dimensions[get_column_letter(9)].visible = False
        if hidde_column_compensation:
            ws.column_dimensions[get_column_letter(10)].visible = False

        current_site_name = Site.objects.get_current().name
        for col_num in xrange(11):
            c = ws.cell(row=row_num, column=col_num)
            c.style.borders.top.border_style = Border.BORDER_THIN
            c.style.borders.bottom.border_style = Border.BORDER_THIN
            if col_num == 1:
                c.value = unicode(_("Total Price")) + " " + current_site_name
            # c.style.font.bold = True
            if col_num == 7:
                formula = 'SUM(H%s:H%s)' % (2, row_num)
                c.value = '=' + formula
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True
            if col_num == 8:
                formula = 'SUM(I%s:I%s)' % (2, row_num)
                c.value = '=' + formula
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True
            if col_num == 9:
                formula = 'SUM(J%s:J%s)' % (2, row_num)
                c.value = '=' + formula
                c.style.number_format.format_code = u'_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * "-"??_ ;_ @_ '
                c.style.font.bold = True

    return wb


def admin_export(request, queryset):
    current_site = get_current_site(request)
    permanence = queryset.first()
    response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = (unicode(_("Accounting report")) + u" - " + permanence.__unicode__() + u'.xlsx').encode('latin-1',
                                                                                                       errors='ignore')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    wb = export(permanence=permanence, wb=None, sheet_name=current_site.name)
    if wb != None:
        wb.save(response)
    return response