import re
import threading
from urllib.parse import parse_qsl

from django.http import HttpResponseRedirect, QueryDict
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
                return HttpResponseRedirect("/")

        _set_request(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_staff:
            _set_filters(request)

        response = get_response(request)

        return response

    return middleware