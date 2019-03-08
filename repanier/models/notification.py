# -*- coding: utf-8

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *
from repanier.tools import cap


class Notification(TranslatableModel):
    translations = TranslatedFields(
        notification=HTMLField(_("Notification"),
                               help_text=EMPTY_STRING,
                               configuration='CKEDITOR_SETTINGS_MODEL2',
                               default=EMPTY_STRING,
                               blank=True),

    )

    def get_notification_display(self):
        return self.safe_translation_getter(
            'notification', any_language=True, default=EMPTY_STRING
        )

    def get_html_notification_card_display(self):
        if settings.REPANIER_SETTINGS_TEMPLATE == "bs4":
            notification = self.get_notification_display()
            if notification:
                html = []
                html.append(
                    format_html(
                        '<div class="card-body">{}</div>',
                        self.get_notification_display()
                    )
                )
                return mark_safe("""
                <div class="container-repanier">
                <div class="container">
                    <div class="row">
                        <div class="col">
                            <div class="card card-flash">
                                {html}
                                <a href="#" class="card-close"><i class="far fa-times-circle"></i></a>
                            </div>
                        </div>
                    </div>
                </div>
                </div>
                <script type="text/javascript">
                // Close card
                $(".card-close").click(function(){{
                    $(this).parent().slideUp(300);
                    $("a").click(function(){{
                        // Stop displaying flash in next pages
                        $(this).attr('href',$(this).attr('href')+"?flash=0");
                        return true;
                    }});
                }});
                </script>
                """.format(
                    html=EMPTY_STRING.join(html)
                ))
        return EMPTY_STRING

    def __str__(self):
        return cap(escape(self.get_notification_display()), 50)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")


@receiver(post_save, sender=Notification)
def configuration_post_save(sender, **kwargs):
    from repanier import apps

    notification = kwargs["instance"]
    if notification.id is not None:
        apps.REPANIER_SETTINGS_NOTIFICATION = notification
    else:
        apps.REPANIER_SETTINGS_NOTIFICATION = EMPTY_STRING
