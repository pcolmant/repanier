from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _
from rapidfuzz import fuzz


class ProductAlias(models.Model):
    id = models.AutoField(primary_key=True)
    canonical_product = models.ForeignKey(
        "Product",
        on_delete=models.PROTECT,
        related_name="aliases",
    )
    alias_label = models.CharField(_("Alias label"), max_length=150)
    confidence = models.DecimalField(
        _("Confidence"),
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    manually_validated = models.BooleanField(
        _("Manually validated"),
        default=False,
    )

    class Meta:
        unique_together = ("canonical_product", "alias_label")


def suggest_product_alias(label, candidates, threshold=80):
    if not 0 <= threshold <= 100:
        raise ValueError("The matching threshold must be between 0 and 100.")
    if not str(label).strip():
        return []
    suggestions = []
    for candidate in candidates:
        score = fuzz.token_sort_ratio(
            str(label).strip().lower(),
            str(candidate.alias_label).strip().lower(),
        )
        if score >= threshold:
            suggestions.append({
                "alias": candidate,
                "score": score,
            })
    return sorted(
        suggestions,
        key=lambda suggestion: (
            -suggestion["score"],
            -int(suggestion["alias"].manually_validated),
            -Decimal(suggestion["alias"].confidence),
            suggestion["alias"].pk or 0,
        ),
    )


def suggest_product_aliases(labels, candidates, threshold=80):
    """Propose matches without changing validated aliases or their confidence."""
    candidates = list(candidates)
    return {
        label: suggest_product_alias(label, candidates, threshold=threshold)
        for label in labels
    }
