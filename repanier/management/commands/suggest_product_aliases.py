import json

from django.core.management.base import BaseCommand, CommandError

from repanier.models.product_alias import ProductAlias, suggest_product_aliases


class Command(BaseCommand):
    help = "Suggest existing product aliases for labels without modifying the catalogue."

    def add_arguments(self, parser):
        parser.add_argument("labels", nargs="+", help="Labels to compare with existing aliases.")
        parser.add_argument("--threshold", type=int, default=80, help="Minimum score, from 0 to 100.")
        parser.add_argument("--producer", type=int, help="Restrict candidates to one producer ID.")

    def handle(self, *args, **options):
        threshold = options["threshold"]
        if not 0 <= threshold <= 100:
            raise CommandError("--threshold must be between 0 and 100.")
        candidates = ProductAlias.objects.select_related("canonical_product").order_by("pk")
        if options["producer"] is not None:
            candidates = candidates.filter(canonical_product__producer_id=options["producer"])
        suggestions = suggest_product_aliases(options["labels"], candidates, threshold)
        results = []
        for label in options["labels"]:
            results.append({
                "label": label,
                "matches": [
                    {
                        "alias_id": match["alias"].pk,
                        "alias_label": match["alias"].alias_label,
                        "product_id": match["alias"].canonical_product_id,
                        "score": match["score"],
                        "confidence": str(match["alias"].confidence),
                        "manually_validated": match["alias"].manually_validated,
                    }
                    for match in suggestions[label]
                ],
            })
        self.stdout.write(json.dumps(results, ensure_ascii=False))
