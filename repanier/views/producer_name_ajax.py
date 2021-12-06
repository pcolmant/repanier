from django.http import Http404
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.producer import Producer


@never_cache
@require_GET
def producer_name_ajax(request, offer_uuid=None):
    producer = (
        Producer.objects.filter(offer_uuid=offer_uuid, is_active=True)
            .first()
    )
    if producer is None:
        return HttpResponse(_("Anonymous"))
    return HttpResponse(producer.short_profile_name)
