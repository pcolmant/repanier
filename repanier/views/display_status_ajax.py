from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.middleware import is_ajax
from repanier.models.permanence import Permanence


@never_cache
@require_GET
@login_required
def display_status(request, permanence_id):
    if is_ajax():
        if request.user.is_staff:
            permanence = (
                Permanence.objects.filter(id=permanence_id).order_by("?").first()
            )
            return HttpResponse(permanence.get_html_status_display(force_refresh=False))
    raise Http404
