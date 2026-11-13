import logging
from functools import wraps
from threading import local

from django.core.checks import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from repanier.const import SaleStatus
from repanier.models import Permanence
from repanier.models import Product

logger = logging.getLogger(__name__)
_thread_locals = local()


def get_back_to_change_list_url(request, model_admin):
    """An admin screen may embed the action of another one: the cancel
    delivery button of the preparation screen targets the view of the
    payment screen. Such URLs carry a ?back= change list, and the user
    must land there after the action - not on the list of the screen
    owning the view.

    The back parameter is compared to the known change list, never
    trusted as-is: a forged value cannot redirect outside the admin.
    Without it the action redirects, as before, to the change list of
    the view owner."""
    back = request.GET.get("back", "")
    if back:
        base = back.split("?", 1)[0]
        if base == reverse("admin:repanier_permanenceinpreparation_changelist"):
            return back
    return model_admin.get_redirect_to_change_list_url()
def check_cancel_in_post(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # logger.debug("check_cancel_in_post, must-have arguments are: {}".format(list(args)))
        # logger.debug("check_cancel_in_post, optional arguments are: {}".format(kwargs))
        # args[0] = self
        # args[1] = request
        if "cancel" in args[1].POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            args[0].message_user(args[1], user_message, user_message_level)
            return HttpResponseRedirect(
                get_back_to_change_list_url(args[1], args[0])
            )
        return func(*args, **kwargs)

    return func_wrapper


def check_done_in_post(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # args[0] = self
        # args[1] = request
        if "done" in args[1].POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            args[0].message_user(args[1], user_message, user_message_level)
            return HttpResponseRedirect(args[0].get_redirect_to_change_list_url())
        return func(*args, **kwargs)

    return func_wrapper


def check_permanence(status: SaleStatus | tuple):
    """Accept one status or several (a tuple): the status check passes when
    the permanence carries any of them."""

    def actual_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            # logger.debug("check_permanence, must-have arguments are: {}".format(list(args)))
            # logger.debug("check_permanence, optional arguments are: {}".format(kwargs))
            # args[0] = self
            # args[1] = request
            permanence_qs = Permanence.objects.filter(id=kwargs["permanence_id"])
            permanence = permanence_qs.first()
            if permanence is None:
                user_message = _("Permanence not found.")
                user_message_level = messages.INFO
                args[0].message_user(args[1], user_message, user_message_level)
                return HttpResponseRedirect(args[0].get_redirect_to_change_list_url())
            if isinstance(status, tuple):
                allowed_values = [one_status.value for one_status in status]
            else:
                allowed_values = [status.value]
            if permanence.status not in allowed_values:
                # logger.debug("check_permanence, permanence.status not in statuses")
                if isinstance(status, tuple):
                    expected_statuses = "' or '.".join(
                        str(one_status.label) for one_status in status
                    )
                    user_message = _(
                        "To perform this action, the status of {permanence} must be '{expected_statuses}.'"
                    ).format(
                        permanence=permanence, expected_statuses=expected_statuses
                    )
                else:
                    user_message = _(
                        "To perform this action, the status of {permanence} must be '{status.label}.'"
                    ).format(permanence=permanence, status=status)
                user_message_level = messages.ERROR
                args[0].message_user(args[1], user_message, user_message_level)
                return HttpResponseRedirect(args[0].get_redirect_to_change_list_url())
            return func(*args, permanence=permanence, **kwargs)

        return func_wrapper

    return actual_decorator


def check_product(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # args[0] = self
        # args[1] = request
        if "done" in args[1].POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            args[0].message_user(args[1], user_message, user_message_level)
            return HttpResponseRedirect(args[0].get_redirect_to_change_list_url())
        product_qs = Product.objects.filter(id=kwargs["product_id"])
        product = product_qs.first()
        if product is None:
            user_message = _("Product not found.")
            user_message_level = messages.INFO
            args[0].message_user(args[1], user_message, user_message_level)
            return HttpResponseRedirect(args[0].get_redirect_to_change_list_url())
        return func(*args, product=product, **kwargs)

    return func_wrapper
