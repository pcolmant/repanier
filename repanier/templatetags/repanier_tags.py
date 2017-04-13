# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import template
from django.utils.safestring import mark_safe

from repanier.const import EMPTY_STRING, PERMANENCE_CLOSED
from repanier.models import PermanenceBoard
from repanier.tools import sint

register = template.Library()


@register.simple_tag(takes_context=False)
def repanier_home(*args, **kwargs):
    from repanier.apps import REPANIER_SETTINGS_HOME_SITE
    return REPANIER_SETTINGS_HOME_SITE


@register.simple_tag(takes_context=False)
def repanier_display_languages(*args, **kwargs):
    from django.conf import settings
    if len(settings.LANGUAGES) > 1:
        return "yes"
    return


@register.simple_tag(takes_context=False)
def repanier_display_task(*args, **kwargs):
    result = EMPTY_STRING
    p_permanence_board_id = sint(kwargs.get('permanence_board_id', 0))
    if p_permanence_board_id > 0:
        permanence_board = PermanenceBoard.objects.filter(id=p_permanence_board_id).select_related(
            "permanence_role"
        ).order_by('?').first()
        if permanence_board is not None:
            if permanence_board.permanence_role.customers_may_register:
                result = permanence_board.permanence_role
            else:
                result = '<p><b>%s</b></p>' % (permanence_board.permanence_role,)
    return mark_safe(result)


@register.simple_tag(takes_context=True)
def repanier_select_task(context, *args, **kwargs):
    request = context['request']
    user = request.user
    result = EMPTY_STRING
    if user.is_staff or user.is_superuser:
        pass
    else:
        p_permanence_board_id = sint(kwargs.get('permanence_board_id', 0))
        if p_permanence_board_id > 0:
            permanence_board = PermanenceBoard.objects.filter(id=p_permanence_board_id).select_related(
                "customer", "permanence_role", "permanence"
            ).order_by('?').first()
            if permanence_board is not None:
                if permanence_board.customer is not None:
                    if permanence_board.customer.user_id == user.id and permanence_board.permanence.status <= PERMANENCE_CLOSED:
                        result = """
                        <b><i>
                        <select name="value" id="permanence_board{permanence_board_id}"
                        onchange="permanence_board_ajax({permanence_board_id})" class="form-control">
                        <option value="0">---</option>
                        <option value="1" selected>{long_basket_name}</option>
                        </select>
                        </i></b>
                        """.format(
                            permanence_board_id=permanence_board.id,
                            long_basket_name=user.customer.long_basket_name
                        )
                    else:
                        result = """
                        <select name="value" id="permanence_board{permanence_board_id}"
                        class="form-control">
                        <option value="0" selected>{long_basket_name}</option>
                        </select>
                        """.format(
                            permanence_board_id=permanence_board.id,
                            long_basket_name=permanence_board.customer.long_basket_name
                        )
                else:
                    if permanence_board.permanence_role.customers_may_register:
                        if permanence_board.permanence.status <= PERMANENCE_CLOSED:
                            result = """
                            <b><i>
                            <select name="value" id="permanence_board{permanence_board_id}"
                            onchange="permanence_board_ajax({permanence_board_id})" class="form-control">
                            <option value="0" selected>---</option>
                            <option value="1">{long_basket_name}</option>
                            </select>
                            </i></b>
                            """.format(
                                permanence_board_id=permanence_board.id,
                                long_basket_name=user.customer.long_basket_name
                            )
                        else:
                            result = """
                            <select name="value" id="permanence_board{permanence_board_id}"
                            class="form-control">
                            <option value="0" selected>---</option>
                            </select>
                            """.format(
                                permanence_board_id=permanence_board.id
                            )
    return mark_safe(result)
