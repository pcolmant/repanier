from repanier.admin.tools import set_filters


def admin_filter_middleware(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        user = getattr(request, "user", None)
        if user is not None and user.is_staff:
            set_filters(request)

        response = get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    return middleware
