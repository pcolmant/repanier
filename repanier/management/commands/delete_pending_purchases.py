# -*- coding: utf-8 -*-
from django.utils import timezone

import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO
from repanier.email.email_order import export_order_2_1_customer
from repanier.models import Permanence, CustomerInvoice, Purchase
from django.conf import settings
from django.utils import translation

from repanier.tools import update_or_create_purchase, get_signature


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
                    # TODO : Send Mail
                    filename = "{0}-{1}.xlsx".format(
                        slugify(_("Canceled order")),
                        slugify(permanence)
                    )
                    sender_email, sender_function, signature, cc_email_staff = get_signature(
                        is_reply_to_order_email=True)
                    export_order_2_1_customer(
                        customer_invoice.customer, filename, permanence, sender_email,
                        sender_function, signature,
                        cancel_order=True
                    )
                    purchase_qs = Purchase.objects.filter(
                        customer_invoice_id=customer_invoice.id,
                        is_box_content=False
                    ).order_by('?')
                    for purchase in purchase_qs.select_related("customer"):
                        update_or_create_purchase(
                            customer=purchase.customer,
                            offer_item_id=purchase.offer_item_id,
                            q_order=DECIMAL_ZERO,
                            batch_job=True
                        )


