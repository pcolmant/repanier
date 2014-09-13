from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from views import OrderView, OrderViewWithoutCache
from views import InvoiceView
from views import InvoicePView
from views import PermanenceView

urlpatterns = patterns('',
                       url(r'^contact/$', views.contact_form, name='contact_form'),
                       # url(r'^order/(\w+)/$', cache_page(60*60)(OrderView.as_view()), name='order_view'),
                       url(r'^order/(\w+)/$', login_required(cache_page(60*60)(OrderView.as_view())), name='order_view'),
                       url(r'^basket/(\w+)/$', login_required(OrderViewWithoutCache.as_view()), name='basket_view'),
                       url(r'^order-ajax/$', views.order_form_ajax, name='order_form_ajax'),
                       url(r'^ajax/order-init/$', views.ajax_order_init, name='ajax_order_init'),
                       url(r'^ajax/order-select/$', views.ajax_order_select, name='ajax_order_select'),
                       url(r'^product-ajax/$', views.product_form_ajax, name='product_form_ajax'),
                       url(r'^permanence/$', login_required(PermanenceView.as_view()), name='permanence_view'),
                       url(r'^permanence-ajax/$', views.permanence_form_ajax, name='permanence_form_ajax'),
                       url(r'^invoice/(?P<pk>\d+)/$', login_required(InvoiceView.as_view()), name='invoice_view'),
                       url(r'^invoicep/(?P<pk>\d+)/$', login_required(InvoicePView.as_view()), name='invoicep_view'),
                       url(
                           r'^invoicep/(?P<pk>\d+)/(?P<uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
                           InvoicePView.as_view(), name='invoicep_uuid_view'),
)
