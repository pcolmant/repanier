from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier_v2.models.customer import Customer
from repanier_v2.models.staff import Staff
from repanier_v2.tools import get_repanier_template_name


@login_required()
@csrf_protect
@never_cache
def who_is_who_view(request):
    from repanier_v2.globals import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO

    if not REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
        raise Http404
    q = request.POST.get("q", None)
    customer_list = Customer.objects.filter(may_order=True, is_default=False).order_by(
        "long_name"
    )
    if q is not None:
        customer_list = customer_list.filter(
            Q(long_name__icontains=q) | Q(city__icontains=q)
        )
    staff_list = Staff.objects.filter(is_active=True, can_be_contacted=True)
    template_name = get_repanier_template_name("who_is_who.html")
    return render(
        request,
        template_name,
        {"staff_list": staff_list, "customer_list": customer_list, "q": q},
    )