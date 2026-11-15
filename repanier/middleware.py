import logging
import re
import threading
from urllib.parse import parse_qsl

from django.http import HttpResponseBadRequest, QueryDict
from django.utils.http import urlencode

threading_local = threading.local()

# Expression régulière pré-compilée pour détecter les boucles de redirection (ex: go_repanier en boucle ou empilement de next=)
REDIRECT_LOOP_PATTERN = re.compile(r"go_repanier|next=.*next=|%2Fgo_repanier", re.IGNORECASE)


def _set_request(request):
    threading_local.repanier_request = request


def get_request():
    return getattr(threading_local, "repanier_request", None)


def set_threading_local(name, value):
    repanier_local = getattr(threading_local, "repanier_local", None)
    if repanier_local is None:
        threading_local.repanier_local = {}
    threading_local.repanier_local[name] = value


def get_threading_local(name, default_value=None):
    repanier_local = getattr(threading_local, "repanier_local", {})
    return repanier_local.get(name, default_value)


def _set_filters(request):
    qs = request.META["QUERY_STRING"]
    if qs:
        if "_changelist_filters=" in qs:
            query_dict = QueryDict(qs)
            repanier_filters = query_dict["_changelist_filters"]
        else:
            repanier_filters = qs
    else:
        repanier_filters = ""
    threading_local.repanier_filters = repanier_filters


def _get_filters():
    return getattr(threading_local, "repanier_filters", "")


def get_preserved_filters():
    filters = _get_filters()
    return urlencode({"_changelist_filters": filters}) if filters else ""


def get_preserved_filters_as_dict():
    filters_as_dict = QueryDict(_get_filters(), mutable=True)
    return filters_as_dict


def get_preserved_filters_from_dict(filters_as_dict):
    return (
        urlencode({"_changelist_filters": filters_as_dict.urlencode()})
        if filters_as_dict
        else ""
    )


def get_query_preserved_filters():
    filters = get_preserved_filters()
    return "?{}".format(filters) if filters else ""


def get_query_filters():
    filters = _get_filters()
    return "?{}".format(filters) if filters else ""


def add_filter(path):
    return "{}{}".format(path, get_query_preserved_filters())


def get_request_params():
    params_inside_filters = dict(parse_qsl(_get_filters()))
    params_inside_url = get_request().resolver_match.kwargs
    params = params_inside_filters | params_inside_url
    return params


def is_ajax():
    request = get_request()
    return request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"


def admin_filter_middleware(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # Protection anti-boucle de redirection optimisée (pour les bots sur go_repanier)
        if "go_repanier" in request.path:
            query_string = request.META.get("QUERY_STRING", "")
            if REDIRECT_LOOP_PATTERN.search(query_string):
                return HttpResponseBadRequest("Malformed redirect loop detected.")

        _set_request(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_staff:
            _set_filters(request)

        response = get_response(request)

        return response

    return middleware

# The Repanier passport: a login on one site of the repanier.be family
# opens the door of the other sites where the member owns an account,
# without asking anything again. A signed cookie travels on the parent
# domain; each site verifies it and opens its own local session - no
# central account, no personal data crossing the databases, only the
# e-mail address inside a signed token the family can verify.

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.core import signing
from django.utils import timezone

from repanier.const import DECIMAL_ZERO, EMPTY_STRING

passport_logger = logging.getLogger("repanier.passport")

PASSPORT_COOKIE = "repanier_passport"
PASSPORT_DOMAIN = ".repanier.be"
PASSPORT_MAX_AGE = 30 * 24 * 60 * 60  # seconds, a sliding month
PASSPORT_SALT = "repanier/1905/passport"


def get_passport_signer():
    """Every site of the family signs with the same key, configured by
    REPANIER_SETTINGS_PASSPORT_SIGNING_KEY (same value in the ini of
    each site). Without it the site falls back on its own SECRET_KEY:
    the passport keeps working for the site alone, nothing breaks."""
    return signing.TimestampSigner(
        key=(
            getattr(
                django_settings, "REPANIER_SETTINGS_PASSPORT_SIGNING_KEY", EMPTY_STRING
            )
            or django_settings.SECRET_KEY
        ),
        salt=PASSPORT_SALT,
    )


def _is_passport_host(request):
    # Only the repanier.be family carries the passport: the sites on
    # their own domain (colibera.be, ...) keep the classical sign in,
    # their cookies never cross anyway.
    host = request.get_host().split(":", 1)[0].lower()
    return host.endswith(PASSPORT_DOMAIN)


def _passport_user(email):
    """Find the local account behind a verified passport - the same
    care as the sign in: the door stays closed for anything but an
    active member, and the temporary lock applies to the passport
    exactly as it applies to a password."""
    # Lazy imports: the models themselves import this module.
    from repanier.auth_backend import LOGIN_LOCK_MINUTES, RepanierAuthBackend
    from repanier.models.customer import Customer

    user_model = get_user_model()
    user = user_model.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or user.is_superuser:
        # Superusers log in by hand: they carry the CMS toolbar.
        return None
    customer = Customer.objects.filter(user_id=user.id).first()
    if customer is None or not customer.is_active:
        # Group accounts and staff-only accounts go through the sign
        # in flow: the passport only opens member sessions.
        return None
    if customer.login_locked_on is not None:
        locked_until = customer.login_locked_on + timezone.timedelta(
            minutes=int(LOGIN_LOCK_MINUTES)
        )
        if timezone.now() < locked_until:
            return None
        # The lock expired: clean slate, as at the sign in.
        Customer.objects.filter(id=customer.id).update(
            login_locked_on=None, login_attempt_counter=DECIMAL_ZERO
        )
    RepanierAuthBackend.set_user_right(
        user=user, is_superuser=False, staff=None, customer=customer
    )
    return user


def repanier_passport_middleware(get_response):
    def middleware(request):
        # The passport opens the door of this site for a member
        # already signed in on another site of the family. It runs
        # before any view: the member arrives signed in wherever the
        # local account exists.
        try:
            if not request.user.is_authenticated:
                passport = request.COOKIES.get(PASSPORT_COOKIE)
                if passport and _is_passport_host(request):
                    try:
                        email = get_passport_signer().unsign(
                            passport, max_age=PASSPORT_MAX_AGE
                        )
                    except signing.BadSignature:
                        email = None
                    if email:
                        user = _passport_user(email)
                        if user is not None:
                            user.backend = "repanier.auth_backend.RepanierAuthBackend"
                            auth_login(request, user)
                            request.user = user
        except Exception as error:
            # A passport problem never blocks a page: the member falls
            # back on the classical sign in.
            passport_logger.error("repanier passport error : {}".format(error))

        response = get_response(request)

        try:
            if request.user.is_authenticated and _is_passport_host(request):
                # Refreshed on every visit: one sign in a month is
                # enough for the whole family.
                response.set_cookie(
                    PASSPORT_COOKIE,
                    get_passport_signer().sign(
                        (request.user.email or EMPTY_STRING).strip().lower()
                    ),
                    max_age=PASSPORT_MAX_AGE,
                    domain=PASSPORT_DOMAIN,
                    secure=True,
                    httponly=True,
                    samesite="Lax",
                )
        except Exception as error:
            passport_logger.error("repanier passport cookie error : {}".format(error))
        return response

    return middleware
