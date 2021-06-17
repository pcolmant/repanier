from django.db.models import F
from django.views.generic import ListView

from repanier_v2.const import ORDER_SEND, EMPTY_STRING
from repanier_v2.models.permanenceboard import PermanenceBoard
from repanier_v2.tools import get_repanier_template_name


class PermanenceView(ListView):
    template_name = get_repanier_template_name("task_form.html")
    success_url = "/"
    paginate_by = 50
    paginate_orphans = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_anonymous:
            from repanier_v2.globals import REPANIER_SETTINGS_CONFIG

            context[
                "how_to_create_an_account"
            ] = REPANIER_SETTINGS_CONFIG.safe_translation_getter(
                "how_to_create_an_account", any_language=True, default=EMPTY_STRING
            )
        else:
            context["how_to_create_an_account"] = EMPTY_STRING

        return context

    def get_queryset(self):
        qs = PermanenceBoard.objects.filter(
            permanence__status__lte=ORDER_SEND,
            permanence__master_permanence__isnull=True,
            permanence_role__rght=F("permanence_role__lft") + 1,
            permanence_role__is_active=True,
        ).order_by(
            "permanence_date", "permanence_role__tree_id", "permanence_role__lft"
        )
        return qs