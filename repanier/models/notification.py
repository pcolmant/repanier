from django.db import models
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from repanier.const import EMPTY_STRING
from repanier.tools import cap


class Notification(models.Model):
    notification_v2 = HTMLField(
        _("Notification"),
        help_text=EMPTY_STRING,
        configuration="CKEDITOR_SETTINGS_MODEL2",
        default=EMPTY_STRING,
        blank=True,
    )

    def get_notification_display(self):
        return self.notification_v2

    def __str__(self):
        return cap(escape(self.get_notification_display()), 50)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
