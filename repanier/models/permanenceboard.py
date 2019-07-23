# -*- coding: utf-8

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

import repanier.apps
from repanier.const import EMPTY_STRING


class PermanenceBoard(models.Model):
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        null=True,
        blank=True,
        db_index=True,
        on_delete=models.PROTECT,
    )
    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.CASCADE,
    )
    permanence_date = models.DateField(
        _("Permanence date"),
        help_text="Date of distribution/task execution. Maybe different from permanence_date in case of solidarity contract for example.",
    )
    permanence_role = models.ForeignKey(
        "LUT_PermanenceRole",
        verbose_name=_("Permanence role"),
        on_delete=models.PROTECT,
    )
    master_permanence_board = models.ForeignKey(
        "PermanenceBoard",
        verbose_name=_("Master permanence board"),
        related_name="child_permanence_boards",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        help_text="Link all PermanenceBoards for a distribution of a given contract"
        "to the initial PermanenceBoard created thanks to the admin ModelInline",
    )
    is_registered_on = models.DateTimeField(_("Registered on"), null=True, blank=True)

    def customers_may_register(self):
        return (
            self.permanence_date > timezone.now().date()
            and self.permanence_role.customers_may_register
        )

    class Meta:
        verbose_name = _("Permanence board")
        verbose_name_plural = _("Permanences board")
        # a customer maybe registered for the same role at different `permanence_date` of the same `permanence`
        # however he can't be at the same role at the same `permanence_date`
        unique_together = ("permanence_date", "permanence_role", "customer")
        index_together = [["permanence_date", "permanence", "permanence_role"]]

    def __str__(self):
        return EMPTY_STRING
