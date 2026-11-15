# The login door of the Repanier passport. The passport cookie opens
# the sites where the member owns an account, but a member logged out
# everywhere still owns his password on his home site. This dance
# asks his home site to vouch for him, in three steps:

# 1. the target site sends the browser to the login page of the home
#    site (the member chose it), with a return URL and his e-mail;
# 2. his home site signs him in - or reuses the session he still
#    owns there - and stamps a short lived token: his e-mail and the
#    subdomain of the home site. The password never leaves the home
#    site, and never travels through a browser;
# 3. the target site verifies the token with the shared family key
#    and opens the door exactly like a passport arrival: the local
#    session of an existing account, or the family enrolment on the
#    profile of his home site.

from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings as django_settings
from django.core import signing

from repanier.const import EMPTY_STRING

from repanier.middleware import PASSPORT_DOMAIN

PASSPORT_LOGIN_SALT = "repanier/1905/passport-login"
PASSPORT_LOGIN_MAX_AGE = 60  # seconds, one jump through the browser
PASSPORT_LOGIN_SCHEMES = ["https", "http"]


def get_login_signer():
    """The same shared key as the passport cookie, with its own salt:
    a login token never mixes with a passport cookie or a network
    token, even when a site without a family key falls back on its
    own SECRET_KEY."""
    return signing.TimestampSigner(
        key=(
            getattr(
                django_settings, "REPANIER_SETTINGS_PASSPORT_SIGNING_KEY", EMPTY_STRING
            )
            or django_settings.SECRET_KEY
        ),
        salt=PASSPORT_LOGIN_SALT,
    )


def build_passport_login_token(email, origin):
    """What a home site stamps for one of its members: his e-mail and
    its own subdomain, valid for one minute through the browser."""
    email = (email or EMPTY_STRING).strip().lower()
    origin = (origin or EMPTY_STRING).strip().lower()
    if not email or "|" in email or not origin:
        return None
    return get_login_signer().sign("{}|{}".format(email, origin))


def read_passport_login_token(token):
    """What the target site reads from the return jump: (email,
    origin) when a family site really stamped it, None otherwise -
    a foreign signature, a forgery, or a member who took his time."""
    token = (token or EMPTY_STRING).strip()
    if not token:
        return None
    try:
        value = get_login_signer().unsign(
            token, max_age=PASSPORT_LOGIN_MAX_AGE
        )
    except signing.BadSignature:
        return None
    email, _separator, origin = value.partition("|")
    email = email.strip().lower()
    origin = origin.strip().lower()
    if not email or not origin or "|" in email:
        return None
    return email, origin


def family_return_url(value):
    """The return URL a target site may pass along, and a home site
    may send a browser back to: only the repanier.be family, the same
    trust boundary the passport cookie lives on. Anything else - an
    open redirect, a stranger, a malformed value - is refused and the
    member falls back on the classical sign in."""
    value = (value or EMPTY_STRING).strip()
    if not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in PASSPORT_LOGIN_SCHEMES:
        return None
    host = (parts.hostname or EMPTY_STRING).lower()
    if not host.endswith(PASSPORT_DOMAIN):
        return None
    if not parts.path.startswith("/"):
        return None
    return urlunsplit(
        (
            parts.scheme,
            "{}{}{}".format(
                host,
                ":{}".format(parts.port) if parts.port else EMPTY_STRING,
                EMPTY_STRING,
            ),
            parts.path,
            parts.query,
            EMPTY_STRING,
        )
    )


def append_query_parameter(url, name, value):
    separator = "&" if "?" in url else "?"
    return "{}{}{}".format(url, separator, urlencode({name: value}))
