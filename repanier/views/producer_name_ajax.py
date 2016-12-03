# -*- coding: utf-8
from __future__ import unicode_literals

from django.http import Http404
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Producer


@never_cache
@require_GET
def producer_name_ajax(request, offer_uuid=None):
    if request.is_ajax():
        producer = Producer.objects.filter(offer_uuid=offer_uuid, is_active=True).order_by('?').first()
        if producer is None:
            return HttpResponse(_('Anonymous'))
        return HttpResponse(producer.short_profile_name)
    raise Http404
