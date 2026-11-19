import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from repanier.const import (
    EMPTY_STRING,
    EmailDeliveryStatus,
    EmailNature,
)


class EmailLog(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )
    message_id = models.CharField(
        verbose_name=_("Message ID"),
        max_length=255,
        blank=True,
        default=EMPTY_STRING,
        db_index=True,
    )
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    recipient_email = models.EmailField(
        verbose_name=_("Recipient email"),
        db_index=True,
    )
    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=_("Permanence"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    nature = models.CharField(
        verbose_name=_("Nature"),
        max_length=3,
        choices=EmailNature.choices,
        default=EmailNature.OTHER,
        db_index=True,
    )
    status = models.CharField(
        verbose_name=_("Delivery status"),
        max_length=3,
        choices=EmailDeliveryStatus.choices,
        default=EmailDeliveryStatus.SENT,
        db_index=True,
    )
    error_reason = models.CharField(
        verbose_name=_("Error reason"),
        max_length=255,
        blank=True,
        default=EMPTY_STRING,
    )
    created_at = models.DateTimeField(
        verbose_name=_("Created at"),
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        verbose_name=_("Updated at"),
        auto_now=True,
    )

    class Meta:
        verbose_name = _("Email log")
        verbose_name_plural = _("Email logs")
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="emaillog_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_email} ({self.get_nature_display()} - {self.get_status_display()})"