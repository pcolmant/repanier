import django
from django.conf.urls import url
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

from repanier.picture.views import ajax_picture
from repanier.rest.lut import departments_for_customers_rest, department_for_customer_rest
from repanier.rest.permanence import permanences_rest, permanence_producer_product_rest, \
    permanence_producer_rest
from repanier.rest.producer import producers_list, producer_detail
from repanier.rest.product import products_rest, product_rest
from repanier.rest.version import version_rest
# from django.views.i18n import JavaScriptCatalog
from repanier.tools import get_repanier_template_name
from repanier.views.basket_message_form_ajax import customer_basket_message_form_ajax, producer_basket_message_form_ajax
from repanier.views.btn_confirm_order_ajax import btn_confirm_order_ajax
from repanier.views.customer_invoice_class import CustomerInvoiceView
from repanier.views.customer_name_ajax import customer_name_ajax
from repanier.views.customer_product_description_ajax import customer_product_description_ajax
from repanier.views.delivery_ajax import delivery_ajax
from repanier.views.delivery_select_ajax import delivery_select_ajax
from repanier.views.display_status_ajax import display_status
from repanier.views.download_customer_invoice import download_customer_invoice
from repanier.views.flexible_dates import flexible_dates
from repanier.views.forms import AuthRepanierSetPasswordForm, AuthRepanierPasswordResetForm
from repanier.views.home_info_ajax import home_info_bs3_ajax
from repanier.views.is_into_offer_ajax import is_into_offer, is_into_offer_content
from repanier.views.like_ajax import like_ajax
from repanier.views.login_view import login_view
from repanier.views.logout_view import logout_view
from repanier.views.my_balance_ajax import my_balance_ajax
from repanier.views.my_cart_amount_ajax import my_cart_amount_ajax
from repanier.views.my_profile_view import my_profile_view
from repanier.views.order_ajax import order_ajax
from repanier.views.order_class import OrderView
from repanier.views.order_description_view import order_description_view
from repanier.views.order_filter_view import order_filter_view
from repanier.views.order_init_ajax import order_init_ajax
from repanier.views.order_select_ajax import order_select_ajax
from repanier.views.pre_order_class import PreOrderView
from repanier.views.pre_order_create_product_ajax import pre_order_create_product_ajax
from repanier.views.pre_order_update_product_ajax import pre_order_update_product_ajax
from repanier.views.producer_invoice_class import ProducerInvoiceView
# from repanier.views.send_mail_to_all_members_view import send_mail_to_all_members_view
from repanier.views.send_mail_to_coordinators_view import send_mail_to_coordinators_view
from repanier.views.task_class import PermanenceView
from repanier.views.task_form_ajax import task_form_ajax
from repanier.views.test_mail_config_ajax import test_mail_config_ajax
from repanier.views.unsubscribe_view import unsubscribe_view
from repanier.views.who_is_who_view import who_is_who_view

if django.VERSION[0] < 2:

    urlpatterns = [
        url(r'^go_repanier/$', login_view, name='login_form'),
        url(r'^leave_repanier/$', logout_view, name='logout'),
        url(r'^password_reset/$', auth_views.PasswordResetView.as_view(),
            {
                'post_reset_redirect': 'done/',
                # The form bellow is responsible of sending the recovery email
                'password_reset_form': AuthRepanierPasswordResetForm,
                'template_name': get_repanier_template_name('registration/password_reset_form.html')
            },
            name='admin_password_reset'),
        url(r'^password_reset/done/$', auth_views.PasswordResetDoneView.as_view(),
            {
                'template_name': get_repanier_template_name('registration/password_reset_done.html')
            },
            name='password_reset_done'),
        url(r'^password_reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$', auth_views.PasswordResetConfirmView.as_view(),
            {
                'set_password_form': AuthRepanierSetPasswordForm,
                'template_name': get_repanier_template_name('registration/password_reset_confirm.html')
            },
            name='password_reset_confirm'),
        url(r'^password_reset/complete/$', auth_views.PasswordResetCompleteView.as_view(),
            {
                'template_name': get_repanier_template_name('registration/password_reset_complete.html')
            },
            name='password_reset_complete'),

        url(r'^order/(?P<permanence_id>\d+)/(?P<delivery_id>\d+)/$', never_cache(OrderView.as_view()),
            name='order_delivery_view'),
        url(r'^order/(?P<permanence_id>\d+)/$', never_cache(OrderView.as_view()),
            name='order_view'),
        # url(r'^basket/(?P<permanence_id>\d+)/(?P<delivery_id>\d+)/$', never_cache(OrderView.as_view()), {'basket': True},
        #     name='basket_view'),
        # url(r'^basket/(?P<permanence_id>\d+)/$', never_cache(OrderView.as_view()), {'basket': True},
        #     name='basket_view'),
        url(r'^like/(?P<permanence_id>\d+)/$', never_cache(OrderView.as_view()), {'like': True},
            name='like_view'),
        url(r'^order-filter/(?P<permanence_id>\d+)/$', order_filter_view, name='order_filter_view'),
        url(r'^order-description/(?P<permanence_id>\d+)/$', order_description_view, name='order_description_view'),

        url(r'^ajax/order/$', order_ajax, name='order_ajax'),
        url(r'^ajax/delivery/$', delivery_ajax, name='delivery_ajax'),
        url(r'^ajax/my-cart_amount/(?P<permanence_id>\d+)/$', my_cart_amount_ajax, name='my_cart_amount_ajax'),
        url(r'^ajax/my-balance/$', my_balance_ajax, name='my_balance'),
        url(r'^ajax/order-name/$', customer_name_ajax, name='order_name'),
        url(r'^ajax/home-info-bs3/$', home_info_bs3_ajax, name='home_info_bs3'),
        url(r'^ajax/order-init/$', order_init_ajax, name='order_init_ajax'),
        url(r'^ajax/order-select/$', order_select_ajax, name='order_select_ajax'),
        url(r'^ajax/delivery-select/$', delivery_select_ajax, name='delivery_select_ajax'),
        url(r'^ajax/permanence/$', task_form_ajax, name='task_form_ajax'),
        url(r'^ajax/customer-basket-message/(?P<pk>\d+)/$', customer_basket_message_form_ajax,
            name='customer_basket_message_form_ajax'),
        url(
            r'^ajax/producer-basket-message/(?P<pk>\d+)/(?P<uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
            producer_basket_message_form_ajax, name='producer_basket_message_form_ajax'),
        url(r'^ajax/customer-product-description/$', customer_product_description_ajax,
            name='customer_product_description_ajax'),
        url(
            r'^ajax/pre-order-create-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<permanence_id>\d+)/$',
            pre_order_create_product_ajax, name='pre_order_create_product_ajax'),
        url(
            r'^ajax/pre-order-update-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
            pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
        url(
            r'^ajax/pre-order-update-product/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/(?P<offer_item_id>\d+)/$',
            pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
        url(r'^ajax/upload-picture/(?P<upload_to>.*)/(?P<size>[0-9]+)/$', ajax_picture, name='ajax_picture'),
        url(r'^ajax/btn-confirm-order/$', btn_confirm_order_ajax, name='btn_confirm_order_ajax'),
        url(r'^ajax/display-status/(?P<permanence_id>\d+)/$', display_status, name='display_status'),
        url(r'^ajax/like/$', like_ajax, name='like_ajax'),
        url(r'^ajax/is-into-offer/(?P<product_id>\d+)/(?P<contract_id>\d+)/$', is_into_offer, name='is_into_offer'),
        url(r'^ajax/is-into-offer-content/(?P<product_id>\d+)/(?P<contract_id>\d+)/(?P<one_date_str>.*)/$',
            is_into_offer_content, name='is_into_offer_content'),
        url(r'^ajax/flexible_dates/(?P<product_id>\d+)/(?P<contract_id>\d+)/$',
            flexible_dates, name='flexible_dates'),
        # url(r'^ajax/test-mail-config/(?P<id_email_host>.*)/(?P<id_email_port>.*)/(?P<id_email_use_tls>.*)/(?P<id_email_host_user>.*)/(?P<id_new_email_host_password>.*)/$', test_mail_config_ajax, name='test_mail_config_ajax'),
        url(r'^ajax/test-mail-config/$', test_mail_config_ajax, name='test_mail_config_ajax'),
        url(r'^permanence/$', never_cache(PermanenceView.as_view()), name='permanence_view'),
        url(r'^customer-invoice/(?P<pk>[0-9]+)/$', login_required(CustomerInvoiceView.as_view()),
            name='customer_invoice_view'),
        url(r'^producer-invoice/(?P<pk>[0-9]+)/(?P<uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
            ProducerInvoiceView.as_view(), name='producer_invoice_uuid_view'),
        url(r'^producer-invoice/(?P<pk>[0-9]+)/$', login_required(ProducerInvoiceView.as_view()),
            name='producer_invoice_view'),
        url(r'^pre-order/(?P<offer_uuid>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/$',
            never_cache(PreOrderView.as_view()), name='pre_order_uuid_view'),

        url(r'^coordinators/$', send_mail_to_coordinators_view, name='send_mail_to_coordinators_view'),
        # url(r'^members/$', send_mail_to_all_members_view, name='send_mail_to_all_members_view'),
        url(r'^who/$', who_is_who_view, name='who_is_who_view'),
        url(r'^me/$', my_profile_view, name='my_profile_view'),
        # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
        url(r'^rest/permanences/$', permanences_rest, name='permanences_rest'),
        url(r'^rest/permanence/(?P<permanence_id>\d+)/(?P<producer_name>.*)/(?P<reference>.*)/$',
            permanence_producer_product_rest,
            name='permanence_producer_product_rest'),
        url(r'^rest/permanence/(?P<permanence_id>\d+)/(?P<producer_name>.*)/$', permanence_producer_rest,
            name='permanence_producer_rest'),
        url(r'^rest/departments-for-customers/$', departments_for_customers_rest, name='departments_for_customers_rest'),
        url(r'^rest/department-for-customer/(?P<short_name>.*)/$', department_for_customer_rest,
            name='department_for_customer_rest'),
        url(r'^rest/producers/$', producers_list, name='producers_rest'),
        url(r'^rest/producer/(?P<short_profile_name>.*)/$', producer_detail,
            name='producer_rest'),
        url(r'^rest/products/(?P<producer_short_profile_name>.*)/$', products_rest, name='products_rest'),
        url(r'^rest/product/(?P<producer_short_profile_name>.*)/(?P<reference>.*)/$', product_rest,
            name='product_rest'),
        url(r'^rest/version/$', version_rest, name='version_rest'),
        url(r'^dowload-customer-invoice/(?P<customer_invoice_id>\d+)/$', download_customer_invoice,
            name='download_customer_invoice'),
        url(r'^unsubscribe/(?P<customer_id>.*)/(?P<token>[\w.:\-_=]+)/$', unsubscribe_view, name='unsubscribe_view'),
    ]

else:

    from django.urls import path

    # https://consideratecode.com/2018/05/02/django-2-0-url-to-path-cheatsheet/
    urlpatterns = [
        path('go_repanier/', login_view, name='login_form'),
        path('leave_repanier/', logout_view, name='logout'),
        path('password_reset/', auth_views.PasswordResetView.as_view(),
            {
                'post_reset_redirect': 'done/',
                # The form bellow is responsible of sending the recovery email
                'password_reset_form': AuthRepanierPasswordResetForm,
                'template_name': get_repanier_template_name('registration/password_reset_form.html')
            },
            name='admin_password_reset'),
        path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(),
            {
                'template_name': get_repanier_template_name('registration/password_reset_done.html')
            },
            name='password_reset_done'),
        path('password_reset/<uidb64>/<token>/',
            auth_views.PasswordResetConfirmView.as_view(),
            {
                'set_password_form': AuthRepanierSetPasswordForm,
                'template_name': get_repanier_template_name('registration/password_reset_confirm.html')
            },
            name='password_reset_confirm'),
        path('password_reset/complete/', auth_views.PasswordResetCompleteView.as_view(),
            {
                'template_name': get_repanier_template_name('registration/password_reset_complete.html')
            },
            name='password_reset_complete'),

        path('order/<int:permanence_id>/<int:delivery_id>/', never_cache(OrderView.as_view()),
            name='order_delivery_view'),
        path('order/<int:permanence_id>/', never_cache(OrderView.as_view()),
            name='order_view'),
        path('like/<int:permanence_id>/', never_cache(OrderView.as_view()), {'like': True},
            name='like_view'),
        path('order-filter/<int:permanence_id>/', order_filter_view, name='order_filter_view'),
        path('order-description/<int:permanence_id>/', order_description_view, name='order_description_view'),

        path('ajax/order/', order_ajax, name='order_ajax'),
        path('ajax/delivery/', delivery_ajax, name='delivery_ajax'),
        path('ajax/my-cart_amount/<int:permanence_id>/', my_cart_amount_ajax, name='my_cart_amount_ajax'),
        path('ajax/my-balance/', my_balance_ajax, name='my_balance'),
        path('ajax/order-name/', customer_name_ajax, name='order_name'),
        path('ajax/home-info-bs3/', home_info_bs3_ajax, name='home_info_bs3'),
        path('ajax/order-init/', order_init_ajax, name='order_init_ajax'),
        path('ajax/order-select/', order_select_ajax, name='order_select_ajax'),
        path('ajax/delivery-select/', delivery_select_ajax, name='delivery_select_ajax'),
        path('ajax/permanence/', task_form_ajax, name='task_form_ajax'),
        path('ajax/customer-basket-message/<int:pk>/', customer_basket_message_form_ajax,
            name='customer_basket_message_form_ajax'),
        path(
            'ajax/producer-basket-message/<int:pk>/<uuid:uuid>/',
            producer_basket_message_form_ajax, name='producer_basket_message_form_ajax'),
        path('ajax/customer-product-description/', customer_product_description_ajax,
            name='customer_product_description_ajax'),
        path(
            'ajax/pre-order-create-product/<uuid:offer_uuid>/<int:permanence_id>/',
            pre_order_create_product_ajax, name='pre_order_create_product_ajax'),
        path(
            'ajax/pre-order-update-product/<uuid:offer_uuid>/',
            pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
        path(
            'ajax/pre-order-update-product/<uuid:offer_uuid>/<int:offer_item_id>/',
            pre_order_update_product_ajax, name='pre_order_update_product_ajax'),
        path('ajax/upload-picture/<path:upload_to>/<int:size>/', ajax_picture, name='ajax_picture'),
        path('ajax/btn-confirm-order/', btn_confirm_order_ajax, name='btn_confirm_order_ajax'),
        path('ajax/display-status/<int:permanence_id>/', display_status, name='display_status'),
        path('ajax/like/', like_ajax, name='like_ajax'),
        path('ajax/is-into-offer/<int:product_id>/<int:contract_id>/', is_into_offer, name='is_into_offer'),
        path('ajax/is-into-offer-content/<int:product_id>/<int:contract_id>/<str:one_date_str>/',
            is_into_offer_content, name='is_into_offer_content'),
        path('ajax/flexible_dates/<int:product_id>/<int:contract_id>/',
            flexible_dates, name='flexible_dates'),
        # url(r'^ajax/test-mail-config/(?P<id_email_host>.*)/(?P<id_email_port>.*)/(?P<id_email_use_tls>.*)/(?P<id_email_host_user>.*)/(?P<id_new_email_host_password>.*)/$', test_mail_config_ajax, name='test_mail_config_ajax'),
        path('ajax/test-mail-config/', test_mail_config_ajax, name='test_mail_config_ajax'),
        path('permanence/', never_cache(PermanenceView.as_view()), name='permanence_view'),
        path('customer-invoice/<int:pk>/', login_required(CustomerInvoiceView.as_view()),
            name='customer_invoice_view'),
        path(
            'producer-invoice/<int:pk>/<uuid:uuid>/',
            ProducerInvoiceView.as_view(), name='producer_invoice_uuid_view'),
        path('producer-invoice/<int:pk>/', login_required(ProducerInvoiceView.as_view()),
            name='producer_invoice_view'),
        path('pre-order/<uuid:offer_uuid>/',
            never_cache(PreOrderView.as_view()), name='pre_order_uuid_view'),

        path('coordinators/', send_mail_to_coordinators_view, name='send_mail_to_coordinators_view'),
        # url(r'^members/$', send_mail_to_all_members_view, name='send_mail_to_all_members_view'),
        path('who/', who_is_who_view, name='who_is_who_view'),
        path('me/', my_profile_view, name='my_profile_view'),
        # url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
        path('rest/permanences/', permanences_rest, name='permanences_rest'),
        path('rest/permanence/<int:permanence_id>/<str:producer_name>/<str:reference>/',
            permanence_producer_product_rest,
            name='permanence_producer_product_rest'),
        path('rest/permanence/<int:permanence_id>/<str:producer_name>/', permanence_producer_rest,
            name='permanence_producer_rest'),
        path('rest/departments-for-customers/', departments_for_customers_rest,
            name='departments_for_customers_rest'),
        path('rest/department-for-customer/<str:short_name>/', department_for_customer_rest,
            name='department_for_customer_rest'),
        path('rest/producers/', producers_list, name='producers_rest'),
        path('rest/producer/<str:short_profile_name>/', producer_detail,
            name='producer_rest'),
        path('rest/products/<str:producer_short_profile_name>/', products_rest, name='products_rest'),
        path('rest/product/<str:producer_short_profile_name>/<str:reference>/', product_rest,
            name='product_rest'),
        path('rest/version/', version_rest, name='version_rest'),
        path('dowload-customer-invoice/<int:customer_invoice_id>/', download_customer_invoice,
            name='download_customer_invoice'),
        path('unsubscribe/<str:customer_id>/<token>/', unsubscribe_view, name='unsubscribe_view'),
    ]
