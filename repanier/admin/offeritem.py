# -*- coding: utf-8

from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _

from repanier.admin.admin_filter import PurchaseFilterByProducerForThisPermanence, \
    ProductFilterByDepartmentForThisProducer, OfferItemFilter
from repanier.const import PERMANENCE_CLOSED, PERMANENCE_OPENED, ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.tools import sint, update_offer_item


class OfferItemClosedDataForm(forms.ModelForm):
    producer_qty_stock_invoiced = forms.CharField(
        label=_("Quantity invoiced by the producer"), required=False, initial=0)

    def __init__(self, *args, **kwargs):
        super(OfferItemClosedDataForm, self).__init__(*args, **kwargs)
        offer_item = self.instance
        self.fields["producer_qty_stock_invoiced"].initial = strip_tags(
            offer_item.get_html_producer_qty_stock_invoiced())
        self.fields["producer_qty_stock_invoiced"].widget.attrs['readonly'] = True
        self.fields["producer_qty_stock_invoiced"].disabled = True

    def get_readonly_fields(self, request, obj=None):
        return ['qty_invoiced', ]


class OfferItemClosedAdmin(admin.ModelAdmin):
    form = OfferItemClosedDataForm
    search_fields = ('translations__long_name',)
    list_display = ['get_html_long_name_with_producer',]
    list_display_links = ('get_html_long_name_with_producer',)
    list_filter = (
        PurchaseFilterByProducerForThisPermanence,
        OfferItemFilter,
        ProductFilterByDepartmentForThisProducer,
    )
    list_select_related = ('producer', 'department_for_customer')
    list_per_page = 13
    list_max_show_all = 13
    ordering = ('translations__long_name',)

    def get_queryset(self, request):
        qs = super(OfferItemClosedAdmin, self).get_queryset(request)
        return qs.filter(
            translations__language_code=translation.get_language()
        ).distinct()

    def get_list_display(self, request):
        producer_id = sint(request.GET.get('producer', 0))
        if producer_id != 0:
            producer_queryset = Producer.objects.filter(id=producer_id).order_by('?')
            producer = producer_queryset.first()
        else:
            producer = None
        permanence_id = sint(request.GET.get('permanence', 0))
        permanence_open = False
        permanence = Permanence.objects.filter(id=permanence_id, status=PERMANENCE_OPENED).order_by('?')
        if permanence.exists():
            permanence_open = True
        if producer is not None:
            if settings.DJANGO_SETTINGS_STOCK:
                self.list_editable = ('stock',)
                if producer.manage_replenishment and not permanence_open:
                    return ('department_for_customer', 'get_html_long_name_with_producer',
                            'stock',
                            'get_html_producer_qty_stock_invoiced',
                            'add_2_stock')
                else:
                    return ('department_for_customer', 'get_html_long_name_with_producer',
                            'stock',
                            'get_html_producer_qty_stock_invoiced')
            else:
                return ('department_for_customer', 'get_html_long_name_with_producer',
                        'get_html_producer_qty_stock_invoiced')
        else:
            return ('department_for_customer', 'get_html_long_name_with_producer',
                    'get_html_producer_qty_stock_invoiced')

    def get_form(self, request, offer_item=None, **kwargs):
        if offer_item.manage_replenishment:
            if offer_item.permanence.status == PERMANENCE_CLOSED:
                fields_basic = [
                    ('permanence', 'department_for_customer', 'product'),
                    ('stock', 'producer_qty_stock_invoiced', 'add_2_stock',)
                ]
            else:
                fields_basic = [
                    ('permanence', 'department_for_customer', 'product'),
                    ('stock', 'producer_qty_stock_invoiced',)
                ]
        else:
            fields_basic = [
                ('permanence', 'department_for_customer', 'product'),
                ('producer_qty_stock_invoiced',)
            ]
        self.fieldsets = (
            (None, {'fields': fields_basic}),
        )

        form = super(OfferItemClosedAdmin, self).get_form(request, offer_item, **kwargs)
        permanence_field = form.base_fields["permanence"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.empty_label = None
        department_for_customer_field.empty_label = None
        product_field.empty_label = None

        permanence_field.queryset = Permanence.objects \
            .filter(id=offer_item.permanence_id)
        department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects \
            .filter(id=offer_item.department_for_customer_id)
        product_field.queryset = Product.objects \
            .filter(id=offer_item.product_id)
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def get_actions(self, request):
        actions = super(OfferItemClosedAdmin, self).get_actions(request)
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

    def save_model(self, request, offer_item, form, change):
        super(OfferItemClosedAdmin, self).save_model(
            request, offer_item, form, change)
        if offer_item.product_id is not None:
            offer_item.product.stock = offer_item.stock
            offer_item.product.save(update_fields=['stock'])
            update_offer_item(product_id=offer_item.product_id)
