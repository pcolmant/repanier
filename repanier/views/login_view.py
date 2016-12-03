# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import (REDIRECT_FIELD_NAME, login as auth_login)
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils.http import is_safe_url
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from forms import AuthRepanierLoginForm
from repanier.const import EMPTY_STRING


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
    redirect_to = request.POST.get(redirect_field_name,
                                   request.GET.get(redirect_field_name, EMPTY_STRING))

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
        'form'             : form,
        redirect_field_name: redirect_to,
        'site'             : current_site,
        'site_name'        : current_site.name,
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context)
