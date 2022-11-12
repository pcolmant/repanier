from django.utils.translation import gettext_lazy as _

from repanier.models.customer import Customer


class Group(Customer):
    def __str__(self):
        return "[{}]".format(self.short_basket_name)

    class Meta:
        proxy = True
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")
