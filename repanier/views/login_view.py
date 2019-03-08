# -*- coding: utf-8
from cms.utils.conf import get_cms_setting
from django.conf import settings
from django.contrib.auth import (REDIRECT_FIELD_NAME, login as auth_login)
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils.http import is_safe_url
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from repanier.auth_backend import RepanierAuthBackend
from repanier.const import EMPTY_STRING
from repanier.models.staff import Staff
from repanier.tools import sint, get_repanier_template_name


@sensitive_post_parameters()
@csrf_protect
@never_cache
def login_view(request, template_name=EMPTY_STRING,
               redirect_field_name=REDIRECT_FIELD_NAME,
               authentication_form=AuthenticationForm,
               extra_context=None):
    """
    Displays the login form and handles the login action.
    """
    template_name = get_repanier_template_name('registration/login.html')
    redirect_to = request.POST.get(
        redirect_field_name,
        request.GET.get(redirect_field_name, EMPTY_STRING)
    )
    # Ensure the user-originating redirection url is safe.
    if not is_safe_url(url=redirect_to, allowed_hosts=request.get_host()):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

    staff_responsibilities = None
    user = request.user

    if request.method == "POST":
        form = authentication_form(request, data=request.POST)

        if form.is_valid():
            # Okay, security check complete. Log the user in.
            auth_login(request, form.get_user())

            # Now the logged in user is set in request.user
            user = request.user

            if user.is_authenticated:

                if user.is_staff:
                    return HttpResponseRedirect(
                        "{}?{}".format(redirect_to, get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON')))

                staff_qs = Staff.objects.filter(
                    customer_responsible_id=user.customer_id,
                    is_active=True
                ).order_by('?')
                may_become_a_staff_user = staff_qs.exists()

                if not may_become_a_staff_user:
                    return HttpResponseRedirect(redirect_to)

                # Ask the user to log in as a customer or as a staff member
                staff_responsibilities = staff_qs.all()

    else:
        if user.is_authenticated:
            as_staff_id = sint(request.GET.get('as_id', 0))

            if as_staff_id == 0:
                if user.is_superuser:
                    return HttpResponseRedirect(
                        "{}?{}".format(redirect_to, get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON')))
                else:
                    # The user want to be logged in as a customer
                    return HttpResponseRedirect(redirect_to)

            as_staff = Staff.objects.filter(
                id=as_staff_id,
                customer_responsible_id=user.customer_id,
                is_active=True
            ).order_by('?').first()

            if as_staff is None:
                # This should not occurs
                # But if ... then log the user as a customer
                return HttpResponseRedirect(redirect_to)

            RepanierAuthBackend.set_staff_right(
                request=request,
                user=user,
                as_staff=as_staff
            )
            return HttpResponseRedirect("{}?{}".format(redirect_to, get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON')))

    form = authentication_form(request)

    if user.is_anonymous:
        from repanier.apps import REPANIER_SETTINGS_CONFIG

        how_to_register = REPANIER_SETTINGS_CONFIG.safe_translation_getter(
            'how_to_register', any_language=True, default=EMPTY_STRING)
    else:
        how_to_register = EMPTY_STRING

    context = {
        'form': form,
        redirect_field_name: redirect_to,
        'how_to_register': how_to_register,
        'staff_responsibilities': staff_responsibilities,
    }
    if extra_context is not None:
        context.update(extra_context)
    return TemplateResponse(request, template_name, context)
