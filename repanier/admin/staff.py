# -*- coding: utf-8

from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, get_language_info
from easy_select2 import apply_select2
from parler.forms import TranslatableModelForm

from repanier.auth_backend import RepanierAuthBackend
from repanier.const import ONE_LEVEL_DEPTH
from repanier.models.customer import Customer
from repanier.models.staff import Staff
from .lut import LUTAdmin


class UserDataForm(TranslatableModelForm):
    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        if self.instance.id is None:
            if self.language_code != settings.LANGUAGE_CODE:
                # Important to also prohibit untranslated instance in settings.LANGUAGE_CODE
                self.add_error(
                    "long_name",
                    _("Please define first a long_name in %(language)s")
                    % {
                        "language": get_language_info(settings.LANGUAGE_CODE)[
                            "name_local"
                        ]
                    },
                )

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
            qs = Staff.objects.filter(is_repanier_admin=True, is_active=True).order_by(
                "?"
            )
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if not qs.exists():
                self.add_error(
                    "is_repanier_admin",
                    _(
                        "At least one Repanier administrator must be set within the management team"
                    ),
                )


# Staff
class StaffWithUserDataForm(UserDataForm):
    class Meta:
        model = Staff
        fields = "__all__"
        widgets = {"customer_responsible": apply_select2(forms.Select)}


class StaffWithUserDataAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH
    item_label_field_name = "get_str_member"
    form = StaffWithUserDataForm
    list_display = ("long_name",)
    list_display_links = ("long_name",)
    list_select_related = ("customer_responsible",)
    list_per_page = 16
    list_max_show_all = 16

    def has_delete_permission(self, request, obj=None):
        return request.user.is_repanier_admin

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def get_fields(self, request, obj=None):
        fields = [
            "long_name",
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer_responsible":
            kwargs["queryset"] = Customer.objects.filter(
                is_active=True
            )  # , represent_this_buyinggroup=False)
        return super(StaffWithUserDataAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

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

        super(StaffWithUserDataAdmin, self).save_model(request, staff, form, change)
        if (
            change_previous_customer_responsible
            and old_customer_responsible_field.user is not None
        ):
            RepanierAuthBackend.remove_staff_right(
                user=old_customer_responsible_field.user
            )
