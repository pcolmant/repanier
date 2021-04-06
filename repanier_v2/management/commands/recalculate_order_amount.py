import logging

from django.core.management.base import BaseCommand

from repanier_v2.models.permanence import Permanence

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = "<none>"
    help = "Recalculate order amount"

    def handle(self, *args, **options):
        for permanence in Permanence.objects.filter(id=796).order_by("permanence_date"):
            permanence.set_qty_invoiced()
            permanence.recalculate_order_amount(re_init=True)

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
        #     if permanence.status == ORDER_INVOICED:
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
        #         status=ORDER_ARCHIVED
        # ).order_by('permanence_date'):
        #     print ("Cancel %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #     task_invoice.admin_cancel(permanence)
        #
        # for permanence in Permanence.objects.filter(
        #     status__lt=ORDER_CLOSED
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
        #         customer_invoice.set_delivery_context(customer_invoice.delivery)
        #         if customer_invoice.is_order_confirm_send:
        #             customer_invoice.confirm_order()
        #         customer_invoice.save()
        #         # if customer_invoice.is_order_confirm_send:
        #         #     confirm_customer_invoice(permanence.id, customer_invoice.customer_id)
        # for permanence in Permanence.objects.filter(
        #     status__gte=ORDER_CLOSED,
        #     status__lt=ORDER_INVOICED
        # ).order_by('permanence_date'):
        #     # Important : Do not reclaculte if permanence is invoiced or archived.
        #     # First, cancel the invoice / archiving.
        #     print ("Recalculate %s %s" % (permanence.permanence_date, permanence.get_status_display()))
        #     status = permanence.status
        #     permanence.set_status(status)
        #     # if status >= ORDER_SEND:
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
        #         customer_invoice.set_delivery_context(customer_invoice.delivery)
        #         if customer_invoice.is_order_confirm_send:
        #             customer_invoice.confirm_order()
        #         customer_invoice.save()
        #
        # for permanence in Permanence.objects.filter(
        #     status=ORDER_SEND,
        #     highest_status__in=[ORDER_INVOICED, ORDER_ARCHIVED]
        # ).order_by(
        #     "payment_date", "is_updated_on"
        # ):
        #     # if permanence.highest_status == ORDER_INVOICED:
        #     # else:
        #     pass
