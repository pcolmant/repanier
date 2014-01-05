from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from views import OrderView, OrderTestView

urlpatterns = patterns('',
    url(r'^contact/$', views.contact_form, name='contact_form'),
    url(r'^contact-ajax/$', views.contact_form_ajax, name='contact_form_ajax'),
    # url(r'^preparation/', login_required(PreparationView.as_view()), name='preparation_view'),
    url(r'^order/(?P<permanence_id>\d+)/$', login_required(OrderView.as_view()), name='order_view'),
    url(r'^order_test/(?P<permanence_id>\d+)/$', login_required(OrderTestView.as_view()), name='order_test_view'),
)
