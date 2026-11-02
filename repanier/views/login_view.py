from cms.utils.conf import get_cms_setting
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from repanier.auth_backend import RepanierAuthBackend
from repanier.const import EMPTY_STRING
from repanier.models.staff import Staff
from repanier.tools import sint, get_repanier_template_name


def _get_redirect_response(redirect_to, request):
    """
    Construit la réponse de redirection en gérant l'activation de la barre d'outils CMS (v3 ou v4).
    """
    # Empêche toute boucle de redirection ou autoréférence anormale
    if not redirect_to or "go_repanier" in redirect_to or redirect_to.count("next=") > 1:
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

    if not url_has_allowed_host_and_scheme(url=redirect_to, allowed_hosts={request.get_host()}):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

    if request.user.is_superuser:
        toolbar_param = get_cms_setting("CMS_TOOLBAR_URL__EDIT_ON")
    else:
        # Essai de repli pour CMS version 4 ou standard
        try:
            toolbar_param = get_cms_setting("CMS_TOOLBAR_URL__EDIT_ON")
        except Exception:
            toolbar_param = get_cms_setting("CMS_TOOLBAR_URL__ENABLE")

    return HttpResponseRedirect(f"{redirect_to}?{toolbar_param}")


@sensitive_post_parameters()
@csrf_protect
@never_cache
def login_view(
    request,
    redirect_field_name=REDIRECT_FIELD_NAME,
    authentication_form=AuthenticationForm,
    extra_context=None,
):
    """
    Displays the login form and handles the login action.
    """
    template_name = get_repanier_template_name("registration/login.html")
    redirect_to = request.POST.get(
        redirect_field_name, request.GET.get(redirect_field_name, EMPTY_STRING)
    )

    # Validation initiale et sécurisation de l'URL cible
    if not redirect_to or "go_repanier" in redirect_to or redirect_to.count("next=") > 1:
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

    if not url_has_allowed_host_and_scheme(url=redirect_to, allowed_hosts={request.get_host()}):
        redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

    staff_responsibilities = None
    user = request.user

    if request.method == "POST":
        form = authentication_form(request, data=request.POST)

        if form.is_valid():
            auth_login(request, form.get_user())
            user = request.user

            if user.is_authenticated:
                staff_qs = Staff.objects.filter(
                    customer_responsible_id=user.customer_id, is_active=True
                )
                if not staff_qs.exists():
                    return HttpResponseRedirect(redirect_to)

                staff_responsibilities = staff_qs.all()

    else:
        if user.is_authenticated:
            as_staff_id = sint(request.GET.get("as_id", 0))

            if as_staff_id == 0:
                if user.is_superuser:
                    return _get_redirect_response(redirect_to, request)
                return HttpResponseRedirect(redirect_to)

            as_staff = Staff.objects.filter(
                id=as_staff_id,
                customer_responsible_id=user.customer_id,
                is_active=True,
            ).first()

            if as_staff is None:
                return HttpResponseRedirect(redirect_to)

            RepanierAuthBackend.set_staff_right(
                request=request, user=user, as_staff=as_staff
            )
            return _get_redirect_response(redirect_to, request)

    form = authentication_form(request)

    if user.is_anonymous:
        from repanier.apps import REPANIER_SETTINGS_CONFIG

        how_to_register = REPANIER_SETTINGS_CONFIG.how_to_register_v2
    else:
        how_to_register = EMPTY_STRING

    context = {
        "form": form,
        redirect_field_name: redirect_to,
        "how_to_register": how_to_register,
        "staff_responsibilities": staff_responsibilities,
    }
    if extra_context is not None:
        context.update(extra_context)

    return TemplateResponse(request, template_name, context)