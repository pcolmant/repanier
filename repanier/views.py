# -*- coding: utf-8 -*-
import json
import datetime

from django.utils.timezone import utc
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslationDoesNotExist
from django.utils import translation

from tools import *

# from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.views.generic import DetailView

from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django.template import RequestContext

from models import LUT_DepartmentForCustomer
from models import OfferItem
from models import Permanence
from models import Producer
from models import ProducerInvoice
from models import Purchase
from models import Customer
from models import CustomerInvoice
from models import Staff
from models import BankAccount
from models import PermanenceBoard
from forms import ContactForm

import logging

logger = logging.getLogger(__name__)


def render_response(req, *args, **kwargs):
    # For csrf :  http://lincolnloop.com/blog/2008/may/10/getting-requestcontext-your-templates/
    kwargs['context_instance'] = RequestContext(req)
    # print(RequestContext(req))
    return render_to_response(*args, **kwargs)


@login_required()
def contact_form(request):
    if request.method == 'POST':  # If the form has been submitted...
        form = ContactForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            return HttpResponseRedirect('/')  # Redirect after POST
    else:
        form = ContactForm()  # An unbound form

    return render_response(request, "repanier/contact_form.html", {'form': form})

# import sys
# import traceback

@login_required()
# @never_cache
def product_form_ajax(request):
    if request.is_ajax():
        if request.method == 'GET':
            result = "-"
            p_offer_item_id = None
            if 'offer_item' in request.GET:
                p_offer_item_id = request.GET['offer_item']
            if p_offer_item_id:
                offer_item = OfferItem.objects.get(id=p_offer_item_id)
                if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
                    try:
                        result = offer_item.product.offer_description
                        if result is None or result == "":
                            result = _("There is no more product's information")
                    except TranslationDoesNotExist:
                        result = ""
                    # except:
                    #     exc_type, exc_value, exc_traceback = sys.exc_info()
                    #     lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    #     print ''.join('!! ' + line for line in lines)
            return HttpResponse(result)
    # Not an AJAX, GET request
    return HttpResponseRedirect('/')


@login_required()
# @never_cache
def order_form_ajax(request):
    if request.is_ajax():
        if request.method == 'GET':
            result = "ko"
            p_offer_item_id = None
            if 'offer_item' in request.GET:
                p_offer_item_id = request.GET['offer_item']
            p_value_id = None
            if 'value' in request.GET:
                p_value_id = request.GET['value']
            if p_offer_item_id and p_value_id:
                result = update_or_create_purchase(
                    user=request.user, p_offer_item_id=p_offer_item_id,
                    p_value_id=p_value_id
                )
            return HttpResponse(result)
    # Not an AJAX, GET request
    return HttpResponseRedirect('/')


@login_required()
@never_cache
def ajax_order_select(request):
    # if request.is_ajax():
    if request.method == 'GET':
        # construct a list which will contain all of the data for the response
        to_json = []
        if 'offer_item' in request.GET:
            p_offer_item_id = request.GET['offer_item']
            user = request.user
            customer = Customer.objects.filter(
                user_id=user.id, is_active=True, may_order=True).order_by().first()
            if customer:
                # The user is an active customer
                offer_item = OfferItem.objects.get(id=p_offer_item_id)
                if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
                    # The offer_item belong to a open permanence
                    q_order = 0
                    q_average_weight = offer_item.product.order_average_weight
                    purchase = Purchase.objects.filter(product_id=offer_item.product_id,
                                                       permanence_id=offer_item.permanence_id,
                                                       customer_id=customer.id).order_by().first()
                    if purchase:
                        q_order = purchase.quantity if purchase.permanence.status < PERMANENCE_SEND else purchase.quantity_send_to_producer
                    # The q_order is either the purchased quantity or 0
                    q_min = offer_item.product.customer_minimum_order_quantity
                    # Limit to available qty
                    q_alert = offer_item.customer_alert_order_quantity + q_order if offer_item.limit_to_alert_order_quantity else offer_item.product.customer_alert_order_quantity
                    q_step = offer_item.product.customer_increment_order_quantity
                    # The q_min cannot be 0. In this case try to replace q_min by q_step.
                    # In last resort by q_alert.

                    q_order_is_displayed = False
                    if q_step <= 0:
                        q_step = q_min
                    if q_min <= 0:
                        q_min = q_step
                    if q_min <= 0:
                        q_min = q_alert
                        q_step = q_alert
                    if q_min <= 0 and offer_item.permanence.status == PERMANENCE_OPENED:
                        option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                        to_json.append(option_dict)
                    else:
                        q_select_id = 0
                        selected = ""
                        if q_order <= 0:
                            q_order_is_displayed = True
                            selected = "selected"
                        if (offer_item.permanence.status == PERMANENCE_OPENED or
                                (PERMANENCE_SEND <= offer_item.permanence.status and selected == "selected")):
                            option_dict = {'value': '0', 'selected': selected, 'label': '---'}
                            to_json.append(option_dict)

                        q_valid = q_min
                        q_counter = 0  # Limit to avoid too long selection list
                        while q_valid <= q_alert and q_counter <= 20:
                            q_select_id += 1
                            q_counter += 1
                            selected = ""
                            if not q_order_is_displayed:
                                if q_order <= q_valid:
                                    q_order_is_displayed = True
                                    selected = "selected"
                            if (offer_item.permanence.status == PERMANENCE_OPENED or
                                    (PERMANENCE_SEND <= offer_item.permanence.status and selected == "selected")):
                                qty_display = get_qty_display(
                                    q_valid,
                                    q_average_weight,
                                    offer_item.product.order_unit
                                )
                                option_dict = {'value': str(q_select_id), 'selected': selected, 'label': qty_display}
                                to_json.append(option_dict)
                            if q_valid < q_step:
                                # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                                # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                                q_valid = q_step
                            else:
                                # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                                # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                                q_valid = q_valid + q_step

                        if not q_order_is_displayed:
                            # An custom order_qty > q_alert
                            q_select_id += 1
                            selected = "selected"
                            qty_display = get_qty_display(
                                q_order,
                                q_average_weight,
                                offer_item.product.order_unit
                            )
                            option_dict = {'value': str(q_select_id), 'selected': selected, 'label': qty_display}
                            to_json.append(option_dict)
                        if offer_item.permanence.status == PERMANENCE_OPENED:
                            option_dict = {'value': 'other_qty', 'selected': '', 'label': unicode(_("Other qty"))}
                            to_json.append(option_dict)

        return HttpResponse(json.dumps(to_json), content_type="application/json")
    # Not an AJAX, GET request
    return HttpResponseRedirect('/')


class OrderView(ListView):
    template_name = 'repanier/order_form.html'
    success_url = '/thanks/'
    paginate_by = 50
    paginate_orphans = 5

    # def get_urls(self):
    # my_urls = patterns('',
    # url(r'^purchase_update/$', self.update, name='sortable_update'),
    # )
    # return my_urls + super(SortableAdminMixin, self).get_urls()

    def __init__(self, **kwargs):
        super(OrderView, self).__init__(**kwargs)
        self.user = None
        self.offeritem_id = 'all'
        self.producer_id = 'all'
        self.departementforcustomer_id = 'all'

    def dispatch(self, request, *args, **kwargs):
        self.user = request.user
        self.offeritem_id = 'all'
        if self.request.GET.get('offeritem'):
            self.offeritem_id = self.request.GET['offeritem']
        self.producer_id = 'all'
        if self.request.GET.get('producer'):
            self.producer_id = self.request.GET['producer']
        self.departementforcustomer_id = 'all'
        if self.request.GET.get('departementforcustomer'):
            self.departementforcustomer_id = self.request.GET['departementforcustomer']
        return super(OrderView, self).dispatch(request, *args, **kwargs)

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        # Here via a form or via Ajax we modifiy the qty
        p_offer_item_id = None
        if 'offer_item' in request.GET:
            p_offer_item_id = request.GET['offer_item']
        p_value_id = None
        if 'value' in request.GET:
            p_value_id = request.GET['value']
        if p_offer_item_id and p_value_id:
            update_or_create_purchase(
                user=request.user, p_offer_item_id=p_offer_item_id,
                p_value_id=p_value_id
            )
        return super(OrderView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)
        if self.permanence:
            try:
                offer_description = self.permanence.offer_description
            except TranslationDoesNotExist:
                offer_description = ""
            context['permanence_offer_description'] = offer_description
            if self.permanence.status == PERMANENCE_OPENED:
                context['display_all_product_button'] = "Ok"
            producer_set = Producer.objects.filter(permanence=self.permanence.id)
            context['producer_set'] = producer_set
            context['producer_id'] = self.producer_id
            if self.producer_id == 'all':
                departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                    product__offeritem__permanence_id=self.permanence.id
                ).distinct()
            else:
                departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                    product__producer_id=self.producer_id,
                    product__offeritem__permanence_id=self.permanence.id
                ).distinct()
            context['departementforcustomer_set'] = departementforcustomer_set
            context['departementforcustomer_id'] = self.departementforcustomer_id
            context['offeritem_id'] = self.offeritem_id
            context['prepared_amount'] = get_user_order_amount(self.permanence,
                                                               user=self.user)  # + ' &euro; <span class="glyphicon glyphicon-shopping-cart"></span>'
            context['staff_order'] = Staff.objects.filter(is_reply_to_order_email=True).order_by().first()
        return context

    def get_queryset(self):
        self.permanence = get_object_or_404(Permanence, id=self.args[0])
        qs = OfferItem.objects.none()
        if PERMANENCE_OPENED <= self.permanence.status <= PERMANENCE_SEND:
            qs = OfferItem.objects.filter(permanence_id=self.permanence.id, is_active=True)
            if self.permanence.status == PERMANENCE_OPENED:
                # Don't display technical products.
                qs = qs.filter(product__order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT)
            if self.producer_id != 'all':
                qs = qs.filter(product__producer=self.producer_id)
            if self.offeritem_id != 'all' or self.permanence.status == PERMANENCE_SEND:
                # if asked or if status is close or send, then display only purchased product
                qs = qs.filter(product__purchase__permanence=self.permanence.id,
                               product__purchase__customer__user=self.user)
            if self.departementforcustomer_id != 'all':
                qs = qs.filter(product__department_for_customer=self.departementforcustomer_id)
            qs = qs.filter(product__translations__language_code=translation.get_language(),
                           product__department_for_customer__translations__language_code=translation.get_language()
            ).order_by(
                'product__department_for_customer__translations__short_name', 'product__translations__long_name'
            )
            # print("---------------")
            # print qs.query
            # print("---------------")
        else:
            self.permanence = None
        return qs


@login_required()
# @never_cache
def permanence_form_ajax(request):
    if request.is_ajax():
        if request.method == 'GET':
            result = "ko"
            p_permanence_board_id = None
            if 'permanence_board' in request.GET:
                p_permanence_board_id = request.GET['permanence_board']
            p_value_id = None
            if 'value' in request.GET:
                p_value_id = request.GET['value']
            if p_permanence_board_id and p_value_id and request.user.customer.may_order:
                if p_value_id == '0':
                    row_counter = PermanenceBoard.objects.filter(
                        id=p_permanence_board_id,
                        customer_id=request.user.customer.id,
                        permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                    ).update(
                        customer=None
                    )
                else:
                    row_counter = PermanenceBoard.objects.filter(
                        id=p_permanence_board_id,
                        customer__isnull=True,
                        permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                    ).update(
                        customer=request.user.customer.id
                    )
                if row_counter > 0:
                    result = "ok"
            return HttpResponse(result)
    # Not an AJAX, GET request
    return HttpResponseRedirect('/')


class PermanenceView(ListView):
    template_name = 'repanier/permanence_form.html'
    success_url = '/thanks/'
    paginate_by = 50
    paginate_orphans = 5

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        # Here via a form or via Ajax we modifiy the qty
        p_permanence_board_id = None
        if 'permanence_board' in request.GET:
            p_permanence_board_id = request.GET['permanence_board']
        p_value_id = None
        if 'value' in request.GET:
            p_value_id = request.GET['value']
        if p_permanence_board_id and p_value_id and request.user.customer.may_order:
            if p_value_id == '0':
                PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer_id=request.user.customer.id,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                ).update(
                    customer=None
                )
            else:
                PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer__isnull=True,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                ).update(
                    customer=request.user.customer.id
                )
        return super(PermanenceView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        qs = PermanenceBoard.objects.filter(
            distribution_date__gte=now,
            permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
        ).order_by(
            "distribution_date", "permanence", "permanence_role"
        )
        return qs


class InvoiceView(DetailView):
    template_name = 'repanier/invoice_form.html'
    model = CustomerInvoice

    def get_context_data(self, **kwargs):
        context = super(InvoiceView, self).get_context_data(**kwargs)
        customer_invoice = self.get_object()
        if customer_invoice:
            bank_account_set = BankAccount.objects.filter(is_recorded_on_customer_invoice=customer_invoice)
            context['bank_account_set'] = bank_account_set
            purchase_set = Purchase.objects.filter(is_recorded_on_customer_invoice=customer_invoice)
            context['purchase_set'] = purchase_set
            previous_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_invoice.customer_id,
                                                                           id__lt=customer_invoice.id).order_by('-id')[
                                            :1]
            if previous_customer_invoice_set:
                context['previous_customer_invoice_id'] = previous_customer_invoice_set[0].id
            next_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_invoice.customer_id,
                                                                       id__gt=customer_invoice.id).order_by('id')[:1]
            if next_customer_invoice_set:
                context['next_customer_invoice_id'] = next_customer_invoice_set[0].id
        return context

    def get_queryset(self):
        # qs = CustomerInvoice.objects.none()
        pk = self.kwargs.get('pk', None)
        if self.request.user.is_staff:
            customer_id = self.request.GET.get('customer', None)
            if (pk is None) or (pk == '0'):
                last_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_id).order_by('-id')[:1]
                if last_customer_invoice_set:
                    self.kwargs['pk'] = last_customer_invoice_set[0].id
            return CustomerInvoice.objects.all()
        else:
            if (pk is None) or (pk == '0'):
                last_customer_invoice_set = CustomerInvoice.objects.filter(
                    customer__user_id=self.request.user.id).order_by('-id')[:1]
                if last_customer_invoice_set:
                    self.kwargs['pk'] = last_customer_invoice_set[0].id

            return CustomerInvoice.objects.filter(customer__user_id=self.request.user.id)


class InvoicePView(DetailView):
    template_name = 'repanier/invoicep_form.html'
    model = ProducerInvoice
    uuid = None

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        return super(InvoicePView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(InvoicePView, self).get_context_data(**kwargs)
        producer_invoice = self.get_object()
        if producer_invoice:
            bank_account_set = BankAccount.objects.filter(is_recorded_on_producer_invoice=producer_invoice)
            context['bank_account_set'] = bank_account_set
            purchase_set = Purchase.objects.filter(is_recorded_on_producer_invoice=producer_invoice)
            context['purchase_set'] = purchase_set
            previous_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_invoice.producer.id,
                                                                           id__lt=producer_invoice.id).order_by('-id')[
                                            :1]
            if previous_producer_invoice_set:
                context['previous_producer_invoice_id'] = previous_producer_invoice_set[0].id
            next_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_invoice.producer.id,
                                                                       id__gt=producer_invoice.id).order_by('id')[:1]
            if next_producer_invoice_set:
                context['next_producer_invoice_id'] = next_producer_invoice_set[0].id
            context['uuid'] = self.uuid
        return context

    def get_queryset(self):
        # qs = producerInvoice.objects.none()
        self.uuid = None
        if self.request.user.is_staff:
            producer_id = self.request.GET.get('producer', None)
        else:
            self.uuid = self.kwargs.get('uuid', None)
            if self.uuid:
                try:
                    producer = Producer.objects.get(uuid=self.uuid)
                    producer_id = producer.id
                except:
                    raise PermissionDenied
            else:
                return ProducerInvoice.objects.none()
        pk = self.kwargs.get('pk', None)
        if (pk is None) or (pk == '0'):
            last_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_id).order_by('-id')[:1]
            if last_producer_invoice_set:
                self.kwargs['pk'] = last_producer_invoice_set[0].id
        return ProducerInvoice.objects.filter(producer_id=producer_id)
