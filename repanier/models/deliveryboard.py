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
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

import invoice
import purchase
from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import LUT_PERMANENCE_STATUS, PERMANENCE_PLANNED, PERMANENCE_SEND, EMPTY_STRING


@python_2_unicode_compatible
class DeliveryBoard(TranslatableModel):
    translations = TranslatedFields(
        delivery_comment=models.CharField(_("comment"), max_length=50, blank=True),
    )

    delivery_point = models.ForeignKey(
        'LUT_DeliveryPoint', verbose_name=_("delivery point"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME)
    delivery_date = models.DateField(_("delivery date"), blank=True, null=True, db_index=True)

    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("permanence_status"))
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("highest permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))

    def set_status(self, new_status, all_producers=True, producers_id=None):
        if all_producers:
            now = timezone.now()
            self.is_updated_on = now
            self.status = new_status
            if self.highest_status < new_status:
                self.highest_status = new_status
            self.save(update_fields=['status', 'is_updated_on', 'highest_status'])
            invoice.CustomerInvoice.objects.filter(
                delivery_id=self.id
            ).order_by('?').update(
                status=new_status
            )
            purchase.Purchase.objects.filter(
                customer_invoice__delivery_id=self.id
            ).order_by('?').update(
                status=new_status)
            menu_pool.clear()
            cache.clear()
        else:
            purchase.Purchase.objects.filter(
                customer_invoice__delivery_id=self.id,
                producer__in=producers_id
            ).order_by('?').update(
                status=new_status
            )

    def get_delivery_display(self, admin=False):
        try:
            short_name = "%s" % self.delivery_point.short_name
        except (TranslationDoesNotExist, AttributeError):
            short_name = EMPTY_STRING
        if admin:
            if self.delivery_date is not None:
                label = mark_safe('%s <font color="green">%s</font>' % (
                    self.delivery_date.strftime(settings.DJANGO_SETTINGS_DATE), short_name))
            else:
                label = mark_safe('<font color="green">%s</font>' % short_name)
        else:
            try:
                if self.delivery_comment != EMPTY_STRING:
                    comment = "%s " % self.delivery_comment
                else:
                    comment = EMPTY_STRING
            except TranslationDoesNotExist:
                comment = EMPTY_STRING
            if self.delivery_date is not None:
                label = mark_safe('%s %s%s' % (
                    self.delivery_date.strftime(settings.DJANGO_SETTINGS_DATE), comment, short_name))
            else:
                label = mark_safe('%s%s' % (comment, short_name))
        return label

    def get_delivery_status_display(self):
        return "%s - %s" % (self, self.get_status_display())

    def get_delivery_customer_display(self):
        if self.status != PERMANENCE_SEND:
            return "%s - %s" % (self, self.get_status_display())
        else:
            return "%s - %s" % (self, _('orders closed'))

    def __str__(self):
        return self.get_delivery_display()

    class Meta:
        verbose_name = _("delivery board")
        verbose_name_plural = _("deliveries board")
