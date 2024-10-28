from django import forms
from django.utils.translation import gettext_lazy as _

from django.contrib import admin
from repanier.auth_backend import RepanierAuthBackend
from repanier.const import MpttLevelDepth
from repanier.models.staff import Staff
from .lut import LUTAdmin


class UserDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        is_active = self.cleaned_data.get("is_active", False)
        is_repanier_admin = self.cleaned_data.get("is_repanier_admin", False)
        is_order_manager = self.cleaned_data.get("is_order_manager", False)
        is_invoice_manager = self.cleaned_data.get("is_invoice_manager", False)
        is_webmaster = self.cleaned_data.get("is_webmaster", False)
        is_other_manager = self.cleaned_data.get("is_other_manager", False)
        if is_active and not (
            is_repanier_admin
            or is_order_manager
            or is_invoice_manager
            or is_webmaster
            or is_other_manager
        ):
            self.add_error(
                None,
                _("Members of the management team must assure at least one function"),
            )

        if not is_repanier_admin:
            qs = Staff.objects.filter(is_repanier_admin=True, is_active=True)
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if not qs.exists():
                self.add_error(
                    "is_repanier_admin",
                    _(
                        "At least one Repanier administrator must be set within the management team."
                    ),
                )


# Staff
class StaffWithUserDataForm(UserDataForm):
    class Meta:
        model = Staff
        fields = "__all__"


@admin.register(Staff)
class StaffWithUserDataAdmin(LUTAdmin):
    mptt_level_limit = MpttLevelDepth.ONE
    item_label_field_name = "get_str_member"
    form = StaffWithUserDataForm

    list_display = ("get_str_member", "is_active")
    list_display_links = ("get_str_member",)
    list_select_related = ("customer_responsible",)
    list_per_page = 16
    list_max_show_all = 16
    autocomplete_fields = ["customer_responsible"]

    def has_delete_permission(self, request, obj=None):
        return request.user.is_repanier_admin

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def get_fields(self, request, obj=None):
        fields = [
            "long_name_v2",
            "customer_responsible",
            "can_be_contacted",
            "is_repanier_admin",
            "is_order_manager",
            "is_invoice_manager",
            "is_other_manager",
            "is_webmaster",
            "is_active",
        ]
        return fields

    def save_model(self, request, staff, form, change):
        old_customer_responsible_field = form.base_fields[
            "customer_responsible"
        ].initial
        new_customer_responsible_field = form.cleaned_data["customer_responsible"]
        change_previous_customer_responsible = (
            change
            and old_customer_responsible_field is not None
            and old_customer_responsible_field.id != new_customer_responsible_field.id
        )

        super().save_model(request, staff, form, change)
        if (
            change_previous_customer_responsible
            and old_customer_responsible_field.user is not None
        ):
            RepanierAuthBackend.remove_staff_right(
                user=old_customer_responsible_field.user
            )
