from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.purchase import Purchase


def compute_benchmarks():
    """Compare total quantities per product and sale using today's active membership."""
    members = Customer.objects.filter(
        is_active=True, is_anonymized=False, may_order=True, is_group=False
    ).count()
    if not members:
        return members, []

    sales = Purchase.objects.filter(
        permanence__is_demo=False,
        permanence__status__in=[
            SaleStatus.SEND, SaleStatus.WAIT_FOR_INVOICED,
            SaleStatus.INVOICED, SaleStatus.ARCHIVED,
        ],
        offer_item__product__isnull=False,
    ).values(
        "producer_id", "offer_item__product_id", "permanence_id",
    ).annotate(total=Sum("quantity_invoiced"))
    quantities = defaultdict(list)
    for sale in sales:
        quantities[(sale["producer_id"], sale["offer_item__product_id"])].append(
            sale["total"] / Decimal(members)
        )
    results = []
    for (producer_id, product_id), values in sorted(quantities.items()):
        results.append({
            "producer_id": producer_id,
            "product_id": product_id,
            "sales": len(values),
            "min": min(values),
            "max": max(values),
            "average": sum(values, Decimal(0)) / len(values),
        })
    return members, results


class Command(BaseCommand):
    help = "Compute indicative demand per currently active member and product."

    def handle(self, *args, **options):
        members, results = compute_benchmarks()
        self.stdout.write(f"{members} active members")
        if not members:
            self.stdout.write("Benchmarks unavailable: no active members.")
        for result in results:
            self.stdout.write(
                "producer={producer_id} product={product_id} sales={sales} "
                "normalized min={min} max={max} average={average}".format(**result)
            )
