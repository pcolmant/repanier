# The family enrolment of the Repanier passport. When a member
# arrives with a valid passport on a site where he owns no account
# yet, and the site runs a mirror group of his home site which
# accepts the passport members, the site asks the home site for the
# member profile - server to server, signed with the shared family
# key - and registers the account locally: the member starts
# ordering without any form to fill in. The profile never travels
# in a browser cookie: it crosses only between the servers of the
# family, once, at the enrolment, over HTTPS.

import json
import re
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings as django_settings
from django.core import signing

from repanier.const import EMPTY_STRING

PASSPORT_NETWORK_SALT = "repanier/1905/passport-network"
# The endpoints live on the language prefixed side of the family
# sites - every enabled language resolves them - because a plain
# 404 without a language prefix is redirected by the locale
# middleware.
PASSPORT_PROFILE_URL = "https://{}.repanier.be/fr/passport/profile/"
PASSPORT_VERIFY_URL = "https://{}.repanier.be/fr/passport/verify/"
PASSPORT_NETWORK_TIMEOUT = 5  # seconds
PASSPORT_NETWORK_MAX_AGE = 60  # seconds

# A subdomain of the family : gasath for gasath.repanier.be. The
# network calls ever address one of these, nothing else.
SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+$")


def get_network_signer():
    """The same shared key as the passport cookie, with its own salt:
    a network token and a passport token never mix, even when both
    fall back on the SECRET_KEY of a site without a family key."""
    return signing.TimestampSigner(
        key=(
            getattr(
                django_settings, "REPANIER_SETTINGS_PASSPORT_SIGNING_KEY", EMPTY_STRING
            )
            or django_settings.SECRET_KEY
        ),
        salt=PASSPORT_NETWORK_SALT,
    )


def fetch_passport_profile(subdomain, email):
    """Ask the home site of a member for the profile the target site
    needs to register him. The request and the answer are both signed
    with the family key: the home site knows the caller holds the
    key, and the target site knows the profile really comes from a
    family site. Any problem - network, signature, delay, wrong
    account - returns None and the arrival falls back on the
    classical sign in of the target site."""
    subdomain = (subdomain or EMPTY_STRING).strip().lower()
    email = (email or EMPTY_STRING).strip().lower()
    if not SUBDOMAIN_PATTERN.match(subdomain) or not email:
        return None
    url = PASSPORT_PROFILE_URL.format(subdomain)
    token = get_network_signer().sign("{}|passport-enrolment".format(email))
    try:
        http_request = urllib_request.Request(
            url,
            data=json.dumps({"token": token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(
            http_request, timeout=PASSPORT_NETWORK_TIMEOUT
        ) as http_response:
            payload = json.loads(http_response.read().decode("utf-8"))
        profile_blob = payload.get("passport_profile", EMPTY_STRING)
        profile = json.loads(
            get_network_signer().unsign(profile_blob, max_age=PASSPORT_NETWORK_MAX_AGE)
        )
        if (profile.get("email") or EMPTY_STRING).strip().lower() != email:
            return None
        return profile
    except (
        AttributeError,
        TypeError,
        ValueError,
        HTTPError,
        URLError,
        TimeoutError,
    ):
        # A payload which is not a plain JSON object (a list, a
        # string, empty), a broken connection, a timeout, a server
        # error: every branch of the crossed network answers the
        # same clean None.
        return None
    except Exception:
        # A bad or expired signature is the only branch left: the
        # answer did not come from a family site holding the key.
        return None


def verify_passport_member(subdomain, email):
    """Ask a home site of the family whether this e-mail still
    belongs to one of its active members - the routine heart of the
    passport audit. The answer has three states, and the distinction
    matters to the audit:

    - True: the home site answered - the member is still one of its
      active members;
    - False: the home site answered - the member is gone (left,
      disabled, group, staff: the answer says nothing about why);
    - None: the home site stayed silent or spoke off key - the
      network, a deployment lag, a wrong key. The audit reports
      but never concludes: silence is never a departure.

    The question and the answer travel signed with the family key:
    only a site holding it may ask, and the answer can only come
    from a family site."""
    subdomain = (subdomain or EMPTY_STRING).strip().lower()
    email = (email or EMPTY_STRING).strip().lower()
    if not SUBDOMAIN_PATTERN.match(subdomain) or not email:
        return None
    url = PASSPORT_VERIFY_URL.format(subdomain)
    token = get_network_signer().sign("{}|passport-audit".format(email))
    try:
        http_request = urllib_request.Request(
            url,
            data=json.dumps({"token": token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(
            http_request, timeout=PASSPORT_NETWORK_TIMEOUT
        ) as http_response:
            payload = json.loads(http_response.read().decode("utf-8"))
        member_blob = payload.get("passport_member", EMPTY_STRING)
        answer = json.loads(
            get_network_signer().unsign(member_blob, max_age=PASSPORT_NETWORK_MAX_AGE)
        )
        if not isinstance(answer, dict) or not isinstance(
            answer.get("member"), bool
        ):
            return None
        return answer.get("member")
    except (
        AttributeError,
        TypeError,
        ValueError,
        HTTPError,
        URLError,
        TimeoutError,
    ):
        return None
    except Exception:
        # A bad or expired signature: the answer did not come from
        # a family site holding the key.
        return None
