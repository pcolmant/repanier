from django.db import models
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
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
        verbose_name=_("Sale"),
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
        if self.customer is None:
            customer_name = EMPTY_STRING
            customer_phone_or_email = EMPTY_STRING
        else:
            customer_name = self.customer.long_basket_name
            customer_phone_or_email = self.customer.get_phone1(
                prefix=", "
            ) or self.customer.get_email1(prefix=", ")
        return format_html(
            "<b>{}</b> : <b>{}</b>{}<br>{}",
            self.permanence_role,
            customer_name,
            customer_phone_or_email,
            self.permanence_role.description_v2,
        )

    class Meta:
        verbose_name = _("Permanence board")
        verbose_name_plural = _("Permanences board")
        unique_together = ("permanence", "permanence_role", "customer")
        indexes = [
            models.Index(fields=["permanence_date", "permanence", "permanence_role"], name="repanier_permanenceboard_idx01"),
        ]

    def __str__(self):
        return EMPTY_STRING
