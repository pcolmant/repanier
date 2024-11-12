from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from repanier.const import SaleStatus
from repanier.models import Permanence


class PermamenceSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return Permanence.objects.filter(
                status__in=[SaleStatus.OPENED, SaleStatus.CLOSED, SaleStatus.SEND],
                master_permanence__isnull=True,
            ).order_by("permanence_date", "id")
        else:
            return Permanence.objects.filter(
                status=SaleStatus.OPENED, master_permanence__isnull=True
            ).order_by("permanence_date", "id")

    def location(self, obj):
        return reverse("repanier:order_view", args=[obj.id])
