from django.contrib import admin
from repanier.models.emaillog import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "updated_at",
        "recipient_email",
        "customer__short_basket_name",
        "permanence",
        "nature",
        "status",
        "reason",
    )
    list_filter = ("nature", "status")
    search_fields = ("recipient_email", "customer__short_basket_name", "customer__user__email",)
    readonly_fields = (
        "customer",
        "recipient_email",
        "permanence",
        "nature",
        "status",
        "reason",
        "updated_at",
    )
    date_hierarchy = "updated_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser