# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
# from wkhtmltopdf.views import PDFTemplateResponse
from django.views.generic import ListView
from django.views.generic.base import View
from django.views.generic.edit import FormView

from django.shortcuts import render
from django.shortcuts import render_to_response
from django.template import RequestContext

from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import SiteProducer
from repanier.models import Purchase
from repanier.models import SiteCustomer
from repanier.forms import ContactForm
from repanier.forms import ContactFormAjax

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
def contact_form_ajax(request):
  if request.is_ajax():
    if request.method == 'GET': # If the form has been submitted...
      form = ContactFormAjax(request.GET) # A form bound to the GET data
      if form.is_valid(): # All validation rules pass
        return HttpResponse("Get is valid")
      else:
        return HttpResponse("Get is not vaild")
    if request.method == 'POST': # If the form has been submitted...
      form = ContactFormAjax(request.POST) # A form bound to the GET data
      if form.is_valid(): # All validation rules pass
        return HttpResponse("Post is valid")
      else:
        return HttpResponse("Post is not valid")
    return HttpResponse("???")
  else:
    # Not an AJAX request
    form = ContactFormAjax() # An unbound form
    return render_response(request, "repanier/contact_form_ajax.html", {'form':form}) 

from django.shortcuts import get_object_or_404
from django.http import Http404

class OrderView(ListView):

  template_name = 'repanier/order_form.html'
  success_url = '/thanks/'
  paginate_by = 10

  # def get_urls(self):
  #     my_urls = patterns('',
  #         url(r'^purchase_update/$', self.update, name='sortable_update'),
  #     )
  #     return my_urls + super(SortableAdminMixin, self).get_urls()

  def dispatch(self, request, *args, **kwargs):        
      return super(OrderView, self).dispatch(request, *args, **kwargs)

  @method_decorator(never_cache)
  def post(self, request, *args, **kwargs):
      if request.is_ajax():
        print("Ajax 1")
      if request.method == 'POST':
        print("Post 1")
      if request.method == 'GET':
        print("Get 1")
      return super(OrderView, self).post(request, *args, **kwargs)


  @method_decorator(never_cache)
  def get(self, request, *args, **kwargs):
    p_offer_item_id = None
    if 'offer_item' in request.GET:
      p_offer_item_id = request.GET['offer_item']
    p_value_id = None
    if 'value' in request.GET:
      p_value_id = request.GET['value']
    if p_offer_item_id and p_value_id:
      user = request.user
      try:
        site_customer_set = list(SiteCustomer.objects.filter(
          site_id = settings.SITE_ID,
          customer_id = user.customer).active()[:1])
        if site_customer_set:
          site_customer = site_customer_set[0]
          # The user is an active customer of this site
          offer_item = OfferItem.objects.get(id=p_offer_item_id)
          if(offer_item.permanence.status == PERMANENCE_OPEN and 
            offer_item.permanence.site_id == settings.SITE_ID):
            # The offer_item belong to a open permanence of this site
            q_order = 0
            pruchase_set = list(Purchase.objects.all().product(
              offer_item.product).permanence(offer_item.permanence).site_customer(
              site_customer)[:1])
            purchase = None
            q_previous_order = 0
            if pruchase_set:
              purchase = pruchase_set[0]
              q_previous_order = purchase.order_quantity
            # The q_order is either the purchased quantity or 0
            q_min = offer_item.product.customer_minimum_order_quantity
            q_alert = offer_item.product.customer_alert_order_quantity
            q_step = offer_item.product.customer_increment_order_quantity
            p_value_id = abs(int(p_value_id[0:3]))
            if p_value_id == 0:
              q_order = 0
            elif p_value_id == 1:
              q_order = q_min
            else:
              q_order = q_min + q_step * ( p_value_id - 1 )
            print(q_order)
            print(q_previous_order)
            if q_order > ( q_alert * 3 ):
              # Not usual -> let it be
              q_order = q_previous_order
            print(q_order)
            print(q_previous_order)
            if q_previous_order != q_order:
              if purchase:
                purchase.order_quantity = q_order
                purchase.save()
              else:
                Purchase.objects.create(site_id = settings.SITE_ID, 
                  permanence = offer_item.permanence,
                  distribution_date = offer_item.permanence.distribution_date,
                  product = offer_item.product,
                  site_producer = offer_item.product.site_producer,
                  site_customer = site_customer,
                  order_quantity = q_order,
                  validated_quantity = 0,
                  preparator_recorded_quantity = 0,
                  effective_balance = 0,
                  )
          else:
            result = "N/A4"
        else:
          result = "N/A3"
      except:
        # user.customer doesn't exist -> the user is not a customer.
        result = "N/A2"
    return super(OrderView, self).get(request, *args, **kwargs)

  def get_context_data(self, **kwargs):
    context = super(OrderView,self).get_context_data(**kwargs)
    context['permanence_memo'] = self.permanence.memo
    siteproducer_set = SiteProducer.objects.all().filter(permanence = self.permanence)
    context['siteproducer_set'] = siteproducer_set
    return context

  def get_queryset(self):
    self.permanence = get_object_or_404(Permanence, id=self.args[0])
    if self.permanence.site_id <> settings.SITE_ID:
      raise Http404
    if self.permanence.status <> PERMANENCE_OPEN:
      raise Http404
    return OfferItem.objects.all().permanence(self.args[0]).active(
      ).order_by('product__site_producer__short_profile_name', 
      'product__department_for_customer__short_name', 'product__long_name')


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