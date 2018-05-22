# -*- coding: utf-8
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from repanier.const import EMPTY_STRING
from repanier.tools import sint, send_test_email


@never_cache
@login_required
@require_POST
def test_mail_config_ajax(request):
    from repanier.apps import REPANIER_SETTINGS_CONFIG
    config = REPANIER_SETTINGS_CONFIG
    html_id = request.POST.get("id", EMPTY_STRING)
    email_host = request.POST.get("id_email_host", EMPTY_STRING)
    email_port = sint(request.POST.get("id_email_port", EMPTY_STRING), 0)
    email_use_tls = request.POST.get("id_email_use_tls", "false") == "true"
    email_host_user = request.POST.get("id_email_host_user", EMPTY_STRING)
    email_host_password = request.POST.get("id_new_email_host_password", EMPTY_STRING)
    to_email = request.user.email
    if not email_host_password:
        email_host_password = config.email_host_password

    # Send test email
    email_send = send_test_email(
        host=email_host,
        port=email_port,
        host_user=email_host_user,
        host_password=email_host_password,
        use_tls=email_use_tls,
        to_email=to_email
    )
    if not email_send:
        json_dict = {"#{}".format(html_id): _(
            "This mail server configuration did not allow to send mail. Retry to validate ?")}

    else:
        json_dict = {
            "#{}".format(html_id): _(
                "This mail server configuration is valid. An email has been sent to {} and to {}.").format(
                email_host_user, to_email)}

    return JsonResponse(json_dict)
