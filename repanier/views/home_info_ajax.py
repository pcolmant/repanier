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

from repanier.const import PERMANENCE_OPENED
from repanier.models import Permanence


@never_cache
@require_GET
def home_info_ajax(request):
    if request.is_ajax():
        result = []
        for permanence in Permanence.objects.filter(
                status=PERMANENCE_OPENED) \
                .only("id", "permanence_date", "with_delivery_point") \
                .order_by('permanence_date'):
            result.append(
                format_html(
                    '<div class="panel-heading"><h4 class="panel-title"><a href="{}">{}</a></h4></div>',
                    reverse('order_view', args=(permanence.id,)),
                    permanence.get_permanence_customer_display()
                )
            )
            if permanence.offer_description_on_home_page and permanence.offer_description:
                if permanence.picture:
                    result.append(
                        format_html(
                            '<div class="panel-body"><div class="col-xs-12"><img class="img-rounded" style="float: left; margin: 5px;" alt="{} title="{}" src="{}{}"/>{}</div></div>',
                            permanence.get_permanence_customer_display(),
                            permanence.get_permanence_customer_display(),
                            settings.MEDIA_URL,
                            permanence.picture,
                            mark_safe(permanence.offer_description)
                        )
                    )
                else:
                    result.append(
                        format_html(
                            '<div class="panel-body"><div class="col-xs-12">{}</div></div>',
                            mark_safe(permanence.offer_description)
                        )
                    )
        if len(result) > 0:
            return HttpResponse("".join(result))
    raise Http404
