# -*- coding: utf-8
from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from recurrence.fields import RecurrenceField

import repanier.apps
from repanier.models import Box
from repanier.const import *


@python_2_unicode_compatible
class Contract(Box):
    first_permanence_date = models.DateField(_("first permanence date"), db_index=True)
    recurrences = RecurrenceField()
    permanence = models.ForeignKey(
        'Permanence', verbose_name=repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT,
        null=True, blank=True, db_index=True)
    customers = models.ManyToManyField(
        'Customer',
        verbose_name=_("customers"),
        blank=True
    )
    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))

    def get_full_status_display(self):
        return self.get_status_display()

    get_full_status_display.short_description = (_("contract status"))
    get_full_status_display.allow_tags = True

    def __str__(self):
        return '%s' % self.long_name

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")
