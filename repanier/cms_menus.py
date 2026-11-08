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
    namespace = "PermanenceMenu"

    def get_nodes(self, request):
        from repanier.apps import REPANIER_SETTINGS_PERMANENCES_NAME

        is_anonymous = request.user.is_anonymous
        nodes = []

        permanences = Permanence.objects.filter(
            status__in=[SaleStatus.OPENED, SaleStatus.CLOSED, SaleStatus.SEND],
            master_permanence__isnull=True,
        ).order_by("-permanence_date", "id")

        has_board = PermanenceBoard.objects.filter(
            permanence__status__lte=SaleStatus.WAIT_FOR_INVOICED
        ).exists()

        # URL du nœud parent : tâches > première permanence > "/"
        parent_url = "/"
        if has_board:
            parent_url = reverse("repanier:permanence_view")
        elif permanences.exists():
            first_perm = permanences.first()
            parent_url = first_perm.get_order_url()
            if not is_anonymous and first_perm.status > SaleStatus.OPENED:
                parent_url += "?is_basket=yes"

        parent_node = NavigationNode(
            REPANIER_SETTINGS_PERMANENCES_NAME,
            parent_url,
            id=0,
            visible=True,
            attr={"soft_root": False},
        )
        nodes.append(parent_node)

        submenu_id = 0
        if has_board:
            submenu_id += 1
            nodes.append(NavigationNode(
                _("Registration for tasks"),
                reverse("repanier:permanence_view"),
                id=submenu_id, parent_id=0, visible=True,
            ))

        first_pass = True
        for permanence in permanences:
            if first_pass and has_board:
                submenu_id += 1
                nodes.append(NavigationNode(
                    "------", "/", id=submenu_id, parent_id=0, visible=True
                ))
            first_pass = False

            path = permanence.get_order_url()
            if not is_anonymous and permanence.status > SaleStatus.OPENED:
                path += "?is_basket=yes"
            submenu_id += 1
            nodes.append(NavigationNode(
                permanence.get_html_permanence_display(),
                path,
                id=submenu_id, parent_id=0, visible=True,
            ))

        return nodes

menu_pool.register_menu(PermanenceMenu)
