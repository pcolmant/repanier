from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier.const import DECIMAL_ZERO
from repanier.models import Staff


@receiver(pre_save, sender=Staff)
def staff_pre_save(sender, **kwargs):
    staff = kwargs["instance"]
    staff.login_attempt_counter = DECIMAL_ZERO

# @receiver(post_save, sender=Staff)
# def staff_post_save(sender, **kwargs):
#     staff = kwargs["instance"]
#     if staff.id is not None:
#         user = staff.user
#         user.groups.clear()
#         if staff.is_webmaster:
#             group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
#             user.groups.add(group_id)

# @receiver(post_delete, sender=Staff)
# def staff_post_delete(sender, **kwargs):
#     staff = kwargs["instance"]
#     user = staff.user
#     user.delete()
