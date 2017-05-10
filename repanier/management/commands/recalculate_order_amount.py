# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from repanier.models import BankAccount
from repanier.models import LUT_DeliveryPoint, DeliveryBoard
from repanier.models import CustomerInvoice, ProducerInvoice
from repanier.const import PERMANENCE_CLOSED, \
    PERMANENCE_INVOICED, PERMANENCE_ARCHIVED, PERMANENCE_SEND
from repanier.models import Permanence
from repanier.tools import reorder_offer_items, recalculate_order_amount

from repanier.task import task_invoice


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate order amount'

    def handle(self, *args, **options):
        recalculate_order_amount(
            permanence_id=229,
            re_init=True
        )

        # latest_total = BankAccount.objects.filter(
        #     producer__isnull=True,
        #     customer__isnull=True,
        #     permanence__isnull=False
        # ).only(
        #     "permanence"
        # ).order_by(
        #     "-id"
        # ).first()
        # while latest_total:
        #     permanence = latest_total.permanence
        #     if permanence.status == PERMANENCE_INVOICED:
        #         print ("Cancel %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #         task_invoice.admin_cancel(permanence)
        #     else:
        #         latest_total.delete()
        #     latest_total = BankAccount.objects.filter(
        #         producer__isnull=True,
        #         customer__isnull=True,
        #         permanence__isnull=False
        #     ).only(
        #         "permanence"
        #     ).order_by(
        #         "-id"
        #     ).first()
        #
        # for permanence in Permanence.objects.filter(
        #         status=PERMANENCE_ARCHIVED
        # ).order_by('permanence_date'):
        #     print ("Cancel %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #     task_invoice.admin_cancel(permanence)
        #
        # for permanence in Permanence.objects.filter(
        #     status__lt=PERMANENCE_CLOSED
        # ).order_by('permanence_date'):
        #     print ("Recalculate %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #     recalculate_order_amount(
        #         permanence_id=permanence.id,
        #         re_init=True
        #     )
        #     reorder_offer_items(permanence.id)
        #     for customer_invoice in CustomerInvoice.objects.filter(permanence_id=permanence.id):
        #         delivery_point = LUT_DeliveryPoint.objects.filter(
        #             customer_responsible=customer_invoice.customer_id
        #         ).order_by('?').first()
        #         if delivery_point is not None:
        #             delivery = DeliveryBoard.objects.filter(
        #                 delivery_point_id=delivery_point.id,
        #                 permanence_id=permanence.id,
        #             ).order_by('?').first()
        #             customer_invoice.delivery = delivery
        #         customer_invoice.set_delivery(customer_invoice.delivery)
        #         if customer_invoice.is_order_confirm_send:
        #             customer_invoice.confirm_order()
        #         customer_invoice.save()
        #         # if customer_invoice.is_order_confirm_send:
        #         #     confirm_customer_invoice(permanence.id, customer_invoice.customer_id)
        # for permanence in Permanence.objects.filter(
        #     status__gte=PERMANENCE_CLOSED,
        #     status__lt=PERMANENCE_INVOICED
        # ).order_by('permanence_date'):
        #     # Important : Do not reclaculte if permanence is invoiced or archived.
        #     # First, cancel the invoice / archiving.
        #     print ("Recalculate %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #     status = permanence.status
        #     permanence.set_status(status)
        #     # if status >= PERMANENCE_SEND:
        #     recalculate_order_amount(
        #         permanence_id=permanence.id,
        #         re_init=True
        #     )
        #     reorder_offer_items(permanence.id)
        #     for customer_invoice in CustomerInvoice.objects.filter(permanence_id=permanence.id):
        #         delivery_point = LUT_DeliveryPoint.objects.filter(
        #             customer_responsible=customer_invoice.customer_id
        #         ).order_by('?').first()
        #         if delivery_point is not None:
        #             print("---- %s" % delivery_point)
        #             delivery = DeliveryBoard.objects.filter(
        #                 delivery_point_id=delivery_point.id,
        #                 permanence_id=permanence.id,
        #             ).order_by('?').first()
        #             customer_invoice.delivery = delivery
        #         customer_invoice.set_delivery(customer_invoice.delivery)
        #         if customer_invoice.is_order_confirm_send:
        #             customer_invoice.confirm_order()
        #         customer_invoice.save()
        #
        # for permanence in Permanence.objects.filter(
        #     status=PERMANENCE_SEND,
        #     highest_status__in=[PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]
        # ).order_by(
        #     "payment_date", "is_updated_on"
        # ):
        #     # if permanence.highest_status == PERMANENCE_INVOICED:
        #     # else:
        #     pass


