from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.http import require_GET

from repanier.models.permanence import Permanence


@require_GET
def display_status(request, permanence_id):
    if request.user.is_staff:
        permanence = Permanence.objects.filter(id=permanence_id).first()
        return HttpResponse(permanence.get_html_status_display(force_refresh=False))
    raise Http404
