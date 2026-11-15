# The profile endpoint of the Repanier passport: the home site of a
# member answers - server to server, never in a browser - the profile
# another site of the family needs to register him. Only a site
# holding the shared family key can ask, and only an active member
# profile travels: group, staff, superuser and locked accounts stay
# out. Everything answers 404, the endpoint never confirms whether an
# account exists.

import json

from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from repanier.const import EMPTY_STRING
from repanier.middleware import _passport_user
from repanier.passport_network import (
    PASSPORT_NETWORK_MAX_AGE,
    get_network_signer,
)

PROFILE_FIELDS = [
    "short_basket_name",
    "long_basket_name",
    "language",
    "phone1",
    "phone2",
    "bank_account1",
    "bank_account2",
    "address",
    "city",
    "may_order",
]


def _profile_of(customer):
    profile = {"email": customer.user.email.strip().lower()}
    for field in PROFILE_FIELDS:
        value = getattr(customer, field)
        profile[field] = value if value is not None else EMPTY_STRING
    return profile


def _profile_not_found():
    return HttpResponse("Not found.", status=404)


@csrf_exempt
@require_http_methods(["POST"])
def passport_profile_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _profile_not_found()
    token = (payload.get("token") or EMPTY_STRING).strip()
    try:
        value = get_network_signer().unsign(token, max_age=PASSPORT_NETWORK_MAX_AGE)
    except signing.BadSignature:
        return _profile_not_found()
    email, _separator, _caller = value.partition("|")
    email = email.strip().lower()
    user = _passport_user(email)
    if user is None:
        # The account does not exist, or the passport may not open it
        # (group, staff, superuser, lock, inactive): the endpoint
        # tells nothing, it only answers the profiles it may answer.
        return _profile_not_found()
    from repanier.models.customer import Customer

    customer = Customer.objects.filter(user_id=user.id).first()
    if customer is None:
        return _profile_not_found()
    profile = _profile_of(customer)
    return JsonResponse(
        {"passport_profile": get_network_signer().sign(json.dumps(profile))}
    )
