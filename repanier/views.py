# -*- coding: utf-8
from __future__ import unicode_literals
import json
import datetime
from django.contrib.sites.models import get_current_site
from django.core import urlresolvers
from django.core.mail import EmailMessage
from django.template.response import TemplateResponse
from django.utils import timezone
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.utils.html import strip_tags
from django.utils.http import is_safe_url
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as _not_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from parler.models import TranslationDoesNotExist
from django.utils import translation
from django.db.models import Q
from django.contrib.auth import (REDIRECT_FIELD_NAME, login as auth_login,
    logout as auth_logout, get_user_model)


from tools import *
from models import repanier_settings

# from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.views.generic import DetailView

from django.shortcuts import render_to_response, get_object_or_404, resolve_url
from django.template import RequestContext

from models import LUT_DepartmentForCustomer, PurchaseClosed, PurchaseOpened
from models import OfferItem
from models import Permanence
from models import Producer
from models import ProducerInvoice
from models import Customer
from models import CustomerInvoice
from models import Staff
from models import BankAccount
from models import PermanenceBoard
from forms import AuthRepanierLoginForm, CustomerForm, CoordinatorsContactForm, MembersContactForm, \
    ProducerProductDescriptionForm

import logging

logger = logging.getLogger(__name__)


def render_response(req, *args, **kwargs):
    # For csrf :  http://lincolnloop.com/blog/2008/may/10/getting-requestcontext-your-templates/
    kwargs['context_instance'] = RequestContext(req)
    # print(RequestContext(req))
    return render_to_response(*args, **kwargs)


@sensitive_post_parameters()
@csrf_protect
@never_cache
def login(request, template_name='repanier/login.html',
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=AuthRepanierLoginForm,
          current_app=None, extra_context=None):
    """
    Displays the login form and handles the login action.
    """
    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, ''))

    if request.method == "POST":
        form = authentication_form(request, data=request.POST)
        if form.is_valid():

            # Ensure the user-originating redirection url is safe.
            if not is_safe_url(url=redirect_to, host=request.get_host()):
                redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

            # Okay, security check complete. Log the user in.
            auth_login(request, form.get_user())

            return HttpResponseRedirect(redirect_to)
    else:
        form = authentication_form(request)

    current_site = get_current_site(request)

    context = {
        'form': form,
        redirect_field_name: redirect_to,
        'site': current_site,
        'site_name': current_site.name,
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context,
                            current_app=current_app)


def logout(request, next_page=None,
           template_name='repanier/logged_out.html',
           redirect_field_name=REDIRECT_FIELD_NAME,
           current_app=None, extra_context=None):
    """
    Logs out the user and displays 'You are logged out' message.
    """
    auth_logout(request)

    if next_page is not None:
        next_page = resolve_url(next_page)

    if (redirect_field_name in request.POST or
            redirect_field_name in request.GET):
        next_page = request.POST.get(redirect_field_name,
                                     request.GET.get(redirect_field_name))
        # Security check -- don't allow redirection to a different host.
        if not is_safe_url(url=next_page, host=request.get_host()):
            next_page = request.path

    if next_page:
        # Redirect to this page until the session has been cleared.
        return HttpResponseRedirect(next_page)

    current_site = get_current_site(request)
    context = {
        'site': current_site,
        'site_name': current_site.name,
        'title': _('Logged out')
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context,
        current_app=current_app)


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators(request):
    if request.method == 'POST':  # If the form has been submitted...
        form = CoordinatorsContactForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            to_email_staff = []
            for staff in Staff.objects.filter(is_active=True).order_by():
                if form.cleaned_data.get('staff_%d' % staff.id):
                    to_email_staff.append(staff.user.email)
            if len(to_email_staff) > 0:
                to = (request.user.email,)
                email = EmailMessage(
                    strip_tags(form.cleaned_data.get('subject')),
                    strip_tags(form.cleaned_data.get('message')),
                    "no-reply" + get_allowed_mail_extension(),
                    to,
                    cc=to_email_staff
                )
                send_email(email=email)
                return HttpResponseRedirect('/')  # Redirect after POST
            else:
                return render_response(request, "repanier/send_mail_to_coordinators.html", {'form': form, 'update': '1'})
    else:
        form = CoordinatorsContactForm()  # An unbound form

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True

    return render_response(request, "repanier/send_mail_to_coordinators.html", {'form': form})


@login_required()
@csrf_protect
@never_cache
def send_mail_to_all_members(request):
    coordinator = Staff.objects.filter(
        customer_responsible_id=request.user.customer.id, is_coordinator=True, is_active=True
    ).order_by().first()
    if request.method == 'POST':  # If the form has been submitted...
        form = MembersContactForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            to_email_customer = []
            if coordinator is not None:
                qs = Customer.objects.filter(is_active=True, represent_this_buyinggroup=False, may_order=True)
            else:
                qs = Customer.objects.filter(is_active=True, accept_mails_from_members=True, represent_this_buyinggroup=False, may_order=True)
            for customer in qs:
                if customer.user_id != request.user.id:
                    to_email_customer.append(customer.user.email)
                if customer.email2 is not None:
                    to_email_customer.append(customer.user.email2)
            to = (request.user.email,)
            email = EmailMessage(
                strip_tags(form.cleaned_data.get('subject')),
                strip_tags(form.cleaned_data.get('message')),
                "no-reply" + get_allowed_mail_extension(),
                to,
                cc=to_email_customer
            )
            send_email(email=email)
            return HttpResponseRedirect('/')  # Redirect after POST
    else:
        form = MembersContactForm()  # An unbound form
        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True
        recipient = form.fields["recipient"]
        if coordinator is not None:
            recipient.initial = _("All members as coordinator")
        else:
            recipient.initial = _("All members accepting to show they mail address")
        recipient.widget.attrs['readonly'] = True

    return render_response(request, "repanier/send_mail_to_all_members.html", {'form': form, 'coordinator': coordinator is not None})


@login_required()
@never_cache
def who_is_who(request):
    customer_list = Customer.objects.filter(is_active=True, represent_this_buyinggroup=False).order_by("long_basket_name")
    staff = Staff.objects.filter(
        customer_responsible_id=request.user.customer.id, is_coordinator=True, is_active=True
    ).order_by().first()
    if staff is not None:
        coordinator = True
    else:
        coordinator = False
    return render_response(request, "repanier/who_is_who.html", {'customer_list': customer_list, 'coordinator': coordinator})


@login_required()
@csrf_protect
@never_cache
def me(request):
    if request.method == 'POST':  # If the form has been submitted...
        form = CustomerForm(request.POST, request=request)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            customer = Customer.objects.filter(user_id=request.user.id).order_by().first()
            if customer is not None:
                customer.long_basket_name = form.cleaned_data.get('long_basket_name')
                customer.phone1 = form.cleaned_data.get('phone1')
                customer.phone2 = form.cleaned_data.get('phone2')
                customer.accept_phone_call_from_members = form.cleaned_data.get('accept_phone_call_from_members')
                customer.email2 = form.cleaned_data.get('email2').lower()
                customer.accept_mails_from_members = form.cleaned_data.get('accept_mails_from_members')
                customer.city = form.cleaned_data.get('city')
                if repanier_settings['DELIVERY_POINT']:
                    customer.delivery_point = form.cleaned_data.get('delivery_point')
                customer.memo = form.cleaned_data.get('memo')
                customer.save()
                # Important : place this code after because form = CustomerForm(data, request=request) delete form.cleaned_data
                email = form.cleaned_data.get('email1')
                user_model = get_user_model()
                user = user_model.objects.filter(email=email).order_by().first()
                if user is None or user.email != email:
                    # user.email != email for case unsensitive SQL query
                    customer.user.email = email.lower()
                    customer.user.save()
                # User feed back : Display email in lower case.
                data = form.data.copy()
                data["email1"] = customer.user.email
                data["email2"] = customer.email2
                form = CustomerForm(data, request=request)
            return render_response(request, "repanier/me_form.html", {'form': form, 'update': '1'})
    else:
        form = CustomerForm()  # An unbound form
        customer = request.user.customer
        field = form.fields["long_basket_name"]
        field.initial = customer.long_basket_name
        field = form.fields["phone1"]
        field.initial = customer.phone1
        field = form.fields["phone2"]
        field.initial = customer.phone2
        field = form.fields["accept_phone_call_from_members"]
        field.initial = customer.accept_phone_call_from_members
        field = form.fields["email1"]
        field.initial = request.user.email
        field = form.fields["email2"]
        field.initial = customer.email2
        field = form.fields["accept_mails_from_members"]
        field.initial = customer.accept_mails_from_members
        field = form.fields["city"]
        field.initial = customer.city
        if repanier_settings['DELIVERY_POINT']:
            field = form.fields["delivery_point"]
            field.initial = customer.delivery_point
        field = form.fields["memo"]
        field.initial = customer.memo


    return render_response(request, "repanier/me_form.html", {'form': form, 'update': None})


def customer_product_description_ajax(request):
    # import sys
    # import traceback
    if request.is_ajax() and request.method == 'GET':
        offer_item_id = sint(request.GET.get('offer_item', 0))
        offer_item = get_object_or_404(OfferItem, id=offer_item_id)
        if PERMANENCE_OPENED <= offer_item.permanence.status <= PERMANENCE_SEND:
            try:
                result = offer_item.cache_part_e
                if result is None or result == "":
                    result = "%s" % _("There is no more product's information")
            except TranslationDoesNotExist:
                result = "%s" % _("There is no more product's information")
            return HttpResponse(result)
    # except:
    #     exc_type, exc_value, exc_traceback = sys.exc_info()
    #     lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    #     print ''.join('!! ' + line for line in lines)
    raise Http404


@never_cache
def customer_name_ajax(request):
    if request.is_ajax() and request.method == 'GET':
        user = request.user
        if user.is_anonymous():
            return HttpResponse(_('Anonymous'))
        customer = Customer.objects.filter(
                user_id=user.id, is_active=True).only("short_basket_name").order_by().first()
        if customer is not None:
            return HttpResponse(customer.short_basket_name)
    raise Http404


@never_cache
def my_balance_ajax(request):
    if request.is_ajax() and request.method == 'GET':
        user = request.user
        if user.is_anonymous():
            return HttpResponse("")
        last_customer_invoice = CustomerInvoice.objects.filter(
            customer__user_id=request.user.id,
            invoice_sort_order__isnull=False)\
            .only("balance", "date_balance")\
            .order_by('-invoice_sort_order').first()
        if last_customer_invoice is not None:
            if last_customer_invoice.balance < DECIMAL_ZERO:
                result = _('My balance : <font color="red">%(balance)s &euro;</font> at %(date)s') % {
                    'balance': number_format(last_customer_invoice.balance, 2),
                    'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}
            else:
                result = _('My balance : <font color="green">%(balance)s &euro;</font> at %(date)s') % {
                        'balance': number_format(last_customer_invoice.balance, 2),
                        'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}
            return HttpResponse(result)
    raise Http404


@never_cache
def producer_name_ajax(request, offer_uuid=None):
    if request.is_ajax() and request.method == 'GET':
        producer = Producer.objects.filter(offer_uuid=offer_uuid, is_active=True).order_by().first()
        if producer is None:
            return HttpResponse(_('Anonymous'))
        return HttpResponse(producer.short_profile_name)
    raise Http404


@never_cache
def producer_product_description_ajax(request, offer_uuid=None, offer_item_id=None):
    if offer_item_id is None or not repanier_settings['PRODUCER_PRE_OPENING']:
        raise Http404
    producer = Producer.objects.filter(offer_uuid=offer_uuid, is_active=True).order_by().first()
    if producer is None:
        raise Http404
    offer_item = get_object_or_404(OfferItem, id=offer_item_id)
    if offer_item.producer_id != producer.id:
        raise Http404
    if not offer_item.is_active:
        raise Http404

    permanence = offer_item.permanence
    if permanence.status == PERMANENCE_PRE_OPEN:
        if request.method == 'POST':  # If the form has been submitted...
            form = ProducerProductDescriptionForm(request.POST)  # A form bound to the POST data
            # to_json = []
            if form.is_valid():  # All validation rules pass
                # Process the data in form.cleaned_data
                # ...
                product = offer_item.product
                product.long_name = form.cleaned_data.get('long_name')
                product.order_unit = form.cleaned_data.get('order_unit')
                product.customer_increment_order_quantity = form.cleaned_data.get('customer_increment_order_quantity')
                if product.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                    product.order_average_weight = form.cleaned_data.get('order_average_weight')
                else:
                    product.order_average_weight = product.customer_increment_order_quantity
                product.producer_unit_price = form.cleaned_data.get('producer_unit_price')
                product.unit_deposit = form.cleaned_data.get('unit_deposit')
                product.stock = form.cleaned_data.get('stock')
                product.vat_level = form.cleaned_data.get('vat_level')
                product.offer_description = form.cleaned_data.get('offer_description')
                product.customer_minimum_order_quantity = product.customer_increment_order_quantity
                product.customer_alert_order_quantity = product.stock
                product.save()
                offer_item_queryset = OfferItem.objects\
                    .filter(
                        id=offer_item.id
                    ).order_by()
                clean_offer_item(permanence, offer_item_queryset, reorder=False)
                # Refresh offer_item
                offer_item = get_object_or_404(OfferItem, id=offer_item_id)
                update = '1'
            #     option_dict = {'id': "#my_balance", 'html': 0}
            #     to_json.append(option_dict)
            else:
                update = None

            #     option_dict = {'id': "#my_balance", 'html': 1}
            #     to_json.append(option_dict)
            # return HttpResponse(json.dumps(to_json), content_type="application/json")

        else:
            # print(request.GET)
            # print("form is NOT initialized")
            # getcontext().rounding = ROUND_HALF_UP
            form = ProducerProductDescriptionForm()  # An unbound form
            field = form.fields["long_name"]
            field.initial = offer_item.long_name
            field = form.fields["order_unit"]
            field.initial = offer_item.order_unit
            field = form.fields["order_average_weight"]
            field.initial = offer_item.order_average_weight.quantize(ONE_DECIMAL)
            field = form.fields["customer_increment_order_quantity"]
            field.initial = offer_item.customer_increment_order_quantity.quantize(ONE_DECIMAL)
            field = form.fields["producer_unit_price"]
            field.initial = offer_item.producer_unit_price
            field = form.fields["unit_deposit"]
            field.initial = offer_item.unit_deposit
            field = form.fields["stock"]
            field.initial = offer_item.stock.quantize(ONE_DECIMAL)
            field = form.fields["vat_level"]
            field.initial = offer_item.vat_level
            field = form.fields["offer_description"]
            field.initial = offer_item.product.offer_description
            update = None

        return render_response(
            request,
            "repanier/producer_product_description_form.html",
            {'form': form, 'offer_uuid' : offer_uuid, 'offer_item': offer_item, 'update': update}
        )
    raise Http404


@never_cache
def order_form_ajax(request):
    result = "ko"
    if request.is_ajax() and request.method == 'GET':
        user = request.user
        if user.is_authenticated():
            offer_item_id = sint(request.GET.get('offer_item', 0))
            value_id = sint(request.GET.get('value', 0))
            result = update_or_create_purchase(
                user_id=user.id, offer_item_id=offer_item_id,
                value_id=value_id
            )
        else:
            raise Http404
    else:
        raise Http404
    return HttpResponse(result)


@never_cache
def order_init_ajax(request):
    if request.is_ajax() and request.method == 'GET':
        # construct a list which will contain all of the data for the response
        if 'offer_item' in request.GET:
            user = request.user
            to_json = []
            my_basket = str(0)
            if user.is_authenticated():
                customer = Customer.objects.filter(
                    user_id=user.id, is_active=True).only("id", "vat_id", "short_basket_name").order_by().first()
                if customer is not None:
                    my_name = customer.short_basket_name
                    last_customer_invoice = CustomerInvoice.objects.filter(
                        customer__user_id=request.user.id,
                        invoice_sort_order__isnull=False)\
                        .only("balance", "date_balance")\
                        .order_by('-invoice_sort_order').first()
                    if last_customer_invoice is not None:
                        if last_customer_invoice.balance < 0:
                            my_balance = _('My balance : <font color="red">%(balance)s &euro;</font> at %(date)s') % {
                                'balance': number_format(last_customer_invoice.balance, 2),
                                'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}
                        else:
                            my_balance = _('My balance : <font color="green">%(balance)s &euro;</font> at %(date)s') % {
                                    'balance': number_format(last_customer_invoice.balance, 2),
                                    'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}
                        option_dict = {'id': "#my_balance", 'html': my_balance}
                        to_json.append(option_dict)
                    if customer.may_order:
                        permanence_id = sint(request.GET.get('permanence', 0))
                        permanence = Permanence.objects.filter(id=permanence_id)\
                            .only("id", "status").order_by().first()
                        if permanence is not None and PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
                            my_basket = get_user_order_amount(permanence.id,customer_id=customer.id)
                        communication = sint(request.GET.get('communication', 0))
                        if communication == 1:
                            # permanence_board_set = PermanenceBoard.objects.filter(
                            #     permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
                            # ).only("id").order_by()
                            # if permanence_board_set.exists():
                            now = timezone.localtime(timezone.now()).date()
                            permanence_boards = PermanenceBoard.objects.filter(
                                customer_id=customer.id, permanence_date__gte=now,
                                permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
                            ).order_by("permanence_date")[:2]
                            is_not_staff = Staff.objects.filter(
                                customer_responsible_id=customer.id
                            ).order_by().first() is None
                            if (repanier_settings['MAX_WEEK_WO_PARTICIPATION'] > DECIMAL_ZERO and is_not_staff) \
                                    or len(permanence_boards) > 0:
                                if len(permanence_boards) == 0:
                                    count_activity = PermanenceBoard.objects.filter(
                                        customer_id=customer.id, permanence_date__lt=now,
                                        permanence_date__gte=now - datetime.timedelta(
                                            days=float(repanier_settings['MAX_WEEK_WO_PARTICIPATION'])*7
                                        )
                                    ).count()
                                else:
                                    count_activity = None
                                html = render_to_string(
                                    'repanier/communication.html',
                                    {'permanence_boards': permanence_boards, 'count_activity': count_activity})
                                option_dict = {'id': "#communication", 'html': html}
                                to_json.append(option_dict)
                    else:
                        option_dict = {'id': "#may_not_order", 'html': '1'}
                        to_json.append(option_dict)
                else:
                    my_name = _not_lazy('Anonymous')
            else:
                customer = None
                my_name = _not_lazy('Anonymous')
            option_dict = {'id': "#my_name", 'html': my_name}
            to_json.append(option_dict)
            option_dict = {'id': "#my_basket", 'html': my_basket}
            to_json.append(option_dict)
            option_dict = {'id': "#prepared_amount", 'html': my_basket}
            to_json.append(option_dict)
            option_dict = {'id': "#prepared_amount_visible_xs", 'html': my_basket}
            to_json.append(option_dict)

            request_offer_items = request.GET.getlist('offer_item')
            for request_offer_item in request_offer_items:
                offer_item_id = sint(request_offer_item)
                if user.is_authenticated() and customer is not None and customer.may_order:
                    offer_item = OfferItem.objects.filter(id=offer_item_id)\
                        .order_by().first()
                    if offer_item is not None:
                        permanence = Permanence.objects.filter(id=offer_item.permanence_id)\
                            .only("status").order_by().first()
                        if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
                            purchase = PurchaseOpened.objects.filter(
                                offer_item_id=offer_item.id, customer_id=customer.id)\
                                .only("quantity_ordered").order_by().first()
                            if purchase is not None:
                                a_price = offer_item.customer_unit_price + offer_item.unit_deposit
                                if customer is not None and offer_item.vat_level in [VAT_200, VAT_300] and \
                                    customer.vat_id is not None and len(customer.vat_id) > 0:
                                    a_price += offer_item.compensation
                                q_order = purchase.quantity_ordered
                                if q_order <= 0:
                                    option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="0" selected>---</option>'}
                                    to_json.append(option_dict)
                                else:
                                    qty_display, price_display, base_unit, unit, price = get_display(
                                        q_order,
                                        offer_item.order_average_weight,
                                        offer_item.order_unit,
                                        a_price
                                    )
                                    option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="' + str(q_order) + '" selected>' + \
                                             qty_display + price_display + '&nbsp;&euro;</option>'}
                                    to_json.append(option_dict)
                            else:
                                option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="0" selected>---</option>'}
                                to_json.append(option_dict)
                        else:
                            option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="0" selected>---</option>'}
                            to_json.append(option_dict)
                    else:
                        option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="0" selected>---</option>'}
                        to_json.append(option_dict)
                else:
                    option_dict = {'id': "#offer_item" + str(offer_item_id), 'html': '<option value="0" selected>---</option>'}
                    to_json.append(option_dict)
        else:
            raise Http404
    else:
        raise Http404
    return HttpResponse(json.dumps(to_json), content_type="application/json")


@never_cache
def order_select_ajax(request):
    if request.is_ajax() and request.method == 'GET':
        # construct a list which will contain all of the data for the response
        user = request.user
        to_json = []
        if user.is_authenticated():
            # print("-----------------order_select_ajax------------------")
            customer = Customer.objects.filter(
                user_id=user.id, is_active=True, may_order=True)\
                .only("id", "vat_id").order_by().first()
            if customer is not None:
                # translation.activate(customer.language)
                offer_item_id = sint(request.GET.get('offer_item', 0))
                offer_item = OfferItem.objects.filter(id=offer_item_id, is_active=True)\
                    .order_by().first()
                if offer_item is not None:
                    permanence = Permanence.objects.filter(id=offer_item.permanence_id)\
                        .only("status").order_by().first()
                    if PERMANENCE_OPENED <= permanence.status <= PERMANENCE_SEND:
                        purchase = PurchaseOpened.objects.filter(
                            offer_item_id=offer_item.id, customer_id=customer.id)\
                            .only("quantity_ordered").order_by().first()
                        if purchase is not None:
                            q_previous_order = purchase.quantity_ordered
                        else:
                            q_previous_order = DECIMAL_ZERO
                        a_price = offer_item.customer_unit_price + offer_item.unit_deposit
                        if customer is not None and offer_item.vat_level in [VAT_200, VAT_300] and \
                            customer.vat_id is not None and len(customer.vat_id) > 0:
                            a_price += offer_item.compensation
                        # The q_order is either the purchased quantity or 0
                        q_min = offer_item.customer_minimum_order_quantity
                        if offer_item.limit_order_quantity_to_stock:
                            available = offer_item.stock - offer_item.quantity_invoiced + q_previous_order
                            q_alert = min(available, offer_item.customer_alert_order_quantity)
                            if q_alert < DECIMAL_ZERO:
                                q_alert = DECIMAL_ZERO
                        else:
                            q_alert = offer_item.customer_alert_order_quantity
                        q_step = offer_item.customer_increment_order_quantity
                        q_order_is_displayed = False
                        q_select_id = 0
                        selected = ""
                        if q_previous_order <= 0:
                            q_order_is_displayed = True
                            selected = "selected"
                        if (permanence.status == PERMANENCE_OPENED or
                                (permanence.status <= PERMANENCE_SEND and selected == "selected")):
                            option_dict = {'value': '0', 'selected': selected, 'label': '---'}
                            to_json.append(option_dict)

                        q_valid = q_min
                        q_counter = 0  # Limit to avoid too long selection list
                        while q_valid <= q_alert and q_counter <= 20:
                            q_select_id += 1
                            q_counter += 1
                            selected = ""
                            if not q_order_is_displayed:
                                if q_previous_order <= q_valid:
                                    q_order_is_displayed = True
                                    selected = "selected"
                            if (permanence.status == PERMANENCE_OPENED or
                                    (permanence.status <= PERMANENCE_SEND and selected == "selected")):
                                qty_display, price_display, base_unit, unit, price = get_display(
                                    q_valid,
                                    offer_item.order_average_weight,
                                    offer_item.order_unit,
                                    a_price
                                )
                                option_dict = {'value': str(q_select_id), 'selected': selected,
                                               'label': qty_display + price_display + '&nbsp;&euro;'}
                                to_json.append(option_dict)
                            if q_valid < q_step:
                                # 1; 2; 4; 6; 8 ... q_min = 1; q_step = 2
                                # 0,5; 1; 2; 3 ... q_min = 0,5; q_step = 1
                                q_valid = q_step
                            else:
                                # 1; 2; 3; 4 ... q_min = 1; q_step = 1
                                # 0,125; 0,175; 0,225 ... q_min = 0,125; q_step = 0,50
                                q_valid = q_valid + q_step

                        if not q_order_is_displayed:
                            # An custom order_qty > q_alert
                            q_select_id += 1
                            selected = "selected"
                            qty_display, price_display, base_unit, unit, price = get_display(
                                q_previous_order,
                                offer_item.order_average_weight,
                                a_price
                            )
                            option_dict = {'value': str(q_select_id), 'selected': selected,
                                           'label': qty_display + price_display + '&nbsp;&euro;'}
                            to_json.append(option_dict)
                        if permanence.status == PERMANENCE_OPENED:
                            # _not_lazy string are not placed in the "django.po"
                            # other = _("Other qty")
                            other = _not_lazy("Other qty")
                            option_dict = {'value': 'other_qty', 'selected': '', 'label': other}
                            to_json.append(option_dict)
                    else:
                        option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                        to_json.append(option_dict)
                else:
                    option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                    to_json.append(option_dict)
            else:
                option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
                to_json.append(option_dict)
            # else:
            #     option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
            #     to_json.append(option_dict)
        else:
            option_dict = {'value': '0', 'selected': 'selected', 'label': '---'}
            to_json.append(option_dict)
    else:
        raise Http404
    return HttpResponse(json.dumps(to_json), content_type="application/json")


class OrderView(ListView):
    template_name = 'repanier/order_form.html'
    success_url = '/'
    paginate_by = 14
    paginate_orphans = 5

    # def get_urls(self):
    # my_urls = patterns('',
    # url(r'^purchase_update/$', self.update, name='sortable_update'),
    # )
    # return my_urls + super(SortableAdminMixin, self).get_urls()

    def __init__(self, **kwargs):
        super(OrderView, self).__init__(**kwargs)
        self.user = None
        self.offeritem_id = 'all'
        self.producer_id = 'all'
        self.departementforcustomer_id = 'all'
        self.communication = 0
        self.q = None

    # @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        permanence_id = sint(self.args[0])
        self.permanence = Permanence.objects.filter(id=permanence_id).only("id", "status").order_by().first()
        self.user = request.user
        self.offeritem_id = self.request.GET.get('offeritem', 'all')
        if self.offeritem_id not in ['all', 'purchased']:
            self.offeritem_id = sint(self.offeritem_id)
        self.producer_id = self.request.GET.get('producer', 'all')
        if self.producer_id != 'all':
            self.producer_id = sint(self.producer_id)
        self.departementforcustomer_id = self.request.GET.get('departementforcustomer', 'all')
        if self.departementforcustomer_id != 'all':
            self.departementforcustomer_id = sint(self.departementforcustomer_id)
        self.communication = 0
        if self.user.is_authenticated():
            self.q = self.request.GET.get('q', None)
            if self.q == '':
                self.q = None
        else:
            self.q = None
        if self.producer_id == 'all' and self.departementforcustomer_id == 'all' \
                and self.offeritem_id == 'all' and 'page' not in request.GET \
                and self.q is None:
            # This to let display a communication into a popup when the user is on the first order screen
            self.communication = 1
        # print("----------------------- q1 : %s" % self.q)
        return super(OrderView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)
        context['permanence'] = self.permanence
        if self.permanence is not None and self.permanence.status == PERMANENCE_OPENED:
            context['display_all_product_button'] = "Ok"
        if repanier_settings['DISPLAY_PRODUCERS_ON_ORDER_FORM']:
            producer_set = Producer.objects.filter(permanence=self.permanence.id).only("id", "short_profile_name")
        else:
            producer_set = None
        context['producer_set'] = producer_set
        # use of str() to avoid "12 345" when rendering the template
        context['producer_id'] = str(self.producer_id)
        if self.producer_id == 'all':
            departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                offeritem__permanence_id=self.permanence.id,
                offeritem__order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT)\
                .order_by("tree_id", "lft")\
                .distinct("id", "tree_id", "lft")
                # .only("id", "parent", "parent__level", "parent__short_name", "parent__level", "parent__short_name")\
        else:
            departementforcustomer_set = LUT_DepartmentForCustomer.objects.filter(
                offeritem__producer_id=self.producer_id,
                offeritem__permanence_id=self.permanence.id,
                offeritem__order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT)\
                .order_by("tree_id", "lft")\
                .distinct("id", "tree_id", "lft")
                # .only("id", "parent", "parent__level", "parent__short_name", "parent__level", "parent__short_name")\
        context['departementforcustomer_set'] = departementforcustomer_set
        # use of str() to avoid "12 345" when rendering the template
        context['departementforcustomer_id'] = str(self.departementforcustomer_id)
        context['offeritem_id'] = self.offeritem_id
        # context['prepared_amount'] = get_user_order_amount(self.permanence.id,
        #                                                    user=self.user)
        context['staff_order'] = Staff.objects.filter(is_reply_to_order_email=True)\
            .only("long_name", "customer_responsible__long_basket_name", "customer_responsible__phone1",
                  "user__email")\
            .order_by().first()
        context['communication'] = self.communication
        context['q'] = self.q
        context['anonymous_basket'] = "0"
        return context

    def get_queryset(self):
        qs = OfferItem.objects.none()
        if self.permanence is not None:
            if PERMANENCE_OPENED <= self.permanence.status <= PERMANENCE_SEND:
                qs = OfferItem.objects.filter(permanence_id=self.permanence.id, is_active=True)
                if self.permanence.status == PERMANENCE_OPENED or self.user.is_anonymous():
                    # Don't display technical products.
                    qs = qs.filter(order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT)
                if self.producer_id != 'all':
                    qs = qs.filter(producer_id=self.producer_id)
                if self.offeritem_id == 'purchased':
                    # display only purchased product. Must arrive here via OrderViewWithoutCache
                    if self.user.is_authenticated():
                        qs = qs.filter(purchase__customer__user=self.user,
                                       purchase__quantity_ordered__gt=0)
                if self.departementforcustomer_id != 'all':
                    department = LUT_DepartmentForCustomer.objects.filter(
                        id=self.departementforcustomer_id
                        ).order_by().only("lft", "rght", "tree_id").first()
                    if department is not None:
                        tmp_qs = qs.filter(department_for_customer__lft__gte=department.lft,
                                       department_for_customer__rght__lte=department.rght,
                                       department_for_customer__tree_id=department.tree_id)
                        if tmp_qs.exists():
                            # Restrict to this department only if no product exists in it
                            qs = tmp_qs
                        else:
                            # otherwise, act like self.departementforcustomer_id == 'all'
                            self.departementforcustomer_id = 'all'
                qs = qs.filter(translations__language_code=translation.get_language(),
                               department_for_customer__translations__language_code=translation.get_language()
                ).order_by(
                    "translations__order_sort_order"
                )
                # print("---------------")
                # print qs.query
                # print("---------------")
            else:
                self.permanence = None
        # print("----------------------- q2 : %s" % self.q)
        if self.permanence is not None:
            if self.q is not None:
                return qs.filter(
                    translations__language_code=translation.get_language(),
                    translations__long_name__icontains=self.q)
            else:
                return qs
        else:
            raise Http404


class OrderViewWithoutCache(OrderView):
    # @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        return super(OrderViewWithoutCache, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrderViewWithoutCache, self).get_context_data(**kwargs)
        if self.request.user.is_anonymous():
            context['anonymous_basket'] = "1"
        return context

    def get_queryset(self):
        if not repanier_settings['DISPLAY_ANONYMOUS_ORDER_FORM']:
            return OfferItem.objects.none()
        else:
            if not self.user.is_authenticated() and self.offeritem_id is not None and self.offeritem_id == 'purchased':
                return OfferItem.objects.none()
            else:
                return super(OrderViewWithoutCache, self).get_queryset()


@login_required()
# @never_cache
def permanence_form_ajax(request):
    if request.is_ajax() and request.method == 'GET':
        result = "ko"
        p_permanence_board_id = None
        if 'permanence_board' in request.GET:
            p_permanence_board_id = request.GET['permanence_board']
        p_value_id = None
        if 'value' in request.GET:
            p_value_id = request.GET['value']
        if p_permanence_board_id and p_value_id and request.user.customer.may_order:
            if p_value_id == '0':
                row_counter = PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer_id=request.user.customer.id,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                ).update(
                    customer=None
                )
            else:
                row_counter = PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer__isnull=True,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_SEND
                ).update(
                    customer=request.user.customer.id
                )
            if row_counter > 0:
                result = "ok"
        return HttpResponse(result)
    raise Http404


class PermanenceView(ListView):
    template_name = 'repanier/permanence_form.html'
    success_url = '/thanks/'
    paginate_by = 50
    paginate_orphans = 5

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        # Here via a form or via Ajax we modifiy the qty
        p_permanence_board_id = None
        if 'permanence_board' in request.GET:
            p_permanence_board_id = request.GET['permanence_board']
        p_value_id = None
        if 'value' in request.GET:
            p_value_id = request.GET['value']
        if p_permanence_board_id and p_value_id and request.user.customer.may_order:
            if p_value_id == '0':
                PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer_id=request.user.customer.id,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
                ).update(
                    customer=None
                )
            else:
                PermanenceBoard.objects.filter(
                    id=p_permanence_board_id,
                    customer__isnull=True,
                    permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
                ).update(
                    customer=request.user.customer.id
                )
        return super(PermanenceView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        # now = datetime.datetime.utcnow().replace(tzinfo=utc)
        qs = PermanenceBoard.objects.filter(
            # permanence_date__gte=now,
            permanence__status__lte=PERMANENCE_WAIT_FOR_DONE
        ).order_by(
            "permanence_date", "permanence",
            "permanence_role__tree_id",
            "permanence_role__lft"
        )
        return qs


class CustomerInvoiceView(DetailView):
    template_name = 'repanier/customer_invoice_form.html'
    model = CustomerInvoice

    def get_context_data(self, **kwargs):
        context = super(CustomerInvoiceView, self).get_context_data(**kwargs)
        customer_invoice = self.get_object()
        if customer_invoice:
            bank_account_set = BankAccount.objects.filter(customer_invoice=customer_invoice)
            context['bank_account_set'] = bank_account_set
            context['DISPLAY_VAT'] = repanier_settings['DISPLAY_VAT']
            if repanier_settings['DISPLAY_PRODUCERS_ON_ORDER_FORM']:
                context['DISPLAY_PRODUCERS_ON_ORDER_FORM'] = True
                purchase_set = PurchaseClosed.objects.filter(
                    Q(customer_invoice=customer_invoice, quantity_invoiced__gt=DECIMAL_ZERO, offer_item__translations__language_code=translation.get_language()) |
                    Q(customer_invoice=customer_invoice, comment__gt="", offer_item__translations__language_code=translation.get_language())
                ).order_by("producer", "offer_item__translations__order_sort_order")
            else:
                context['DISPLAY_PRODUCERS_ON_ORDER_FORM'] = False
                purchase_set = PurchaseClosed.objects.filter(
                    Q(customer_invoice=customer_invoice, quantity_invoiced__gt=DECIMAL_ZERO, offer_item__translations__language_code=translation.get_language()) |
                    Q(customer_invoice=customer_invoice, comment__gt="", offer_item__translations__language_code=translation.get_language())
                ).order_by("offer_item__translations__order_sort_order")
            context['purchase_set'] = purchase_set
            previous_customer_invoice = CustomerInvoice.objects.filter(
                customer_id=customer_invoice.customer_id,
                invoice_sort_order__isnull=False,
                invoice_sort_order__lt=customer_invoice.invoice_sort_order)\
                .order_by('-invoice_sort_order').only("id").first()
            if previous_customer_invoice is not None:
                context['previous_customer_invoice_id'] = previous_customer_invoice.id
            next_customer_invoice = CustomerInvoice.objects.filter(
                customer_id=customer_invoice.customer_id,
                invoice_sort_order__isnull=False,
                invoice_sort_order__gt=customer_invoice.invoice_sort_order)\
                .order_by('invoice_sort_order').only("id").first()
            if next_customer_invoice is not None:
                context['next_customer_invoice_id'] = next_customer_invoice.id
        return context

    def get_queryset(self):
        # qs = CustomerInvoice.objects.none()
        pk = self.kwargs.get('pk', None)
        if self.request.user.is_staff:
            if (pk is None) or (pk == '0'):
                customer_id = self.request.GET.get('customer', None)
                last_customer_invoice = CustomerInvoice.objects.filter(
                    customer_id=customer_id, invoice_sort_order__isnull=False
                ).only("id").order_by('-invoice_sort_order').first()
                if last_customer_invoice is not None:
                    self.kwargs['pk'] = last_customer_invoice.id
            return CustomerInvoice.objects.all()
        else:
            if (pk is None) or (pk == '0'):
                last_customer_invoice = CustomerInvoice.objects.filter(
                    customer__user_id=self.request.user.id,
                    invoice_sort_order__isnull=False
                ).only("id").order_by('-invoice_sort_order').first()
                if last_customer_invoice is not None:
                    self.kwargs['pk'] = last_customer_invoice.id

            return CustomerInvoice.objects.filter(customer__user_id=self.request.user.id)


class ProducerInvoiceView(DetailView):
    template_name = 'repanier/producer_invoice_form.html'
    model = ProducerInvoice
    uuid = None

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        return super(ProducerInvoiceView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProducerInvoiceView, self).get_context_data(**kwargs)
        producer_invoice = self.get_object()
        if producer_invoice:
            bank_account_set = BankAccount.objects.filter(producer_invoice=producer_invoice)
            context['bank_account_set'] = bank_account_set
            offer_item_set = OfferItem.objects.filter(
                permanence_id=producer_invoice.permanence_id,
                producer_id=producer_invoice.producer_id,
                translations__language_code=translation.get_language()
            ).exclude(
                quantity_invoiced=DECIMAL_ZERO
            ).order_by(
                "translations__order_sort_order"
            ).distinct()
            context['offer_item_set'] = offer_item_set
            previous_producer_invoice = ProducerInvoice.objects.filter(
                producer_id=producer_invoice.producer_id,
                invoice_sort_order__isnull=False,
                invoice_sort_order__lt=producer_invoice.invoice_sort_order)\
                .order_by('-invoice_sort_order').only("id").first()
            if previous_producer_invoice is not None:
                context['previous_producer_invoice_id'] = previous_producer_invoice.id
            next_producer_invoice = ProducerInvoice.objects.filter(
                producer_id=producer_invoice.producer_id,
                invoice_sort_order__isnull=False,
                invoice_sort_order__gt=producer_invoice.invoice_sort_order)\
                .order_by('invoice_sort_order').only("id").first()
            if next_producer_invoice is not None:
                context['next_producer_invoice_id'] = next_producer_invoice.id
            context['uuid'] = self.uuid
        return context

    def get_queryset(self):
        self.uuid = None
        if self.request.user.is_staff:
            producer_id = self.request.GET.get('producer', None)
        else:
            self.uuid = self.kwargs.get('uuid', None)
            if self.uuid:
                try:
                    producer = Producer.objects.filter(uuid=self.uuid).order_by().first()
                    producer_id = producer.id
                except:
                    raise PermissionDenied
            else:
                return ProducerInvoice.objects.none()
        pk = self.kwargs.get('pk', None)
        if (pk is None) or (pk == '0'):
            last_producer_invoice = ProducerInvoice.objects.filter(
                producer_id=producer_id, invoice_sort_order__isnull=False
            ).only("id").order_by("-invoice_sort_order").first()
            if last_producer_invoice is not None:
                self.kwargs['pk'] = last_producer_invoice.id
        return ProducerInvoice.objects.filter(producer_id=producer_id)


class PreOrderView(DetailView):
    template_name = 'repanier/pre_order_form.html'
    model = Permanence
    producer = None

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        self.producer = None
        if request.user.is_staff:
            producer_id = request.GET.get('producer', None)
            if producer_id is not None:
                producer = Producer.objects.filter(
                    id=producer_id
                ).order_by().only("id").first()
                if producer is None:
                    raise PermissionDenied
                else:
                    self.producer = producer
            else:
                raise PermissionDenied
        else:
            offer_uuid = kwargs.get('offer_uuid', None)
            if offer_uuid is not None:
                producer = Producer.objects.filter(
                    offer_uuid=offer_uuid
                ).order_by().only("id").first()
                if producer is None:
                    raise PermissionDenied
                else:
                    self.producer = producer
            else:
                raise PermissionDenied

        return super(PreOrderView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PreOrderView, self).get_context_data(**kwargs)
        permanence_pre_opened = self.get_object()
        if permanence_pre_opened is not None:
            offer_item_set = OfferItem.objects.filter(
                Q(
                    producer_id=self.producer,
                ) |
                Q(
                    stock__gt=DECIMAL_ZERO,
                ),
                permanence_id=permanence_pre_opened.id,
                translations__language_code=translation.get_language(),
                producer_price_are_wo_vat=True,
                is_active=True
            ).order_by(
                "translations__long_name"
            ).distinct()
            context['offer_item_set'] = offer_item_set
            context['producer'] = self.producer
        return context

    def get_queryset(self):
        pk = self.kwargs.get('pk', None)
        if (pk is None) or (pk == '0'):
            permanence_pre_opened = Permanence.objects.filter(
                status=PERMANENCE_PRE_OPEN
            ).order_by("-is_updated_on").only("id").first()
            if permanence_pre_opened is not None:
                self.kwargs['pk'] = permanence_pre_opened.id
        return Permanence.objects.all()