# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.admin.templatetags.admin_list import _boolean_icon
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Product


@never_cache
@require_GET
@transaction.atomic
def is_into_offer(request, product_id):
    if request.is_ajax():
        user = request.user
        if user.is_staff or user.is_superuser:
            is_into_offer = not(Product.objects.filter(id=product_id).order_by('?').only(
                'is_into_offer').first().is_into_offer)
            Product.objects.filter(id=product_id).update(is_into_offer=is_into_offer)
            return HttpResponse(mark_safe(_boolean_icon(is_into_offer)))
    raise Http404
