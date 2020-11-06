from django.conf import settings
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, EMPTY_STRING
from repanier.models.permanence import Permanence


@never_cache
@require_GET
def home_info_bs3_ajax(request):
    if request.is_ajax():
        from repanier.apps import REPANIER_SETTINGS_NOTIFICATION

        permanences = []
        for permanence in (
            Permanence.objects.filter(status=PERMANENCE_OPENED)
            .only("id", "permanence_date", "with_delivery_point")
            .order_by("-permanence_date", "-id")
        ):
            permanences.append(
                format_html(
                    '<div class="panel-heading"><h4 class="panel-title"><a href="{}">{}</a></h4></div>',
                    reverse("repanier:order_view", args=(permanence.id,)),
                    permanence.get_permanence_display(),
                )
            )
            if permanence.offer_description:
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
                            mark_safe(permanence.offer_description),
                        )
                    )
                else:
                    permanences.append(
                        format_html(
                            '<div class="panel-body"><div class="col-xs-12">{}</div></div>',
                            mark_safe(permanence.offer_description),
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

        notification = REPANIER_SETTINGS_NOTIFICATION.get_notification_display()
        if notification:
            notification_html = """
                <div class="container">
                    <div class="row">
                        <div class="panel-group">
                            <div class="panel panel-default">
                                <div class="panel-body">
                                    {notification}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                """.format(
                notification=notification,
            )
        else:
            notification_html = EMPTY_STRING

        html = "{notification_html}{permanences_info_html}".format(
            notification_html=notification_html,
            permanences_info_html=permanences_info_html,
        )
        if html:
            return JsonResponse({"#containerInfo": mark_safe(html)})
    raise Http404
