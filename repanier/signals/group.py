from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver

from repanier.models.group import Group
from repanier.signals.customer import customer_pre_save, customer_post_delete


@receiver(pre_save, sender=Group)
def group_pre_save(sender, **kwargs):
    customer_pre_save(sender, **kwargs)
    group = kwargs["instance"]
    group.is_group = True
    # A group cannot place an order
    group.may_order = False
    group.delivery_point = None
    # find or create delivery point with this group:
    #     set price_list_multiplier
    #     set transport
    #     set min transport


@receiver(post_delete, sender=Group)
def group_post_delete(sender, **kwargs):
    customer_post_delete(sender, **kwargs)
