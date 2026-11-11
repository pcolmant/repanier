from django.db import models
from django.template.loader import render_to_string
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

    def get_html_notification_card_display(self):
        """Render the flash card (repanier/notification_card.html), or
        nothing when the notification is empty.

        The notification content is escaped by the template, exactly as
        the previous format_html based rendering did."""
        notification = self.get_notification_display()
        if notification:
            return render_to_string(
                "repanier/notification_card.html", {"notification": notification}
            )
        return EMPTY_STRING

    def __str__(self):
        return cap(escape(self.get_notification_display()), 50)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
