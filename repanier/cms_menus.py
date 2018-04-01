# -*- coding: utf-8
import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool

from repanier.const import *
from repanier.models import Permanence
from repanier.models import PermanenceBoard

logger = logging.getLogger(__name__)


class PermanenceMenu(Menu):
    def get_nodes(self, request):
        from repanier.apps import REPANIER_SETTINGS_PERMANENCES_NAME
        user = request.user
        if user.is_anonymous or user.is_staff:
            is_anonymous = True
        else:
            is_anonymous = False
        nodes = []
        master_id = 0
        node = NavigationNode(
            "{}".format(REPANIER_SETTINGS_PERMANENCES_NAME),
            "/",
            id=master_id,
            visible=True,
            attr={'soft_root': False}
        )
        nodes.append(node)
        submenu_id = master_id

        separator = False
        permanence_board_set = PermanenceBoard.objects.filter(
            permanence__status__lte=PERMANENCE_WAIT_FOR_INVOICED).only(
            "id").order_by('?')
        if permanence_board_set.exists():
            submenu_id += 1
            node = NavigationNode(
                _('Registration for tasks'),
                reverse('permanence_view'),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            separator = True

        displayed_permanence_counter = 0

        first_pass = True
        for permanence in Permanence.objects.filter(status=PERMANENCE_OPENED) \
                .only("id", "permanence_date", "with_delivery_point") \
                .order_by("permanence_date", "id"):
            displayed_permanence_counter += 1
            if first_pass and separator:
                submenu_id = self.append_separator(nodes, master_id, submenu_id)
            first_pass = False
            separator = True
            submenu_id = self.append_permanence(is_anonymous, permanence, nodes, master_id, submenu_id)

        first_pass = True
        closed_separator = separator
        for permanence in Permanence.objects.filter(
                status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND],
                master_permanence__isnull=True
        ).only("id", "permanence_date").order_by('-permanence_date'):
            displayed_permanence_counter += 1
            if first_pass and closed_separator:
                submenu_id = self.append_separator(nodes, master_id, submenu_id)
            first_pass = False
            closed_separator = False
            submenu_id = self.append_permanence(is_anonymous, permanence, nodes, master_id, submenu_id)
            if displayed_permanence_counter > 4:
                break

        return nodes

    def append_permanence(self, is_anonymous, permanence, nodes, master_id, submenu_id):
        path = reverse('order_view', args=(permanence.id,))
        if not is_anonymous and permanence.status > PERMANENCE_OPENED:
            path = path + "?is_basket=yes"
        submenu_id += 1
        node = NavigationNode(
            permanence.get_permanence_customer_display(),
            path,
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)
        return submenu_id

    def append_separator(self, nodes, master_id, submenu_id):
        submenu_id += 1
        node = NavigationNode(
            '------',
            "/",
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)
        return submenu_id


menu_pool.register_menu(PermanenceMenu)
