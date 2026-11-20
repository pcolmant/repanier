from django.core import signing
from django.db import models
from django.utils.translation import gettext_lazy as _

REMINDER_TOKEN_SALT = "repanier.permanence.reminder"


class PermanenceReminder(models.Model):
    permanence = models.ForeignKey(
        "repanier.Permanence",
        verbose_name=_("Offer"),
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    customer = models.ForeignKey(
        "repanier.Customer",
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        related_name="permanence_reminders",
    )
    requested_at = models.DateTimeField(
        _("Requested on"),
        auto_now_add=True,
    )
    sent_at = models.DateTimeField(
        _("Sent on"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Order reminder request")
        verbose_name_plural = _("Order reminder requests")
        constraints = [
            models.UniqueConstraint(
                fields=["permanence", "customer"],
                name="unique_permanence_customer_reminder",
            )
        ]

    @classmethod
    def make_token(cls, permanence_id: int, customer_id: int) -> str:
        signer = signing.TimestampSigner(salt=REMINDER_TOKEN_SALT)
        return signer.sign(f"{permanence_id}:{customer_id}")

    @classmethod
    def parse_token(cls, token: str, max_age: int = 60 * 60 * 24 * 30):
        signer = signing.TimestampSigner(salt=REMINDER_TOKEN_SALT)
        raw_value = signer.unsign(token, max_age=max_age)
        permanence_str, customer_str = raw_value.split(":", 1)
        return int(permanence_str), int(customer_str)

    def __str__(self):
        return f"{self.permanence} - {self.customer}"