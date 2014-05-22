# -*- coding: utf-8 -*-
from const import *
from tools import *
from django.utils.translation import ugettext_lazy as _
import datetime
from django.utils.timezone import utc

from django.conf import settings
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.views.generic import DetailView
from django.utils.formats import number_format

from django.shortcuts import render
from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django.template import RequestContext

from repanier.models import LUT_DepartmentForCustomer
from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import Producer
from repanier.models import ProducerInvoice
from repanier.models import Purchase
from repanier.models import Customer
from repanier.models import CustomerInvoice
from repanier.models import BankAccount
from repanier.models import PermanenceBoard
from repanier.forms import ContactForm

import logging
logger = logging.getLogger(__name__)

def render_response(req, *args, **kwargs):
  # For csrf :  http://lincolnloop.com/blog/2008/may/10/getting-requestcontext-your-templates/
  kwargs['context_instance'] = RequestContext(req)
  # print(RequestContext(req))
  return render_to_response(*args, **kwargs)

@login_required()
def contact_form(request):
	if request.method == 'POST': # If the form has been submitted...
		form = ContactForm(request.POST) # A form bound to the POST data
		if form.is_valid(): # All validation rules pass
			# Process the data in form.cleaned_data
			# ...
			return HttpResponseRedirect('/') # Redirect after POST
	else:
		form = ContactForm() # An unbound form

	return render_response(request, "repanier/contact_form.html", {'form':form})


@login_required()
# @never_cache
def product_form_ajax(request):
  if request.is_ajax():
    if request.method == 'GET': 
      result = "-"
      p_offer_item_id = None
      if 'offer_item' in request.GET:
        p_offer_item_id = request.GET['offer_item']
      if p_offer_item_id :
        offer_item = OfferItem.objects.get(id=p_offer_item_id)
        if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
          result = offer_item.product.offer_description if offer_item.product.offer_description else unicode(_("There is no more product's information"))
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
      if p_offer_item_id and p_value_id :
        result = update_or_create_purchase(
          user=request.user, p_offer_item_id=p_offer_item_id,
          p_value_id=p_value_id
        )
      return HttpResponse(result)
  # Not an AJAX, GET request
  return HttpResponseRedirect('/')

class OrderView(ListView):

  template_name = 'repanier/order_form.html'
  success_url = '/thanks/'
  paginate_by = 50
  paginate_orphans = 5

  # def get_urls(self):
  #     my_urls = patterns('',
  #         url(r'^purchase_update/$', self.update, name='sortable_update'),
  #     )
  #     return my_urls + super(SortableAdminMixin, self).get_urls()

  def dispatch(self, request, *args, **kwargs):
    self.user = request.user
    self.offeritem_id = 'all'
    if self.request.GET.get('offeritem'):
      self.offeritem_id = self.request.GET['offeritem']
    self.producer_id = 'all'
    if self.request.GET.get('producer'):
      self.producer_id = self.request.GET['producer']
    self.departementforcusomer_id = 'all'
    if self.request.GET.get('departementforcusomer'):
      self.departementforcusomer_id = self.request.GET['departementforcusomer']
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
    context = super(OrderView,self).get_context_data(**kwargs)
    if self.permanence:
      context['permanence_offer_description'] = self.permanence.offer_description
      if self.permanence.status == PERMANENCE_OPENED:
        context['display_all_product_button'] = "Ok"
      producer_set = Producer.objects.all().filter(permanence = self.permanence)
      context['producer_set'] = producer_set
      context['producer_id'] = self.producer_id
      departementforcusomer_set = LUT_DepartmentForCustomer.objects.none()
      if self.producer_id == 'all':
        departementforcusomer_set = LUT_DepartmentForCustomer.objects.all().filter(
          product__offeritem__permanence = self.permanence
        ).distinct()
      else:
        departementforcusomer_set = LUT_DepartmentForCustomer.objects.all().filter(
          product__producer = self.producer_id,
          product__offeritem__permanence = self.permanence
        ).distinct()
      context['departementforcusomer_set'] = departementforcusomer_set
      context['departementforcusomer_id'] = self.departementforcusomer_id
      context['offeritem_id'] = self.offeritem_id
      context['prepared_amount'] = get_user_order_amount(self.permanence, user = self.user)
    return context

  def get_queryset(self):
    self.permanence = get_object_or_404(Permanence, id=self.args[0])
    qs = OfferItem.objects.none()
    if PERMANENCE_OPENED <= self.permanence.status <= PERMANENCE_SEND :
      qs = OfferItem.objects.all().permanence(self.permanence.id).active()
      if self.permanence.status == PERMANENCE_OPENED:
        # Don't display technical products.
        qs = qs.filter(product__order_unit__lt = PRODUCT_ORDER_UNIT_DEPOSIT)
      if self.producer_id != 'all':
        qs = qs.filter(product__producer=self.producer_id)
      if self.offeritem_id != 'all' or self.permanence.status == PERMANENCE_SEND:
        #if asked or if status is close or send, then display only purchased product
        qs = qs.filter(product__purchase__permanence=self.permanence.id,
          product__purchase__customer__user=self.user).order_by(
          'product__long_name'
        )
      if self.departementforcusomer_id != 'all':
        qs = qs.filter(product__department_for_customer=self.departementforcusomer_id)
      qs = qs.order_by(
        # 'product__producer__short_profile_name', 
        'product__department_for_customer__short_name', 'product__long_name'
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
        row_counter = 0
        if p_value_id == '0':
          row_counter = PermanenceBoard.objects.filter(
            id = p_permanence_board_id,
            customer = request.user.customer.id,
            permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
          ).update(
            customer = None
          )
        else:
          row_counter = PermanenceBoard.objects.filter(
            id = p_permanence_board_id,
            customer__isnull=True,
            permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
          ).update(
            customer = request.user.customer.id
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
          id = p_permanence_board_id,
          customer = request.user.customer.id,
          permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
        ).update(
          customer = None
        )
      else:
        PermanenceBoard.objects.filter(
          id = p_permanence_board_id,
          customer__isnull=True,
          permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
        ).update(
          customer = request.user.customer.id
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
    context = super(InvoiceView,self).get_context_data(**kwargs)
    customer_invoice = self.get_object()
    if customer_invoice:
      bank_account_set = BankAccount.objects.all().filter(is_recorded_on_customer_invoice = customer_invoice)
      context['bank_account_set'] = bank_account_set
      purchase_set = Purchase.objects.all().filter(is_recorded_on_customer_invoice = customer_invoice)
      context['purchase_set'] = purchase_set
      previous_customer_invoice_id = None
      previous_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_invoice.customer.id, id__lt=customer_invoice.id).order_by('-id')[:1]
      if previous_customer_invoice_set:
        context['previous_customer_invoice_id'] = previous_customer_invoice_set[0].id
      next_customer_invoice_id = None
      next_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_invoice.customer.id, id__gt=customer_invoice.id).order_by('id')[:1]
      if next_customer_invoice_set:
        context['next_customer_invoice_id'] = next_customer_invoice_set[0].id
    return context

  def get_queryset(self):
    # qs = CustomerInvoice.objects.none()
    pk = self.kwargs.get('pk', None)
    if self.request.user.is_staff:
      customer_id = self.request.GET.get('customer', None)
      if (pk == None) or (pk == '0'):
        last_customer_invoice_set = CustomerInvoice.objects.filter(customer_id=customer_id).order_by('-id')[:1]
        if last_customer_invoice_set:
          self.kwargs['pk'] = last_customer_invoice_set[0].id
      return CustomerInvoice.objects.all()
    else:
      if (pk == None) or (pk == '0'):
        last_customer_invoice_set = CustomerInvoice.objects.filter(customer__user_id=self.request.user.id).order_by('-id')[:1]
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
    context = super(InvoicePView,self).get_context_data(**kwargs)
    producer_invoice = self.get_object()
    if producer_invoice:
      bank_account_set = BankAccount.objects.all().filter(is_recorded_on_producer_invoice = producer_invoice)
      context['bank_account_set'] = bank_account_set
      purchase_set = Purchase.objects.all().filter(is_recorded_on_producer_invoice = producer_invoice)
      context['purchase_set'] = purchase_set
      previous_producer_invoice_id = None
      previous_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_invoice.producer.id, id__lt=producer_invoice.id).order_by('-id')[:1]
      if previous_producer_invoice_set:
        context['previous_producer_invoice_id'] = previous_producer_invoice_set[0].id
      next_producer_invoice_id = None
      next_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_invoice.producer.id, id__gt=producer_invoice.id).order_by('id')[:1]
      if next_producer_invoice_set:
        context['next_producer_invoice_id'] = next_producer_invoice_set[0].id
      context['uuid'] = self.uuid
    return context

  def get_queryset(self):
    # qs = producerInvoice.objects.none()
    producer_id = None
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
    if (pk == None) or (pk == '0'):
      last_producer_invoice_set = ProducerInvoice.objects.filter(producer_id=producer_id).order_by('-id')[:1]
      if last_producer_invoice_set:
        self.kwargs['pk'] = last_producer_invoice_set[0].id
    return ProducerInvoice.objects.filter(producer_id=producer_id)

# class PreparationView(View):

#    template='index.html'
#    context= {'title': 'Hello World!'}

#    def get(self, request):
#        response = PDFTemplateResponse(request=request,
#                                       template=self.template,
#                                       filename='toto.pdf',
#                                       context= self.context,
#                                       show_content_in_browser=True,
#                                       cmd_options={'margin-top': 10,},
#                                       )
#        return response