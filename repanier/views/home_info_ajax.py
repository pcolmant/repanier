from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from repanier.const import EMPTY_STRING, SaleStatus
from repanier.models.permanence import Permanence


@never_cache
@require_GET
def home_info_ajax(request):
    permanences = []
    for permanence in (
        Permanence.objects.filter(status=SaleStatus.OPENED)
        .order_by("-permanence_date", "-id")
    ):
        permanences.append(
            format_html(
                '<div class="card-header"><h4 class="mb-0"><a href="{}" class="text-decoration-none">{}</a></h4></div>',
                permanence.get_order_url(),
                permanence.get_permanence_display(),
            )
        )
        if permanence.offer_description_v2:
            if permanence.picture:
                permanences.append(
                    format_html(
                        """
                        <div class="card-body">
                            <div class="col-12">
                                <img class="img-fluid rounded float-start me-3 mb-2" alt="{0}" title="{0}" src="{1}{2}"/>
                                <div class="clearfix d-block d-md-none"></div>
                                {3}
                            </div>
                        </div>
                        """,
                        permanence.get_permanence_display(),
                        settings.MEDIA_URL,
                        permanence.picture,
                        mark_safe(permanence.offer_description_v2),
                    )
                )
            else:
                permanences.append(
                    format_html(
                        '<div class="card-body"><div class="col-12">{}</div></div>',
                        mark_safe(permanence.offer_description_v2),
                    )
                )
    if len(permanences) > 0:
        permanences_info_html = """
        <div class="container">
            <div class="row">
                <div class="card border-default mb-3">
                    {permanences}
                </div>
            </div>
        </div>
        """.format(
            permanences="".join(permanences)
        )
    else:
        permanences_info_html = EMPTY_STRING

    html = "{permanences_info_html}".format(
        permanences_info_html=permanences_info_html,
    )
    if html:
        return JsonResponse({"#containerInfo": mark_safe(html)})
    raise Http404