from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.templatetags.repanier_tags import history_label


@never_cache
@require_GET
def my_balance_ajax(request):
    # history_label returns an html snippet, not an HttpResponse: wrap it
    # or never_cache crashes with "'str' object has no attribute 'has_header'"
    return HttpResponse(history_label(request))
