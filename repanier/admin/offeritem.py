from admin_auto_filters.filters import AutocompleteFilter
from admin_auto_filters.views import AutocompleteJsonView
from django import forms
from django.contrib import admin
from django.urls import path, reverse
from django.utils.translation import ugettext_lazy as _
from repanier.middleware import get_request_params
from repanier.models import Producer


class AdminFilterProducerOfPermanenceSearchView(AutocompleteJsonView):
    model_admin = None

    @staticmethod
    def display_text(obj):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return obj.get_filter_display(permanence_id)

    def get_queryset(self):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        queryset = Producer.objects.filter(producerinvoice__permanence_id=permanence_id)
        return queryset


class AdminFilterProducerOfPermanenceChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return obj.get_filter_display(permanence_id)


class AdminFilterProducerOfPermanence(AutocompleteFilter):
    title = _("Producers")
    field_name = "producer"  # name of the foreign key field
    parameter_name = "producer"
    form_field = AdminFilterProducerOfPermanenceChoiceField

    def get_autocomplete_url(self, request, model_admin):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return reverse(
            "admin:offeritemopen-admin-producer-of-permanence", args=(permanence_id,)
        )


class OfferItemOpenAdmin(admin.ModelAdmin):
    fields = None
    search_fields = ("long_name_v2",)
    list_display = (
        "producer",
        "department_for_customer",
        "get_long_name_with_producer_price",
        "stock",
        "get_quantity_invoiced",
    )
    list_display_links = None
    list_editable = ("stock",)
    list_filter = (AdminFilterProducerOfPermanence,)
    list_select_related = ("producer", "department_for_customer")
    list_per_page = 13
    list_max_show_all = 13
    ordering = (
        "department_for_customer",
        "long_name_v2",
    )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "producer_of_permanence/<int:permanence>/",
                self.admin_site.admin_view(
                    AdminFilterProducerOfPermanenceSearchView.as_view(model_admin=self)
                ),
                name="offeritemopen-admin-producer-of-permanence",
            ),
        ]
        return my_urls + urls

    def get_queryset(self, request):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return (
            super()
            .get_queryset(request)
            .filter(
                permanence_id=permanence_id,
                is_box_content=False,
            )
        )

    def has_module_permission(self, request):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_repanier_staff

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

    def save_model(self, request, offer_item, form, change):
        super().save_model(request, offer_item, form, change)
        if offer_item.product_id is not None:
            offer_item.product.stock = offer_item.stock
            offer_item.product.save(update_fields=["stock"])
