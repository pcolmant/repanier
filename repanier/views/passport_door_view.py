# The login door of the passport: three views, one dance. A member
# logged out everywhere still owns his password on his home site; the
# dance asks the home site to vouch for him, the browser carrying
# only short lived signed tokens - the password itself never leaves
# the home site and never travels through a browser.

# - passport_request_view (on the target site): a small form - the
#   e-mail of the member, his home site chosen among the mirror
#   groups which accept the passport members here - then the browser
#   leaves for the login page of that home site;
# - passport_login_view (on the home site): the classical sign in of
#   the home site, or the session the member still owns there. The
#   vouching token carries the e-mail the home site authenticated
#   and the subdomain of the home site, and lives one minute;
# - passport_arrive_view (on the target site): the token verified,
#   the member arrives exactly like a passport arrival - his local
#   session when the account exists, the family enrolment on the
#   profile of his home site when it does not. Any refusal stays
#   silent: the member falls back on the classical sign in.

import logging

from django import forms
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from repanier.const import EMPTY_STRING
from repanier.middleware import (
    _attach_passport_group,
    _enrol_passport_member,
    _is_passport_host,
    _passport_origin,
    _passport_user,
)
from repanier.passport_login import (
    append_query_parameter,
    build_passport_login_token,
    family_return_url,
    read_passport_login_token,
)
from repanier.passport_network import SUBDOMAIN_PATTERN

passport_logger = logging.getLogger("repanier.passport")

TEMPLATES = "repanier/registration/{}"

# The choice which brings a member without a home site back to the
# classical sign in of this site. It never matches a mirror: the
# underscore cannot be a subdomain.
NO_HOME = "no_home"


def _login_url():
    return reverse("repanier:login_form")


def _mirror_choices(request):
    """The home sites this site may send a member to: the subdomains
    its accepting mirror groups wear, never its own - coming home
    needs no door."""
    from repanier.models.customer import Customer

    own = _passport_origin(request).lower()
    choices = []
    for group in Customer.objects.filter(
        is_group=True,
        is_active=True,
        accepts_passport_members=True,
    ).only("short_basket_name"):
        home = (group.short_basket_name or EMPTY_STRING).strip().lower()
        if home and home != own and SUBDOMAIN_PATTERN.match(home):
            choices.append((home, home))
    return sorted(set(choices))


class PassportRequestForm(forms.Form):
    email = forms.EmailField(
        label=_("E-mail address"),
        widget=forms.EmailInput(attrs={"autofocus": "autofocus"}),
    )
    home = forms.ChoiceField(
        label=_("Your home site"),
        error_messages={
            # The home comes back chosen by the member, but the
            # authority stays server side: the error says it.
            "invalid_choice": _("Choose your home site in the list.")
        },
    )

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop("choices", [])
        super().__init__(*args, **kwargs)
        # The screen opens on the pale choice: nothing leaves until
        # the member chose a home site, and the member without a
        # home site finds the way out right under it.
        self.fields["home"].choices = (
            [(EMPTY_STRING, _("Choose your home site"))]
            + [(NO_HOME, _("I have no home site"))]
            + list(choices)
        )


@sensitive_post_parameters()
@csrf_protect
@never_cache
def passport_request_view(request):
    """On the target site: pick the member who signs in elsewhere,
    then send his browser to the login page of his home site."""
    if not _is_passport_host(request):
        # A site on its own domain keeps the classical sign in.
        return HttpResponseRedirect(_login_url())
    choices = _mirror_choices(request)
    if not choices:
        # Nobody accepts the passport members here: no door to open.
        return HttpResponseRedirect(_login_url())
    if request.method == "POST":
        # The member without a home site goes back to the classical
        # sign in whatever the rest of the form says: his e-mail
        # belongs to the door he is leaving, the form must not ask
        # for it once he said he has no home site.
        if request.POST.get("home") == NO_HOME:
            return HttpResponseRedirect(_login_url())
        form = PassportRequestForm(request.POST, choices=choices)
        if form.is_valid():
            home = form.cleaned_data["home"]
            email = form.cleaned_data["email"].strip().lower()
            arrive_url = request.build_absolute_uri(
                reverse("passport_arrive")
            )
            login_url = "https://{}.repanier.be{}".format(
                home,
                reverse("passport_login"),
            )
            login_url = append_query_parameter(login_url, "next", arrive_url)
            login_url = append_query_parameter(login_url, "email", email)
            passport_logger.info(
                "repanier passport : {} asks for the door of [{}]".format(
                    email, home
                )
            )
            return HttpResponseRedirect(login_url)
    else:
        form = PassportRequestForm(choices=choices)
    context = {
        "form": form,
        "next": request.GET.get("next", EMPTY_STRING),
        "no_home": NO_HOME,
    }
    return TemplateResponse(
        request, TEMPLATES.format("passport_request.html"), context
    )


@sensitive_post_parameters()
@csrf_protect
@never_cache
def passport_login_view(request):
    """On the home site: the member signs in here - or reuses the
    session he still owns - and the site stamps the vouching token
    for the target site which asked for him."""
    if not _is_passport_host(request):
        return HttpResponseRedirect(_login_url())
    if request.method == "POST":
        next_url = family_return_url(request.POST.get("next", EMPTY_STRING))
        form = AuthenticationForm(request, data=request.POST)
    else:
        next_url = family_return_url(request.GET.get("next", EMPTY_STRING))
        form = AuthenticationForm(request)
        form.initial["username"] = request.GET.get("email", EMPTY_STRING)
        if (
            next_url
            and request.user.is_authenticated
            and not request.user.is_superuser
            and not request.user.is_staff
        ):
            email = (
                request.user.email or EMPTY_STRING
            ).strip().lower()
            token = build_passport_login_token(email, _passport_origin(request))
            if token:
                passport_logger.info(
                    "repanier passport : {} vouched for by his session"
                    " for the door of a family site".format(email)
                )
                return HttpResponseRedirect(
                    append_query_parameter(next_url, "token", token)
                )
    if not next_url:
        # The return target is not a family site: the dance goes
        # nowhere, the member falls back on the classical sign in.
        return HttpResponseRedirect(_login_url())
    if form.is_valid():
        user = form.get_user()
        auth_login(request, user)
        email = (user.email or EMPTY_STRING).strip().lower()
        token = build_passport_login_token(email, _passport_origin(request))
        if token is None:
            # A home site which cannot name itself vouches for
            # nobody: the member keeps his local session here.
            return HttpResponseRedirect(_login_url())
        passport_logger.info(
            "repanier passport : {} signed in on his home site for the"
            " door of a family site".format(email)
        )
        return HttpResponseRedirect(
            append_query_parameter(next_url, "token", token)
        )
    context = {
        "form": form,
        "next": next_url,
        "username_initial": (request.POST if request.method == "POST" else request.GET).get(
            "username" if request.method == "POST" else "email",
            EMPTY_STRING,
        ),
    }
    return TemplateResponse(
        request, TEMPLATES.format("passport_login.html"), context
    )


@never_cache
def passport_arrive_view(request):
    """On the target site: the token of a home site opens the door
    like a passport arrival - the local session of an existing
    account, or the family enrolment. Everything else stays silent:
    the member falls back on the classical sign in."""
    if not _is_passport_host(request):
        return HttpResponseRedirect(_login_url())
    token = request.GET.get("token", EMPTY_STRING)
    arrived = read_passport_login_token(token)
    if arrived is None:
        return HttpResponseRedirect(_login_url())
    email, origin = arrived
    if origin == _passport_origin(request).lower():
        # The home site IS this site: the cookie alone opens the
        # door, the dance never loops on itself.
        return HttpResponseRedirect(_login_url())
    user = _passport_user(email)
    if user is None:
        user = _enrol_passport_member(request, email, origin)
    if user is None:
        # Nothing opens for this member here: the classical sign in
        # keeps saying it its own way.
        return HttpResponseRedirect(_login_url())
    user.backend = "repanier.auth_backend.RepanierAuthBackend"
    auth_login(request, user)
    _attach_passport_group(request, user, origin)
    passport_logger.info(
        "repanier passport : {} opened the door of [{}] with his home"
        " password".format(email, _passport_origin(request))
    )
    return HttpResponseRedirect(resolve_url(settings.LOGIN_REDIRECT_URL))
