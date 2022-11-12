import logging

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
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
        parent_node = NavigationNode(
            "{}".format(REPANIER_SETTINGS_PERMANENCES_NAME),
            "/",
            id=0,
            visible=True,
            attr={"soft_root": False},
        )
        nodes.append(parent_node)
        submenu_id = 0

        submenu_id, separator_needed = self.append_permanence_board(
            nodes, parent_node, submenu_id
        )

        displayed_permanence_counter = 0
        first_pass = True
        for permanence in (
            Permanence.objects.filter(status=PERMANENCE_OPENED)
            .only("id", "permanence_date", "status")
            .order_by("permanence_date", "id")
        ):
            displayed_permanence_counter += 1
            if first_pass and separator_needed:
                submenu_id = self.append_separator(nodes, parent_node, submenu_id)
            first_pass = False
            separator_needed = True
            submenu_id = self.append_permanence(
                nodes, parent_node, submenu_id, is_anonymous, permanence
            )

        first_pass = True
        if displayed_permanence_counter <= 4:
            for permanence in (
                Permanence.objects.filter(
                    status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND],
                    master_permanence__isnull=True,
                )
                .only("id", "permanence_date")
                .order_by("-permanence_date")
            ):

                displayed_permanence_counter += 1
                if first_pass and separator_needed:
                    submenu_id = self.append_separator(nodes, parent_node, submenu_id)
                first_pass = False
                submenu_id = self.append_permanence(
                    nodes, parent_node, submenu_id, is_anonymous, permanence
                )
                if displayed_permanence_counter > 4:
                    break

        if len(nodes) > 1:
            return nodes
        return []

    def append_permanence_board(self, nodes, parent_node, submenu_id):
        permanence_board_set = PermanenceBoard.objects.filter(
            permanence__status__lte=PERMANENCE_WAIT_FOR_INVOICED
        ).only("id")
        separator_needed = False
        if permanence_board_set.exists():
            submenu_id += 1
            node = NavigationNode(
                _("Registration for tasks"),
                reverse("repanier:permanence_view"),
                id=submenu_id,
                parent_id=parent_node.id,
                visible=True,
            )
            nodes.append(node)
            separator_needed = True

        return submenu_id, separator_needed

    def append_permanence(
        self, nodes, parent_node, submenu_id, is_anonymous, permanence
    ):

        path = reverse("repanier:order_view", args=(permanence.id,))
        if not is_anonymous and permanence.status > PERMANENCE_OPENED:
            path = path + "?is_basket=yes"
        submenu_id += 1
        node = NavigationNode(
            permanence.get_html_permanence_display(),
            path,
            id=submenu_id,
            parent_id=parent_node.id,
            visible=True,
        )
        nodes.append(node)
        return submenu_id

    def append_separator(self, nodes, parent_node, submenu_id):
        submenu_id += 1
        node = NavigationNode(
            "------", "/", id=submenu_id, parent_id=parent_node.id, visible=True
        )
        nodes.append(node)
        return submenu_id

if settings.REPANIER_SETTINGS_SHOW_PERMANENCE_MENU:
    menu_pool.register_menu(PermanenceMenu)
