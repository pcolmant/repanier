from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from views import OrderView
from views import InvoiceView

urlpatterns = patterns('',
    url(r'^contact/$', views.contact_form, name='contact_form'),
    url(r'^contact-ajax/$', views.contact_form_ajax, name='contact_form_ajax'),
    url(r'^order/(\w+)/$', login_required(OrderView.as_view()), name='order_view'),
    url(r'^order-ajax/$', views.order_form_ajax, name='order_form_ajax'),
    url(r'^product-ajax/$', views.product_form_ajax, name='product_form_ajax'),
    url(r'^invoice/(?P<pk>\d+)/$', login_required(InvoiceView.as_view()), name='invoice_view'),
)
