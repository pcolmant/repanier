from django.db import models
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

import repanier.apps
from repanier.const import EMPTY_STRING


class SaleActivity(models.Model):
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        null=True,
        blank=True,
        db_index=True,
        on_delete=models.PROTECT,
    )
    sale = models.ForeignKey(
        "Sale",
        verbose_name=_("Offer"),
        on_delete=models.CASCADE,
    )
    # permanence_date duplicated to quickly calculate # participation of lasts 12 months
    sale_date = models.DateField(_("Permanence date"), db_index=True)
    activity = models.ForeignKey(
        "Activity",
        verbose_name=_("Sale activity"),
        on_delete=models.PROTECT,
    )
    is_registered_on = models.DateTimeField(_("Registered on"), null=True, blank=True)

    @property
    def get_html_board_member(self):
        # Do not return phone2 nor email2
        if self.customer is None:
            customer_name = EMPTY_STRING
            customer_phone_or_email = EMPTY_STRING
        else:
            customer_name = self.customer.long_name
            customer_phone_or_email = self.customer.get_phone1(
                prefix=", "
            ) or self.customer.get_email1(prefix=", ")
        return format_html(
            "<b>{}</b> : <b>{}</b>{}<br>{}",
            self.activity,
            customer_name,
            customer_phone_or_email,
            self.activity.description,
        )

    class Meta:
        verbose_name = _("Sale activities")
        verbose_name_plural = _("Sales activities")
        unique_together = ("sale", "activity", "customer")
        index_together = [["sale_date", "sale", "activity"]]

    def __str__(self):
        return EMPTY_STRING
