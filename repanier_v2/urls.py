from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.decorators.cache import never_cache

from repanier_v2.picture.views import ajax_picture
from repanier_v2.rest.lut import (
    departments_for_customers_rest,
    department_rest,
)
from repanier_v2.rest.permanence import (
    permanences_rest,
    permanence_producer_product_rest,
    permanence_producer_rest,
)
from repanier_v2.rest.producer import producers_list, producer_detail
from repanier_v2.rest.product import products_rest, product_rest
from repanier_v2.rest.version import version_rest
from repanier_v2.tools import get_repanier_template_name
from repanier_v2.views.basket_message_form_ajax import (
    customer_basket_message_form_ajax,
    producer_basket_message_form_ajax,
)
from repanier_v2.views.btn_confirm_order_ajax import btn_confirm_order_ajax
from repanier_v2.views.customer_invoice_class import CustomerInvoiceView
from repanier_v2.views.customer_name_ajax import customer_name_ajax
from repanier_v2.views.customer_product_description_ajax import (
    customer_product_description_ajax,
)
from repanier_v2.views.delivery_ajax import delivery_ajax
from repanier_v2.views.delivery_select_ajax import delivery_select_ajax
from repanier_v2.views.display_status_ajax import display_status
from repanier_v2.views.download_customer_invoice import download_customer_invoice
from repanier_v2.views.forms import (
    AuthRepanierSetPasswordForm,
    AuthRepanierPasswordResetForm,
)
from repanier_v2.views.home_info_ajax import home_info_bs3_ajax
from repanier_v2.views.is_into_offer_ajax import is_into_offer
from repanier_v2.views.like_ajax import like_ajax
from repanier_v2.views.login_view import login_view
from repanier_v2.views.logout_view import logout_view
from repanier_v2.views.my_balance_ajax import my_balance_ajax
from repanier_v2.views.my_cart_amount_ajax import my_cart_amount_ajax
from repanier_v2.views.published_customer_view import published_customer_view
from repanier_v2.views.order_ajax import order_ajax
from repanier_v2.views.order_class import OrderView
from repanier_v2.views.order_description_view import order_description_view
from repanier_v2.views.order_filter_view import order_filter_view
from repanier_v2.views.order_init_ajax import order_init_ajax
from repanier_v2.views.order_select_ajax import order_select_ajax
from repanier_v2.views.producer_invoice_class import ProducerInvoiceView
from repanier_v2.views.send_mail_to_coordinators_view import send_mail_to_coordinators_view
from repanier_v2.views.task_class import PermanenceView
from repanier_v2.views.task_form_ajax import task_form_ajax
from repanier_v2.views.test_mail_config_ajax import test_mail_config_ajax
from repanier_v2.views.unsubscribe_view import unsubscribe_view
from repanier_v2.views.who_is_who_view import who_is_who_view

app_name = "repanier_v2"
# https://consideratecode.com/2018/05/02/django-2-0-url-to-path-cheatsheet/
urlpatterns = [
    path("go_repanier/", login_view, name="login_form"),
    path("leave_repanier/", logout_view, name="logout"),
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            success_url="/",
            # The form bellow is responsible of sending the recovery email
            form_class=AuthRepanierPasswordResetForm,
            template_name=get_repanier_template_name(
                "registration/password_reset_form.html"
            ),
            html_email_template_name=get_repanier_template_name(
                "registration/password_reset_email.html"
            ),
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name=get_repanier_template_name(
                "registration/password_reset_done.html"
            )
        ),
        name="password_reset_done",
    ),
    path(
        "password_reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=AuthRepanierSetPasswordForm,
            template_name=get_repanier_template_name(
                "registration/password_reset_confirm.html"
            ),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password_reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name=get_repanier_template_name(
                "registration/password_reset_complete.html"
            )
        ),
        name="password_reset_complete",
    ),
    path(
        "order/<int:permanence_id>/<int:delivery_id>/",
        never_cache(OrderView.as_view()),
        name="order_delivery_view",
    ),
    path(
        "order/<int:permanence_id>/",
        never_cache(OrderView.as_view()),
        name="order_view",
    ),
    path(
        "like/<int:permanence_id>/",
        never_cache(OrderView.as_view()),
        {"like": True},
        name="like_view",
    ),
    path(
        "order-filter/<int:permanence_id>/", order_filter_view, name="order_filter_view"
    ),
    path(
        "order-description/<int:permanence_id>/",
        order_description_view,
        name="order_description_view",
    ),
    path("ajax/order/", order_ajax, name="order_ajax"),
    path("ajax/delivery/", delivery_ajax, name="delivery_ajax"),
    path(
        "ajax/my-cart_amount/<int:permanence_id>/",
        my_cart_amount_ajax,
        name="my_cart_amount_ajax",
    ),
    path("ajax/my-balance/", my_balance_ajax, name="my_balance"),
    path("ajax/order-name/", customer_name_ajax, name="order_name"),
    path("ajax/home-info-bs3/", home_info_bs3_ajax, name="home_info_bs3"),
    path("ajax/order-init/", order_init_ajax, name="order_init_ajax"),
    path("ajax/order-select/", order_select_ajax, name="order_select_ajax"),
    path("ajax/delivery-select/", delivery_select_ajax, name="delivery_select_ajax"),
    path("ajax/permanence/", task_form_ajax, name="task_form_ajax"),
    path(
        "ajax/customer-basket-message/<int:pk>/",
        customer_basket_message_form_ajax,
        name="customer_basket_message_form_ajax",
    ),
    path(
        "ajax/producer-basket-message/<uuid:login_uuid>/",
        producer_basket_message_form_ajax,
        name="producer_basket_message_form_ajax",
    ),
    path(
        "ajax/customer-product-description/",
        customer_product_description_ajax,
        name="customer_product_description_ajax",
    ),
    path(
        "ajax/upload-picture/<path:upload_to>/<int:size>/",
        ajax_picture,
        name="ajax_picture",
    ),
    path(
        "ajax/btn-confirm-order/", btn_confirm_order_ajax, name="btn_confirm_order_ajax"
    ),
    path(
        "ajax/display-status/<int:permanence_id>/",
        display_status,
        name="display_status",
    ),
    path("ajax/like/", like_ajax, name="like_ajax"),
    path("ajax/is-into-offer/<int:product_id>/", is_into_offer, name="is_into_offer"),
    path("ajax/test-mail-config/", test_mail_config_ajax, name="test_mail_config_ajax"),
    path("permanence/", never_cache(PermanenceView.as_view()), name="permanence_view"),
    path(
        "customer-invoice/<int:pk>/<int:customer_id>",
        login_required(CustomerInvoiceView.as_view()),
        name="customer_invoice_view",
    ),
    path(
        "producer-invoice/<int:pk>/<uuid:login_uuid>/",
        ProducerInvoiceView.as_view(),
        name="producer_invoice_view",
    ),
    path(
        "coordinators/",
        send_mail_to_coordinators_view,
        name="send_mail_to_coordinators_view",
    ),
    path("who/", who_is_who_view, name="who_is_who_view"),
    # path("me/", published_customer_view, name="published_customer_view"),
    path(
        "customer/<int:customer_id>/",
        published_customer_view,
        name="published_customer_view",
    ),
    path("rest/permanences/", permanences_rest, name="permanences_rest"),
    path(
        "rest/permanence/<int:permanence_id>/<str:producer_name>/<str:reference>/",
        permanence_producer_product_rest,
        name="permanence_producer_product_rest",
    ),
    path(
        "rest/permanence/<int:permanence_id>/<str:producer_name>/",
        permanence_producer_rest,
        name="permanence_producer_rest",
    ),
    path(
        "rest/departments-for-customers/",
        departments_for_customers_rest,
        name="departments_for_customers_rest",
    ),
    path(
        "rest/department-for-customer/<str:short_name>/",
        department_rest,
        name="department_rest",
    ),
    path("rest/producers/", producers_list, name="producers_rest"),
    path("rest/producer/<str:short_name>/", producer_detail, name="producer_rest"),
    path(
        "rest/products/<str:producer_short_name>/",
        products_rest,
        name="products_rest",
    ),
    path(
        "rest/product/<str:producer_short_name>/<str:reference>/",
        product_rest,
        name="product_rest",
    ),
    path("rest/version/", version_rest, name="version_rest"),
    path(
        "dowload-customer-invoice/<int:customer_invoice_id>/",
        download_customer_invoice,
        name="download_customer_invoice",
    ),
    path(
        "unsubscribe/<str:customer_id>/<token>/",
        unsubscribe_view,
        name="unsubscribe_view",
    ),
]