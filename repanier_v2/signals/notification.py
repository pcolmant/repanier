from django.db.models.signals import post_save
from django.dispatch import receiver

from repanier_v2.const import EMPTY_STRING
from repanier_v2.models.notification import Notification


@receiver(post_save, sender=Notification)
def configuration_post_save(sender, **kwargs):
    from repanier_v2 import globals

    notification = kwargs["instance"]
    if notification.id is not None:
        globals.REPANIER_SETTINGS_NOTIFICATION = notification
    else:
        globals.REPANIER_SETTINGS_NOTIFICATION = EMPTY_STRING
