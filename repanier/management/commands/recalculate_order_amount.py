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
    PRODUCT_ORDER_UNIT_DEPOSIT
from repanier.models import Permanence
from repanier.tools import reorder_offer_items, recalculate_order_amount
from django.conf import settings
from django.utils import translation


class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate order amount'

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        # Les producer price (et donc la tva) des produits, offer item dont is_box = true est à zéro au lieu d'être = au prix, eva consommateur
        Product.objects.filter(
            is_box=True
        ).update(
            producer_unit_price=F('customer_unit_price'),
            producer_vat=F('customer_vat')
        )
        Product.objects.filter(
            vat_level='200'
        ).update(
            vat_level='100'
        )
        Product.objects.filter(
            vat_level='300'
        ).update(
            vat_level='100'
        )
        OfferItem.objects.filter(
            is_box=True
        ).update(
            producer_unit_price=F('customer_unit_price'),
            producer_vat=F('customer_vat')
        )
        OfferItem.objects.filter(
            vat_level='200'
        ).update(
            vat_level='100'
        )
        OfferItem.objects.filter(
            vat_level='300'
        ).update(
            vat_level='100'
        )
        Purchase.objects.filter(
            offer_item__is_box=True
        ).update(
            purchase_price=F('selling_price'),
            producer_vat=F('customer_vat')
        )
        # Mettre purchase price et selling price des purchase dont is_box_content = True à zéro
        Purchase.objects.filter(
            is_box_content=True
        ).update(
            purchase_price=DECIMAL_ZERO,
            selling_price=DECIMAL_ZERO,
            producer_vat=DECIMAL_ZERO,
            customer_vat=DECIMAL_ZERO,
            # compensation=DECIMAL_ZERO,
            deposit=DECIMAL_ZERO,
        )
        Purchase.objects.filter(
            vat_level='200'
        ).update(
            vat_level='100'
        )
        Purchase.objects.filter(
            vat_level='300'
        ).update(
            vat_level='100'
        )
        qs = CustomerInvoice.objects.filter(
            permanence__with_delivery_point=True, status__lte=PERMANENCE_CLOSED, delivery__isnull=True
        ).order_by('?')
        Purchase.objects.filter(
            customer_invoice__in=qs
        ).order_by('?').delete()
        qs.delete()
        OfferItem.objects.filter(
            producer_price_are_wo_vat=True
        ).update(
            producer_price_are_wo_vat=False,
            producer_unit_price=F('producer_unit_price') + F('producer_vat')
        )
        OfferItem.objects.filter(
            order_unit__gte=PRODUCT_ORDER_UNIT_DEPOSIT
        ).update(
            manage_replenishment=False
        )

        for permanence in Permanence.objects.filter(
                with_delivery_point=False
        ).order_by('?'):
            CustomerInvoice.objects.filter(
                permanence_id=permanence.id,
            ).order_by('?').update(
                customer_who_pays_id=F('customer_id')
            )
            Purchase.objects.filter(
                permanence_id=permanence.id,
            ).order_by('?').update(
                customer_who_pays_id=F('customer_id')
            )

        for producer_invoice in ProducerInvoice.objects.filter(
                invoice_reference__isnull=True
        ):
            bank_account = BankAccount.objects.filter(
                producer_invoice_id = producer_invoice.id,
                operation_status=BANK_CALCULATED_INVOICE
            ).order_by('?').first()
            if bank_account is not None:
                producer_invoice.invoice_reference = bank_account.operation_comment
                producer_invoice.to_be_invoiced_balance = bank_account.bank_amount_out - bank_account.bank_amount_in
                producer_invoice.save(update_fields=['invoice_reference', 'to_be_invoiced_balance'])

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
            status__gte=PERMANENCE_CLOSED
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
                # confirm_customer_invoice(permanence.id, customer_invoice.customer_id)


