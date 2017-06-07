# -*- coding: utf-8
from __future__ import unicode_literals

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from django.conf import settings
from repanier.const import *
# Filters in the right sidebar of the change list page of the admin
from django.contrib.admin import SimpleListFilter

from repanier.models import Producer, Product, LUT_DepartmentForCustomer, Customer, CustomerInvoice, ProducerInvoice, \
    Permanence, LUT_ProductionMode
from repanier.tools import sint


class ProductFilterByProducer(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar.
    title = _("producers")
    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'producer'
    template = 'admin/producer_filter.html'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        # This list is a collection of producer.id, .name
        return [(c.id, c.short_profile_name) for c in
                Producer.objects.filter(is_active=True)
                ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # This query set is a collection of products
        if self.value():
            return queryset.filter(producer_id=self.value())
        else:
            return queryset


class ProductFilterByDepartmentForThisProducer(SimpleListFilter):
    title = _("departments for customer")
    parameter_name = 'department_for_customer'
    template = 'admin/department_filter.html'

    def lookups(self, request, model_admin):
        producer_id = request.GET.get('producer')
        if producer_id:
            inner_qs = Product.objects.filter(is_active=True, producer_id=producer_id).order_by().distinct(
                'department_for_customer__id')
        else:
            permanence_id = request.GET.get('permanence')
            if permanence_id:
                inner_qs = Product.objects.filter(offeritem__permanence_id=permanence_id).order_by().distinct(
                    'department_for_customer__id')
            else:
                inner_qs = Product.objects.filter(is_active=True).order_by().distinct(
                    'department_for_customer__id')

        return [(d.id, d.short_name) for d in
                LUT_DepartmentForCustomer.objects.filter(is_active=True, product__in=inner_qs)
                ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department_for_customer_id=self.value())
        else:
            return queryset


class ProductFilterByProductioMode(SimpleListFilter):
    title = _("production modes")
    parameter_name = 'production_mode'
    template = 'admin/production_mode_filter.html'

    def lookups(self, request, model_admin):
        return [(p.id, p.short_name) for p in
                LUT_ProductionMode.objects.filter(is_active=True)
                ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(production_mode=self.value())
        else:
            return queryset


class ProductFilterByPlacement(SimpleListFilter):
    title = _("product_placement")
    parameter_name = 'placement'
    template = 'admin/placement_filter.html'

    def lookups(self, request, model_admin):
        return [(p[0], p[1]) for p in
                LUT_PRODUCT_PLACEMENT
                ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(placement=self.value())
        else:
            return queryset


class ProductFilterByVatLevel(SimpleListFilter):
    title = _("vat")
    parameter_name = 'vat_level'
    template = 'admin/vat_level_filter.html'

    def lookups(self, request, model_admin):
        return [(p[0], p[1]) for p in
                LUT_ALL_VAT  # settings.LUT_VAT
                ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(vat_level=self.value())
        else:
            return queryset


class PurchaseFilterByCustomer(SimpleListFilter):
    title = _("customer")
    parameter_name = 'customer'
    template = 'admin/customer_filter.html'

    def lookups(self, request, model_admin):
        permanence_id = request.GET.get('permanence', None)
        list_filter = []
        for c in Customer.objects.filter(may_order=True):
            ci = CustomerInvoice.objects.filter(permanence_id=permanence_id, customer_id=c.id).order_by('?').first()
            if ci is not None:
                if ci.is_order_confirm_send:
                    list_filter.append(
                        (c.id, "%s (%s) %s" % (c.short_basket_name, ci.get_total_price_with_tax(), LOCK_UNICODE)))
                else:
                    list_filter.append((c.id, "%s (%s)" % (c.short_basket_name, ci.total_price_with_tax,)))
            else:
                list_filter.append((c.id, c.short_basket_name))
        return list_filter

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(customer_id=self.value())
        else:
            return queryset


class PurchaseFilterByProducerForThisPermanence(SimpleListFilter):
    title = _("producers")
    parameter_name = 'producer'
    template = 'admin/producer_filter.html'

    def lookups(self, request, model_admin):
        permanence_id = request.GET.get('permanence', None)
        list_filter = []
        for p in Producer.objects.filter(permanence=permanence_id):
            pi = ProducerInvoice.objects.filter(permanence_id=permanence_id, producer_id=p.id).order_by('?').first()
            if pi is not None:
                list_filter.append((p.id, "%s (%s)" % (p.short_profile_name, pi.total_price_with_tax,)))
            else:
                list_filter.append((p.id, p.short_profile_name))
        return list_filter

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(producer_id=self.value())
        else:
            return queryset


class PurchaseFilterByPermanence(SimpleListFilter):
    title = _("permanence")
    parameter_name = 'permanence'

    def lookups(self, request, model_admin):
        permanence_id = request.GET.get('permanence', None)
        if permanence_id is None:
            return [(p.id, p.get_permanence_display()) for p in
                    Permanence.objects.filter(status__in=[PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND])
                    ]
        else:
            return []

    def queryset(self, request, queryset):
        if self.value():
            permanence_id = sint(self.value(), 0)
            if permanence_id > 0:
                return queryset.filter(permanence_id=permanence_id)
        return queryset


class OfferItemSendFilterByPermanence(SimpleListFilter):
    title = _("permanence")
    parameter_name = 'permanence'

    def lookups(self, request, model_admin):
        return [(p.id, p.get_permanence_display()) for p in
                Permanence.objects.filter(status=PERMANENCE_SEND)
                ]

    def queryset(self, request, queryset):
        if self.value():
            permanence_id = sint(self.value(), 0)
            if permanence_id > 0:
                return queryset.filter(permanence_id=permanence_id)
        else:
            return queryset.filter(permanence__status=PERMANENCE_SEND)
        return queryset


class OfferItemFilter(SimpleListFilter):
    title = _("products")
    parameter_name = 'is_filled_exact'

    def lookups(self, request, model_admin):
        return [(1, _('only invoiced')), ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.exclude(quantity_invoiced=DECIMAL_ZERO)
        else:
            return queryset


class BankAccountFilterByStatus(SimpleListFilter):
    title = _("status")
    parameter_name = 'is_filled_exact'

    def lookups(self, request, model_admin):
        return [
            (1, _('not invoiced')),
            (2, _('balance')),
            (3, _('loses and profits')),
            (4, _('taxes'))]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == "1":
                return queryset.filter(
                    Q(permanence_id__isnull=True, customer_id__isnull=False) |
                    Q(permanence_id__isnull=True, producer_id__isnull=False)
                )
            elif value == "2":
                return queryset.filter(permanence_id__isnull=False, customer_id__isnull=True, producer_id__isnull=True)
            elif value == "3":
                return queryset.filter(operation_status=BANK_PROFIT)
            else:
                return queryset.filter(operation_status=BANK_TAX)

        else:
            return queryset