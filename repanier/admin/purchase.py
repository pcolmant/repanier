import logging

from dal import autocomplete
from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.core.checks import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

# from django.views.i18n import JavaScriptCatalog
from easy_select2 import Select2
from repanier.admin.admin_filter import (
    AdminFilterCustomerOfPermanence,
    AdminFilterProducerOfPermanence,
)
from repanier.const import *
from repanier.email.email_order import export_order_2_1_customer
from repanier.middleware import get_request_params, get_request, get_query_filters
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.tools import sint, get_repanier_static_name
from repanier.widget.select_admin_delivery import SelectAdminDeliveryWidget

logger = logging.getLogger(__name__)


class ProductAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        # if not self.request.user.is_staff:
        #     return OfferItem.objects.none()
        permanence_id = self.forwarded.get("permanence", None)
        # customer_id = self.forwarded.get('customer', None)
        # print("######### permanence_id : {}".format(permanence_id))
        # print("######### customer_id : {}".format(customer_id))
        # if customer_id is None or permanence_id is None:
        #     qs = Product.objects.none()
        # else:
        #     producer_id = self.forwarded.get('producer', None)
        #     purchased_product = Product.objects.filter(
        #         permanence_id=permanence_id,
        #         purchase__customer_id=customer_id,
        #     )
        #     qs = Product.objects.filter(
        #         producer__permanence=permanence_id,
        #         is_into_offer=True,
        #     ).order_by("department_for_customer", "long_name_v2")
        #     if producer_id is not None:
        #         qs = qs.filter(producer_id=producer_id)
        #     if customer_id is not None and purchased_product.exists():
        #         qs = qs.exclude(id__in=purchased_product)
        #     if self.q:
        #         qs = qs.filter(long_name_v2__istartswith=self.q)
        qs = OfferItem.objects.filter(
            permanence_id=permanence_id,
            is_box_content=False,
        ).order_by("department_for_customer", "long_name_v2")

        if self.q:
            qs = qs.filter(long_name_v2__istartswith=self.q)

        return qs

    def get_result_label(self, item):
        if item.department_for_customer is None:
            return "{} - {}".format(
                item.producer,
                item.get_long_name_with_customer_price(),
            )
        else:
            return "{} - {} - {}".format(
                item.department_for_customer,
                item.producer,
                item.get_long_name_with_customer_price(),
            )


class DeliveryAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        # if not self.request.user.is_staff:
        #     return OfferItem.objects.none()
        permanence_id = self.forwarded.get("permanence", None)
        customer_id = self.forwarded.get("customer", None)
        qs = DeliveryBoard.objects.filter(
            permanence_id=permanence_id,
        ).order_by("long_name_v2")

        return qs


class PurchaseForm(forms.ModelForm):
    delivery = forms.ModelChoiceField(
        label=_("Delivery point"), queryset=DeliveryBoard.objects.none(), required=False
    )
    quantity = forms.DecimalField(
        min_value=DECIMAL_ZERO,
        label=_("Qty"),
        max_digits=9,
        decimal_places=4,
        required=True,
        initial=0,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        purchase = self.instance

        if purchase.id is None:
            # Add new purchase
            param = get_request_params()
            permanence_id = param.get("permanence", None)
            self.fields["permanence"].initial = permanence_id
            customer_id = param.get("customer", None)
            self.fields["customer"].initial = customer_id
            delivery_point_id = None
        else:
            # Update existing purchase
            if purchase.status < PERMANENCE_SEND:
                self.fields["quantity"].initial = purchase.quantity_ordered
            else:
                self.fields["quantity"].initial = purchase.quantity_invoiced

            permanence_id = purchase.permanence_id
            delivery_point_id = purchase.customer_invoice.delivery

            self.fields["offer_item"].widget.attrs["readonly"] = True
            self.fields["offer_item"].disabled = True

        self.fields["permanence"].widget.attrs["readonly"] = True
        self.fields["permanence"].disabled = True
        self.fields["customer"].widget.attrs["readonly"] = True
        self.fields["customer"].disabled = True

        if Permanence.objects.filter(
            id=permanence_id, with_delivery_point=True
        ).exists():
            self.fields["delivery"].initial = delivery_point_id
        else:
            self.fields["delivery"].initial = None
            self.fields["delivery"].widget = forms.HiddenInput()

    def clean_product(self):
        product_id = sint(self.cleaned_data.get("product"), 0)
        if product_id <= 0:
            if product_id == -1:
                self.add_error(
                    "product",
                    _(
                        "Please select first a producer in the filter of previous screen..."
                    ),
                )
            else:
                self.add_error(
                    "product",
                    _(
                        "No more product to add. Please update a product of previous screen."
                    ),
                )
        return product_id

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if self.instance.id is None:
            quantity = self.cleaned_data.get("quantity", DECIMAL_ZERO)
            if quantity == DECIMAL_ZERO:
                self.add_error(
                    "quantity", _("The quantity must be different than zero.")
                )
        # self._validate_unique = False

    class Meta:
        model = Purchase
        fields = "__all__"
        widgets = {
            "offer_item": autocomplete.ModelSelect2(
                url="admin:product-autocomplete",
                forward=["permanence", "customer"],
                attrs={"data-dropdown-auto-width": "true", "data-width": "100%"},
            ),
            "delivery": autocomplete.ModelSelect2(
                url="admin:delivery-autocomplete",
                forward=["permanence", "customer"],
                attrs={"data-dropdown-auto-width": "true", "data-width": "100%"},
            ),
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
        AdminFilterCustomerOfPermanence,  # Do not limit to customer in this permanence
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
        return (
            super()
            .get_queryset(request)
            .filter(
                is_box_content=False,
            )
        )

    def has_delete_permission(self, request, purchase=None):
        return False

    def has_add_permission(self, request):
        param = get_request_params()
        permanence_id = param.get("permanence", None)
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
        if purchase is not None and purchase.status > PERMANENCE_SEND:
            return False
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url(
                r"^is_order_confirm_send/$",
                self.admin_site.admin_view(self.is_order_confirm_send),
            ),
            url(
                r"^product_autocomplete/$",
                ProductAutocomplete.as_view(),
                name="product-autocomplete",
            ),
            url(
                r"^delivery_autocomplete/$",
                DeliveryAutocomplete.as_view(),
                name="delivery-autocomplete",
            ),
            # url(r'^is_order_confirm_not_send/$', self.admin_site.admin_view(self.is_order_confirm_not_send)),
            # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), {'packages': ('repanier',)}, name='javascript-catalog'),
            # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
        ]
        return my_urls + urls
        return urls

    def changelist_view(self, request, extra_context=None):
        # Add extra context data to pass to change list template
        # extra_context = extra_context or {}
        # extra_context['my_store_data'] = {'onsale': ['Item 1', 'Item 2']}
        changelist_view = super().changelist_view(request, extra_context)
        filtered_queryset = changelist_view.context_data["cl"].queryset
        first_purchase = filtered_queryset.first()
        if first_purchase is None:
            delivery_point = None
            permanence = None
        else:
            delivery_point = first_purchase.get_delivery_display()
            permanence = first_purchase.get_permanence_display()
        extra_context = {
            "PERMANENCE": permanence,
            "DELIVERY_POINT": delivery_point,
        }
        changelist_view.context_data.update(extra_context)
        return changelist_view

    def is_order_confirm_send(self, request):
        param = get_request_params()
        permanence_id = param.get("permanence", None)
        customer_id = param.get("customer", None)
        user_message_level = messages.ERROR
        user_message = _("Action canceled by the system.")
        if permanence_id is not None and customer_id is not None:
            customer = Customer.objects.filter(id=customer_id).first()
            permanence = Permanence.objects.filter(id=permanence_id).first()
            if permanence is not None and customer is not None:
                customer_invoice = CustomerInvoice.objects.filter(
                    customer_id=customer_id, permanence_id=permanence_id
                ).first()
                if customer_invoice is not None:
                    if (
                        customer_invoice.status == PERMANENCE_OPENED
                        and not customer_invoice.is_order_confirm_send
                    ):
                        filename = "{}-{}.xlsx".format(_("Order"), permanence)
                        export_order_2_1_customer(customer, filename, permanence)
                        user_message_level = messages.INFO
                        user_message = customer.my_order_confirmation_email_send_to()
                    else:
                        user_message_level = messages.INFO
                        user_message = _("Order confirmed")
                    customer_invoice.confirm_order()
                    customer_invoice.save()
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
        if purchase is None:
            param = get_request_params()
            permanence_id = param.get("permanence", None)
        else:
            permanence_id = purchase.permanence_id

        if permanence_id is not None:
            fields = [
                "permanence",
                "delivery",
                "customer",
                "offer_item",
                "quantity",
                "comment",
                "is_updated_on",
            ]
        else:
            fields = []
        return fields

    def get_readonly_fields(self, request, purchase=None):
        if purchase is not None and purchase.status > PERMANENCE_SEND:
            return ["is_updated_on", "quantity"]
        return ["is_updated_on"]

    def get_form(self, request, purchase=None, **kwargs):

        form = super().get_form(request, purchase, **kwargs)

        # /purchase/add/?_changelist_filters=permanence%3D6%26customer%3D3
        # If we are coming from a list screen, use the filter to pre-fill the form
        # if purchase is None:
        #     param = get_request_params()
        #     permanence_id = param.get("permanence", None)
        #     customer_id = param.get("customer", None)
        #     producer_id = param.get("producer", None)
        #     delivery_id = param.get("delivery", None)
        # else:
        #     permanence_id = purchase.permanence_id
        #     customer_id = purchase.customer_id
        #     producer_id = purchase.producer_id
        #     delivery_id = purchase.customer_invoice.delivery
        #
        # permanence_field = form.base_fields["permanence"]
        # customer_field = form.base_fields["customer"]
        # delivery_field = form.base_fields["delivery"]
        #
        #     delivery_field.widget.can_add_related = False
        #     delivery_field.widget.can_delete_related = False
        #
        #     if permanence_id is not None:
        #         # reset permanence_id if the delivery_id is not one of this permanence
        #         if Permanence.objects.filter(
        #             id=permanence_id, with_delivery_point=True
        #         ).exists():
        #             customer_invoice = CustomerInvoice.objects.filter(
        #                 customer_id=customer_id, permanence_id=permanence_id
        #             ).only("delivery_id")
        #             if customer_invoice.exists():
        #                 delivery_field.initial = customer_invoice.first().delivery_id
        #             elif delivery_id is not None:
        #                 delivery_field.initial = delivery_id
        #             delivery_field.choices = [
        #                 (o.id, o.get_delivery_status_display())
        #                 for o in DeliveryBoard.objects.filter(
        #                     permanence_id=permanence_id
        #                 )
        #             ]
        #         else:
        #             delivery_field.required = False
        #         permanence_field.empty_label = None
        #         permanence_field.initial = permanence_id
        #         permanence_field.choices = [
        #             (o.id, o) for o in Permanence.objects.filter(id=permanence_id)
        #         ]
        #     else:
        #         permanence_field.choices = [
        #             (
        #                 "-1",
        #                 _(
        #                     "Please select first a permanence in the filter of previous screen..."
        #                 ),
        #             )
        #         ]
        #         permanence_field.disabled = True
        #
        #     if len(delivery_field.choices) == 0:
        #         delivery_field.required = False
        #
        #     if purchase is not None:
        #         permanence_field.empty_label = None
        #         permanence_field.queryset = Permanence.objects.filter(id=permanence_id)
        #         customer_field.empty_label = None
        #         customer_field.queryset = Customer.objects.filter(id=customer_id)
        #         # product_field.empty_label = None
        #         # product_field.choices = [
        #         #     (o.id, str(o))
        #         #     for o in OfferItemWoReceiver.objects.filter(
        #         #         id=purchase.offer_item_id,
        #         #     ).order_by("department_for_customer", "long_name_v2")
        #         # ]
        #     else:
        #         if permanence_id is not None:
        #             if customer_id is not None:
        #                 customer_field.empty_label = None
        #                 customer_field.queryset = Customer.objects.filter(
        #                     id=customer_id, may_order=True
        #                 )
        #                 purchased_product = Product.objects.filter(
        #                     offeritem__permanence_id=permanence_id,
        #                     offeritem__purchase__customer_id=customer_id,
        #                 )
        #                 qs = Product.objects.filter(
        #                     producer__permanence=permanence_id,
        #                     is_into_offer=True,
        #                 ).order_by("department_for_customer", "long_name_v2")
        #                 if producer_id is not None:
        #                     qs = qs.filter(producer_id=producer_id)
        #                 if customer_id is not None and purchased_product.exists():
        #                     qs = qs.exclude(id__in=purchased_product)
        #                 # product_field.choices = [
        #                 #     (o.id, "{}".format(o)) for o in qs.distinct()
        #                 # ]
        #                 # if len(product_field.choices) == 0:
        #                 #     product_field.choices = [
        #                 #         (
        #                 #             "-2",
        #                 #             _(
        #                 #                 "No more product to add. Please update a product of previous screen."
        #                 #             ),
        #                 #         )
        #                 #     ]
        #                 #     product_field.disabled = True
        #             else:
        #                 customer_field.choices = [
        #                     (
        #                         "-1",
        #                         _(
        #                             "Please select first a customer in the filter of previous screen..."
        #                         ),
        #                     )
        #                 ]
        #                 customer_field.disabled = True
        #                 # product_field.choices = []
        #         else:
        #             customer_field.choices = []
        #             # product_field.choices = []
        return form

    @transaction.atomic
    def save_model(self, request, purchase, form, change):
        status = purchase.permanence.status
        delivery = None
        if "delivery" in form.fields:
            delivery_id = form.cleaned_data.get("delivery")
            if delivery_id != EMPTY_STRING:
                delivery = (
                    DeliveryBoard.objects.filter(id=delivery_id).only("status").first()
                )
                if delivery is not None:
                    status = delivery.status

        if status > PERMANENCE_SEND:
            # The purchase is maybe already invoiced
            # Do not update it
            # It is forbidden to change invoiced permanence
            return

        product_or_offer_item_id = form.cleaned_data.get("product")
        if purchase.id is not None:
            # Update : product_or_offer_item_id is an offer_item_id
            offer_item = OfferItem.objects.filter(
                id=product_or_offer_item_id, permanence_id=purchase.permanence_id
            ).first()
        else:
            # New : product_or_offer_item_id is a product_id
            product = Product.objects.filter(id=product_or_offer_item_id).first()
            offer_item = product.get_or_create_offer_item(purchase.permanence)

        if offer_item is not None:

            purchase.offer_item = offer_item
            if status < PERMANENCE_SEND:
                purchase.quantity_ordered = form.cleaned_data.get(
                    "quantity", DECIMAL_ZERO
                )
            else:
                purchase.quantity_invoiced = form.cleaned_data.get(
                    "quantity", DECIMAL_ZERO
                )

            purchase.status = status
            purchase.producer = offer_item.producer
            purchase.permanence.producers.add(offer_item.producer)
            purchase.save()
            purchase.save_box()
            # The customer_invoice may be created with "purchase.save()"
            customer_invoice = CustomerInvoice.objects.filter(
                customer_id=purchase.customer_id,
                permanence_id=purchase.permanence_id,
            ).first()
            customer_invoice.status = status
            customer_invoice.set_order_delivery(delivery)
            customer_invoice.calculate_order_price()
            customer_invoice.confirm_order()
            customer_invoice.save()

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
            # logger.debug(
            #     "purchase admin media : {}".format(
            #         get_repanier_static_name("js/is_order_confirm_send.js")
            #     )
            # )
            js = (
                "admin/js/jquery.init.js",
                get_repanier_static_name("js/is_order_confirm_send.js"),
            )
