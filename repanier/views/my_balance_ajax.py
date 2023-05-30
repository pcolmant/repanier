from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, EMPTY_STRING, SaleStatus
from repanier.models.invoice import CustomerInvoice


@never_cache
@require_GET
def my_balance_ajax(request):
    user = request.user
    if user.is_anonymous or user.is_repanier_staff:
        return HttpResponse(EMPTY_STRING)
    last_customer_invoice = (
        CustomerInvoice.objects.filter(
            customer_id=request.customer_id,
            invoice_sort_order__isnull=False,
            status__lte=SaleStatus.INVOICED,
        )
        .only("balance", "date_balance")
        .order_by("-invoice_sort_order")
        .first()
    )
    if last_customer_invoice is not None:
        if last_customer_invoice.balance < DECIMAL_ZERO:
            result = _(
                'My balance : <font color="red">%(balance)s</font> at %(date)s'
            ) % {
                "balance": last_customer_invoice.balance,
                "date": last_customer_invoice.date_balance.strftime(
                    settings.DJANGO_SETTINGS_DATE
                ),
            }
        else:
            result = _(
                'My balance : <font color="green">%(balance)s</font> at %(date)s'
            ) % {
                "balance": last_customer_invoice.balance,
                "date": last_customer_invoice.date_balance.strftime(
                    settings.DJANGO_SETTINGS_DATE
                ),
            }
    else:
        result = _("My balance")
    return HttpResponse(result)
