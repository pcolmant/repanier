from django.contrib import admin
from repanier.models.emaillog import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "recipient_email",
        "customer",
        "permanence",
        "nature",
        "status",
        "error_reason",
    )
    list_filter = ("nature", "status", "permanence")
    search_fields = ("recipient_email", "customer__short_basket_name", "error_reason")
    readonly_fields = (
        "uuid",
        "message_id",
        "customer",
        "recipient_email",
        "permanence",
        "nature",
        "status",
        "error_reason",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser