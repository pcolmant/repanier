from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier.models import PermanenceBoard


@receiver(pre_save, sender=PermanenceBoard)
def permanence_board_pre_save(sender, **kwargs):
    permanence_board = kwargs["instance"]
    permanence_board.permanence_date = permanence_board.permanence.permanence_date
