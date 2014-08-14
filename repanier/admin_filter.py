# -*- coding: utf-8 -*-
from const import *

from django.utils.translation import ugettext_lazy as _
from repanier.models import Customer
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import Product

# Filters in the right sidebar of the change list page of the admin
from django.contrib.admin import SimpleListFilter


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
            return [(c.id, c.short_basket_name) for c in
                    Customer.objects.filter(purchase__permanence_id=permanence_id).distinct()
            ]
        else:
            return [(c.id, c.short_basket_name) for c in
                    Customer.objects.filter(may_order=True)
            ]

    def queryset(self, request, queryset):
        # This query set is a collection of permanence
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
            return [(c.id, c.short_profile_name) for c in
                    Producer.objects.filter(permanence=permanence_id).distinct()
            ]
        else:
            return [(c.id, c.short_profile_name) for c in
                    Producer.objects.filter(is_active=True)
            ]

    def queryset(self, request, queryset):
        # This query set is a collection of permanence
        if self.value():
            return queryset.filter(producer_id=self.value())
        else:
            return queryset


class PurchaseFilterByPermanence(SimpleListFilter):
    title = _("permanences")
    parameter_name = 'permanence'

    def lookups(self, request, model_admin):
        # This list is a collection of permanence.id, .name
        return [(c.id, c.__unicode__()) for c in
                Permanence.objects.filter(status__in=[PERMANENCE_OPENED, PERMANENCE_SEND])
        ]

    def queryset(self, request, queryset):
        # This query set is a collection of permanence
        if self.value():
            return queryset.filter(permanence_id=self.value())
        else:
            return queryset
