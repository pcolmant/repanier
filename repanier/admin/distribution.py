from django.contrib import admin

from repanier.models.distribution import (
    DistributionEvent,
    Offer,
    PickupSlot,
)
from repanier.models.product_alias import ProductAlias


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("title", "producer", "opening_at", "closing_at", "is_uncertain_arrival")
    list_filter = ("is_uncertain_arrival", "producer")
    search_fields = ("title", "producer__short_profile_name")


@admin.register(DistributionEvent)
class DistributionEventAdmin(admin.ModelAdmin):
    list_display = ("permanence", "offer", "distribution_date")
    list_filter = ("distribution_date",)
    search_fields = ("permanence__short_name_v2", "offer__title")


@admin.register(PickupSlot)
class PickupSlotAdmin(admin.ModelAdmin):
    list_display = ("distribution_event", "location", "starts_at", "ends_at")
    list_filter = ("starts_at",)
    search_fields = ("location", "distribution_event__permanence__short_name_v2")


@admin.register(ProductAlias)
class ProductAliasAdmin(admin.ModelAdmin):
    list_display = ("alias_label", "canonical_product", "confidence", "manually_validated")
    list_filter = ("manually_validated",)
    search_fields = ("alias_label", "canonical_product__long_name_v2")
