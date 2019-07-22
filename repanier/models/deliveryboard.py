# -*- coding: utf-8

from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import (
    LUT_PERMANENCE_STATUS,
    PERMANENCE_PLANNED,
    PERMANENCE_SEND,
    EMPTY_STRING,
)


class DeliveryBoard(TranslatableModel):
    translations = TranslatedFields(
        delivery_comment=models.CharField(
            _("Comment"), max_length=50, blank=True, default=EMPTY_STRING
        )
    )

    delivery_point = models.ForeignKey(
        "LUT_DeliveryPoint",
        verbose_name=_("Delivery point"),
        db_index=True,
        on_delete=models.PROTECT,
    )
    permanence = models.ForeignKey(
        "Permanence",
        verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.CASCADE,
    )

    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Status"),
    )
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Highest status"),
    )

    def set_status(self, new_status):
        from repanier.models.invoice import CustomerInvoice
        from repanier.models.purchase import PurchaseWoReceiver

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
        short_name = "{}".format(
            self.delivery_point.safe_translation_getter(
                "short_name", any_language=True, default=EMPTY_STRING
            )
        )
        comment = self.safe_translation_getter(
            "delivery_comment", any_language=True, default=EMPTY_STRING
        )
        if color:
            label = mark_safe(
                '<font color="green">{} {}</font>'.format(comment, short_name)
            )
        elif br:
            label = mark_safe("{}<br>{}".format(comment, short_name))
        else:
            label = "{} {}".format(comment, short_name)
        return label

    def get_delivery_status_display(self):
        return "{} - {}".format(self, self.get_status_display())

    def get_delivery_customer_display(self):
        if self.status != PERMANENCE_SEND:
            return "{} - {}".format(self, self.get_status_display())
        else:
            return "{} - {}".format(self, _("Orders closed"))

    def __str__(self):
        return self.get_delivery_display()

    class Meta:
        verbose_name = _("Delivery board")
        verbose_name_plural = _("Deliveries board")
        ordering = ("id",)
