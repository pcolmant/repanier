# -*- coding: utf-8
from __future__ import unicode_literals

from parler.admin import TranslatableAdmin

from repanier.const import COORDINATION_GROUP, ORDER_GROUP, INVOICE_GROUP


class NotificationAdmin(TranslatableAdmin):
    def has_delete_permission(self, request, obj=None):
        # nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one configuration record created at application start
        return False

    def has_change_permission(self, request, obj=None):
        # Only a coordinator has this permission
        if request.user.is_superuser or request.user.groups.filter(name__in=[COORDINATION_GROUP, ORDER_GROUP, INVOICE_GROUP]).exists():
            return True
        return False

    def get_fields(self, request, obj=None):
        return [
            'notification_is_public',
            'notification'
        ]
