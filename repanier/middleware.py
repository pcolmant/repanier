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
# central account, only the e-mail address and the subdomain of the
# site which last welcomed the member inside a signed token the
# family can verify. That origin name places the member, by default,
# in the local mirror group of their home site when the group
# explicitly accepts passport members: the customer lists show
# [home site] + name, and the delivery board follows the group. The
# origin label never drifts with the hops of the member: his mirror
# group names his home, and coming back home attaches nothing. On a
# site where the member owns no account yet, that mirror group
# welcoming him also means the site can register him on the spot:
# it asks his home site for his profile - server to server, signed
# with the shared family key, never in a browser - and creates the
# local account. The cookie itself never carries any personal data
# beyond the sign in e-mail.

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.core import signing
from django.utils import timezone

from repanier.const import DECIMAL_ZERO, EMPTY_STRING
from repanier.passport_network import fetch_passport_profile

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
    user = (
        user_model.objects.filter(email__iexact=email, is_active=True)
        .order_by("id")
        .first()
    )
    if user is None or user.is_superuser or user.is_staff:
        # Superusers log in by hand: they carry the CMS toolbar.
        # Staff accounts go through the roles chooser of the sign
        # in, they too carry the toolbar.
        return None
    customer = Customer.objects.filter(user_id=user.id).first()
    if customer is None or not customer.is_active or customer.is_group:
        # Group accounts go through the sign in flow: the
        # passport only opens member sessions.
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


def _passport_origin(request):
    """The subdomain prefix this site lives on (gasath for
    gasath.repanier.be): the name every other site of the family can
    discover in its own browser, without reading anybody's ini. It
    travels in every issued passport so the next site knows where
    the member comes from."""
    host = request.get_host().split(":", 1)[0].lower()
    if not host.endswith(PASSPORT_DOMAIN):
        return EMPTY_STRING
    return host[: -len(PASSPORT_DOMAIN)]


def _passport_home(request, user):
    """The home of the member, stamped in every issued passport. The
    emitting site derives it, in this order:

    1. a member placed in a mirror group which accepts the passport
       arrivals belongs to the home site that mirror wears;
    2. otherwise, the home of the passport the member arrived with -
       his own, since it must carry his e-mail - so that a member of
       gasath passing through a site without a gasath mirror keeps
       travelling as gasath;
    3. otherwise the subdomain of the site emitting the passport -
       his home, or the site the coordination treats him as coming
       from.

    Whatever the hops of the member, his home never drifts with the
    last visited site."""
    try:
        from repanier.models.customer import Customer

        customer = Customer.objects.select_related("group").filter(
            user_id=user.id
        ).first()
        if (
            customer is not None
            and customer.group_id is not None
            and customer.group.accepts_passport_members
        ):
            return customer.group.short_basket_name.strip()
        passport = request.COOKIES.get(PASSPORT_COOKIE)
        if passport:
            try:
                passport_value = get_passport_signer().unsign(
                    passport, max_age=PASSPORT_MAX_AGE
                )
            except signing.BadSignature:
                passport_value = None
            if passport_value:
                email, _separator, origin = passport_value.partition("|")
                if (
                    origin.strip()
                    and email.strip().lower()
                    == (user.email or EMPTY_STRING).strip().lower()
                ):
                    return origin.strip()
    except Exception as error:
        passport_logger.error("repanier passport home error : {}".format(error))
    return _passport_origin(request)


def _attach_passport_group(request, user, origin):
    """A member arriving with a passport mentions the site which last
    welcomed them. When this site owns a mirror group of that home
    site - a group wearing its subdomain name, which explicitly
    accepts the passport arrivals - and the local coordination has
    never placed the member in another group, the
    passport places them there by default: the customer lists show
    [home site] + name and the delivery board follows the group. Never
    twice, never over a decision of the coordination: a group already
    set is final, an ambiguous, missing or refusing mirror group
    changes nothing."""
    origin = (origin or EMPTY_STRING).strip()
    if not origin or origin.lower() == _passport_origin(request):
        # Coming home attaches nothing.
        return
    try:
        from repanier.models.customer import Customer

        mirror_group = _passport_mirror_group(request, origin)
        if mirror_group is None:
            return
        attached = Customer.objects.filter(
            user_id=user.id,
            is_group=False,
            is_active=True,
            group__isnull=True,
        ).update(group=mirror_group)
        if attached:
            passport_logger.info(
                "repanier passport : {} attached to the group [{}]".format(
                    user.email, origin
                )
            )
    except Exception as error:
        # An attach problem never blocks the session.
        passport_logger.error("repanier passport group attach error : {}".format(error))


def _passport_mirror_group(request, origin):
    """The mirror group of a home site on this site: a group wearing
    its subdomain name, active, which explicitly accepts the
    passport arrivals. Ambiguous or missing: no mirror group, the
    passport keeps its classical behaviour."""
    origin = (origin or EMPTY_STRING).strip()
    if not origin or origin.lower() == _passport_origin(request):
        # Coming home enrols nobody.
        return None
    try:
        from repanier.models.customer import Customer

        mirror_groups = Customer.objects.filter(
            is_group=True,
            is_active=True,
            short_basket_name__iexact=origin,
            accepts_passport_members=True,
        )
        if mirror_groups.count() != 1:
            return None
        return mirror_groups.first()
    except Exception as error:
        passport_logger.error("repanier passport mirror group error : {}".format(error))
        return None


def _unique_short_basket_name(email, origin, short_basket_name):
    """The short name is unique on a site: an arriving member may
    collide with a local namesake. The members of the family unfold
    candidates - the short name of the home site, the name wearing
    his home between brackets, then numbered twins - and take the
    first free one. The customer lists prefix the group anyway:
    [gasath] Michel stays readable in every case."""
    from repanier.models.customer import Customer

    base = (
        (short_basket_name or EMPTY_STRING).strip()
        or (email or EMPTY_STRING).split("@", 1)[0].strip()
        or "member"
    )[:25]
    candidates = [base]
    with_home = "{} ({})".format(base, origin)[:25]
    candidates.append(with_home)
    for number in range(2, 99):
        candidates.append("{} {}".format(base, number)[:25])
    for candidate in candidates:
        if not Customer.objects.filter(short_basket_name__iexact=candidate).exists():
            return candidate
    return None


def _enrol_passport_member(request, email, origin):
    """The family enrolment: a member arrives with a valid passport
    on a site where he owns no account yet. When this site runs a
    mirror group of his home site which accepts the passport
    members, the site asks his home site for his profile - a
    server-to-server call signed with the family key, not a sign in,
    nobody reconnects anywhere - and registers the local account :
    short and long names, phones, address, city, bank accounts, the
    language of his mails and the may-order trust of the home site.
    The arriving member lands directly in his mirror group, which
    keeps his home stable across all his hops. Any problem - no
    mirror group, the home site unreachable, a signature gone, a
    local account appearing in between - leaves the site just as it
    was: the passport never blocks a page."""
    from django.db.utils import IntegrityError

    email = (email or EMPTY_STRING).strip().lower()
    if not email or "|" in email:
        return None
    user_model = get_user_model()
    try:
        from repanier.models.customer import Customer

        # The enrolment never writes over an account: it runs only
        # when nothing local answers this e-mail, or when a previous
        # enrolment broke in between creating the user and creating
        # the customer - an active user without a customer is
        # repaired; a staff, superuser or disabled account never is.
        user = (
            user_model.objects.filter(email__iexact=email).order_by("id").first()
        )
        if user is not None:
            if user.is_superuser or user.is_staff or not user.is_active:
                # A disabled account stays disabled - the coordination
                # closed that door, the enrolment never reopens it - and
                # the staff and superuser accounts keep their classical
                # sign in.
                return None
            if Customer.objects.filter(user_id=user.id).exists():
                # An existing member refused by _passport_user stays
                # refused: locked, inactive, group sessions never open
                # through the enrolment.
                return None
        mirror_group = _passport_mirror_group(request, origin)
        if mirror_group is None:
            return None
        profile = fetch_passport_profile(
            mirror_group.short_basket_name.strip().lower(), email
        )
        if profile is None:
            return None
        if (profile.get("email") or EMPTY_STRING).strip().lower() != email:
            return None
        short_basket_name = _unique_short_basket_name(
            email, origin, profile.get("short_basket_name")
        )
        if short_basket_name is None:
            return None
        if user is None:
            try:
                user = user_model.objects.create_user(
                    username=email,
                    email=email,
                    password=None,
                    first_name=EMPTY_STRING,
                    last_name=short_basket_name,
                )
            except IntegrityError:
                # A parallel arrival created it first: the enrolment
                # picks up where it stands and goes on.
                user = (
                    user_model.objects.filter(email__iexact=email)
                    .order_by("id")
                    .first()
                )
                if user is None:
                    return None
        valid_languages = [code for code, _label in django_settings.LANGUAGES]
        profile_language = profile.get("language")
        customer = Customer.objects.create(
            user=user,
            short_basket_name=short_basket_name,
            long_basket_name=(profile.get("long_basket_name") or EMPTY_STRING)[:100],
            language=profile_language
            if profile_language in valid_languages
            else django_settings.LANGUAGE_CODE,
            phone1=(profile.get("phone1") or EMPTY_STRING)[:25],
            phone2=(profile.get("phone2") or EMPTY_STRING)[:25],
            bank_account1=(profile.get("bank_account1") or EMPTY_STRING)[:100],
            bank_account2=(profile.get("bank_account2") or EMPTY_STRING)[:100],
            address=profile.get("address") or EMPTY_STRING,
            city=(profile.get("city") or EMPTY_STRING)[:50],
            may_order=bool(profile.get("may_order")),
            group=mirror_group,
        )
        from repanier.auth_backend import RepanierAuthBackend

        RepanierAuthBackend.set_user_right(
            user=user, is_superuser=False, staff=None, customer=customer
        )
        passport_logger.info(
            "repanier passport : {} enrolled by [{}] in [{}]".format(
                email, origin, customer.short_basket_name
            )
        )
        return user
    except Exception as error:
        # An enrolment problem never blocks the page: the member
        # falls back on the classical sign in.
        passport_logger.error("repanier passport enrolment error : {}".format(error))
        return None


def repanier_passport_middleware(get_response):
    def middleware(request):
        # The passport opens the door of this site for a member
        # already signed in on another site of the family. It runs
        # before any view: the member arrives signed in wherever the
        # local account exists.
        was_authenticated = request.user.is_authenticated
        try:
            if not request.user.is_authenticated:
                passport = request.COOKIES.get(PASSPORT_COOKIE)
                if passport and _is_passport_host(request):
                    try:
                        passport_value = get_passport_signer().unsign(
                            passport, max_age=PASSPORT_MAX_AGE
                        )
                    except signing.BadSignature:
                        passport_value = None
                    if passport_value:
                        email, _separator, origin = passport_value.partition("|")
                        user = _passport_user(email.strip().lower())
                        if user is None:
                            # No local account opens for this passport,
                            # or the account refuses it. When the site
                            # runs a mirror group of the home site which
                            # welcomes him, the family enrolment may
                            # register him from the profile of his home
                            # site before opening the session.
                            user = _enrol_passport_member(
                                request, email.strip().lower(), origin
                            )
                        if user is not None:
                            user.backend = "repanier.auth_backend.RepanierAuthBackend"
                            auth_login(request, user)
                            _attach_passport_group(request, user, origin)
                            request.user = user
        except Exception as error:
            # A passport problem never blocks a page: the member falls
            # back on the classical sign in.
            passport_logger.error("repanier passport error : {}".format(error))

        response = get_response(request)

        try:
            if (
                request.user.is_authenticated
                and not was_authenticated
                and not request.user.is_superuser
                and not request.user.is_staff
            ):
                # The site speaks the language of the member it just
                # welcomed, when it knows it: a sign in by hand, a
                # passport arrival, the passport login door - every
                # opening of a member session plants his language as
                # a host only cookie: each site keeps its own, and a
                # member registered by the family enrolment keeps the
                # language copied from his home site. A language this
                # site does not run changes nothing: the CMS and the
                # browser stay in charge, the fallback of the site
                # applies.
                from repanier.models.customer import Customer

                customer = (
                    Customer.objects.filter(
                        user_id=request.user.id, is_group=False, is_active=True
                    )
                    .only("language")
                    .first()
                )
                if customer is not None:
                    language = (customer.language or EMPTY_STRING).strip()
                    if language and language in dict(django_settings.LANGUAGES):
                        response.set_cookie(
                            django_settings.LANGUAGE_COOKIE_NAME,
                            language,
                            max_age=10 * 365 * 24 * 60 * 60,
                        )

            if (
                request.user.is_authenticated
                and not was_authenticated
                and _is_passport_host(request)
                and not request.user.is_superuser
                and not request.user.is_staff
            ):
                # The member just signed in on this site by hand. When
                # his browser still carries a valid passport of a home
                # site of the family, the same guarded attach repairs
                # his local account - an account already registered
                # here for years gets its group exactly like a fresh
                # passport arrival. The e-mail must match: a stray
                # passport of somebody else repairs nothing.
                passport = request.COOKIES.get(PASSPORT_COOKIE)
                if passport:
                    try:
                        passport_value = get_passport_signer().unsign(
                            passport, max_age=PASSPORT_MAX_AGE
                        )
                    except signing.BadSignature:
                        passport_value = None
                    if passport_value:
                        email, _separator, origin = passport_value.partition("|")
                        if (
                            email.strip().lower()
                            == (request.user.email or EMPTY_STRING).strip().lower()
                        ):
                            _attach_passport_group(request, request.user, origin)

            if request.user.is_authenticated and _is_passport_host(request):
                # Refreshed on every visit: one sign in a month is
                # enough for the whole family. The token carries the
                # e-mail and the home of the member - his mirror
                # group when he has one, the subdomain of this site
                # otherwise: the next site knows where he comes from
                # and his home never drifts with his hops.
                # Superusers log in by hand: no passport for them.
                passport_email = (request.user.email or EMPTY_STRING).strip().lower()
                if (
                    not request.user.is_superuser
                    and passport_email
                    and "|" not in passport_email
                ):
                    response.set_cookie(
                        PASSPORT_COOKIE,
                        get_passport_signer().sign(
                            "{}|{}".format(
                                passport_email,
                                _passport_home(request, request.user),
                            )
                        ),
                        max_age=PASSPORT_MAX_AGE,
                        domain=PASSPORT_DOMAIN,
                        secure=True,
                        httponly=True,
                        samesite="Lax",
                    )
        except Exception as error:
            # A passport problem never blocks the response.
            passport_logger.error("repanier passport cookie error : {}".format(error))
        return response

    return middleware
