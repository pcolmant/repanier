# -*- coding: utf-8
from __future__ import unicode_literals

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.const import EMPTY_STRING


class PermanenceBoard(models.Model):
    customer = models.ForeignKey(
        'Customer', verbose_name=_("Customer"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME)
    # permanence_date duplicated to quickly calculate # participation of lasts 12 months
    permanence_date = models.DateField(_("Permanence date"), db_index=True)
    permanence_role = models.ForeignKey(
        'LUT_PermanenceRole', verbose_name=_("Permanence role"),
        on_delete=models.PROTECT)
    is_registered_on = models.DateTimeField(
        _("Registered on"), null=True, blank=True)

    class Meta:
        verbose_name = _("Permanence board")
        verbose_name_plural = _("Permanences board")
        unique_together = ("permanence", "permanence_role", "customer",)
        index_together = [
            ["permanence_date", "permanence", "permanence_role"],
        ]

    def __str__(self):
        return EMPTY_STRING


@receiver(pre_save, sender=PermanenceBoard)
def permanence_board_pre_save(sender, **kwargs):
    permanence_board = kwargs["instance"]
    permanence_board.permanence_date = permanence_board.permanence.permanence_date
