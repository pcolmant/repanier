# -*- coding: utf-8
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models import Permanence
from repanier.tools import get_full_status_display


@never_cache
@require_GET
def display_status(request, permanence_id):
    if request.is_ajax():
        if request.user.is_staff:
            permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
            return HttpResponse(get_full_status_display(permanence))
    raise Http404
