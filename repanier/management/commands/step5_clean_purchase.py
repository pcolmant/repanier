# -*- coding: utf-8 -*-
import uuid
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import translation
from repanier.const import *
from repanier.models import LUT_DepartmentForCustomer, LUT_PermanenceRole, LUT_ProductionMode, Product, Permanence, \
    OfferItem, Purchase, Producer, BankAccount, ProducerInvoice, CustomerInvoice, PermanenceBoard


class Command(BaseCommand):
    args = '<none>'
    help = 'Fill translation'

    def handle(self, *args, **options):
        translation.activate('fr')
        PermanenceBoard.objects.all().update(
            permanence_date=F('distribution_date'))
        Permanence.objects.filter(status__lte=PERMANENCE_SEND).update(
            permanence_date=F('distribution_date'),
            payment_date=F('distribution_date'))
        Permanence.objects.filter(status__gt=PERMANENCE_SEND).update(
            permanence_date=F('distribution_date'),
            payment_date=None)
        for producer_invoice in ProducerInvoice.objects.all():
            bank_account = BankAccount.objects.filter(
                permanence_id=producer_invoice.permanence_id,
                producer__isnull=True,
                customer__isnull=True).order_by().only("id").first()
            if bank_account is not None:
                producer_invoice.invoice_sort_order = bank_account.id
                producer_invoice.save(update_fields=['invoice_sort_order'])
        for customer_invoice in CustomerInvoice.objects.all():
            bank_account = BankAccount.objects.filter(
                permanence_id=customer_invoice.permanence_id,
                producer__isnull=True,
                customer__isnull=True).order_by().only("id").first()
            if bank_account is not None:
                customer_invoice.invoice_sort_order = bank_account.id
                customer_invoice.save(update_fields=['invoice_sort_order'])
        for product in Product.objects.all().order_by():
            product.producer_unit_price = product.original_unit_price
            product.customer_unit_price = product.unit_price_with_vat
            product.producer_vat = DECIMAL_ZERO
            if product.vat_level == VAT_400:
                product.producer_vat = (product.producer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
            elif product.vat_level == VAT_500:
                product.producer_vat = (product.producer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
            elif product.vat_level == VAT_600:
                product.producer_vat = (product.producer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
            product.customer_vat = DECIMAL_ZERO
            if product.vat_level == VAT_400:
                product.customer_vat = (product.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
            elif product.vat_level == VAT_500:
                product.customer_vat = (product.customer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
            elif product.vat_level == VAT_600:
                product.customer_vat = (product.customer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
            product.compensation = DECIMAL_ZERO
            if product.vat_level == VAT_200:
                product.compensation = (product.customer_unit_price * DECIMAL_0_02).quantize(FOUR_DECIMALS)
            elif product.vat_level == VAT_300:
                product.compensation = (product.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
            product.limit_order_quantity_to_stock = product.producer.limit_to_alert_order_quantity if \
                product.producer.limit_to_alert_order_quantity is not None else False
            product.save(update_fields=['producer_unit_price', 'customer_unit_price',
                                        'customer_vat', 'producer_vat',
                                        'compensation', 'limit_order_quantity_to_stock'])

        for offer_item in OfferItem.objects.filter(product__isnull=False).order_by():
            offer_item.limit_order_quantity_to_stock = offer_item.product.limit_order_quantity_to_stock
            offer_item.vat_level = offer_item.product.vat_level
            # Must be set manually
            offer_item.stock = DECIMAL_ZERO
            offer_item.unit_deposit = offer_item.product.unit_deposit
            offer_item.compensation = offer_item.product.compensation
            offer_item.producer_vat = offer_item.product.producer_vat
            offer_item.customer_vat = offer_item.product.customer_vat
            offer_item.customer_unit_price = offer_item.product.customer_unit_price
            offer_item.producer_unit_price = offer_item.product.producer_unit_price
            offer_item.placement = offer_item.product.placement
            offer_item.order_average_weight = offer_item.product.order_average_weight
            offer_item.wrapped = offer_item.product.wrapped
            offer_item.order_unit = offer_item.product.order_unit
            offer_item.producer = offer_item.product.producer
            offer_item.department_for_customer = offer_item.product.department_for_customer
            offer_item.reference = offer_item.product.reference
            offer_item.long_name = offer_item.product.long_name
            offer_item.customer_minimum_order_quantity = offer_item.product.customer_minimum_order_quantity
            offer_item.customer_increment_order_quantity = offer_item.product.customer_increment_order_quantity
            offer_item.customer_alert_order_quantity = offer_item.product.customer_alert_order_quantity
            offer_item.save()
        for purchase in Purchase.objects.filter(offer_item__isnull=False).order_by():
            purchase.permanence_date = purchase.distribution_date
            purchase.purchase_price = purchase.original_price
            purchase.selling_price = purchase.price_with_compensation if purchase.invoiced_price_with_compensation else purchase.price_with_vat
            if purchase.permanence.status < PERMANENCE_SEND:
                purchase.quantity_ordered = purchase.quantity
            else:
                purchase.quantity_ordered = purchase.quantity_send_to_producer if \
                    purchase.quantity_send_to_producer > 0 else purchase.quantity
            purchase.quantity_for_preparation_sort_order = purchase.quantity_for_preparation_order
            purchase.quantity_invoiced = purchase.quantity
            purchase.producer_invoice_id = purchase.is_recorded_on_producer_invoice_id
            purchase.customer_invoice_id = purchase.is_recorded_on_customer_invoice_id
            purchase.save()
            if purchase.offer_item.department_for_customer is None:
                purchase.offer_item.department_for_customer = purchase.department_for_customer
                purchase.offer_item.save(update_fields=['department_for_customer'])
            if purchase.offer_item.producer is None:
                purchase.offer_item.producer = purchase.producer
                purchase.offer_item.save(update_fields=['producer'])
            if purchase.offer_item.order_unit is None:
                purchase.offer_item.order_unit = purchase.order_unit
                purchase.offer_item.save(update_fields=['order_unit'])

        default_producer = Producer.objects.filter(represent_this_buyinggroup=True, is_active=True).first()
        # print default_producer
        for purchase in Purchase.objects.filter(offer_item__isnull=True).order_by():
            purchase.permanence_date = purchase.distribution_date
            purchase.purchase_price = purchase.original_price
            purchase.selling_price = purchase.price_with_compensation if purchase.invoiced_price_with_compensation else purchase.price_with_vat
            if purchase.permanence.status < PERMANENCE_SEND:
                purchase.quantity_ordered = purchase.quantity
            else:
                purchase.quantity_ordered = purchase.quantity_send_to_producer if \
                    purchase.quantity_send_to_producer > 0 else purchase.quantity
            purchase.quantity_for_preparation_sort_order = purchase.quantity_for_preparation_order
            purchase.quantity_invoiced = purchase.quantity
            purchase.producer_invoice_id = purchase.is_recorded_on_producer_invoice_id
            purchase.customer_invoice_id = purchase.is_recorded_on_customer_invoice_id
            if purchase.product is None:
                offer_item = OfferItem.objects.filter(
                    translations__long_name=purchase.long_name,
                    translations__language_code='fr',
                    permanence=purchase.permanence,
                    producer=purchase.producer,
                ).order_by().first()
            else:
                offer_item = OfferItem.objects.filter(
                    permanence=purchase.permanence,
                    product=purchase.product
                ).order_by().first()
            if offer_item is None:
                if purchase.product is None:
                    limit_order_quantity_to_stock = False
                    stock = DECIMAL_ZERO
                    customer_minimum_order_quantity = DECIMAL_ZERO
                    customer_increment_order_quantity = DECIMAL_ZERO
                    customer_alert_order_quantity = DECIMAL_ZERO
                else:
                    limit_order_quantity_to_stock = purchase.product.limit_order_quantity_to_stock
                    stock = purchase.product.stock
                    customer_minimum_order_quantity = purchase.product.customer_minimum_order_quantity
                    customer_increment_order_quantity = purchase.product.customer_increment_order_quantity
                    customer_alert_order_quantity = purchase.product.customer_alert_order_quantity
                vat_level = purchase.vat_level
                unit_deposit = purchase.unit_deposit
                if purchase.producer is None:
                    customer_unit_price = purchase.original_unit_price
                    producer = default_producer
                else:
                    customer_unit_price = (purchase.original_unit_price *
                                          purchase.producer.price_list_multiplier).quantize(
                                          TWO_DECIMALS)
                    producer = purchase.producer
                producer_unit_price = purchase.original_unit_price
                producer_vat = DECIMAL_ZERO
                if vat_level == VAT_400:
                    producer_vat = (producer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                elif vat_level == VAT_500:
                    producer_vat = (producer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
                elif vat_level == VAT_600:
                    producer_vat = (producer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
                customer_vat = DECIMAL_ZERO
                if vat_level == VAT_400:
                    customer_vat = (customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                elif vat_level == VAT_500:
                    customer_vat = (customer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
                elif vat_level == VAT_600:
                    customer_vat = (customer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
                compensation = DECIMAL_ZERO
                if vat_level == VAT_200:
                    compensation = (customer_unit_price * DECIMAL_0_02).quantize(FOUR_DECIMALS)
                elif vat_level == VAT_300:
                    compensation = (customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                placement = PRODUCT_PLACEMENT_BASKET
                order_average_weight = purchase.order_average_weight
                wrapped = purchase.wrapped
                order_unit = purchase.order_unit if purchase.order_unit is not None else PRODUCT_ORDER_UNIT_PC
                department_for_customer = purchase.department_for_customer
                reference = uuid.uuid4()
                permanence = purchase.permanence
                long_name = purchase.long_name

                offer_item = OfferItem.objects.create(
                    long_name=long_name,
                    permanence=permanence,
                    product=purchase.product,
                    reference=reference,
                    department_for_customer=department_for_customer,
                    producer=producer,
                    order_unit=order_unit,
                    wrapped=wrapped,
                    order_average_weight=order_average_weight,
                    placement=placement,
                    producer_unit_price=producer_unit_price,
                    customer_unit_price=customer_unit_price,
                    producer_vat=producer_vat,
                    customer_vat=customer_vat,
                    compensation=compensation,
                    unit_deposit=unit_deposit,
                    vat_level=vat_level,
                    is_active=True,
                    limit_order_quantity_to_stock=limit_order_quantity_to_stock,
                    stock=stock,
                    customer_minimum_order_quantity=customer_minimum_order_quantity,
                    customer_increment_order_quantity=customer_increment_order_quantity,
                    customer_alert_order_quantity=customer_alert_order_quantity
                )
            else:
                offer_item.limit_order_quantity_to_stock = offer_item.product.limit_order_quantity_to_stock if \
                    offer_item.product is not None else False
                offer_item.vat_level = purchase.vat_level
                offer_item.stock = offer_item.customer_alert_order_quantity if \
                    offer_item.customer_alert_order_quantity is not None else DECIMAL_ZERO
                offer_item.unit_deposit = purchase.unit_deposit
                if purchase.producer is None:
                    offer_item.customer_unit_price = purchase.original_unit_price
                    offer_item.producer = default_producer
                else:
                    offer_item.customer_unit_price = (purchase.original_unit_price *
                                          purchase.producer.price_list_multiplier).quantize(
                                          TWO_DECIMALS)
                    offer_item.producer = purchase.producer
                offer_item.producer_unit_price = purchase.original_unit_price
                offer_item.producer_vat = DECIMAL_ZERO
                if offer_item.vat_level == VAT_400:
                    offer_item.producer_vat = (producer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                elif offer_item.vat_level == VAT_500:
                    offer_item.producer_vat = (producer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
                elif offer_item.vat_level == VAT_600:
                    offer_item.producer_vat = (producer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
                offer_item.customer_vat = DECIMAL_ZERO
                if offer_item.vat_level == VAT_400:
                    offer_item.customer_vat = (offer_item.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                elif offer_item.vat_level == VAT_500:
                    offer_item.customer_vat = (offer_item.customer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
                elif offer_item.vat_level == VAT_600:
                    offer_item.customer_vat = (offer_item.customer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
                offer_item.compensation = DECIMAL_ZERO
                if offer_item.vat_level == VAT_200:
                    offer_item.compensation = (offer_item.customer_unit_price * DECIMAL_0_02).quantize(FOUR_DECIMALS)
                elif offer_item.vat_level == VAT_300:
                    offer_item.compensation = (offer_item.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
                offer_item.placement = offer_item.product.placement if \
                    offer_item.product is not None else PRODUCT_PLACEMENT_BASKET
                offer_item.order_average_weight = purchase.order_average_weight
                offer_item.wrapped = purchase.wrapped
                offer_item.order_unit = purchase.order_unit if \
                    purchase.order_unit is not None else PRODUCT_ORDER_UNIT_PC
                offer_item.producer = purchase.producer
                offer_item.department_for_customer = purchase.department_for_customer
                if offer_item.product is None:
                    offer_item.reference = uuid.uuid4()
                else:
                    offer_item.reference = offer_item.product.reference
                offer_item.long_name = purchase.long_name
                offer_item.save()
            purchase.offer_item = offer_item
            purchase.save()
        for bank in BankAccount.objects.all().order_by():
            bank.producer_invoice_id = bank.is_recorded_on_producer_invoice_id
            bank.customer_invoice_id = bank.is_recorded_on_customer_invoice_id
            bank.save(update_fields=['producer_invoice', 'customer_invoice'])

        LUT_DepartmentForCustomer.objects.rebuild()
        LUT_PermanenceRole.objects.rebuild()
        LUT_ProductionMode.objects.rebuild()

