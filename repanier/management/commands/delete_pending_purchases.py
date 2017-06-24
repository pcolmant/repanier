# -*- coding: utf-8 -*-
from django.utils import timezone

import datetime
from django.core.management.base import BaseCommand

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO
from repanier.models.permanence import Permanence
from repanier.models.invoice import CustomerInvoice
from django.conf import settings
from django.utils import translation


class Command(BaseCommand):
    args = '<none>'
    help = 'Open pre opened orders'

    def handle(self, *args, **options):
        from repanier.apps import REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS
        if REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
            now_less_one_hour = timezone.now() - datetime.timedelta(hours=1)
            translation.activate(settings.LANGUAGE_CODE)

            for permanence in Permanence.objects.filter(
                    status=PERMANENCE_OPENED
            ).order_by('?'):
                recently_updated_customer_invoice_qs = CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    is_order_confirm_send=False,
                    total_price_with_tax__gt=DECIMAL_ZERO,
                    purchase__is_updated_on__gte=now_less_one_hour
                ).distinct()
                customer_invoice_qs = CustomerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    is_order_confirm_send=False,
                    total_price_with_tax__gt=DECIMAL_ZERO,
                ).exclude(
                    id__in=recently_updated_customer_invoice_qs
                )
                for customer_invoice in customer_invoice_qs:
                    customer_invoice.delete_if_unconfirmed(permanence)




