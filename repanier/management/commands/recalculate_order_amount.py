# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db.models import F

from repanier.models import BankAccount
from repanier.models import ProducerInvoice
from repanier.models import LUT_DeliveryPoint, DeliveryBoard
from repanier.models import OfferItem
from repanier.models import Product
from repanier.models import Purchase
from repanier.models import CustomerInvoice
from repanier.const import PERMANENCE_SEND, DECIMAL_ZERO, PERMANENCE_CLOSED, BANK_CALCULATED_INVOICE, \
    PRODUCT_ORDER_UNIT_DEPOSIT, PERMANENCE_DONE
from repanier.models import Permanence
from repanier.tools import reorder_offer_items, recalculate_order_amount
from django.conf import settings
from django.utils import translation


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate order amount'

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(
            status__lt=PERMANENCE_CLOSED
        ).order_by('permanence_date'):
            print ("%s %s" % (permanence.permanence_date, permanence.get_status_display()))
            recalculate_order_amount(
                permanence_id=permanence.id,
                all_producers=True,
                send_to_producer=False,
                re_init=True)
            reorder_offer_items(permanence.id)
            for customer_invoice in CustomerInvoice.objects.filter(permanence_id=permanence.id):
                delivery_point = LUT_DeliveryPoint.objects.filter(
                    customer_responsible=customer_invoice.customer_id
                ).order_by('?').first()
                if delivery_point is not None:
                    delivery = DeliveryBoard.objects.filter(
                        delivery_point_id=delivery_point.id,
                        permanence_id=permanence.id,
                    ).order_by('?').first()
                    customer_invoice.delivery = delivery
                customer_invoice.set_delivery(customer_invoice.delivery)
                if customer_invoice.is_order_confirm_send:
                    customer_invoice.confirm_order()
                customer_invoice.save()
                # if customer_invoice.is_order_confirm_send:
                #     confirm_customer_invoice(permanence.id, customer_invoice.customer_id)
        for permanence in Permanence.objects.filter(
            status__lt=PERMANENCE_DONE
        ).order_by('permanence_date'):
            print ("%s %s" % (permanence.permanence_date, permanence.get_status_display()))
            status = permanence.status
            permanence.set_status(status)
            if status == PERMANENCE_SEND:
                recalculate_order_amount(
                    permanence_id=permanence.id,
                    all_producers=True,
                    send_to_producer=False,
                    re_init=True
                )
            reorder_offer_items(permanence.id)
            for customer_invoice in CustomerInvoice.objects.filter(permanence_id=permanence.id):
                delivery_point = LUT_DeliveryPoint.objects.filter(
                    customer_responsible=customer_invoice.customer_id
                ).order_by('?').first()
                if delivery_point is not None:
                    print("---- %s" % delivery_point)
                    delivery = DeliveryBoard.objects.filter(
                        delivery_point_id=delivery_point.id,
                        permanence_id=permanence.id,
                    ).order_by('?').first()
                    customer_invoice.delivery = delivery
                customer_invoice.set_delivery(customer_invoice.delivery)
                if customer_invoice.is_order_confirm_send:
                    customer_invoice.confirm_order()
                customer_invoice.save()


