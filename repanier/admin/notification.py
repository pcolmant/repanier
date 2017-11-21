# -*- coding: utf-8

from parler.admin import TranslatableAdmin


class NotificationAdmin(TranslatableAdmin):
    def has_delete_permission(self, request, obj=None):
        # nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one notification record created at application start
        return False

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_order or user.is_invoice or user.is_coordinator:
            return True
        return False

    def get_fields(self, request, obj=None):
        return [
            'notification_is_public',
            'notification'
        ]
