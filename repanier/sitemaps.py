from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from repanier.const import SaleStatus
from repanier.models import Permanence


class PermanenceSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return (
            Permanence.objects.filter(
                status=SaleStatus.OPENED,
                master_permanence__isnull=True,
            )
            .exclude(id__isnull=True)
            .order_by("permanence_date", "id")
        )

    def location(self, obj):
        return reverse("repanier:order_view", args=[obj.id])