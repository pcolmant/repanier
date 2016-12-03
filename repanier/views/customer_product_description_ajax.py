# -*- coding: utf-8
from __future__ import unicode_literals

from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_GET
from parler.models import TranslationDoesNotExist

from repanier.const import EMPTY_STRING, PERMANENCE_OPENED, PERMANENCE_SEND
from repanier.models import OfferItem, BoxContent
from repanier.tools import permanence_ok_or_404, sint, get_display, html_box_content


@require_GET
def customer_product_description_ajax(request):
    if request.is_ajax():
        offer_item_id = sint(request.GET.get('offer_item', 0))
        offer_item = get_object_or_404(OfferItem, id=offer_item_id)
        permanence = offer_item.permanence
        permanence_ok_or_404(permanence)
        if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
            try:
                result = offer_item.cache_part_e
                result = html_box_content(offer_item, request.user, result)

                if result is None or result == EMPTY_STRING:
                    result = "%s" % _("There is no more product's information")
            except TranslationDoesNotExist:
                result = "%s" % _("There is no more product's information")
        else:
            result = "%s" % _("There is no more product's information")
        return HttpResponse(result)
    raise Http404
