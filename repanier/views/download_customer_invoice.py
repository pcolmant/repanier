from django.conf import settings
from django.http import Http404
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.invoice import CustomerInvoice
from repanier.xlsx.xlsx_invoice import export_invoice


@never_cache
@require_GET
def download_customer_invoice(request, customer_invoice_id):
    user = request.user
    if user.is_authenticated:
        if user.is_repanier_staff:
            customer_invoice = CustomerInvoice.objects.filter(
                id=customer_invoice_id,
                # invoice_sort_order__isnull=False,
                # status__in=[SaleStatus.INVOICED, SaleStatus.ARCHIVED],
            ).first()
        else:
            customer_invoice = CustomerInvoice.objects.filter(
                customer__user_id=user.id,
                id=customer_invoice_id,
                # invoice_sort_order__isnull=False,
                # status__in=[SaleStatus.INVOICED, SaleStatus.ARCHIVED],
            ).first()
        if customer_invoice is not None:
            wb = export_invoice(
                permanence=customer_invoice.permanence,
                customer=customer_invoice.customer,
                wb=None,
                sheet_name=customer_invoice.permanence,
            )
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}-{2}.xlsx".format(
                _("Purchases"),
                settings.REPANIER_SETTINGS_GROUP_NAME,
                customer_invoice.permanence,
            )
            if wb is not None:
                wb.save(response)
                return response
    raise Http404
