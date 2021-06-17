from admin_auto_filters.filters import AutocompleteFilter
from admin_auto_filters.views import AutocompleteJsonView
from dal import autocomplete, forward
from django import forms
from django.contrib import admin
from django.db import transaction
from django.forms import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.fields.RepanierMoneyField import FormMoneyField
from repanier.middleware import get_request_params
from repanier.models.offeritem import OfferItemSend, OfferItem
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.purchase import Purchase
from repanier.tools import rule_of_3_reload_purchase


class OfferItemAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        permanence_id = self.forwarded.get("permanence", None)
        producer_id = self.forwarded.get("producer", None)
        qs = OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer_id=producer_id,
            is_box_content=False,
        ).order_by("department_for_customer", "long_name_v2")

        if self.q:
            qs = qs.filter(long_name_v2__icontains=self.q)

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


class OfferItemAutocompleteOfferItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, selected_item):
        if selected_item.department_for_customer is None:
            return "{} - {}".format(
                selected_item.producer,
                selected_item.get_long_name_with_customer_price(),
            )
        else:
            return "{} - {} - {}".format(
                selected_item.department_for_customer,
                selected_item.producer,
                selected_item.get_long_name_with_customer_price(),
            )


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
            "admin:repanier_customersend_list_producer",
            args=(permanence_id,),
        )


class CustomerPurchaseSendInlineFormSet(BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        values = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                # This is not an empty form or a "to be deleted" form
                value = form.cleaned_data.get("offer_item", None)
                if value is not None:
                    if value in values:
                        raise forms.ValidationError(
                            _("The same product can not be selected twice.")
                        )
                    else:
                        values.add(value)


class CustomerPurchaseSendInlineForm(forms.ModelForm):
    previous_purchase_price = FormMoneyField(
        max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO
    )
    previous_offer_item = forms.ModelChoiceField(
        OfferItemSend.objects.none(), required=False
    )
    offer_item = OfferItemAutocompleteOfferItemChoiceField(
        label=_("Offer item"),
        queryset=OfferItem.objects.all(),
        required=True,
        widget=autocomplete.ModelSelect2(
            url="admin:repanier_customersend_form_offeritem",
            forward=(
                # forward.Const(42, 'permanence') ??
                forward.Field("permanence"),
                forward.Field("producer"),
            ),
            attrs={
                "data-dropdown-auto-width": "true",
                "data-width": "100%",
                "data-html": True,
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        purchase = self.instance
        self.fields["previous_purchase_price"].initial = purchase.purchase_price
        try:
            offer_item = purchase.offer_item
        except AttributeError:
            offer_item = None
        self.fields["previous_offer_item"].initial = offer_item


class CustomerPurchaseSendInline(admin.TabularInline):
    form = CustomerPurchaseSendInlineForm
    formset = CustomerPurchaseSendInlineFormSet
    model = Purchase
    fields = [
        "offer_item",
        "quantity_invoiced",
        "get_html_producer_unit_price",
        "get_html_unit_deposit",
        "purchase_price",
        "comment",
    ]
    readonly_fields = ["get_html_producer_unit_price", "get_html_unit_deposit"]
    extra = 0
    fk_name = "customer_producer_invoice"
    parent_object = None

    def has_delete_permission(self, request, obj=None):
        # To delete the purchase, set the quantity to zero
        return False

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "offer_item":
            # Important : allow is_active or not active offer_item, we are into the admin interface.
            kwargs["queryset"] = (
                OfferItemSend.objects.filter(
                    producer_id=self.parent_object.producer_id,
                    permanence_id=self.parent_object.permanence_id,
                )
                .select_related("producer")
                .order_by("preparation_sort_order_v2")
                .distinct()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(
            is_box_content=False,
        ).order_by("offer_item__preparation_sort_order_v2")


class CustomerSendForm(forms.ModelForm):
    offer_purchase_price = FormMoneyField(
        label=_("Producer amount invoiced"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    offer_selling_price = FormMoneyField(
        label=_("Invoiced to the customer including VAT"),
        max_digits=8,
        decimal_places=2,
        required=True,
        initial=REPANIER_MONEY_ZERO,
    )
    rule_of_3 = forms.BooleanField(
        label=_("Apply the rule of 3"), required=False, initial=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        customer_producer_invoice = self.instance
        self.fields[
            "offer_purchase_price"
        ].initial = customer_producer_invoice.total_purchase_with_tax
        self.fields[
            "offer_selling_price"
        ].initial = customer_producer_invoice.total_selling_with_tax
        if customer_producer_invoice.producer.price_list_multiplier >= DECIMAL_ONE:
            self.fields["offer_selling_price"].widget = forms.HiddenInput()
        else:
            self.fields["offer_purchase_price"].widget = forms.HiddenInput()

        permanence_field = self.fields["permanence"]
        producer_field = self.fields["producer"]

        permanence_field.widget.can_add_related = False
        producer_field.widget.can_add_related = False
        permanence_field.widget.can_delete_related = False
        producer_field.widget.can_delete_related = False
        permanence_field.widget.can_change_related = False
        producer_field.widget.can_change_related = False
        permanence_field.widget.can_view_related = False
        producer_field.widget.can_view_related = False
        permanence_field.disabled = True
        producer_field.disabled = True
        permanence_field.empty_label = None
        producer_field.empty_label = None
        permanence_field.queryset = Permanence.objects.filter(
            id=customer_producer_invoice.permanence_id
        )
        producer_field.queryset = Producer.objects.filter(
            id=customer_producer_invoice.producer_id
        )
        permanence_field.widget = forms.HiddenInput()
        producer_field.widget = forms.HiddenInput()


class CustomerSendAdmin(admin.ModelAdmin):
    form = CustomerSendForm
    fields = (
        (
            "permanence",
            "producer",
        ),
        ("offer_purchase_price", "offer_selling_price", "rule_of_3"),
    )
    list_per_page = 16
    list_max_show_all = 16
    inlines = [CustomerPurchaseSendInline]
    list_display = ["producer", "customer", "get_html_producer_price_purchased"]
    list_display_links = ("customer",)
    list_filter = (AdminFilterProducerOfPermanence,)
    search_fields = ("customer__short_basket_name",)
    ordering = ("customer",)

    def has_module_permission(self, request):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_repanier_staff:
            return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "producer_of_permanence/<int:permanence>/",
                self.admin_site.admin_view(
                    AdminFilterProducerOfPermanenceSearchView.as_view(model_admin=self)
                ),
                name="repanier_customersend_list_producer",
            ),
            path(
                "offer_item_autocomplete/",
                OfferItemAutocomplete.as_view(),
                name="repanier_customersend_form_offeritem",
            ),
        ]
        return my_urls + urls

    def changelist_view(self, request, extra_context=None):
        query_params = get_request_params()
        producer_id = query_params.get("producer", "0")
        if Producer.objects.filter(id=producer_id, invoice_by_basket=False).exists():
            # Goto rule_of_3_per_product
            send_offeritem_changelist_url = "{}?is_filled_exact=1&".format(
                reverse("admin:repanier_offeritemsend_changelist")
            )
            permanence_id = query_params.get("permanence", "0")
            changelist_url = "{}permanence={}&producer={}".format(
                send_offeritem_changelist_url,
                permanence_id,
                producer_id,
            )
            return HttpResponseRedirect(changelist_url)
        permanence_id = query_params.get("permanence", "0")
        permanence = Permanence.objects.filter(id=permanence_id).first()
        extra_context = extra_context or {}
        extra_context.update(
            {
                "PERMANENCE": permanence,
            }
        )
        return super().changelist_view(request, extra_context)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        # obj is the edited customer_producer_invoice
        if obj is None:
            # Adding is not allowed in the administration interface but you never know
            permanence = None
            customer_producer_invoice = None
        else:
            permanence = str(obj.permanence)
            customer_producer_invoice = str(obj)
        extra_context = {
            "PERMANENCE": permanence,
            "DELIVERY_POINT": EMPTY_STRING,  # TODO
            "CUSTOMER_PRODUCER_INVOICE": customer_producer_invoice,
        }
        context.update(extra_context)
        return super().render_change_form(request, context, add, change, form_url, obj)

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

    def save_model(self, request, customer_producer_invoice, form, change):
        super().save_model(request, customer_producer_invoice, form, change)

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, "new_objects"):
                formset.new_objects = []
            if not hasattr(formset, "changed_objects"):
                formset.changed_objects = []
            if not hasattr(formset, "deleted_objects"):
                formset.deleted_objects = []
        customer_producer_invoice = form.instance
        customer = customer_producer_invoice.customer
        formset = formsets[0]
        for purchase_form in formset:
            purchase = purchase_form.instance
            previous_offer_item = purchase_form.fields["previous_offer_item"].initial
            if (
                previous_offer_item is not None
                and previous_offer_item != purchase.offer_item
            ):
                # Delete the purchase because the offer_item has changed
                purchase = Purchase.objects.filter(
                    customer_id=customer.id,
                    offer_item_id=previous_offer_item.id,
                    is_box_content=False,
                ).first()
                if purchase is not None:
                    purchase.quantity_invoiced = DECIMAL_ZERO
                    purchase.save()
                    purchase.save_box()
        for purchase_form in formset:
            purchase_form_instance = purchase_form.instance
            try:
                offer_item = purchase_form_instance.offer_item
            except OfferItem.DoesNotExist:  # RelatedObjectDoesNotExist
                offer_item = None
            if offer_item is None:
                purchase_form.repanier_is_valid = False
            else:
                purchase = rule_of_3_reload_purchase(
                    customer, offer_item, purchase_form, purchase_form_instance
                )
                previous_purchase_price = purchase_form.fields[
                    "previous_purchase_price"
                ].initial
                if purchase.purchase_price != previous_purchase_price:
                    producer_unit_price = purchase.get_producer_unit_price()
                    if producer_unit_price != DECIMAL_ZERO:
                        purchase.quantity_invoiced = (
                            purchase.purchase_price.amount / producer_unit_price
                        ).quantize(FOUR_DECIMALS)
                    else:
                        purchase.quantity_invoiced = DECIMAL_ZERO
                purchase.save()
        rule_of_3 = form.cleaned_data["rule_of_3"]
        if rule_of_3:
            if customer_producer_invoice.producer.price_list_multiplier >= DECIMAL_ONE:
                rule_of_3_target = form.cleaned_data[
                    "offer_purchase_price"
                ].amount.quantize(TWO_DECIMALS)
                selling_price = False
            else:
                rule_of_3_target = form.cleaned_data[
                    "offer_selling_price"
                ].amount.quantize(TWO_DECIMALS)
                selling_price = True
            rule_of_3_source = DECIMAL_ZERO
            max_purchase_counter = 0
            for purchase_form in formset:
                if purchase_form.repanier_is_valid:
                    if selling_price:
                        rule_of_3_source += purchase_form.instance.selling_price.amount
                    else:
                        rule_of_3_source += purchase_form.instance.purchase_price.amount
                    max_purchase_counter += 1
            if rule_of_3_target is not None and rule_of_3_target != rule_of_3_source:
                if rule_of_3_source != DECIMAL_ZERO:
                    ratio = (rule_of_3_target / rule_of_3_source).quantize(
                        FOUR_DECIMALS
                    )
                else:
                    if rule_of_3_target == DECIMAL_ZERO:
                        ratio = DECIMAL_ZERO
                    else:
                        ratio = DECIMAL_ONE
                if ratio != DECIMAL_ONE:
                    adjusted_invoice = DECIMAL_ZERO
                    i = 0
                    for purchase_form in formset:
                        if purchase_form.repanier_is_valid:
                            i += 1
                            purchase = purchase_form.instance
                            if i == max_purchase_counter:
                                if purchase.get_producer_unit_price() != DECIMAL_ZERO:
                                    delta = rule_of_3_target - adjusted_invoice
                                    if selling_price:
                                        purchase.quantity_invoiced = (
                                            delta / purchase.get_customer_unit_price()
                                        ).quantize(FOUR_DECIMALS)
                                    else:
                                        purchase.quantity_invoiced = (
                                            delta / purchase.get_producer_unit_price()
                                        ).quantize(FOUR_DECIMALS)
                                else:
                                    purchase.quantity_invoiced = DECIMAL_ZERO
                            else:
                                purchase.quantity_invoiced = (
                                    purchase.quantity_invoiced * ratio
                                ).quantize(FOUR_DECIMALS)

                            purchase.save()
                            purchase.save_box()
                            if selling_price:
                                adjusted_invoice += purchase.selling_price.amount
                            else:
                                adjusted_invoice += purchase.purchase_price.amount
        for purchase_form in formset:
            if purchase_form.has_changed() and purchase_form.repanier_is_valid:
                purchase_form.instance.save()
                purchase_form.instance.save_box()
