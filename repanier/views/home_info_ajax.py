# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.http import Http404
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, EMPTY_STRING
from repanier.models import Permanence


@never_cache
@require_GET
def home_info_ajax(request):
    if request.is_ajax():
        from repanier.apps import REPANIER_SETTINGS_CONFIG
        permanences = []
        home_info = EMPTY_STRING
        for permanence in Permanence.objects.filter(
                status=PERMANENCE_OPENED) \
                .only("id", "permanence_date", "with_delivery_point") \
                .order_by('-permanence_date', '-id'):
            permanences.append(
                format_html(
                    '<div class="panel-heading"><h4 class="panel-title"><a href="{}">{}</a></h4></div>',
                    reverse('order_view', args=(permanence.id,)),
                    permanence.get_permanence_customer_display()
                )
            )
            if permanence.offer_description_on_home_page and permanence.offer_description:
                if permanence.picture:
                    permanences.append(
                        format_html(
                            '<div class="panel-body"><div class="col-xs-12"><img class="img-responsive img-rounded" style="float: left; margin: 5px;" alt="{}" title="{}" src="{}{}"/><div class="clearfix visible-xs-block visible-sm-block"></div>{}</div></div>',
                            permanence.get_permanence_customer_display(),
                            permanence.get_permanence_customer_display(),
                            settings.MEDIA_URL,
                            permanence.picture,
                            mark_safe(permanence.offer_description)
                        )
                    )
                else:
                    permanences.append(
                        format_html(
                            '<div class="panel-body"><div class="col-xs-12">{}</div></div>',
                            mark_safe(permanence.offer_description)
                        )
                    )
        if len(permanences) > 0:
            home_info = """
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
        if REPANIER_SETTINGS_CONFIG.notification:
            if REPANIER_SETTINGS_CONFIG.notification_is_public or request.user.is_authenticated:
                home_info = """
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
                {home_info}
                """.format(
                    notification=REPANIER_SETTINGS_CONFIG.notification,
                    home_info=home_info
                )

        return HttpResponse(home_info)
    raise Http404
