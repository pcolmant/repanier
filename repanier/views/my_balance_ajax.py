from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.templatetags.repanier_tags import history_label


@never_cache
@require_GET
def my_balance_ajax(request):
    return history_label(request)
