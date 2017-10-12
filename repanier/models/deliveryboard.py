# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields

from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import LUT_PERMANENCE_STATUS, PERMANENCE_PLANNED, PERMANENCE_SEND, EMPTY_STRING


@python_2_unicode_compatible
class DeliveryBoard(TranslatableModel):
    translations = TranslatedFields(
        delivery_comment=models.CharField(_("Comment"), max_length=50, blank=True),
    )

    delivery_point = models.ForeignKey(
        'LUT_DeliveryPoint', verbose_name=_("Delivery point"),
        db_index=True, on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME)
    # delivery_date = models.DateField(_("delivery date"), blank=True, null=True, db_index=True)

    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Status"))
    is_updated_on = models.DateTimeField(
        _("Is updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Highest status"),
        help_text=_('Status of the permanence from planned, orders opened, orders closed, send, done'))

    def set_status(self, new_status, all_producers=True, producers_id=None):
        from repanier.models.invoice import CustomerInvoice
        from repanier.models.purchase import Purchase

        if all_producers:
            now = timezone.now()
            self.is_updated_on = now
            self.status = new_status
            if self.highest_status < new_status:
                self.highest_status = new_status
            self.save(update_fields=['status', 'is_updated_on', 'highest_status'])
            CustomerInvoice.objects.filter(
                delivery_id=self.id
            ).order_by('?').update(
                status=new_status
            )
            Purchase.objects.filter(
                customer_invoice__delivery_id=self.id
            ).order_by('?').update(
                status=new_status)
            menu_pool.clear()
            cache.clear()
        else:
            Purchase.objects.filter(
                customer_invoice__delivery_id=self.id,
                producer__in=producers_id
            ).order_by('?').update(
                status=new_status
            )

    def get_delivery_display(self, admin=False):
        short_name = "%s" % self.delivery_point.safe_translation_getter(
            'short_name', any_language=True, default=EMPTY_STRING
        )
        if admin:
            # if self.delivery_date is not None:
            #     label = '%s <font color="green">%s</font>' % (
            #         self.delivery_date.strftime(settings.DJANGO_SETTINGS_DAY), short_name
            #     )
            # else:
            label = '<font color="green">%s</font>' % short_name
        else:
            comment = self.safe_translation_getter(
                'delivery_comment', any_language=True, default=EMPTY_STRING
            )
            # if self.delivery_date is not None:
            #     label = '%s %s%s' % (
            #         self.delivery_date.strftime(settings.DJANGO_SETTINGS_DAY),
            #         "%s " % comment if comment else EMPTY_STRING,
            #         short_name
            #     )
            # else:
            label = '%s%s' % (comment, short_name)
        return mark_safe(label)

    def get_delivery_status_display(self):
        return "%s - %s" % (self, self.get_status_display())

    def get_delivery_customer_display(self):
        if self.status != PERMANENCE_SEND:
            return "%s - %s" % (self, self.get_status_display())
        else:
            return "%s - %s" % (self, _('Orders closed'))

    def __str__(self):
        return self.get_delivery_display()

    class Meta:
        verbose_name = _("Delivery board")
        verbose_name_plural = _("Deliveries board")
