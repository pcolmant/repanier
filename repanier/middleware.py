import threading
from urllib.parse import parse_qsl

from django.http import QueryDict
from django.utils.http import urlencode

threading_local = threading.local()


def _set_request(request):
    threading_local.repanier_request = request


def get_request():
    return getattr(threading_local, "repanier_request", None)


def _set_filters(request):
    # """
    # Set the admin filters querystring.
    # Assigns current admin query string from request to thread_locals, used by
    # repanier_v2 admin custom actions.
    # """
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
    """
    Return the admin filters querystring.
    """
    return getattr(threading_local, "repanier_filters", "")


def get_query_preserved_filters():
    """
    Return the admin preserved filters querystring.
    """
    filters = _get_filters()
    return "?{}".format(urlencode({"_changelist_filters": filters})) if filters else ""


def get_query_filters():
    """
    Return the admin filters querystring.
    """
    filters = _get_filters()
    return "?{}".format(filters) if filters else ""


def add_filter(path):
    return "{}{}".format(path, get_query_preserved_filters())


def get_query_params():
    """
    Return the params present in the querystring as a dict
    """
    filters = _get_filters()
    return dict(parse_qsl(filters))


def is_ajax():
    request = get_request()
    # See : https://docs.djangoproject.com/en/3.1/releases/3.1/
    # The HttpRequest.is_ajax() method is deprecated as it relied on a jQuery-specific way of signifying AJAX calls
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def admin_filter_middleware(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        _set_request(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_staff:
            _set_filters(request)

        response = get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    return middleware
