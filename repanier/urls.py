from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from views import OrderView, OrderViewWithoutCache, PreOrderView
from views import CustomerInvoiceView
from views import ProducerInvoiceView
from views import PermanenceView
from picture.views import ajax_picture

urlpatterns = patterns('',
    url(r'^go_repanier/$', views.login, name='login_form'),
    url(r'^leave_repanier/$', views.logout, name='logout_form'),

    url(r'^order/(\w+)/$', login_required(OrderView.as_view()), name='order_view'),
    # url(r'^order/(\w+)/$', login_required(cache_page(12*60*60)(OrderView.as_view())), name='order_view'),
    url(r'^order-search/(\w+)/$', login_required(OrderView.as_view()), name='orderq_view'),
    url(r'^basket/(\d+)/$', OrderViewWithoutCache.as_view(), name='basket_view'),

    url(r'^ajax/order/$', views.order_form_ajax, name='order_form_ajax'),
    url(r'^ajax/my-balance/$', views.my_balance_ajax, name='my_balance'),
    url(r'^ajax/order-name/$', views.customer_name_ajax, name='order_name'),
    url(r'^ajax/pre-order-name/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        views.producer_name_ajax, name='pre_order_name_ajax'),
    url(r'^ajax/order-init/$', views.order_init_ajax, name='order_init_ajax'),
    url(r'^ajax/order-select/$', views.order_select_ajax, name='order_select_ajax'),
    url(r'^ajax/permanence/$', views.permanence_form_ajax, name='permanence_form_ajax'),
    url(r'^ajax/customer-product-description/$', views.customer_product_description_ajax, name='customer_product_description_ajax'),
    url(r'^ajax/producer-product-description/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        views.producer_product_description_ajax, name='producer_product_description_ajax'),
    url(r'^ajax/producer-product-description/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<offer_item_id>\d+)/$',
        views.producer_product_description_ajax, name='producer_product_description_ajax'),
                       url('^ajax/upload-picture/(?P<upload_to>.*)/(?P<size>\d+)/$', ajax_picture, name='ajax_picture'),
    # url(r'^producer-product-description/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<offer_item_id>\d+)/$',
    #     views.producer_product_description, name='producer_product_description'),

    url(r'^permanence/$', login_required(PermanenceView.as_view()), name='permanence_view'),
    url(r'^customer-invoice/(?P<pk>\d+)/$', login_required(CustomerInvoiceView.as_view()), name='customer_invoice_view'),
    url(r'^producer-invoice/(?P<pk>\d+)/$', login_required(ProducerInvoiceView.as_view()), name='producer_invoice_view'),
    url(r'^producer-invoice/(?P<pk>\d+)/(?P<uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        ProducerInvoiceView.as_view(), name='producer_invoice_uuid_view'),
    url(r'^pre-order/(?P<pk>\d+)/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        PreOrderView.as_view(), name='pre_order_uuid_view'),

    url(r'^coordinators/$', views.send_mail_to_coordinators, name='send_mail_to_coordinators_view'),
    url(r'^members/$', views.send_mail_to_all_members, name='send_mail_to_all_members_view'),
    url(r'^who/$', views.who_is_who, name='who_is_who_view'),
    url(r'^me/$', views.me, name='me_view'),
)
