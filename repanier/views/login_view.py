# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import (REDIRECT_FIELD_NAME, login as auth_login, logout as auth_logout)
from django.contrib.auth.models import Group
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils.http import is_safe_url
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from repanier.views.forms import AuthRepanierLoginForm
from repanier.models.staff import Staff
from repanier.const import EMPTY_STRING, ORDER_GROUP, INVOICE_GROUP, WEBMASTER_GROUP, CONTRIBUTOR_GROUP, \
    COORDINATION_GROUP


@sensitive_post_parameters()
@csrf_protect
@never_cache
def login_view(request, template_name='repanier/registration/login.html',
               redirect_field_name=REDIRECT_FIELD_NAME,
               authentication_form=AuthRepanierLoginForm,
               current_app=None, extra_context=None):
    """
    Displays the login form and handles the login action.
    """
    from repanier.apps import REPANIER_SETTINGS_CONFIG
    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, EMPTY_STRING))
    staff_responsibilities = None
    how_to_register = EMPTY_STRING

    if request.method == "GET" and request.user.is_authenticated:
        as_id = request.GET.get('as_id', None)
        if request.user.is_staff:
            as_staff = None
        else:
            as_staff = Staff.objects.filter(
                id=as_id,
                customer_responsible_id=request.user.customer.id,
                is_active=True
            ).order_by('?').first()
        # Ensure the user-originating redirection url is safe.
        if as_staff is None or not is_safe_url(url=redirect_to, host=request.get_host()):
            redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

        if as_staff is not None:
            user = request.user
            auth_logout(request)
            user.is_staff = True
            user.groups.clear()
            if as_staff.is_reply_to_order_email:
                group_id = Group.objects.filter(name=ORDER_GROUP).first()
                user.groups.add(group_id)
            if as_staff.is_reply_to_invoice_email:
                group_id = Group.objects.filter(name=INVOICE_GROUP).first()
                user.groups.add(group_id)
            if as_staff.is_webmaster:
                group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
                user.groups.add(group_id)
            if as_staff.is_contributor:
                group_id = Group.objects.filter(name=CONTRIBUTOR_GROUP).first()
                user.groups.add(group_id)
            if as_staff.is_coordinator:
                group_id = Group.objects.filter(name=COORDINATION_GROUP).first()
                user.groups.add(group_id)
            user.save()
            auth_login(request, user)
        return HttpResponseRedirect(redirect_to)
    elif request.method == "POST":
        form = authentication_form(request, data=request.POST)
        if form.is_valid():

            # Ensure the user-originating redirection url is safe.
            if not is_safe_url(url=redirect_to, host=request.get_host()):
                redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

            # Okay, security check complete. Log the user in.
            auth_login(request, form.get_user())
            if request.user.is_staff:
                may_become_a_staff_user = False
            else:
                may_become_a_staff_user = Staff.objects.filter(
                    customer_responsible_id=request.user.customer.id,
                    is_active=True
                ).order_by('?').exists()
            if may_become_a_staff_user:
                # Ask the user to log in as a customer or as a staff member
                staff_responsibilities = Staff.objects.filter(
                    customer_responsible_id=request.user.customer.id,
                    is_active=True
                ).all()
            else:
                return HttpResponseRedirect(redirect_to)
    else:
        form = authentication_form(request)
        try:
            how_to_register = REPANIER_SETTINGS_CONFIG.safe_translation_getter(
                'how_to_register', any_language=True, default=EMPTY_STRING)
        except:
            how_to_register = EMPTY_STRING

    current_site = get_current_site(request)

    context = {
        'form'             : form,
        redirect_field_name: redirect_to,
        'site'             : current_site,
        'site_name'        : current_site.name,
        'how_to_register'  : how_to_register,
        'staff_responsibilities': staff_responsibilities
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context)
