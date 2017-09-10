# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.admin.templatetags.admin_list import _boolean_icon
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, DECIMAL_MAX_STOCK
from repanier.models.product import Product


@never_cache
@require_GET
@transaction.atomic
@login_required
def is_into_offer(request, product_id):
    if request.is_ajax():
        user = request.user
        if user.is_staff or user.is_superuser:
            product = Product.objects.filter(id=product_id).order_by('?').only(
                'is_into_offer', 'limit_order_quantity_to_stock', 'stock').first()
            if product is not None:
                new_is_into_offer = not product.is_into_offer
                if product.limit_order_quantity_to_stock:
                    if new_is_into_offer and product.stock <= DECIMAL_ZERO:
                        new_is_into_offer = False
                Product.objects.filter(id=product_id).update(is_into_offer=new_is_into_offer)
                return HttpResponse(mark_safe(_boolean_icon(new_is_into_offer)))
    raise Http404
