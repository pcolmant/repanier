# -*- coding: utf-8

from django.db import models
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

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
    # permanence_date duplicated to quickly calculate # participation of lasts 12 months
    permanence_date = models.DateField(_("Permanence date"), db_index=True)
    permanence_role = models.ForeignKey(
        "LUT_PermanenceRole",
        verbose_name=_("Permanence role"),
        on_delete=models.PROTECT,
    )
    is_registered_on = models.DateTimeField(_("Registered on"), null=True, blank=True)

    @property
    def get_html_board_member(self):
        # Do not return phone2 nor email2
        return format_html(
            "<b>{}</b> : <b>{}</b>{}<br>{}",
            self.permanence_role,
            self.customer.long_basket_name,
            self.customer.get_phone1(for_members=False, prefix=", ")
            or self.customer.get_email1(prefix=", "),
            self.permanence_role.safe_translation_getter(
                "description", any_language=True, default=EMPTY_STRING
            ),
        )

    class Meta:
        verbose_name = _("Permanence board")
        verbose_name_plural = _("Permanences board")
        unique_together = ("permanence", "permanence_role", "customer")
        index_together = [["permanence_date", "permanence", "permanence_role"]]

    def __str__(self):
        return EMPTY_STRING
