from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils import translation
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET

from repanier_v2.const import EMPTY_STRING
from repanier_v2.models import Customer
from repanier_v2.models import Permanence
from repanier_v2.models.lut import LUT_DepartmentForCustomer
from repanier_v2.models.offeritem import OfferItemWoReceiver
from repanier_v2.models.producer import Producer
from repanier_v2.tools import permanence_ok_or_404, get_repanier_template_name


@never_cache
@require_GET
@csrf_protect
@login_required
def order_filter_view(request, permanence_id):
    user = request.user
    customer = (
        Customer.objects.filter(user_id=user.id, may_order=True).order_by("?").first()
    )
    if customer is None:
        raise Http404
    translation.activate(customer.language)
    permanence = Permanence.objects.filter(id=permanence_id).order_by("?").first()
    permanence_ok_or_404(permanence)
    is_basket = request.GET.get("is_basket", EMPTY_STRING)
    is_like = request.GET.get("is_like", EMPTY_STRING)
    producer_id = request.GET.get("producer", "all")
    department_id = request.GET.get("department", "all")
    box_id = request.GET.get("box", "all")
    if box_id != "all":
        is_box = True
        # Do not display "all department" as selected
        department_id = None
    else:
        is_box = False
    q = request.GET.get("q", None)

    if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
        producer_set = Producer.objects.filter(permanence=permanence_id).only(
            "id", "short_name"
        )
    else:
        producer_set = None

    department_set = (
        LUT_DepartmentForCustomer.objects.filter(
            offeritem__permanence_id=permanence_id,
            offeritem__is_active=True,
            offeritem__is_box=False,
        )
        .order_by("tree_id", "lft")
        .distinct("id", "tree_id", "lft")
    )
    if producer_id != "all":
        department_set = department_set.filter(offeritem__producer_id=producer_id)

    box_set = OfferItemWoReceiver.objects.filter(
        permanence_id=permanence_id,
        is_box=True,
        is_active=True,
        may_order=True,
        translations__language_code=translation.get_language(),
    ).order_by(
        "customer_unit_price",
        "unit_deposit",
        "translations__long_name",
    )

    template_name = get_repanier_template_name("order_filter.html")
    return render(
        request,
        template_name,
        {
            "is_like": is_like,
            "is_basket": is_basket,
            "is_box": is_box,
            "q": q,
            "producer_id": producer_id,
            "department_id": department_id,
            "box_id": box_id,
            "permanence_id": permanence_id,
            "may_order": True,
            "producer_set": producer_set,
            "department_set": department_set,
            "box_set": box_set,
            "is_filter_view": "active",
        },
    )
