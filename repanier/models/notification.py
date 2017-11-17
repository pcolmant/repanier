# -*- coding: utf-8

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *


class Notification(TranslatableModel):
    notification_is_public = models.BooleanField(_("The notification is public"), default=False)
    translations = TranslatedFields(
        notification=HTMLField(_("Notification"),
                               help_text=EMPTY_STRING,
                               configuration='CKEDITOR_SETTINGS_MODEL2',
                               default=EMPTY_STRING,
                               blank=True),

    )

    def __str__(self):
        return self.safe_translation_getter(
            'notification', any_language=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")


@receiver(post_save, sender=Notification)
def configuration_post_save(sender, **kwargs):
    import repanier.cms_toolbar

    notification = kwargs["instance"]
    if notification.id is not None:
        repanier.apps.REPANIER_SETTINGS_NOTIFICATION = notification
