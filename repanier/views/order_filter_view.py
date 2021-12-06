from django.conf import settings
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
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.producer import Producer
from repanier.tools import permanence_ok_or_404, get_repanier_template_name


@never_cache
@require_GET
@csrf_protect
@login_required
def order_filter_view(request, permanence_id):
    user = request.user
    customer = Customer.objects.filter(user_id=user.id, may_order=True).first()
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence = Permanence.objects.filter(id=permanence_id).first()
    permanence_ok_or_404(permanence)
    is_basket = request.GET.get("is_basket", EMPTY_STRING)
    is_like = request.GET.get("is_like", EMPTY_STRING)
    producer_id = request.GET.get("producer", "all")
    department_id = request.GET.get("department", "all")
    q = request.GET.get("q", None)

    if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
        producer_set = Producer.objects.filter(permanence=permanence_id).only(
            "id", "short_profile_name"
        )
    else:
        producer_set = None

    department_set = (
        LUT_DepartmentForCustomer.objects.filter(
            offeritem__permanence_id=permanence_id,
            offeritem__is_active=True,
        )
        .order_by("tree_id", "lft")
        .distinct("id", "tree_id", "lft")
    )
    if producer_id != "all":
        department_set = department_set.filter(offeritem__producer_id=producer_id)

    template_name = get_repanier_template_name("order_filter.html")
    return render(
        request,
        template_name,
        {
            "is_like": is_like,
            "is_basket": is_basket,
            "q": q,
            "producer_id": producer_id,
            "department_id": department_id,
            "permanence_id": permanence_id,
            "may_order": True,
            "producer_set": producer_set,
            "department_set": department_set,
            "is_filter_view": "active",
        },
    )
