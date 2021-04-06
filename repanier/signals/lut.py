from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier.models import LUT_PermanenceRole


@receiver(pre_save, sender=LUT_PermanenceRole)
def lut_permanence_role_pre_save(sender, **kwargs):
    permanence_role = kwargs["instance"]
    if not permanence_role.is_active:
        permanence_role.automatically_added = False
