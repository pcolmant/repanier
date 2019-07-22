# -*- coding: utf-8

from django.utils.translation import ugettext_lazy as _

from repanier.models.customer import Customer


class Group(Customer):
    class Meta:
        proxy = True
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")
