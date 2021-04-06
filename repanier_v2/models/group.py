from django.db.models import Manager
from django.utils.translation import ugettext_lazy as _

from repanier_v2.models.customer import Customer


class GroupManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_group=True)


class Group(Customer):
    objects = GroupManager()

    class Meta:
        proxy = True
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")
