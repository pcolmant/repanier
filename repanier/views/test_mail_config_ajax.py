# -*- coding: utf-8
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from repanier.const import EMPTY_STRING
from repanier.email.email import RepanierEmail

logger = logging.getLogger(__name__)


@never_cache
@login_required
@require_POST
def test_mail_config_ajax(request):
    html_id = request.POST.get("id", EMPTY_STRING)
    to_email = request.user.email

    # Send test email
    email_send = RepanierEmail.send_test_email(
        to_email=to_email
    )
    json_dict = {"#{}".format(html_id): email_send}

    return JsonResponse(json_dict)
