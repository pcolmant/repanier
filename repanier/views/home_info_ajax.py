from django.conf import settings
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.utils.safestring import mark_safe

from repanier.const import SaleStatus
from repanier.models.permanence import Permanence


@never_cache
@require_GET
def home_info_ajax(request):
    """Render the opened permanences box for the home page.

    The markup lives in repanier/home_info.html; the fragment is
    injected into #containerInfo client side. Without any opened
    permanence the fragment is not served at all (404, the client keeps
    the container empty).
    """
    permanences = [
        {
            "order_url": permanence.get_order_url(),
            "display": permanence.get_permanence_display(),
            "offer_description_v2": mark_safe(permanence.offer_description_v2),
            "picture": permanence.picture,
        }
        for permanence in Permanence.objects.filter(status=SaleStatus.OPENED)
        .order_by("-permanence_date", "-id")
    ]
    if permanences:
        html = render_to_string(
            "repanier/home_info.html",
            {"permanences": permanences, "media_url": settings.MEDIA_URL},
        )
        return JsonResponse({"#containerInfo": html})
    raise Http404
