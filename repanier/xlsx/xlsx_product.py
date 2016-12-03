# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from export_tools import *
from repanier.const import *
from repanier.models import Product
from repanier.tools import next_row


def export(producer_qs, wb=None, producer_prices=True):
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
        translations__language_code=translation.get_language(),
        producer__in=producer_qs
    ).order_by(
        "department_for_customer__tree_id",
        "translations__long_name",
        "order_average_weight",
    ).select_related(
        'producer', 'department_for_customer'
    ).iterator()
    product = next_row(products)
    while product is not None:
        row = [
            (_("reference"), 10, product.reference if len(product.reference) < 36 else EMPTY_STRING,
             NumberFormat.FORMAT_TEXT, False),
            (_("department_for_customer"), 15,
             product.department_for_customer.short_name if product.department_for_customer is not None else " ",
             NumberFormat.FORMAT_TEXT, False),
            (_("is_into_offer"), 7, _("Yes") if product.is_into_offer else _("No"),
             NumberFormat.FORMAT_TEXT, False),
            (_("wrapped"), 7, _("Yes") if product.wrapped else _("No"),
             NumberFormat.FORMAT_TEXT, False),
            (_("producer"), 15, product.producer.short_profile_name, NumberFormat.FORMAT_TEXT, False),
            (_("long_name"), 60, product.get_long_name(), NumberFormat.FORMAT_TEXT, False),
            (_("vat"), 10, product.get_vat_level_display(), NumberFormat.FORMAT_TEXT, False),
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


def admin_export(request, queryset, producer_prices=True):
    wb = export(producer_qs=queryset, wb=None, producer_prices=producer_prices)
    if wb is not None:
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = "attachment; filename={0}.xlsx".format(
            slugify(_("Products"))
        )
        wb.save(response)
        return response
    else:
        return None
