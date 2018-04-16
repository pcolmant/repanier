# -*- coding: utf-8

from urllib.parse import parse_qsl

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.core import urlresolvers
from django.core.checks import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
# from django.views.i18n import JavaScriptCatalog
from easy_select2 import Select2
from import_export import resources, fields
from import_export.admin import ExportMixin
from import_export.formats.base_formats import CSV, ODS, JSON, XLS

from repanier.admin.admin_filter import PurchaseFilterByProducerForThisPermanence, \
    PurchaseFilterByCustomer, PurchaseFilterByPermanence
from repanier.const import *
from repanier.email.email_order import export_order_2_1_customer
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.product import Product
from repanier.models.purchase import Purchase
from repanier.models.staff import Staff
from repanier.tools import sint
from repanier.widget.select_admin_delivery import SelectAdminDeliveryWidget
from repanier.widget.select_admin_permanence import SelectAdminPermanenceWidget
from repanier.xlsx.extended_formats import XLSX_OPENPYXL_1_8_6
from repanier.xlsx.widget import IdWidget, \
    ChoiceWidget, FourDecimalsWidget, TwoMoneysWidget, DateWidgetExcel


class PurchaseResource(resources.ModelResource):
    id = fields.Field(attribute='id', widget=IdWidget(), readonly=True)
    short_name = fields.Field(attribute='permanence__short_name', readonly=True)
    date = fields.Field(attribute='permanence__permanence_date', widget=DateWidgetExcel(), readonly=True)
    product_id = fields.Field(attribute='offer_item__product__id', readonly=True)
    product = fields.Field(attribute='offer_item__get_long_name', readonly=True)
    producer_id = fields.Field(attribute='producer__id', readonly=True)
    producer_name = fields.Field(attribute='producer__short_profile_name', readonly=True)
    customer_id = fields.Field(attribute='customer__id', readonly=True)
    customer_name = fields.Field(attribute='customer__short_basket_name', readonly=True)
    unit_deposit = fields.Field(attribute='offer_item__unit_deposit', widget=TwoMoneysWidget(), readonly=True)
    producer_unit_price_wo_tax = fields.Field(attribute='offer_item__producer_unit_price_wo_tax',
                                              widget=TwoMoneysWidget(), readonly=True)
    producer_vat = fields.Field(attribute='offer_item__producer_vat', widget=TwoMoneysWidget(), readonly=True)
    customer_unit_price = fields.Field(attribute='offer_item__customer_unit_price', widget=TwoMoneysWidget(),
                                       readonly=True)
    customer_vat = fields.Field(attribute='offer_item__customer_vat', widget=TwoMoneysWidget(), readonly=True)
    quantity_invoiced = fields.Field(attribute='quantity_invoiced', widget=FourDecimalsWidget(), readonly=True)
    producer_row_price = fields.Field(attribute='purchase_price', widget=TwoMoneysWidget(), readonly=True)
    customer_row_price = fields.Field(attribute='selling_price', widget=TwoMoneysWidget(), readonly=True)
    vat_level = fields.Field(attribute='offer_item__vat_level',
                             widget=ChoiceWidget(LUT_ALL_VAT, LUT_ALL_VAT_REVERSE), readonly=True)

    class Meta:
        model = Purchase
        fields = (
            'id', 'date', 'short_name',
            'producer_id',
            'producer_name',
            'product_id',
            'product',
            'customer_id',
            'customer_name',
            'quantity_invoiced', 'unit_deposit',
            'producer_unit_price_wo_tax',
            'producer_vat',
            'customer_unit_price',
            'customer_vat',
            'producer_row_price',
            'customer_row_price',
            'vat_level',
            'comment'
        )
        export_order = fields
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


class PurchaseForm(forms.ModelForm):
    product = forms.ChoiceField(label=_("Product"), widget=Select2(select2attrs={'width': '450px'}))
    delivery = forms.ChoiceField(label=_("Delivery point"), widget=SelectAdminDeliveryWidget())

    def clean_product(self):
        product_id = sint(self.cleaned_data.get("product"), 0)
        if product_id <= 0:
            if product_id == -1:
                self.add_error(
                    'product',
                    _("Please select first a producer in the filter of previous screen")
                )
            else:
                self.add_error(
                    'product',
                    _("No more product to add. Please update a product of previous screen")
                )
        return product_id

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if self.instance.id is None:
            quantity_ordered = self.cleaned_data.get("quantity_ordered", DECIMAL_ZERO)
            quantity_invoiced = self.cleaned_data.get("quantity_invoiced", DECIMAL_ZERO)
            if quantity_ordered == quantity_invoiced == DECIMAL_ZERO:
                self.add_error(
                    "quantity_ordered",
                    _('The quantity must be different than zero.'))
                self.add_error(
                    "quantity_invoiced",
                    _('The quantity must be different than zero.'))
        self._validate_unique = False

    class Meta:
        model = Purchase
        fields = "__all__"
        widgets = {
            'permanence': SelectAdminPermanenceWidget(),
            'customer': Select2(select2attrs={'width': '450px'})
        }


class PurchaseAdmin(ExportMixin, admin.ModelAdmin):
    form = PurchaseForm
    resource_class = PurchaseResource
    list_display = [
        'get_permanence_display',
        'get_delivery_display',
        'customer',
        'offer_item',
        'get_quantity',
        'get_selling_price',
    ]
    list_select_related = ('permanence', 'customer')
    list_per_page = 16
    list_max_show_all = 16
    ordering = ('customer', 'offer_item__translations__order_sort_order')
    list_filter = (
        PurchaseFilterByPermanence,
        PurchaseFilterByProducerForThisPermanence,
        PurchaseFilterByCustomer,  # Do not limit to customer in this permanence
    )
    list_display_links = ('offer_item',)
    search_fields = ('offer_item__translations__long_name',)
    actions = []

    # change_list_template = 'admin/purchase_change_list.html'

    def __init__(self, model, admin_site):
        super(PurchaseAdmin, self).__init__(model, admin_site)
        self.producer_id = None

    def get_department_for_customer(self, obj):
        return obj.offer_item.department_for_customer

    get_department_for_customer.short_description = _("Department")

    def get_queryset(self, request):
        permanence_id = request.GET.get('permanence', None)
        if permanence_id is not None:
            return super(PurchaseAdmin, self).get_queryset(request).filter(
                permanence=permanence_id,
                offer_item__translations__language_code=translation.get_language(),
                is_box_content=False
            ).distinct()
        else:
            return super(PurchaseAdmin, self).get_queryset(request).filter(
                offer_item__translations__language_code=translation.get_language(),
                is_box_content=False
            ).distinct()

    def has_delete_permission(self, request, purchase=None):
        return False

    def has_add_permission(self, request):
        preserved_filters = request.GET.get('_changelist_filters', None)
        permanence_id = None
        if preserved_filters is not None:
            param = dict(parse_qsl(preserved_filters))
            if 'permanence' in param:
                permanence_id = param['permanence']
        else:
            permanence_id = request.GET.get('permanence', None)
        if permanence_id is not None:
            if Permanence.objects.filter(id=permanence_id, status__gt=PERMANENCE_SEND).order_by('?').exists():
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
        urls = super(PurchaseAdmin, self).get_urls()
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            my_urls = [
                url(r'^is_order_confirm_send/$', self.admin_site.admin_view(self.is_order_confirm_send)),
                # url(r'^is_order_confirm_not_send/$', self.admin_site.admin_view(self.is_order_confirm_not_send)),
                # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), {'packages': ('repanier',)}, name='javascript-catalog'),
                # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
            ]
            return my_urls + urls
        return urls

    def is_order_confirm_send(self, request):
        permanence_id = request.GET.get('permanence', None)
        customer_id = request.GET.get('customer', None)
        user_message_level = messages.ERROR
        user_message = _("Action canceled by the system.")
        if permanence_id is not None and customer_id is not None:
            customer = Customer.objects.filter(id=customer_id).order_by('?').first()
            permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
            if permanence is not None and customer is not None:
                customer_invoice = CustomerInvoice.objects.filter(
                    customer_id=customer_id,
                    permanence_id=permanence_id,
                ).order_by('?').first()
                if customer_invoice is not None:
                    if customer_invoice.status == PERMANENCE_OPENED and not customer_invoice.is_order_confirm_send:
                        filename = "{0}-{1}.xlsx".format(
                            _("Order"),
                            permanence
                        )
                        export_order_2_1_customer(
                            customer, filename, permanence)
                        user_message_level = messages.INFO
                        user_message = customer.my_order_confirmation_email_send_to()
                    else:
                        user_message_level = messages.INFO
                        user_message = _('Order confirmed')
                    customer_invoice.confirm_order()
                    customer_invoice.save()
                else:
                    user_message_level = messages.INFO
                    user_message = _('Nothing to confirm')

            redirect_to = "{}?permanence={}&customer={}".format(
                urlresolvers.reverse('admin:repanier_purchase_changelist', ), permanence_id, customer_id)
        elif permanence_id is not None:
            redirect_to = "{}?permanence={}".format(
                urlresolvers.reverse('admin:repanier_purchase_changelist', ), permanence_id)
        else:
            redirect_to = urlresolvers.reverse('admin:repanier_purchase_changelist', )
        self.message_user(request, user_message, user_message_level)
        return HttpResponseRedirect(redirect_to)

    # def is_order_confirm_not_send(self, request):
    #     permanence_id = request.GET.get('permanence', None)
    #     customer_id = request.GET.get('customer', None)
    #     user_message_level = messages.ERROR
    #     user_message = _("Action canceled by the system.")
    #     if permanence_id is not None and customer_id is not None:
    #         customer = Customer.objects.filter(id=customer_id).order_by('?').first()
    #         permanence = Permanence.objects.filter(id=permanence_id).order_by('?').first()
    #         if permanence is not None and customer is not None:
    #             customer_invoice = CustomerInvoice.objects.filter(
    #                 customer_id=customer_id,
    #                 permanence_id=permanence_id,
    #             ).order_by('?').first()
    #             if customer_invoice is not None \
    #                     and customer_invoice.status == PERMANENCE_OPENED \
    #                     and customer_invoice.is_order_confirm_send:
    #                 user_message_level = messages.INFO
    #                 user_message = _('Order not confirmed')
    #                 customer_invoice.is_order_confirm_send = False
    #                 customer_invoice.save(update_fields=['is_order_confirm_send'])
    #             else:
    #                 user_message_level = messages.INFO
    #                 user_message = _('Nothing to unconfirm')
    #
    #         redirect_to = "{}?permanence={}&customer={}".format(
    #             urlresolvers.reverse('admin:repanier_purchase_changelist', ), permanence_id, customer_id)
    #     elif permanence_id is not None:
    #         redirect_to = "{}?permanence={}".format(
    #             urlresolvers.reverse('admin:repanier_purchase_changelist', ), permanence_id)
    #     else:
    #         redirect_to = urlresolvers.reverse('admin:repanier_purchase_changelist', )
    #     self.message_user(request, user_message, user_message_level)
    #     return HttpResponseRedirect(redirect_to)

    def get_fieldsets(self, request, purchase=None):
        permanence_id = None
        preserved_filters = request.GET.get('_changelist_filters', None)
        if preserved_filters is not None and purchase is None:
            param = dict(parse_qsl(preserved_filters))
            if 'permanence' in param:
                permanence_id = param['permanence']
        else:
            permanence_id = purchase.permanence_id if purchase is not None else None
        if permanence_id is not None:
            if Permanence.objects.filter(id=permanence_id, with_delivery_point=True).order_by('?').exists():
                fields_basic = [
                    'permanence', 'delivery',
                    'customer', 'product',
                    'quantity_ordered',
                    'quantity_invoiced', 'comment', 'is_updated_on'
                ]
            else:
                fields_basic = [
                    'permanence',
                    'customer', 'product',
                    'quantity_ordered',
                    'quantity_invoiced', 'comment', 'is_updated_on'
                ]
        else:
            fields_basic = []
        fieldsets = (
            (None, {'fields': fields_basic}),
        )
        return fieldsets

    def get_readonly_fields(self, request, purchase=None):
        if purchase is not None:
            status = purchase.status
            if status > PERMANENCE_SEND:
                return ['quantity_ordered', 'quantity_invoiced', 'is_updated_on']
        return ['is_updated_on']

    def get_form(self, request, purchase=None, **kwargs):
        form = super(PurchaseAdmin, self).get_form(request, purchase, **kwargs)
        # /purchase/add/?_changelist_filters=permanence%3D6%26customer%3D3
        # If we are coming from a list screen, use the filter to pre-fill the form
        permanence_id = None
        customer_id = None
        self.producer_id = None
        delivery_id = None
        preserved_filters = request.GET.get('_changelist_filters', None)
        if preserved_filters and purchase is None:
            param = dict(parse_qsl(preserved_filters))
            if 'permanence' in param:
                permanence_id = param['permanence']
            if 'customer' in param:
                customer_id = param['customer']
            if 'producer' in param:
                self.producer_id = param['producer']
            if 'delivery' in param:
                delivery_id = param['delivery']
        elif purchase is not None:
            permanence_id = purchase.permanence_id
            customer_id = purchase.customer_id
        if "permanence" in form.base_fields:
            permanence_field = form.base_fields["permanence"]
            customer_field = form.base_fields["customer"]
            product_field = form.base_fields["product"]
            delivery_field = form.base_fields["delivery"]
            permanence_field.widget.can_add_related = False
            permanence_field.widget.attrs['readonly'] = True
            permanence_field.disabled = True
            customer_field.widget.can_add_related = False
            product_field.widget.can_add_related = False
            delivery_field.widget.can_add_related = False
            customer_field.widget.can_delete_related = False
            product_field.widget.can_delete_related = False
            delivery_field.widget.can_delete_related = False
            customer_field.widget.attrs['readonly'] = True

            if permanence_id is not None:
                # reset permanence_id if the delivery_id is not one of this permanence
                if Permanence.objects.filter(id=permanence_id, with_delivery_point=True).order_by('?').exists():
                    customer_invoice = CustomerInvoice.objects.filter(
                        customer_id=customer_id, permanence_id=permanence_id
                    ).order_by('?').only("delivery_id")
                    if customer_invoice.exists():
                        delivery_field.initial = customer_invoice.first().delivery_id
                    elif delivery_id is not None:
                        delivery_field.initial = delivery_id
                    delivery_field.choices = [
                        (o.id, o.get_delivery_status_display()) for o in DeliveryBoard.objects.filter(
                            permanence_id=permanence_id
                        )
                    ]
                else:
                    delivery_field.required = False
                permanence_field.empty_label = None
                permanence_field.initial = permanence_id
                permanence_field.choices = [(o.id, o) for o in Permanence.objects.filter(
                    id=permanence_id
                ).order_by('?')]
            else:
                permanence_field.choices = [
                    ('-1', _("Please select first a permanence in the filter of previous screen"))]
                permanence_field.disabled = True

            if len(delivery_field.choices) == 0:
                delivery_field.required = False

            if purchase is not None:
                permanence_field.empty_label = None
                permanence_field.queryset = Permanence.objects \
                    .filter(id=permanence_id)
                customer_field.empty_label = None
                customer_field.queryset = Customer.objects \
                    .filter(id=customer_id)
                product_field.empty_label = None
                product_field.choices = [(o.id, str(o)) for o in OfferItemWoReceiver.objects.filter(
                    id=purchase.offer_item_id,
                    translations__language_code=translation.get_language()
                ).order_by('translations__long_name')]
            else:
                if permanence_id is not None:
                    if customer_id is not None:
                        customer_field.empty_label = None
                        customer_field.queryset = Customer.objects.filter(id=customer_id, is_active=True,
                                                                          may_order=True)
                        purchased_product = Product.objects.filter(
                            offeritem__permanence_id=permanence_id,
                            offeritem__purchase__customer_id=customer_id
                        ).order_by('?')
                        qs = Product.objects.filter(
                            producer__permanence=permanence_id,
                            is_into_offer=True,
                            translations__language_code=translation.get_language()
                        ).order_by('translations__long_name')
                        if self.producer_id is not None:
                            qs = qs.filter(
                                producer_id=self.producer_id
                            )
                        if customer_id is not None and purchased_product.exists():
                            qs = qs.exclude(
                                id__in=purchased_product
                            )
                        product_field.choices = [(o.id, "{}".format(o)) for o in qs.distinct()]
                        if len(product_field.choices) == 0:
                            product_field.choices = [
                                ('-2', _("No more product to add. Please update a product of previous screen"))]
                            product_field.disabled = True
                    else:
                        customer_field.choices = [
                            ('-1', _("Please select first a customer in the filter of previous screen"))]
                        customer_field.disabled = True
                        product_field.choices = []
                else:
                    customer_field.choices = []
                    product_field.choices = []
        return form

    @transaction.atomic
    def save_model(self, request, purchase, form, change):
        status = None
        delivery = None
        if "delivery" in form.fields:
            delivery_id = form.cleaned_data.get("delivery")
            if delivery_id != EMPTY_STRING:
                delivery = DeliveryBoard.objects.filter(id=delivery_id).only('status').order_by('?').first()
                if delivery is not None:
                    status = delivery.status
        if status is None:
            status = purchase.permanence.status

        if status <= PERMANENCE_SEND:
            # Forbidden to change invoiced permanence
            product_or_offer_item_id = form.cleaned_data.get("product")
            if purchase.id is not None:
                # Update : product_or_offer_item_id is an offer_item_id
                offer_item = OfferItem.objects.filter(id=product_or_offer_item_id,
                                                      permanence_id=purchase.permanence_id).order_by('?').first()
            else:
                # New : product_or_offer_item_id is a product_id
                product = Product.objects.filter(id=product_or_offer_item_id).order_by('?').first()
                offer_item = product.get_or_create_offer_item(purchase.permanence)
                # Select one purchase
                previous_purchase = Purchase.objects.filter(
                    customer=purchase.customer,
                    offer_item=offer_item,
                    is_box_content=False
                ).order_by('?')
                if previous_purchase.exists():
                    # add to it
                    previous_purchase = previous_purchase.first()
                    purchase.id = previous_purchase.id
                    if status != PERMANENCE_SEND:
                        purchase.quantity_ordered += previous_purchase.quantity_ordered
                    else:
                        purchase.quantity_invoiced += previous_purchase.quantity_invoiced
            if offer_item is not None:
                purchase.offer_item = offer_item
                purchase.status = status
                purchase.producer = offer_item.producer
                purchase.permanence.producers.add(offer_item.producer)
                purchase.save()
                purchase.save_box()
                # The customer_invoice may be created with "purchase.save()"
                customer_invoice = CustomerInvoice.objects.filter(
                    customer_id=purchase.customer_id,
                    permanence_id=purchase.permanence_id
                ).order_by('?').first()
                customer_invoice.status = status
                customer_invoice.set_delivery(delivery)
                customer_invoice.confirm_order()
                customer_invoice.save()

    def get_actions(self, request):
        actions = super(PurchaseAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (CSV, ODS, JSON, XLS, XLSX_OPENPYXL_1_8_6) if f().can_import()]

    class Media:
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            js = ('js/is_order_confirm_send.js',)
