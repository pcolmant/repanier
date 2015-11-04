# -*- coding: utf-8
from __future__ import unicode_literals
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from const import *
from models import Customer
from models import LUT_DepartmentForCustomer
from models import Permanence
from models import Producer
from models import Product

# Filters in the right sidebar of the change list page of the admin
from django.contrib.admin import SimpleListFilter
from tools import sint


class ProductFilterByProducer(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar.
    title = _("producers")
    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'producer'

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

        return [(c.id, c.short_name) for c in
                LUT_DepartmentForCustomer.objects.filter(is_active=True, product__in=inner_qs)
        ]

    def queryset(self, request, queryset):
        # This query set is a collection of products
        if self.value():
            return queryset.filter(department_for_customer_id=self.value())
        else:
            return queryset


class PurchaseFilterByCustomerForThisPermanence(SimpleListFilter):
    title = _("customer")
    parameter_name = 'customer'

    def lookups(self, request, model_admin):
        permanence_id = request.GET.get('permanence')
        if permanence_id:
            permanence_id = sint(permanence_id, 0)
            if permanence_id >= 0:
                return [(c.id, c.short_basket_name) for c in
                        Customer.objects.filter(purchase__permanence_id=permanence_id).distinct()
                ]
            else:
                # This is a year
                return [(c.id, c.short_basket_name) for c in
                        Customer.objects.filter(purchase__permanence_date__year=-permanence_id).distinct()
                ]
        else:
            return [(c.id, c.short_basket_name) for c in
                    Customer.objects.filter(may_order=True)
            ]

    def queryset(self, request, queryset):
        # This query set is a collection of purchase
        if self.value():
            return queryset.filter(customer_id=self.value())
        else:
            return queryset


class PurchaseFilterByProducerForThisPermanence(SimpleListFilter):
    title = _("producer")
    parameter_name = 'producer'

    def lookups(self, request, model_admin):
        permanence_id = request.GET.get('permanence')
        if permanence_id:
            permanence_id = sint(permanence_id, 0)
            if permanence_id >= 0:
                return [(c.id, c.short_profile_name) for c in
                        Producer.objects.filter(permanence=permanence_id).distinct()
                ]
            else:
                # This is a year
                return [(c.id, c.short_profile_name) for c in
                        Producer.objects.filter(permanence__permanence_date__year=-permanence_id).distinct()
                ]
        else:
            return [(c.id, c.short_profile_name) for c in
                    Producer.objects.filter(is_active=True)
            ]

    def queryset(self, request, queryset):
        # This query set is a collection of purchase
        if self.value():
            return queryset.filter(producer_id=self.value())
        else:
            return queryset


class PurchaseFilterByPermanence(SimpleListFilter):
    title = _("permanence")
    parameter_name = 'permanence'

    def lookups(self, request, model_admin):
        # This list is a collection of permanence.id, .name
        if PERMANENCE_DONE in model_admin.permanence_status_list \
                or PERMANENCE_ARCHIVED in model_admin.permanence_status_list:
            this_year = timezone.now().year
            return [
                (-(this_year -i), str(this_year - i)) for i in xrange(10)
            ]
        else:
            return [(c.id, c.__str__()) for c in
                    Permanence.objects.filter(status__in=model_admin.permanence_status_list)
            ]

    def queryset(self, request, queryset):
        # This query set is a collection of purchase
        if self.value():
            permanence_id = sint(self.value(),0)
            if permanence_id >= 0:
                return queryset.filter(permanence_id=permanence_id)
            else:
                return queryset.filter(permanence_date__year=-permanence_id)
        else:
            return queryset


class OfferItemFilter(SimpleListFilter):
    title = _("products")
    parameter_name = 'is_filled_exact'

    def lookups(self, request, model_admin):
        # This list is a collection of offer_item.id, .name
        return [(1, _('only invoiced')),]

    def queryset(self, request, queryset):
        # This query set is a collection of offer_item
        if self.value():
            return queryset.exclude(quantity_invoiced=DECIMAL_ZERO)
        else:
            return queryset

class BankAccountFilterByPermanence(SimpleListFilter):
    title = _("permanence")
    parameter_name = 'is_filled_exact'

    def lookups(self, request, model_admin):
        # This list is a collection of bankaccount.id, .name
        return [(1, _('not invoiced')),]

    def queryset(self, request, queryset):
        # This query set is a collection of bankaccount
        if self.value():
            return queryset.filter(permanence_id__isnull=True)
        else:
            return queryset