# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
# from wkhtmltopdf.views import PDFTemplateResponse
from django.views.generic.base import View
from django.views.generic.edit import FormView
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.template import RequestContext

from repanier.models import OfferItem
from repanier.models import Permanence
from repanier.models import SiteProducer
from repanier.forms import ContactForm, ContactFormAjax, OrderForm, OrderTestForm

def render_response(req, *args, **kwargs):
  # For csrf :  http://lincolnloop.com/blog/2008/may/10/getting-requestcontext-your-templates/
  kwargs['context_instance'] = RequestContext(req)
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

class OrderView(FormView):
  template_name = 'repanier/order_form.html'
  form_class = OrderTestForm
  success_url = '/thanks/'

  def get_context_data(self, **kwargs):
    context = super(OrderView,self).get_context_data(**kwargs)
    if not self.request.user.customer:
      raise Http404
    permanence = get_object_or_404(Permanence, pk = kwargs['permanence_id'])
    if permanence.site_id <> settings.SITE_ID:
      raise Http404
    if permanence.status <> PERMANENCE_OPEN:
      raise Http404

    # https://docs.djangoproject.com/en/dev/topics/http/shortcuts/
    # https://docs.djangoproject.com/en/dev/topics/class-based-views/generic-display/#dynamic-filtering
    context['email'] = 'ask.it@to.me'
    context['permanence_memo'] = permanence.memo
    siteproducer_set = SiteProducer.objects.all().filter(permanence = permanence)
    context['siteproducer_set'] = siteproducer_set
    offeritem_set = OfferItem.objects.all().filter(
          permanence = permanence
          ).order_by('product__site_producer__short_profile_name', 
          'product__department_for_customer__short_name', 'product__long_name')
    context['offeritem_set'] = offeritem_set
    return context

  def get(self, request, *args, **kwargs):
    self.object = None
    form_class = self.get_form_class()
    form = self.get_form(self.form_class)
    context = self.get_context_data(form=form, **kwargs)
    return self.render_to_response(context)

  def form_valid(self, form):
    # This method is called when valid form data has been POSTed.
    # It should return an HttpResponse.
    return super(OrderView, self).form_valid(form)

class OrderTestView(FormView):
  template_name = 'repanier/order_test_form.html'
  form_class = OrderTestForm
  success_url = '/thanks/'

  def get_context_data(self, **kwargs):
    context = super(OrderTestView,self).get_context_data(**kwargs)
    if not self.request.user.customer:
      raise Http404
    permanence = get_object_or_404(Permanence, pk = kwargs['permanence_id'])
    if permanence.site_id <> settings.SITE_ID:
      raise Http404
    if permanence.status <> PERMANENCE_OPEN:
      raise Http404

    # https://docs.djangoproject.com/en/dev/topics/http/shortcuts/
    # https://docs.djangoproject.com/en/dev/topics/class-based-views/generic-display/#dynamic-filtering
    context['email'] = 'ask.it@to.me'
    context['permanence_memo'] = permanence.memo
    siteproducer_set = SiteProducer.objects.all().filter(permanence = permanence)
    context['siteproducer_set'] = siteproducer_set
    offeritem_set = OfferItem.objects.all().filter(
          permanence = permanence
          ).order_by('product__site_producer__short_profile_name', 
          'product__department_for_customer__short_name', 'product__long_name')
    context['offeritem_set'] = offeritem_set
    return context

  def get(self, request, *args, **kwargs):
    self.object = None
    form_class = self.get_form_class()
    form = self.get_form(self.form_class)
    context = self.get_context_data(form=form, **kwargs)
    return self.render_to_response(context)

  def form_valid(self, form):
    # This method is called when valid form data has been POSTed.
    # It should return an HttpResponse.
    return super(OrderTestView, self).form_valid(form)

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