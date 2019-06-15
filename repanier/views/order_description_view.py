# -*- coding: utf-8

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils import translation
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET

from repanier.const import EMPTY_STRING
from repanier.models import Customer
from repanier.models import Permanence
from repanier.tools import permanence_ok_or_404, get_repanier_template_name, sint


@never_cache
@require_GET
@csrf_protect
@login_required
def order_description_view(request, permanence_id):
    user = request.user
    customer = Customer.objects.filter(
        user_id=user.id, may_order=True).order_by('?').first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    permanence_ok_or_404(permanence)
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

    template_name = get_repanier_template_name("order_description.html")
    return render(
        request, template_name,
        {
            'is_like': is_like,
            'is_basket': is_basket,
            'is_box': is_box,
            'q': q,
            'all_dates': all_dates,

            'date_id': date_id,
            'producer_id': producer_id,
            'department_id': department_id,
            'box_id': box_id,
            'permanence_id': permanence_id,
            'may_order': True,

            'permanence': permanence,

            'is_description_view': 'active'
        }
    )