# -*- coding: utf-8
from __future__ import unicode_literals

from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Permanence


@never_cache
@require_GET
def display_status(request, permanence_id):
    if request.is_ajax():
        if request.user.is_staff:
            permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
            return HttpResponse(permanence.get_full_status_display())
    raise Http404
