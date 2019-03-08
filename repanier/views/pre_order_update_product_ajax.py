# -*- coding: utf-8
from os import sep as os_sep

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from repanier.const import ONE_DECIMAL, TWO_DECIMALS, DECIMAL_ZERO, PRODUCT_ORDER_UNIT_PC_KG, DECIMAL_ONE, \
    PERMANENCE_PRE_OPEN
from repanier.models.offeritem import OfferItem
from repanier.models.producer import Producer
from repanier.tools import clean_offer_item, get_repanier_template_name
from repanier.views.forms import ProducerProductForm


@never_cache
def pre_order_update_product_ajax(request, offer_uuid=None, offer_item_id=None):
    if offer_item_id is None:
        raise Http404
    producer = Producer.objects.filter(offer_uuid=offer_uuid, is_active=True, producer_pre_opening=True).only(
        'id').order_by('?').first()
    if producer is None:
        template_name = get_repanier_template_name("pre_order_closed_form.html")
        return render(
            request,
            template_name,
        )
    offer_item = get_object_or_404(OfferItem, id=offer_item_id)
    if offer_item.producer_id != producer.id:
        raise Http404

    permanence = offer_item.permanence
    if permanence.status == PERMANENCE_PRE_OPEN:
        if request.method == 'POST':  # If the form has been submitted...
            form = ProducerProductForm(request.POST)  # A form bound to the POST data
            if form.is_valid():
                product = offer_item.product
                long_name = form.cleaned_data.get('long_name')
                product.long_name = long_name
                product.order_unit = form.cleaned_data.get('order_unit')
                product.producer_unit_price = form.cleaned_data.get('producer_unit_price')
                product.stock = form.cleaned_data.get('stock')
                if product.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                    product.customer_increment_order_quantity = form.cleaned_data.get(
                        'customer_increment_order_quantity').quantize(ONE_DECIMAL)
                    product.order_average_weight = form.cleaned_data.get('order_average_weight')
                    product.customer_alert_order_quantity = product.stock
                else:
                    product.customer_increment_order_quantity = 1
                    product.order_average_weight = form.cleaned_data.get('customer_increment_order_quantity').quantize(
                        ONE_DECIMAL)
                    if product.order_average_weight <= DECIMAL_ZERO:
                        product.order_average_weight = DECIMAL_ONE
                    product.producer_unit_price = (
                            product.producer_unit_price.amount * product.order_average_weight
                    ).quantize(TWO_DECIMALS)
                    product.stock = product.customer_alert_order_quantity = product.stock / product.order_average_weight
                product.unit_deposit = form.cleaned_data.get('unit_deposit')
                product.vat_level = form.cleaned_data.get('vat_level')
                product.offer_description = form.cleaned_data.get('offer_description')
                product.customer_minimum_order_quantity = product.customer_increment_order_quantity
                product.picture2 = form.cleaned_data.get('picture')
                product.save()
                product.production_mode.clear()
                production_mode = form.cleaned_data.get('production_mode', None)
                if production_mode is not None:
                    product.production_mode.add(production_mode)
                offer_item_qs = OfferItem.objects.filter(
                    id=offer_item.id
                ).order_by('?')
                clean_offer_item(permanence, offer_item_qs)
                # Refresh offer_item
                offer_item = get_object_or_404(OfferItem, id=offer_item_id)
                update = True
            else:
                update = False
        else:
            form = ProducerProductForm()  # An unbound form
            field = form.fields["long_name"]
            field.initial = offer_item.safe_translation_getter('long_name', any_language=True)
            if settings.REPANIER_SETTINGS_PRODUCT_LABEL:
                field = form.fields["production_mode"]
                field.initial = offer_item.product.production_mode.first()
            field = form.fields["order_unit"]
            field.initial = offer_item.order_unit
            field = form.fields["order_average_weight"]
            field.initial = offer_item.order_average_weight.quantize(ONE_DECIMAL)
            if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                customer_increment_order_quantity = offer_item.customer_increment_order_quantity.quantize(ONE_DECIMAL)
                field = form.fields["customer_increment_order_quantity"]
                field.initial = customer_increment_order_quantity
                field = form.fields["producer_unit_price"]
                field.initial = offer_item.producer_unit_price.amount
                field = form.fields["stock"]
                field.initial = offer_item.stock.quantize(ONE_DECIMAL)
            else:
                customer_increment_order_quantity = offer_item.order_average_weight.quantize(ONE_DECIMAL)
                field = form.fields["customer_increment_order_quantity"]
                field.initial = customer_increment_order_quantity
                field = form.fields["producer_unit_price"]
                if customer_increment_order_quantity > DECIMAL_ZERO:
                    field.initial = (
                            offer_item.producer_unit_price.amount / customer_increment_order_quantity).quantize(
                        TWO_DECIMALS)
                else:
                    field.initial = offer_item.producer_unit_price.amount
                field = form.fields["stock"]
                field.initial = (customer_increment_order_quantity * offer_item.stock).quantize(ONE_DECIMAL)
            field = form.fields["unit_deposit"]
            field.initial = offer_item.unit_deposit.amount
            field = form.fields["vat_level"]
            field.initial = offer_item.vat_level
            field = form.fields["offer_description"]
            field.initial = offer_item.product.offer_description
            field = form.fields["picture"]
            field.initial = offer_item.product.picture2
            field.widget.upload_to = "{}{}{}".format("product", os_sep, offer_item.producer_id)
            update = None

        template_name = get_repanier_template_name('pre_order_update_product_form.html')
        return render(
            request,
            template_name,
            {'form': form, 'offer_uuid': offer_uuid, 'offer_item': offer_item, 'update': update}
        )
    raise Http404
