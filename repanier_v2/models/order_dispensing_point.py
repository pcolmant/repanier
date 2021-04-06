from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier_v2.const import (
    EMPTY_STRING,
)


class OrderDispensingPoint(models.Model):
    order = models.ForeignKey(
        "Order",
        verbose_name=_("Sale"),
        on_delete=models.CASCADE,
    )
    distribution_point = models.ForeignKey(
        "DispensingPoint",
        verbose_name=_("Distribution point"),
        db_index=True,
        on_delete=models.PROTECT,
    )
    period = models.CharField(
        _("Period"), max_length=50, blank=True, default=EMPTY_STRING
    )
    order_is_open = models.BooleanField(default=False)

    def set_status(self, new_status):
        from repanier_v2.models.invoice import CustomerInvoice
        from repanier_v2.models.purchase import PurchaseWoReceiver

        now = timezone.now()
        self.is_updated_on = now
        self.status = new_status
        if self.highest_status < new_status:
            self.highest_status = new_status
        self.save(update_fields=["status", "is_updated_on", "highest_status"])
        CustomerInvoice.objects.filter(delivery_id=self.id).order_by("?").update(
            status=new_status
        )
        PurchaseWoReceiver.objects.filter(
            customer_invoice__delivery_id=self.id
        ).order_by("?").update(status=new_status)

    def get_delivery_display(self, br=False, color=False):
        short_name = self.distribution_point.short_name
        period = self.period
        if color:
            label = mark_safe(f'<font color="green">{period} {short_name}</font>')
        elif br:
            label = mark_safe(f"{period}<br>{short_name}")
        else:
            label = f"{period} {short_name}"
        return label

    def get_delivery_status_display(self):
        return " - ".join([self.get_delivery_display(), self.order_is_open])

    def __str__(self):
        return self.get_delivery_display()

    class Meta:
        verbose_name = _("Dispensing point of an order")
        verbose_name_plural = _("Dispensing points of an order")
        db_table = "repanier_order_dsp_point"
        # ordering = ["id",]
