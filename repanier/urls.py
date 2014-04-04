from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from views import OrderView
from views import InvoiceView
from views import PermanenceView

urlpatterns = patterns('',
    url(r'^contact/$', views.contact_form, name='contact_form'),
    url(r'^order/(\w+)/$', login_required(OrderView.as_view()), name='order_view'),
    url(r'^order-ajax/$', views.order_form_ajax, name='order_form_ajax'),
    url(r'^product-ajax/$', views.product_form_ajax, name='product_form_ajax'),
    url(r'^permanence/$', login_required(PermanenceView.as_view()), name='permanence_view'),
    url(r'^permanence-ajax/$', views.permanence_form_ajax, name='permanence_form_ajax'),
    url(r'^invoice/(?P<pk>\d+)/$', login_required(InvoiceView.as_view()), name='invoice_view'),
)
