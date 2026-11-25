import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.const import DECIMAL_ZERO


class PermanencePreparationAccess(models.Model):
    permanence = models.OneToOneField(
        "Permanence",
        on_delete=models.CASCADE,
        related_name="preparation_access",
    )
    token_hash = models.CharField(
        _("Opaque token hash"),
        max_length=64,
        unique=True,
        editable=False,
    )
    expires_at = models.DateTimeField(_("Expires at"))
    revoked_at = models.DateTimeField(
        _("Revoked at"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    def is_valid(self, at=None):
        at = at or timezone.now()
        return self.revoked_at is None and self.expires_at > at

    class Meta:
        verbose_name = _("Permanence preparation access")
        verbose_name_plural = _("Permanence preparation accesses")


class PreparationSyncEvent(models.Model):
    STATUS_CREATED = "created"
    STATUS_APPLIED = "applied"
    STATUS_CONFLICT = "conflict"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_CREATED, _("Created")),
        (STATUS_APPLIED, _("Applied")),
        (STATUS_CONFLICT, _("Conflict")),
        (STATUS_REJECTED, _("Rejected")),
    )

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )
    permanence = models.ForeignKey(
        "Permanence",
        on_delete=models.PROTECT,
        related_name="preparation_sync_events",
    )
    purchase = models.ForeignKey(
        "Purchase",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparation_sync_events",
    )
    client_timestamp = models.DateTimeField(db_index=True)
    server_timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    operation = models.CharField(max_length=32)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
        db_index=True,
    )
    conflict_reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    validated_by = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparation_sync_events_validated",
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    accounting_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    accounting_status = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = _("Preparation synchronization event")
        verbose_name_plural = _("Preparation synchronization events")
        indexes = [
            models.Index(
                fields=["permanence", "client_timestamp"],
                name="repa_prep_sync_idx01",
            ),
            models.Index(
                fields=["permanence", "status", "server_timestamp"],
                name="repa_prep_sync_idx02",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["permanence", "uuid"],
                name="unique_prep_sync_permanence_uuid",
            )
        ]


class DepositContainerType(models.Model):
    code = models.CharField(
        _("Code"),
        max_length=32,
        unique=True,
    )
    label = models.CharField(
        _("Label"),
        max_length=100,
    )
    unit_credit = ModelRepanierMoneyField(
        _("Credit per returned container"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        db_index=True,
    )
    sort_order = models.PositiveSmallIntegerField(
        _("Sort order"),
        default=0,
        db_index=True,
    )

    class Meta:
        verbose_name = _("Deposit container type")
        verbose_name_plural = _("Deposit container types")
        ordering = ("sort_order", "label")

    def __str__(self):
        return self.label


class DepositReceipt(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )
    permanence = models.ForeignKey(
        "Permanence",
        on_delete=models.PROTECT,
        related_name="deposit_receipts",
    )
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deposit_receipts",
    )
    container_type = models.ForeignKey(
        DepositContainerType,
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    returned_count = models.PositiveIntegerField(
        _("Returned containers"),
        default=0,
    )
    missing_count = models.PositiveIntegerField(
        _("Missing containers"),
        default=0,
    )
    credit_amount = ModelRepanierMoneyField(
        _("Credit amount"),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
    )
    status = models.CharField(
        _("Status"),
        max_length=16,
        choices=PreparationSyncEvent.STATUS_CHOICES,
        default=PreparationSyncEvent.STATUS_CREATED,
        db_index=True,
    )
    client_timestamp = models.DateTimeField(db_index=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    accounting_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    accounting_status = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = _("Deposit receipt")
        verbose_name_plural = _("Deposit receipts")
        constraints = [
            models.UniqueConstraint(
                fields=["permanence", "uuid"],
                name="unique_deposit_receipt_uuid",
            )
        ]
        indexes = [
            models.Index(
                fields=["permanence", "customer", "container_type"],
                name="repa_dep_receipt_idx01",
            )
        ]
