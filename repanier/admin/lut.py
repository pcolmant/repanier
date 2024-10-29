from django.contrib import admin
from django.db.models import F
from django_mptt_admin.admin import DjangoMpttAdmin

from repanier.models import LUT_DeliveryPoint, LUT_PermanenceRole
from repanier.const import MpttLevelDepth
from repanier.models import LUT_DepartmentForCustomer, LUT_ProductionMode, Customer


class LUTAdmin(DjangoMpttAdmin):
    list_display = ("__str__", "is_active")
    list_display_links = ("__str__",)
    mptt_level_indent = 20
    mptt_indent_field = "__str__"
    list_filter = ("is_active",)
    mptt_level_limit = None

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_order_manager or user.is_invoice_manager:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Overrides parent class formfield_for_foreignkey method."""
        # If mptt_level_limit is set filter levels depending on the limit.
        if db_field.name == "parent" and self.mptt_level_limit is not None:
            kwargs["queryset"] = self.model.objects.filter(
                level__lt=self.mptt_level_limit
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def do_move(self, instance, position, target_instance):
        """
        Overwritting parent do_move method to disallow users to exceed the self.mptt_level_limit value when drag and
        dropping items.
        """
        if self.mptt_level_limit is not None:
            if position == "inside":
                if target_instance.level >= self.mptt_level_limit:
                    raise Exception("Unknown position")
            else:
                # position in ["before", "after"]
                if target_instance.level > self.mptt_level_limit:
                    raise Exception("Unknown position")
        super().do_move(instance, position, target_instance)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs

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

@admin.register(LUT_ProductionMode)
class LUTProductionModeAdmin(LUTAdmin):
    mptt_level_limit = MpttLevelDepth.TWO
    search_fields = ("short_name_v2",)

    def has_add_permission(self, request):
        if "/lut_productionmode/" in request.path:
            # Only if in admin > producer
            return self.has_delete_permission(request)
        # If in autocomplete field
        return False

    def get_fields(self, request, obj=None):
        fields = ["parent", "short_name_v2", "picture2", "is_active"]
        return fields

    def get_queryset(self, request):
        if "/autocomplete/" in request.path:
            # Autocomplete
            qs = LUT_ProductionMode.objects.filter(
                rght=F("lft") + 1,
                is_active=True,
            ).order_by("short_name_v2")
        else:
            qs = super().get_queryset(request)
        return qs

@admin.register(LUT_DeliveryPoint)
class LUTDeliveryPointAdmin(LUTAdmin):
    mptt_level_limit = MpttLevelDepth.ONE
    search_fields = ("short_name_v2",)

    def get_fields(self, request, obj=None):
        fields = ["short_name_v2", "is_active", ("transport", "min_transport")]
        return fields

    def save_model(self, request, delivery_point, form, change):
        super().save_model(request, delivery_point, form, change)
        if delivery_point.group is not None:
            Customer.objects.filter(id=delivery_point.group_id, is_group=True).update(
                short_basket_name=delivery_point.short_name_v2,
                is_active=delivery_point.is_active,
            )

@admin.register(LUT_DepartmentForCustomer)
class LUTDepartmentForCustomerAdmin(LUTAdmin):
    mptt_level_limit = MpttLevelDepth.TWO
    search_fields = ("short_name_v2",)

    def get_fields(self, request, obj=None):
        fields = ["parent", "short_name_v2", "is_active"]
        return fields

    def get_queryset(self, request):
        if "/autocomplete/" in request.path:
            # Autocomplete
            qs = LUT_DepartmentForCustomer.objects.filter(
                rght=F("lft") + 1,
                is_active=True,
            ).order_by("short_name_v2")
        else:
            qs = super().get_queryset(request)
        return qs

@admin.register(LUT_PermanenceRole)
class LUTPermanenceRoleAdmin(LUTAdmin):
    mptt_level_limit = MpttLevelDepth.ONE
    search_fields = ("short_name_v2",)

    def get_fields(self, request, obj=None):
        fields = [
            "short_name_v2",
            "customers_may_register",
            "is_counted_as_participation",
            "description_v2",
            "is_active",
        ]
        return fields
