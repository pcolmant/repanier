from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Offer(models.Model):
    id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(
        "Producer",
        on_delete=models.PROTECT,
        related_name="distribution_offers",
        null=True,
        blank=True,
    )
    title = models.CharField(_("Offer title"), max_length=150)
    opening_at = models.DateTimeField(_("Opening date"), null=True, blank=True)
    closing_at = models.DateTimeField(_("Closing date"), null=True, blank=True)
    is_uncertain_arrival = models.BooleanField(
        _("Uncertain arrival"),
        default=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-opening_at", "-id")


class DistributionEvent(models.Model):
    id = models.AutoField(primary_key=True)
    permanence = models.OneToOneField(
        "Permanence",
        on_delete=models.PROTECT,
        related_name="distribution_event",
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.PROTECT,
        related_name="distribution_events",
        null=True,
        blank=True,
    )
    distribution_date = models.DateField(_("Distribution date"))

    @property
    def has_uncertain_arrival(self):
        return bool(self.offer_id and self.offer.is_uncertain_arrival)

    class Meta:
        ordering = ("distribution_date", "-id")


class PickupSlot(models.Model):
    id = models.AutoField(primary_key=True)
    distribution_event = models.ForeignKey(
        DistributionEvent,
        on_delete=models.CASCADE,
        related_name="pickup_slots",
    )
    location = models.CharField(_("Pickup location"), max_length=200)
    starts_at = models.DateTimeField(_("Starts at"))
    ends_at = models.DateTimeField(_("Ends at"))

    class Meta:
        ordering = ("starts_at", "ends_at")

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError(
                {"ends_at": _("The end of the slot cannot precede its start.")}
            )