# -*- coding: utf-8
from __future__ import unicode_literals

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.views.generic import ListView

import repanier.apps
from repanier.const import PERMANENCE_OPENED, EMPTY_STRING, PRODUCT_ORDER_UNIT_DEPOSIT
from repanier.models import Permanence, Producer, LUT_DepartmentForCustomer, OfferItem, Staff, BoxContent
from repanier.tools import sint, permanence_ok_or_404, html_box_content


class OrderView(ListView):
    template_name = 'repanier/order_form.html'
    success_url = '/'
    paginate_by = 28
    paginate_orphans = 6

    def __init__(self, **kwargs):
        super(OrderView, self).__init__(**kwargs)
        self.user = None
        self.producer_id = 'all'
        self.departementforcustomer_id = 'all'
        self.box_id = 'all'
        self.is_box = False
        self.communication = 0
        self.q = None
        self.basket = None
        self.like = None
        self.is_anonymous = None
        self.may_order = None
        self.permanence = None
        self.delivery_id = 0

    def dispatch(self, request, *args, **kwargs):
        permanence_id = sint(kwargs.get('permanence_id', 0))
        self.permanence = Permanence.objects.filter(id=permanence_id).only("id", "status", "permanence_date",
                                                                           "with_delivery_point").order_by('?').first()
        permanence_ok_or_404(self.permanence)
        self.user = request.user
        self.basket = kwargs.get('basket', False)
        if not self.basket:
            self.like = kwargs.get('like', False)
        else:
            # Not both favorite and basket
            self.like = False
        if self.permanence.with_delivery_point:
            self.delivery_id = sint(kwargs.get('delivery_id', 0))
        if self.user.is_anonymous() or self.user.is_staff:
            self.is_anonymous = True
            self.may_order = False
            self.q = None
        else:
            self.is_anonymous = False
            customer = self.user.customer
            self.may_order = customer.may_order if customer is not None else False
            self.q = self.request.GET.get('q', None)
            if self.q == EMPTY_STRING:
                self.q = None
        self.producer_id = self.request.GET.get('producer', 'all')
        if self.producer_id != 'all':
            self.producer_id = sint(self.producer_id)
        self.departementforcustomer_id = self.request.GET.get('departementforcustomer', 'all')
        if self.departementforcustomer_id != 'all':
            self.departementforcustomer_id = sint(self.departementforcustomer_id)
        self.box_id = self.request.GET.get('box', 'all')
        if self.box_id != 'all':
            self.box_id = sint(self.box_id)
            self.is_box = True
            # Do not display "all department" as selected
            self.departementforcustomer_id = None
        else:
            self.is_box = False
        if self.producer_id == 'all' and self.departementforcustomer_id == 'all' \
                and not self.basket and 'page' not in request.GET \
                and self.q is None:
            # This to let display a communication into a popup when the user is on the first order screen
            self.communication = True
        else:
            self.communication = False
        return super(OrderView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)
        context['permanence'] = self.permanence
        if self.permanence.status == PERMANENCE_OPENED:
            context['display_all_product_button'] = "Ok"
        context['delivery_id'] = self.delivery_id
        from repanier.apps import REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM
        if REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM:
            producer_set = Producer.objects.filter(permanence=self.permanence.id).only("id", "short_profile_name")
        else:
            producer_set = None
        context['producer_set'] = producer_set
        # use of str() to avoid "12 345" when rendering the template
        context['producer_id'] = str(self.producer_id)
        if self.producer_id == 'all':
            departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                offeritem__permanence_id=self.permanence.id,
                offeritem__is_active=True,
                offeritem__is_box=False) \
                .order_by("tree_id", "lft") \
                .distinct("id", "tree_id", "lft")
        else:
            departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                offeritem__producer_id=self.producer_id,
                offeritem__permanence_id=self.permanence.id,
                offeritem__is_active=True,
                offeritem__is_box=False) \
                .order_by("tree_id", "lft") \
                .distinct("id", "tree_id", "lft")
        context['departementforcustomer_set'] = departementforcustomer_set
        # use of str() to avoid "12 345" when rendering the template
        context['departementforcustomer_id'] = str(self.departementforcustomer_id)
        context['box_set'] = OfferItem.objects.filter(
            permanence_id=self.permanence.id,
            is_box=True,
            is_active=True,
            may_order=True,
            translations__language_code=translation.get_language()
        ).order_by(
            'customer_unit_price',
            'unit_deposit',
            'translations__long_name',
        )
        context['box_id'] = str(self.box_id)
        context['box'] = self.is_box
        if self.is_box:
            html = EMPTY_STRING
            offer_item = get_object_or_404(OfferItem, id=self.box_id)
            context['box_description']=html_box_content(offer_item, self.user, html)
        context['basket'] = self.basket
        context['like'] = self.like
        context['staff_order'] = Staff.objects.filter(
            is_reply_to_order_email=True) \
            .only("customer_responsible__long_basket_name", "customer_responsible__phone1",
                  "user__email") \
            .order_by('?').first()
        context['communication'] = self.communication
        context['q'] = self.q
        context['is_anonymous'] = self.is_anonymous
        context['may_order'] = self.may_order
        return context

    def get_queryset(self):
        from repanier.apps import REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM
        if self.is_anonymous and \
                (not REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM or self.basket or self.like):
            return OfferItem.objects.none()
        else:
            if self.is_box:
                offer_item = OfferItem.objects.filter(
                    id=self.box_id,
                    permanence_id=self.permanence.id, is_active=True,
                ).order_by('?').only("product").first()
                if offer_item is not None:
                    box_id = offer_item.product
                else:
                    # Gogglebot is back
                    raise Http404
                product_ids = BoxContent.objects.filter(
                    box_id=box_id
                ).only("product_id")
                qs = OfferItem.objects.filter(
                    Q(
                        permanence_id=self.permanence.id, # is_active=True,
                        product=box_id,
                        translations__language_code=translation.get_language()
                    ) |
                    Q(
                        permanence_id=self.permanence.id, # is_active=True,
                        product__box_content__in=product_ids,
                        translations__language_code=translation.get_language()
                    )
                ).order_by(
                    "translations__order_sort_order"
                )
            else:
                if self.basket:
                    qs = OfferItem.objects.filter(
                        permanence_id=self.permanence.id,
                        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                        purchase__customer__user=self.user,
                        purchase__quantity_ordered__gt=0,
                        is_box=False,
                        translations__language_code=translation.get_language()
                    ).order_by(
                        "translations__order_sort_order"
                    ).distinct()
                    if self.q is not None:
                        qs = qs.filter(
                            translations__long_name__icontains=self.q,
                            translations__language_code=translation.get_language()
                        )
                else:
                    qs = OfferItem.objects.filter(
                        Q(
                            permanence_id=self.permanence.id, is_active=True,
                            is_box=False,  # Don't display boxes -> Added from customers reactions.
                            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT  # Don't display technical products.
                        ) | Q(
                            permanence_id=self.permanence.id, is_box_content=True,
                            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT  # Don't display technical products.
                        )
                    )
                    if self.producer_id != 'all':
                        qs = qs.filter(producer_id=self.producer_id)
                    if self.departementforcustomer_id != 'all':
                        department = LUT_DepartmentForCustomer.objects.filter(
                            id=self.departementforcustomer_id
                        ).order_by('?').only("lft", "rght", "tree_id").first()
                        if department is not None:
                            tmp_qs = qs.filter(department_for_customer__lft__gte=department.lft,
                                               department_for_customer__rght__lte=department.rght,
                                               department_for_customer__tree_id=department.tree_id)
                            if tmp_qs.exists():
                                # Restrict to this department only if no product exists in it
                                qs = tmp_qs
                            else:
                                # otherwise, act like self.departementforcustomer_id == 'all'
                                self.departementforcustomer_id = 'all'
                    qs = qs.filter(
                        translations__language_code=translation.get_language()
                    ).order_by(
                        "translations__order_sort_order"
                    )
                    if self.q is not None:
                        qs = qs.filter(
                            translations__long_name__icontains=self.q,
                            translations__language_code=translation.get_language()
                        )
        if self.like:
            qs = qs.filter(product__likes__id=self.user.id)
        return qs
