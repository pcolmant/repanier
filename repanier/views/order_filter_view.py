# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import translation
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET

from repanier.const import EMPTY_STRING
from repanier.models import Permanence
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.producer import Producer
from repanier.tools import permanence_ok_or_404, sint


@never_cache
@require_GET
@csrf_protect
@login_required
def order_filter_view(request, permanence_id):
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    permanence_ok_or_404(permanence)
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
    if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
        producer_set = Producer.objects.filter(permanence=permanence_id).only("id", "short_profile_name")
    else:
        producer_set = None
    is_basket = request.GET.get('is_basket', EMPTY_STRING)
    is_like = request.GET.get('is_like', EMPTY_STRING)
    if permanence.contract is not None:
        all_dates = permanence.contract.all_dates
        len_all_dates = len(all_dates)
        if len_all_dates < 2:
            date_id = 'all'
        else:
            date_id = sint(request.GET.get('date'), -1)
            if date_id < 0 or date_id >= len_all_dates:
                date_id = 'all'
    else:
        all_dates = []
        date_id = 'all'
    producer_id = request.GET.get('producer', 'all')
    department_id = request.GET.get('department', 'all')
    box_id = request.GET.get('box', 'all')
    if box_id != 'all':
        is_box = True
        # Do not display "all department" as selected
        department_id = None
    else:
        is_box = False
    q = request.GET.get('q', None)
    department_set = LUT_DepartmentForCustomer.objects.filter(
        offeritem__permanence_id=permanence_id,
        offeritem__is_active=True,
        offeritem__is_box=False) \
        .order_by("tree_id", "lft") \
        .distinct("id", "tree_id", "lft")
    if producer_id != 'all':
        department_set = department_set.filter(
            offeritem__producer_id=producer_id
        )
    return render(
        request, "repanier/order_filter.html",
        {
            'is_like': is_like,
            'is_basket': is_basket,
            'is_box': is_box,
            'q': q,
            'all_dates': all_dates,
            'date_id': date_id,
            'producer_set': producer_set,
            'producer_id': producer_id,
            'department_set': department_set,
            'department_id': department_id,
            'box_set':  OfferItemWoReceiver.objects.filter(
                            permanence_id=permanence_id,
                            is_box=True,
                            is_active=True,
                            may_order=True,
                            translations__language_code=translation.get_language()
                        ).order_by(
                            'customer_unit_price',
                            'unit_deposit',
                            'translations__long_name',
                        ),
            'box_id': box_id,
            'permanence_id': permanence_id,
            'may_order': True
        }
    )
