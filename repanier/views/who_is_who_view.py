# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier.models.customer import Customer
from repanier.models.staff import Staff
from repanier.tools import check_if_is_coordinator


@login_required()
@csrf_protect
@never_cache
def who_is_who_view(request):
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO
    if not REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
        raise Http404
    q = request.POST.get('q', None)
    customer_list = Customer.objects.filter(may_order=True, represent_this_buyinggroup=False).order_by(
        "long_basket_name")
    if q is not None:
        customer_list = customer_list.filter(Q(long_basket_name__icontains=q) | Q(city__icontains=q))
    staff_list = Staff.objects.filter(
        is_active=True, is_contributor=False
    )
    is_coordinator = check_if_is_coordinator(request)
    return render(
        request,
        "repanier/who_is_who.html",
        {
            'staff_list': staff_list,
            'customer_list': customer_list,
            'coordinator': is_coordinator,
            'q': q
        }
    )
