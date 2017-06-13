# -*- coding: utf-8
from __future__ import unicode_literals

import datetime
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_CLOSED, PERMANENCE_SEND, PERMANENCE_OPENED
from repanier.models import PermanenceBoard
from repanier.tools import sint


@login_required()
@never_cache
@require_GET
def permanence_form_ajax(request):
    if not request.is_ajax() or request.user.is_staff:
        raise Http404
    result = "ko"
    p_permanence_board_id = sint(request.GET.get('permanence_board', -1))
    p_value_id = sint(request.GET.get('value', -1))
    if p_permanence_board_id >= 0 and p_value_id >= 0:
        if p_value_id == 0:
            # The customer may leave if (1) PLANNED or (2) less then 24h after registration and < CLOSED
            row_counter = PermanenceBoard.objects.filter(
                id=p_permanence_board_id,
                customer_id=request.user.customer.id,
                permanence__status__lt=PERMANENCE_OPENED,
                permanence_role__customers_may_register=True,
            ).update(
                customer=None
            )
            if row_counter == 0:
                row_counter = PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer_id=request.user.customer.id,
                    permanence__status__lt=PERMANENCE_CLOSED,
                    permanence_role__customers_may_register=True,
                    is_registered_on__gte=timezone.now() - datetime.timedelta(days=1)
                ).update(
                    customer=None
                )
        elif request.user.customer.may_order:
            # The customer may enroll until <= SEND
            row_counter = PermanenceBoard.objects.filter(
                id=p_permanence_board_id,
                customer__isnull=True,
                permanence__status__lte=PERMANENCE_SEND,
                permanence_role__customers_may_register=True
            ).update(
                customer_id=request.user.customer.id,
                is_registered_on=timezone.now()
            )
        else:
            row_counter = 0
        if row_counter > 0:
            result = "ok"
    return HttpResponse(result)
