import logging

from admin_auto_filters.filters import AutocompleteFilter
from admin_auto_filters.views import AutocompleteJsonView
from dal import autocomplete, forward
from django import forms
from django.contrib import admin
from django.core.checks import messages
from django.db import transaction
from django.db.models import Q
from django.forms.widgets import TextInput
from django.http import HttpResponseRedirect
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.email.email_order import export_order_2_1_customer
from repanier.middleware import (
    get_request_params,
    set_threading_local,
    get_threading_local,
    get_preserved_filters,
    get_preserved_filters_as_dict,
    get_preserved_filters_from_dict,
)
from repanier.models import Producer, Product
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.purchase import Purchase
from repanier.tools import get_repanier_static_name, create_or_update_one_purchase

logger = logging.getLogger(__name__)


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
    def label_from_instance(self, selected_item):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return selected_item.get_filter_display(permanence_id)


class AdminFilterProducerOfPermanence(AutocompleteFilter):
    title = _("Producers")
    field_name = "producer"  # name of the foreign key field
    parameter_name = "producer"
    form_field = AdminFilterProducerOfPermanenceChoiceField

    def get_autocomplete_url(self, request, model_admin):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return reverse("admin:repanier_purchase_list_producer", args=(permanence_id,))


class AdminFilterCustomerOfPermanenceSearchView(AutocompleteJsonView):
    model_admin = None

    @staticmethod
    def display_text(obj):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return obj.get_filter_display(permanence_id)

    def get_queryset(self):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        queryset = Customer.objects.filter(customerinvoice__permanence_id=permanence_id)
        return queryset


class AdminFilterCustomerOfPermanenceChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return obj.get_filter_display(permanence_id)


class AdminFilterCustomerOfPermanence(AutocompleteFilter):
    title = _("Customers")
    field_name = "customer"  # name of the foreign key field
    parameter_name = "customer"
    form_field = AdminFilterCustomerOfPermanenceChoiceField

    def get_autocomplete_url(self, request, model_admin):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return reverse("admin:repanier_purchase_list_customer", args=(permanence_id,))


class CustomerAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        # if not self.request.user.is_staff:
        #     return OfferItem.objects.none()
        qs = Customer.objects.filter(may_order=True)

        if self.q:
            qs = qs.filter(
                Q(short_basket_name__icontains=self.q)
                | Q(long_basket_name__icontains=self.q)
                | Q(user__email__icontains=self.q)
                # | Q(email2__icontains=self.q)
            )
        return qs

    def get_result_label(self, item):
        permanence_id = self.forwarded.get("permanence", None)

        ci = CustomerInvoice.objects.filter(
            permanence_id=permanence_id, customer_id=item.id
        ).first()
        if ci is not None:
            if ci.is_order_confirm_send:
                result = "{} {} ({})".format(
                    settings.LOCK_UNICODE,
                    item.short_basket_name,
                    ci.get_total_price_with_tax(),
                )
            else:
                result = "{} ({})".format(
                    item.short_basket_name, ci.total_price_with_tax
                )
        else:
            result = item.short_basket_name

        return result


class DeliveryAutocomplete(autocomplete.Select2QuerySetView):
    search_fields = [
        "long_name_v2",
    ]

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        # if not self.request.user.is_staff:
        #     return OfferItem.objects.none()
        permanence_id = self.forwarded.get("permanence", None)
        customer_id = self.forwarded.get("customer", None)
        customer = Customer.objects.filter(id=customer_id).first()
        if customer is not None:

            if customer.group is not None:
                # The customer is member of a group
                qs = DeliveryBoard.objects.filter(
                    Q(
                        permanence_id=permanence_id,
                        delivery_point__group_id=customer.group_id,
                    )
                    | Q(
                        permanence_id=permanence_id,
                        delivery_point__group__isnull=True,
                    )
                )
            else:
                qs = DeliveryBoard.objects.filter(
                    permanence_id=permanence_id,
                    delivery_point__group__isnull=True,
                )

            if self.q:
                qs = qs.filter(long_name_v2__icontains=self.q)

        else:
            qs = DeliveryBoard.objects.none()

        return qs

    def get_result_label(self, item):
        permanence_id = self.forwarded.get("permanence", None)
        customer_id = self.forwarded.get("customer", None)
        customer_invoice = (
            CustomerInvoice.objects.filter(
                permanence_id=permanence_id,
                customer_id=customer_id,
            )
            .only("delivery_id")
            .first()
        )
        if customer_invoice is not None and customer_invoice.delivery_id == item.id:
            return mark_safe(
                "<i class='fas fa-shopping-basket'></i> <i class='fas fa-arrow-right'></i> {}".format(
                    item.get_delivery_display()
                )
            )
        return item.get_delivery_display()


class ProductAutocompleteChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_long_name_with_customer_price()


class ProductAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        qs = Product.objects.filter(is_box=False, is_active=True).order_by(
            "department_for_customer", "long_name_v2"
        )

        if self.q:
            qs = qs.filter(
                Q(long_name_v2__icontains=self.q)
                | Q(producer__short_profile_name__icontains=self.q)
                | Q(department_for_customer__short_name_v2__icontains=self.q)
            )

        return qs

    def get_result_label(self, item):
        permanence_id = self.forwarded.get("permanence", None)
        customer_id = self.forwarded.get("customer", None)
        purchase = Purchase.objects.filter(
            permanence_id=permanence_id,
            customer_id=customer_id,
            offer_item__product_id=item.id,
        ).first()
        purchased_symbol = EMPTY_STRING
        if purchase is not None:
            if purchase.status < PERMANENCE_SEND:
                qty = _("Quantity requested")
                purchased_symbol = mark_safe(
                    "[<b>{} : {:.2f}</b>] ".format(qty, purchase.quantity_ordered)
                )
            else:
                qty = _("Quantity prepared")
                purchased_symbol = mark_safe(
                    "[<b>{} : {:.4f}</b>] ".format(qty, purchase.quantity_invoiced)
                )

        if item.department_for_customer is None:
            return "{}{} - {}".format(
                purchased_symbol,
                item.producer,
                item.get_long_name_with_customer_price(),
            )
        else:
            return "{}{} - {} - {}".format(
                purchased_symbol,
                item.department_for_customer,
                item.producer,
                item.get_long_name_with_customer_price(),
            )


class PurchaseForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        label=_("Customer"),
        queryset=Customer.objects.all(),
        required=True,
        widget=autocomplete.ModelSelect2(
            url="admin:repanier_purchase_form_customer",
            forward=(forward.Field("permanence"),),
            attrs={
                "data-dropdown-auto-width": "true",
                "data-width": "80%",
            },
        ),
    )
    delivery = forms.ModelChoiceField(
        label=_("Delivery point"),
        queryset=DeliveryBoard.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="admin:repanier_purchase_form_delivery",
            forward=(
                forward.Field("permanence"),
                forward.Field("customer"),
            ),
            attrs={
                "data-dropdown-auto-width": "true",
                "data-width": "80%",
                "data-html": True,
            },
        ),
    )
    product = ProductAutocompleteChoiceField(
        label=_("Product Customer rate"),
        queryset=Product.objects.all(),
        required=True,
        widget=autocomplete.ModelSelect2(
            url="admin:repanier_purchase_form_product",
            forward=(
                forward.Field("permanence"),
                forward.Field("customer"),
            ),
            attrs={
                "data-dropdown-auto-width": "true",
                "data-width": "80%",
                "data-html": True,
            },
        ),
    )
    offer_item = forms.ModelChoiceField(
        label=_("Customer rate"),
        queryset=OfferItem.objects.all(),
        required=False,
    )
    quantity = forms.DecimalField(
        min_value=DECIMAL_ZERO,
        label=_("Qty"),
        max_digits=9,
        decimal_places=4,
        required=True,
        initial=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        purchase = self.instance

        permanence_field = self.fields["permanence"]
        customer_field = self.fields["customer"]
        quantity_field = self.fields["quantity"]
        delivery_field = self.fields["delivery"]
        offer_item_field = self.fields["offer_item"]
        product_field = self.fields["product"]

        if purchase.id is None:
            # Add new purchase
            query_params = get_request_params()
            permanence_id = query_params.get("permanence", None)
            permanence_field.initial = permanence_id
            customer_id = query_params.get("customer", None)
            customer_field.initial = customer_id
            customer_invoice = CustomerInvoice.objects.filter(
                customer_id=customer_id,
                permanence_id=permanence_id,
            ).first()
            if customer_invoice is not None:
                delivery_point_id = customer_invoice.delivery_id
            else:
                delivery_point_id = None
            product_field.initial = None
        else:
            # Update existing purchase
            if purchase.status < PERMANENCE_SEND:
                quantity_field.initial = purchase.quantity_ordered
            else:
                quantity_field.initial = purchase.quantity_invoiced

            permanence_id = purchase.permanence_id
            delivery_point_id = purchase.customer_invoice.delivery
            product_field.initial = purchase.offer_item.product_id

        permanence_field.widget = forms.HiddenInput()
        permanence_field.widget.attrs["readonly"] = True
        permanence_field.disabled = True

        offer_item_field.widget = forms.HiddenInput()
        offer_item_field.widget.attrs["readonly"] = True
        offer_item_field.disabled = True

        customer_field.widget.can_change_related = False
        customer_field.widget.can_add_related = False
        customer_field.widget.can_delete_related = False

        if Permanence.objects.filter(
            id=permanence_id, with_delivery_point=True
        ).exists():
            delivery_field.initial = delivery_point_id
            delivery_field.required = True
        else:
            delivery_field.initial = None
            delivery_field.required = False
            delivery_field.widget = forms.HiddenInput()

    class Meta:
        model = Purchase
        fields = "__all__"
        widgets = {
            "comment": TextInput(attrs={"style": "width: 80%;"}),
        }


class PurchaseAdmin(admin.ModelAdmin):
    form = PurchaseForm
    list_display = [
        "producer",
        "get_department_for_customer",
        "get_long_name_with_customer_price",
        "get_quantity",
        "get_selling_price",
    ]
    list_select_related = ("permanence", "customer")
    list_per_page = 16
    list_max_show_all = 16
    ordering = (
        "producer",
        "offer_item__department_for_customer",
        "offer_item__long_name_v2",
    )
    list_filter = (
        AdminFilterProducerOfPermanence,
        AdminFilterCustomerOfPermanence,
    )
    list_display_links = ("get_long_name_with_customer_price",)
    search_fields = ("offer_item__long_name_v2", "producer__short_profile_name")
    actions = []

    def get_department_for_customer(self, obj):
        return obj.offer_item.department_for_customer

    get_department_for_customer.short_description = _("Department")
    get_department_for_customer.admin_order_field = (
        "offer_item__department_for_customer"
    )

    def get_long_name_with_customer_price(self, obj):
        return obj.offer_item.get_long_name_with_customer_price()

    get_long_name_with_customer_price.short_description = _("Customer tariff")
    get_long_name_with_customer_price.admin_order_field = "offer_item__long_name_v2"

    def get_queryset(self, request):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        return (
            super()
            .get_queryset(request)
            .filter(
                permanence_id=permanence_id,
            )
        )

    def has_module_permission(self, request):
        return False

    def has_delete_permission(self, request, purchase=None):
        return False

    def has_add_permission(self, request):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", None)
        if permanence_id is not None:
            if Permanence.objects.filter(
                id=permanence_id, status__gt=PERMANENCE_SEND
            ).exists():
                return False
            user = request.user
            if user.is_repanier_staff:
                return True
        return False

    def has_change_permission(self, request, purchase=None):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", None)
        if permanence_id is not None:
            if purchase is not None and purchase.status > PERMANENCE_SEND:
                return False
            user = request.user
            if user.is_repanier_staff:
                return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "is_order_confirm_send/",
                self.admin_site.admin_view(self.is_order_confirm_send),
            ),
            path(
                "customer_autocomplete/",
                CustomerAutocomplete.as_view(),
                name="repanier_purchase_form_customer",
            ),
            path(
                "delivery_autocomplete/",
                DeliveryAutocomplete.as_view(),
                name="repanier_purchase_form_delivery",
            ),
            path(
                "product_autocomplete/",
                ProductAutocomplete.as_view(),
                name="repanier_purchase_form_product",
            ),
            path(
                "producer_of_permanence/<int:permanence>/",
                self.admin_site.admin_view(
                    AdminFilterProducerOfPermanenceSearchView.as_view(model_admin=self)
                ),
                name="repanier_purchase_list_producer",
            ),
            path(
                "customer_of_permanence/<int:permanence>/",
                self.admin_site.admin_view(
                    AdminFilterCustomerOfPermanenceSearchView.as_view(model_admin=self)
                ),
                name="repanier_purchase_list_customer",
            ),
        ]
        return my_urls + urls

    def get_preserved_filters(self, request):
        purchase_saved = get_threading_local("purchase_saved")
        if purchase_saved is not None:
            dict = get_preserved_filters_as_dict()
            # Update the customer which is an editable field into the current admin form
            dict["customer"] = purchase_saved.customer_id
            return get_preserved_filters_from_dict(dict)
        else:
            return get_preserved_filters()

    def response_add(self, request, obj, post_url_continue=None):

        purchase_saved = get_threading_local("purchase_saved")
        return super().response_add(request, purchase_saved, post_url_continue)

    def changelist_view(self, request, extra_context=None):
        # Add extra context data to pass to change list template
        # extra_context = extra_context or {}
        # extra_context['my_store_data'] = {'onsale': ['Item 1', 'Item 2']}
        view = super().changelist_view(request, extra_context)
        filtered_queryset = view.context_data["cl"].queryset
        first_purchase = filtered_queryset.first()
        self.update_extra_context(view, first_purchase)
        return view

    def update_extra_context(self, view, purchase):
        if purchase is None:
            delivery_point = None
            permanence = None
        else:
            delivery_point = purchase.get_delivery_display()
            permanence = purchase.get_permanence_display()
        extra_context = {
            "PERMANENCE": permanence,
            "DELIVERY_POINT": delivery_point,
        }
        view.context_data.update(extra_context)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        permanence = Permanence.objects.filter(id=permanence_id).first()
        context = context or {}
        context.update(
            {
                "PERMANENCE": permanence,
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def is_order_confirm_send(self, request):
        query_params = get_request_params()
        permanence_id = query_params.get("permanence", "0")
        customer_id = query_params.get("customer", "0")
        user_message_level = messages.ERROR
        user_message = _("Action canceled by the system.")
        customer = Customer.objects.filter(id=customer_id).first()
        permanence = Permanence.objects.filter(id=permanence_id).first()
        if permanence is not None and customer is not None:
            customer_invoice = CustomerInvoice.objects.filter(
                customer_id=customer_id, permanence_id=permanence_id
            ).first()
            if customer_invoice is not None:
                customer_invoice.calculate_order_amount()
                customer_invoice.confirm_order()
                customer_invoice.save()
                user_message_level = messages.INFO
                user_message = _("Order confirmed")
            else:
                user_message_level = messages.INFO
                user_message = _("Nothing to confirm.")

            redirect_to = "{}?permanence={}&customer={}".format(
                reverse("admin:repanier_purchase_changelist"),
                permanence_id,
                customer_id,
            )
        elif permanence_id is not None:
            redirect_to = "{}?permanence={}".format(
                reverse("admin:repanier_purchase_changelist"), permanence_id
            )
        else:
            redirect_to = reverse("admin:repanier_purchase_changelist")
        self.message_user(request, user_message, user_message_level)
        return HttpResponseRedirect(redirect_to)

    def get_fields(self, request, purchase=None):
        return [
            "permanence",
            "customer",
            "delivery",
            "product",
            "offer_item",
            "quantity",
            "comment",
        ]

    def get_readonly_fields(self, request, purchase=None):
        if purchase is not None and purchase.status > PERMANENCE_SEND:
            return [
                "quantity",
            ]
        return []

    @transaction.atomic
    def save_model(self, request, purchase, form, change):
        customer = form.cleaned_data.get("customer")
        permanence = form.cleaned_data.get("permanence")
        status = permanence.status
        delivery = None

        if permanence.with_delivery_point and "delivery" in form.fields:
            delivery = form.cleaned_data.get("delivery")
            if delivery is not None:
                status = delivery.status

        if status > PERMANENCE_SEND:
            # The purchase is maybe already invoiced
            # Do not update it
            # It is forbidden to change invoiced permanence
            return

        product = form.cleaned_data.get("product")
        offer_item = product.get_or_create_offer_item(permanence)
        quantity = form.cleaned_data.get("quantity", DECIMAL_ZERO)
        comment = form.cleaned_data.get("comment")

        purchase, _ = create_or_update_one_purchase(
            customer.id,
            offer_item,
            status,
            q_order=quantity,
            batch_job=True,
            comment=comment,
        )

        # The customer_invoice may be created with "purchase.save()"
        customer_invoice = CustomerInvoice.objects.filter(
            customer_id=purchase.customer_id,
            permanence_id=purchase.permanence_id,
        ).first()
        customer_invoice.status = status
        customer_invoice.set_order_delivery(delivery)
        customer_invoice.calculate_order_amount()
        customer_invoice.confirm_order()
        customer_invoice.save()

        set_threading_local("purchase_saved", purchase)

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

    class Media:
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            js = (
                "admin/js/jquery.init.js",
                get_repanier_static_name("js/admin/confirm_purchase.js"),
                get_repanier_static_name("js/admin/reset_purchase.js"),
            )
        else:
            js = (
                "admin/js/jquery.init.js",
                get_repanier_static_name("js/admin/reset_purchase.js"),
            )
