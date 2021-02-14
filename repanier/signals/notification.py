from django.db.models.signals import post_save
from django.dispatch import receiver

from repanier.const import EMPTY_STRING
from repanier.models.notification import Notification


@receiver(post_save, sender=Notification)
def configuration_post_save(sender, **kwargs):
    from repanier import globals

    notification = kwargs["instance"]
    if notification.id is not None:
        globals.REPANIER_SETTINGS_NOTIFICATION = notification
    else:
        globals.REPANIER_SETTINGS_NOTIFICATION = EMPTY_STRING
