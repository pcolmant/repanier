from django.db.models import F
from django.views.generic import ListView

from repanier.const import SaleStatus
from repanier.models.permanenceboard import PermanenceBoard
from repanier.tools import get_repanier_template_name


class PermanenceView(ListView):
    template_name = get_repanier_template_name("task_form.html")
    success_url = "/"
    paginate_by = 50
    paginate_orphans = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = context.get("page_obj")
        if page_obj and page_obj.object_list:
            first_item = page_obj.object_list[0]
            if hasattr(first_item, "permanence_id"):
                context["permanence_id"] = first_item.permanence_id

        # Sécurité pour s'assurer qu'on transmet bien une URL de filtre exploitable par le template
        qs = self.get_queryset()
        if qs.exists():
            context["first_permanence_filter_url"] = qs.first().permanence.get_order_filter_url()

        context["hide_cart_button"] = True
        return context

    def get_queryset(self):
        qs = PermanenceBoard.objects.filter(
            permanence__status__lte=SaleStatus.SEND,
            permanence__master_permanence__isnull=True,
            permanence_role__rght=F("permanence_role__lft") + 1,
            permanence_role__is_active=True,
        ).order_by(
            "permanence_date", "permanence_role__tree_id", "permanence_role__lft"
        )
        return qs