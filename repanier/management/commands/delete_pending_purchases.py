import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from repanier.const import DECIMAL_ZERO, SaleStatus
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence import Permanence


class Command(BaseCommand):
    args = "<none>"
    help = "Delete pending purchases"

    def handle(self, *args, **options):
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            now_less_one_hour = timezone.now() - datetime.timedelta(hours=1)

            for permanence in Permanence.objects.filter(status=SaleStatus.OPENED):
                # All product of a invoice may be free of charge
                # so don't use the total price with tax
                # but the purchase quantity ordered
                recently_updated_customer_invoice_qs = CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    is_order_confirm_send=False,
                    is_group=False,
                    # total_price_with_tax__gt=DECIMAL_ZERO,
                    # purchase__quantity_ordered__gt=DECIMAL_ZERO,
                    purchase__is_updated_on__gte=now_less_one_hour,
                ).distinct()
                customer_invoice_qs = (
                    CustomerInvoice.objects.filter(
                        permanence_id=permanence.id,
                        is_order_confirm_send=False,
                        is_group=False,
                        # total_price_with_tax__gt=DECIMAL_ZERO,
                        purchase__quantity_ordered__gt=DECIMAL_ZERO,
                    )
                    .exclude(id__in=recently_updated_customer_invoice_qs)
                    .distinct()
                )
                for customer_invoice in customer_invoice_qs:
                    customer_invoice.cancel_if_unconfirmed(send_mail=True)
