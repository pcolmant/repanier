from django.conf.urls import patterns, url
from repanier import views
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page, never_cache
from views import OrderView, PreOrderView
from views import CustomerInvoiceView
from views import ProducerInvoiceView
from views import PermanenceView
from picture.views import ajax_picture
from django.contrib.auth import views as auth_views
from repanier.forms import AuthRepanierPasswordResetForm, AuthRepanierSetPasswordForm

urlpatterns = patterns('',
    url(r'^go_repanier/$', views.login, name='login_form'),
    url(r'^leave_repanier/$', views.logout, name='logout_form'),
    url(r'^coordi/password_reset/$', auth_views.password_reset,
        {
            'post_reset_redirect': 'done/',
            'password_reset_form': AuthRepanierPasswordResetForm,
            'template_name': 'repanier/registration/password_reset_form.html'
        },
        name='admin_password_reset'),
    url(r'^coordi/password_reset/done/$', auth_views.password_reset_done,
        {
            'template_name': 'repanier/registration/password_reset_done.html'
        },
        name='password_reset_done'),
    url(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$', auth_views.password_reset_confirm,
        {
            'set_password_form': AuthRepanierSetPasswordForm,
            'template_name': 'repanier/registration/password_reset_confirm.html'
        },
        name='password_reset_confirm'),
    url(r'^reset/done/$', auth_views.password_reset_complete,
        {
            'template_name': 'repanier/registration/password_reset_complete.html'
        },
        name='password_reset_complete'),

    url(r'^order/(?P<permanence_id>\d+)/$', OrderView.as_view(), name='order_view'),
    url(r'^basket/(?P<permanence_id>\d+)/$', never_cache(OrderView.as_view()), {'basket': True}, name='order_view_wo_cache'),

    url(r'^ajax/order/$', views.order_form_ajax, name='order_form_ajax'),
    url(r'^ajax/my-balance/$', views.my_balance_ajax, name='my_balance'),
    url(r'^ajax/order-name/$', views.customer_name_ajax, name='order_name'),
    url(r'^ajax/pre-order-name/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        views.producer_name_ajax, name='pre_order_name_ajax'),
    url(r'^ajax/order-init/$', views.order_init_ajax, name='order_init_ajax'),
    url(r'^ajax/order-select/$', views.order_select_ajax, name='order_select_ajax'),
    url(r'^ajax/permanence/$', views.permanence_form_ajax, name='permanence_form_ajax'),
    url(r'^ajax/basket-message/(?P<customer_id>\d+)/$', views.basket_message_form_ajax, name='basket_message_form_ajax'),
    url(r'^ajax/customer-product-description/$', views.customer_product_description_ajax, name='customer_product_description_ajax'),
    url(r'^ajax/pre-order-create-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<permanence_id>\d+)/$',
        views.pre_order_create_product_ajax, name='pre_order_create_product_ajax'),
    url(r'^ajax/pre-order-update-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        views.pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
    url(r'^ajax/pre-order-update-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<offer_item_id>\d+)/$',
        views.pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
    url('^ajax/upload-picture/(?P<upload_to>.*)/(?P<size>\d+)/$', ajax_picture, name='ajax_picture'),

    url(r'^permanence/$', login_required(PermanenceView.as_view()), name='permanence_view'),
    url(r'^customer-invoice/(?P<pk>\d+)/$', login_required(CustomerInvoiceView.as_view()), name='customer_invoice_view'),
    url(r'^producer-invoice/(?P<pk>\d+)/$', login_required(ProducerInvoiceView.as_view()), name='producer_invoice_view'),
    url(r'^producer-invoice/(?P<pk>\d+)/(?P<uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        ProducerInvoiceView.as_view(), name='producer_invoice_uuid_view'),
    url(r'^pre-order/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
        never_cache(PreOrderView.as_view()), name='pre_order_uuid_view'),

    url(r'^coordinators/$', views.send_mail_to_coordinators, name='send_mail_to_coordinators_view'),
    url(r'^members/$', views.send_mail_to_all_members, name='send_mail_to_all_members_view'),
    url(r'^who/$', views.who_is_who, name='who_is_who_view'),
    url(r'^me/$', views.me, name='me_view'),
)
