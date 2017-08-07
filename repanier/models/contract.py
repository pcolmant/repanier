# -*- coding: utf-8
from __future__ import unicode_literals

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from recurrence.fields import RecurrenceField

from repanier.const import *
from repanier.models import Box
from repanier.models.box import box_pre_save


@python_2_unicode_compatible
class Contract(Box):
    first_permanence_date = models.DateField(
        verbose_name=_("first permanence date"),
        db_index=True
    )
    recurrences = RecurrenceField()
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
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("highest permanence_status"),
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


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, **kwargs):
    # ! Important to initialise all fields of the contract. Remember : a contract is a box.
    box_pre_save(sender, **kwargs)