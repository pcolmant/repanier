# -*- coding: utf-8
from __future__ import unicode_literals

from os import sep as os_sep

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache

from repanier.views.forms import ProducerProductForm
from repanier.const import DECIMAL_ZERO, DECIMAL_ONE, PRODUCT_ORDER_UNIT_PC_PRICE_KG, TWO_DECIMALS, ONE_DECIMAL, \
    PRODUCT_ORDER_UNIT_PC_KG, PERMANENCE_PRE_OPEN, EMPTY_STRING, VAT_400
from repanier.models.offeritem import OfferItem
from repanier.models.product import Product
from repanier.models.producer import Producer
from repanier.models.permanence import Permanence
from repanier.tools import clean_offer_item


@never_cache
def pre_order_create_product_ajax(request, permanence_id=None, offer_uuid=None):
    if permanence_id is None:
        raise Http404
    producer = Producer.objects.filter(offer_uuid=offer_uuid, is_active=True, producer_pre_opening=True).only(
        'id').order_by('?').first()
    if producer is None:
        return render(
            request,
            "repanier/pre_order_closed_form.html",
        )

    permanence = get_object_or_404(Permanence, id=permanence_id)
    offer_item = None
    if permanence.status == PERMANENCE_PRE_OPEN:
        if request.method == 'POST':  # If the form has been submitted...
            form = ProducerProductForm(request.POST)  # A form bound to the POST data
            if form.is_valid():
                long_name = form.cleaned_data.get('long_name')
                if long_name != _("long_name"):
                    order_unit = form.cleaned_data.get('order_unit')
                    producer_unit_price = form.cleaned_data.get('producer_unit_price')
                    stock = form.cleaned_data.get('stock')
                    if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                        customer_increment_order_quantity = form.cleaned_data.get(
                            'customer_increment_order_quantity').quantize(ONE_DECIMAL)
                        order_average_weight = form.cleaned_data.get('order_average_weight')
                        customer_alert_order_quantity = stock
                    else:
                        customer_increment_order_quantity = 1
                        order_average_weight = form.cleaned_data.get('customer_increment_order_quantity').quantize(
                            ONE_DECIMAL)
                        if order_average_weight <= DECIMAL_ZERO:
                            order_average_weight = DECIMAL_ONE
                        producer_unit_price = (producer_unit_price * order_average_weight).quantize(TWO_DECIMALS)
                        stock = customer_alert_order_quantity = stock / order_average_weight
                    unit_deposit = form.cleaned_data.get('unit_deposit')
                    vat_level = form.cleaned_data.get('vat_level')
                    offer_description = form.cleaned_data.get('offer_description')
                    customer_minimum_order_quantity = customer_increment_order_quantity
                    picture2 = form.cleaned_data.get('picture')
                    product = Product.objects.create(
                        producer_id=producer.id,
                        long_name=long_name,
                        order_unit=order_unit,
                        customer_increment_order_quantity=customer_increment_order_quantity,
                        customer_alert_order_quantity=customer_alert_order_quantity,
                        order_average_weight=order_average_weight,
                        producer_unit_price=producer_unit_price,
                        unit_deposit=unit_deposit,
                        stock=stock,
                        vat_level=vat_level,
                        offer_description=offer_description,
                        customer_minimum_order_quantity=customer_minimum_order_quantity,
                        picture2=picture2,
                        is_into_offer=True,
                        limit_order_quantity_to_stock=True,
                        is_active=True
                    )
                    production_mode = form.cleaned_data.get('production_mode')
                    if production_mode is not None:
                        product.production_mode.add(form.cleaned_data.get('production_mode'))
                    offer_item = OfferItem.objects.create(
                        permanence_id=permanence_id,
                        product_id=product.id,
                        producer_id=producer.id,
                        is_active=True
                    )
                    offer_item_qs = OfferItem.objects.filter(
                        id=offer_item.id
                    ).order_by('?')
                    clean_offer_item(permanence, offer_item_qs)
                    # Refresh offer_item
                    offer_item = get_object_or_404(OfferItem, id=offer_item.id)
        else:
            form = ProducerProductForm()  # An unbound form
            field = form.fields["long_name"]
            field.initial = _("long_name")
            field = form.fields["order_unit"]
            field.initial = PRODUCT_ORDER_UNIT_PC_PRICE_KG
            field = form.fields["order_average_weight"]
            field.initial = DECIMAL_ZERO
            field = form.fields["customer_increment_order_quantity"]
            field.initial = DECIMAL_ONE
            field = form.fields["producer_unit_price"]
            field.initial = DECIMAL_ZERO
            field = form.fields["unit_deposit"]
            field.initial = DECIMAL_ZERO
            field = form.fields["stock"]
            field.initial = DECIMAL_ZERO
            field = form.fields["vat_level"]
            field.initial = VAT_400
            field = form.fields["offer_description"]
            field.initial = EMPTY_STRING
            field = form.fields["picture"]
            field.widget.upload_to = "%s%s%d" % ("product", os_sep, producer.id)
        return render(
            request,
            "repanier/pre_order_create_product_form.html",
            {'form'    : form, 'permanence_id': permanence_id, 'offer_uuid': offer_uuid, 'offer_item': offer_item,
             'producer': producer}
        )
    raise Http404
