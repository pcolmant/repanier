from dal import autocomplete
from django import forms
from django.conf import settings
from django.contrib import admin
from django.db import transaction
from django.db.models import F
from django.utils.translation import ugettext_lazy as _
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import PERMANENCE_PLANNED, PERMANENCE_CLOSED, EMPTY_STRING
from repanier.middleware import get_query_filters
from repanier.models import (
    PermanenceBoard,
    Customer,
    LUT_PermanenceRole,
    DeliveryBoard,
    Permanence,
    LUT_DeliveryPoint,
    Producer,
    Box,
)


class ProducerAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Producer.objects.filter(is_active=True)

        if self.q:
            qs = qs.filter(short_profile_name__istartswith=self.q)

        return qs


class BoxesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Box.objects.filter(is_box=True, is_into_offer=True)

        if self.q:
            qs = qs.filter(long_name_v2__istartswith=self.q)

        return qs


class PermanenceBoardInline(InlineForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ["permanence_role", "customer"]
    extra = 0

    def has_delete_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        widget = form.base_fields["permanence_role"].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_delete_related = False
        widget = form.base_fields["customer"].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_delete_related = False
        return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(
                is_active=True, rght=F("lft") + 1
            ).order_by("tree_id", "lft")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class DeliveryBoardInline(admin.TabularInline):
    model = DeliveryBoard
    ordering = ("id",)
    fields = ["delivery_comment_v2", "delivery_point", "status"]
    extra = 0
    readonly_fields = ["status"]

    def has_delete_permission(self, request, obj=None):
        object_id = request.resolver_match.kwargs.get("object_id", None)
        if object_id:
            # Update
            return Permanence.objects.filter(
                id=object_id, highest_status=PERMANENCE_PLANNED
            ).exists()
        else:
            # Create
            return True

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        widget = form.base_fields["delivery_comment_v2"].widget
        widget.attrs["size"] = "100%"
        widget = form.base_fields["delivery_point"].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_delete_related = False
        return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "delivery_point":
            kwargs["queryset"] = LUT_DeliveryPoint.objects.filter(
                is_active=True, rght=F("lft") + 1
            ).order_by("tree_id", "lft")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SaleForm(forms.ModelForm):
    short_name_v2 = forms.CharField(
        label=_("Offer name"),
        widget=forms.TextInput(attrs={"style": "width:70%"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permanence = self.instance

        if "producers" in self.fields:
            producer_field = self.fields["producers"]
            producer_field.widget.can_add_related = False
        if settings.REPANIER_SETTINGS_BOX:
            if "boxes" in self.fields:
                boxes_field = self.fields["boxes"]
                boxes_field.widget.can_add_related = False

    class Meta:
        model = Permanence
        fields = "__all__"
        widgets = {
            "producers": autocomplete.ModelSelect2Multiple(
                url="admin:producer-autocomplete",
                attrs={"data-dropdown-auto-width": "true", "data-width": "100%"},
            ),
            "boxes": autocomplete.ModelSelect2Multiple(
                url="admin:boxes-autocomplete",
                attrs={"data-dropdown-auto-width": "true", "data-width": "100%"},
            ),
        }


class SaleAdmin(admin.ModelAdmin):
    form = SaleForm

    change_list_url = EMPTY_STRING
    description = EMPTY_STRING
    list_per_page = 15
    list_max_show_all = 15
    inlines = [DeliveryBoardInline, PermanenceBoardInline]
    date_hierarchy = "permanence_date"

    list_display_links = ("get_permanence_admin_display",)
    search_fields = [
        "producers__short_profile_name",
        "permanenceboard__customer__short_basket_name",
        "customerinvoice__customer__short_basket_name",
        "producerinvoice__producer__short_profile_name",
    ]

    def get_redirect_to_change_list_url(self):
        return "{}{}".format(self.change_list_url, get_query_filters())

    def get_fields(self, request, permanence=None):
        fields = [
            ("permanence_date", "picture"),
            "automatically_closed",
            "short_name_v2",
            self.description,
            "producers",
        ]

        if settings.REPANIER_SETTINGS_BOX:
            fields.append("boxes")

        return fields

    def get_readonly_fields(self, request, permanence=None):
        readonly_fields = [
            "status",
        ]
        if permanence is not None and permanence.status > PERMANENCE_PLANNED:
            readonly_fields.append("producers")
            if settings.REPANIER_SETTINGS_BOX:
                readonly_fields.append("boxes")
        if permanence.status >= PERMANENCE_CLOSED:
            readonly_fields.append("automatically_closed")
        return readonly_fields

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # hide DeliveryBoardInline if no delivery point
            if (
                isinstance(inline, DeliveryBoardInline)
                and not LUT_DeliveryPoint.objects.filter(is_active=True).exists()
            ):
                continue
            # hide DeliveryBoardInline if no permanence role
            if (
                isinstance(inline, PermanenceBoardInline)
                and not LUT_PermanenceRole.objects.filter(is_active=True).exists()
            ):
                continue
            yield inline.get_formset(request, obj), inline

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

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "producers":
            kwargs["queryset"] = Producer.objects.filter(is_active=True)
        if db_field.name == "boxes":
            kwargs["queryset"] = Box.objects.filter(is_box=True, is_into_offer=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        permanence = form.instance
        permanence.with_delivery_point = DeliveryBoard.objects.filter(
            permanence_id=permanence.id
        ).exists()
        form.instance.save(update_fields=["with_delivery_point"])

    def save_model(self, request, permanence, form, change):
        if change and ("permanence_date" in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date
            )
        super().save_model(request, permanence, form, change)
