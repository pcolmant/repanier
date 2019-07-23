from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from repanier.models import PermanenceBoard


@receiver(pre_save, sender=PermanenceBoard)
def permanence_board_pre_save(sender, **kwargs):
    permanence_board = kwargs["instance"]

    if permanence_board.master_permanence_board is None:
        permanence_board.permanence_date = permanence_board.permanence.permanence_date


@receiver(post_save, sender=PermanenceBoard)
def permanence_board_post_save(sender, instance, created, **kwargs):
    permanence_board = instance

    if (
        permanence_board.permanence.contract
        is None  # no extra overhead for permanence that have only one distribution date
        or permanence_board.master_permanence_board
        is not None  # only the 'master' accessible from the admin will be modified so skip 'child' PermanenceBoard
    ):
        return

    if created:
        # create the corresponding PermanenceBoard for all distribution dates
        for date in permanence_board.permanence.contract.permanences_dates.split(","):
            date = timezone.datetime.strptime(date, "%Y-%m-%d").date()
            PermanenceBoard.objects.create(
                permanence_date=date,
                permanence=permanence_board.permanence,
                permanence_role=permanence_board.permanence_role,
                master_permanence_board=permanence_board,
            )
    else:
        # update corresponding permanence roles for all distribution dates
        PermanenceBoard.objects.filter(master_permanence_board=permanence_board).update(
            permanence_role=permanence_board.permanence_role
        )


@receiver(post_delete, sender=PermanenceBoard)
def permanence_board_post_delete(sender, instance, **kwargs):
    instance.child_permanence_boards.all().delete()
