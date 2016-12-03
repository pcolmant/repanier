# -*- coding: utf-8
from __future__ import unicode_literals

from django.db.models import F
from django.views.generic import ListView

import repanier.apps
from repanier.const import PERMANENCE_SEND
from repanier.models import PermanenceBoard


class PermanenceView(ListView):
    template_name = 'repanier/task_form.html'
    success_url = '/thanks/'
    paginate_by = 50
    paginate_orphans = 5

    def get_context_data(self, **kwargs):
        context = super(PermanenceView, self).get_context_data(**kwargs)
        context['DISPLAY_PRODUCER'] = repanier.apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
        return context

    def get_queryset(self):
        qs = PermanenceBoard.objects.filter(
            permanence__status__lte=PERMANENCE_SEND,
            permanence_role__rght=F('permanence_role__lft') + 1,
            permanence_role__is_active=True
        ).order_by(
            "permanence_date", "permanence",
            "permanence_role__tree_id",
            "permanence_role__lft"
        )
        return qs
