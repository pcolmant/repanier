# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.utils import timezone
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.xlsx.export_tools import *
from repanier.const import *
from repanier.models.product import Product
from repanier.tools import next_row


def export_customer_prices(producer_qs, wb=None, producer_prices=True):
    now = timezone.now()
    if producer_prices:
        wb, ws = new_landscape_a4_sheet(wb, "%s" % _("Producer prices list"),
                                        now.strftime(settings.DJANGO_SETTINGS_DATETIME))
    else:
        wb, ws = new_landscape_a4_sheet(wb, "%s" % _("Customer prices list"),
                                        now.strftime(settings.DJANGO_SETTINGS_DATETIME))
    row_num = 0
    products = Product.objects.filter(
        is_active=True,
        is_into_offer=True,
        translations__language_code=translation.get_language(),
        producer__in=producer_qs
    ).order_by(
        "department_for_customer",
        "translations__long_name",
        "order_average_weight",
    ).select_related(
        'producer', 'department_for_customer'
    ).iterator()
    product = next_row(products)
    while product is not None:
        row = [
            (_("Reference"), 10, product.reference if len(product.reference) < 36 else EMPTY_STRING,
             NumberFormat.FORMAT_TEXT, False),
            (_("Department"), 15,
             product.department_for_customer.short_name if product.department_for_customer is not None else " ",
             NumberFormat.FORMAT_TEXT, False),
            # (_("is_into_offer"), 7, _("Yes") if product.is_into_offer else _("No"),
            #  NumberFormat.FORMAT_TEXT, False),
            (_("Wrapped"), 7, _("Yes") if product.wrapped else _("No"),
             NumberFormat.FORMAT_TEXT, False),
            (_("Producer"), 15, product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
            (_("Long name"), 60, product.get_long_name(), NumberFormat.FORMAT_TEXT, False),
            (_("VAT"), 10, product.get_vat_level_display(), NumberFormat.FORMAT_TEXT, False),
        ]

        if row_num == 0:
            worksheet_set_header(ws, row)
            row_num += 1

        for col_num in range(len(row)):
            c = ws.cell(row=row_num, column=col_num)
            c.value = "%s" % (row[col_num][ROW_VALUE])
            c.style.number_format.format_code = row[col_num][ROW_FORMAT]
            if row[col_num][ROW_BOX]:
                c.style.borders.top.border_style = Border.BORDER_THIN
                c.style.borders.bottom.border_style = Border.BORDER_THIN
                c.style.borders.left.border_style = Border.BORDER_THIN
                c.style.borders.right.border_style = Border.BORDER_THIN
            else:
                c.style.borders.bottom.border_style = Border.BORDER_HAIR
        row_num += 1
        product = next_row(products)
    return wb

