from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.views.generic import ListView
from repanier.models.permanenceboard import PermanenceBoard
from repanier.tools import get_repanier_template_name


class TaskHistoryView(LoginRequiredMixin, ListView):
    template_name = get_repanier_template_name("task_history_form.html")
    context_object_name = "customer_tasks"
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.customer_id:
            return PermanenceBoard.objects.none()

        # Calcule la date limite (il y a exactement 2 an)
        one_year_ago = timezone.now().date() - relativedelta(years=2)

        # Filtre les inscriptions pour ce client et pour les permanences des 24 derniers mois minimum
        return PermanenceBoard.objects.filter(
            customer_id=user.customer_id,
            permanence__permanence_date__gte=one_year_ago
        ).select_related(
            'permanence', 'permanence_role'
        ).order_by("-permanence__permanence_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hide_cart_button"] = True
        context["permanence_id"] = "0"
        return context