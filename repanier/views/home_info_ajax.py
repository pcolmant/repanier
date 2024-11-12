from django.conf import settings
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from repanier.const import EMPTY_STRING, SaleStatus
from repanier.models.permanence import Permanence


@never_cache
@require_GET
def home_info_ajax(request):
    if settings.REPANIER_SETTINGS_TEMPLATE == "bs3":
        return home_info_bs3_ajax(request)
    elif settings.REPANIER_SETTINGS_TEMPLATE == "bs5":
        return home_info_bs5_ajax(request)

def home_info_bs3_ajax(request):
    permanences = []
    for permanence in (
        Permanence.objects.filter(status=SaleStatus.OPENED)
        .order_by("-permanence_date", "-id")
    ):
        permanences.append(
            format_html(
                '<div class="panel-heading"><h4 class="panel-title"><a href="{}">{}</a></h4></div>',
                permanence.get_order_url(),
                permanence.get_permanence_display(),
            )
        )
        if permanence.offer_description_v2:
            if permanence.picture:
                permanences.append(
                    format_html(
                        """
                        <div class="panel-body">
                            <div class="col-xs-12">
                                <img class="img-responsive img-rounded" style="float: left; margin: 5px;" alt="{0}" title="{0}" src="{1}{2}"/>
                                <div class="clearfix visible-xs-block visible-sm-block"></div>
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
                        '<div class="panel-body"><div class="col-xs-12">{}</div></div>',
                        mark_safe(permanence.offer_description_v2),
                    )
                )
    if len(permanences) > 0:
        permanences_info_html = """
        <div class="container">
            <div class="row">
                <div class="panel-group">
                    <div class="panel panel-default">
                        {permanences}
                    </div>
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

def home_info_bs5_ajax(request):
    permanences = []
    for permanence in (
        Permanence.objects.filter(status=SaleStatus.OPENED)
        .order_by("-permanence_date", "-id")
    ):
        permanences.append(
            format_html(
                '<div class="panel-heading"><h4 class="panel-title"><a href="{}">{}</a></h4></div>',
                permanence.get_order_url(),
                permanence.get_permanence_display(),
            )
        )
        if permanence.offer_description_v2:
            if permanence.picture:
                permanences.append(
                    format_html(
                        """
                        <div class="panel-body">
                            <div class="col-xs-12">
                                <img class="img-responsive img-rounded" style="float: left; margin: 5px;" alt="{0}" title="{0}" src="{1}{2}"/>
                                <div class="clearfix visible-xs-block visible-sm-block"></div>
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
                        '<div class="panel-body"><div class="col-xs-12">{}</div></div>',
                        mark_safe(permanence.offer_description_v2),
                    )
                )
    if len(permanences) > 0:
        permanences_info_html = """
        <div class="container">
            <div class="row">
                <div class="panel-group">
                    <div class="panel panel-default">
                        {permanences}
                    </div>
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
