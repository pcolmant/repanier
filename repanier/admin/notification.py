from django.contrib import admin

from repanier.models.notification import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        # nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one notification record created at application start
        return False

    def has_change_permission(self, request, notification=None):
        user = request.user
        if user.is_order_manager or user.is_invoice_manager:
            return True
        return False

    def get_fields(self, request, obj=None):
        return ["notification_v2"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        if not actions:
            try:
                self.list_display.remove("action_checkbox")
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions
