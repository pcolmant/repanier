from django.db import models
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

import repanier_v2.globals
from repanier_v2.const import EMPTY_STRING


class OrderTask(models.Model):
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer"),
        null=True,
        blank=True,
        db_index=True,
        on_delete=models.PROTECT,
    )
    order = models.ForeignKey(
        "Order",
        verbose_name=_("Offer"),
        on_delete=models.CASCADE,
    )
    # permanence_date duplicated to quickly calculate # participation of lasts 12 months
    sale_date = models.DateField(_("Permanence date"), db_index=True)
    task = models.ForeignKey(
        "Task",
        verbose_name=_("Sale task"),
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
            self.task,
            customer_name,
            customer_phone_or_email,
            self.task.description,
        )

    class Meta:
        verbose_name = _("Sale activities")
        verbose_name_plural = _("Sales activities")
        unique_together = ("order", "task", "customer")
        index_together = [["sale_date", "order", "task"]]

    def __str__(self):
        return EMPTY_STRING
