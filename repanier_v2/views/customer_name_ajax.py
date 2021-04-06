from django.http import Http404
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier_v2.middleware import is_ajax


@never_cache
@require_GET
def customer_name_ajax(request):
    if is_ajax():
        user = request.user
        if user.is_anonymous:
            result = _("Anonymous")
        else:
            result = user.username
        return HttpResponse(result)
    raise Http404
