# -*- coding: utf-8

from django.contrib.auth import (REDIRECT_FIELD_NAME, logout as auth_logout)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.signals import user_logged_out
from django.contrib.sites.shortcuts import get_current_site
from django.dispatch import receiver
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils.http import is_safe_url
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier.models.customer import Customer


@login_required()
@csrf_protect
@never_cache
def logout_view(request, next_page=None,
                template_name='repanier/registration/logged_out.html',
                redirect_field_name=REDIRECT_FIELD_NAME,
                extra_context=None):
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

    return TemplateResponse(request, template_name, context)


def remove_staff_right(user, is_customer=False):
    is_customer = is_customer or Customer.objects.filter(user_id=user.id).exists()
    if is_customer and user.is_staff:
        Customer.objects.filter(user_id=user.id).order_by('?').update(as_staff=None)
        user.is_staff = False
        user.groups.clear()
        user.save()


@receiver(user_logged_out)
def receiver_user_logged_out(sender, request, user, **kwargs):
    remove_staff_right(user)
