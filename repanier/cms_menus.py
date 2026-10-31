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

        # 1. Récupérer d'abord les permanences
        qs = Permanence.objects.filter(
            status__in=[SaleStatus.OPENED, SaleStatus.CLOSED, SaleStatus.SEND],
            master_permanence__isnull=True,
        ).order_by(
            "-permanence_date", "id"
        )

        # 2. Vérifier l'existence de tâches (PermanenceBoard)
        permanence_board_set = PermanenceBoard.objects.filter(
            permanence__status__lte=SaleStatus.WAIT_FOR_INVOICED
        ).only("id")

        # 3. Déterminer l'URL intelligente du nœud parent :
        # - S'il y a des tâches, on pointe vers la vue des tâches.
        # - S'il n'y a pas de tâches mais des permanences, on pointe DIRECTEMENT vers la première permanence (évite le menu vide).
        # - Sinon, repli sur "/".
        parent_url = "/"
        if permanence_board_set.exists():
            parent_url = reverse("repanier:permanence_view")
        elif qs.exists():
            first_perm = qs.first()
            parent_url = first_perm.get_order_url()
            if not is_anonymous and first_perm.status > SaleStatus.OPENED:
                parent_url = parent_url + "?is_basket=yes"

        parent_node = NavigationNode(
            "{}".format(REPANIER_SETTINGS_PERMANENCES_NAME),
            parent_url,
            id=0,
            visible=True,
            attr={"soft_root": False},
        )
        nodes.append(parent_node)
        submenu_id = 0

        submenu_id, separator_needed = self.append_permanence_board(
            nodes, parent_node, submenu_id
        )

        first_pass = True
        for permanence in qs:
            if first_pass and separator_needed:
                submenu_id = self.append_separator(nodes, parent_node, submenu_id)
            first_pass = False
            separator_needed = True
            submenu_id = self.append_permanence(
                nodes, parent_node, submenu_id, is_anonymous, permanence
            )

        return nodes

    def append_permanence_board(self, nodes, parent_node, submenu_id):
        permanence_board_set = PermanenceBoard.objects.filter(
            permanence__status__lte=SaleStatus.WAIT_FOR_INVOICED
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

        path = permanence.get_order_url()
        if not is_anonymous and permanence.status > SaleStatus.OPENED:
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

menu_pool.register_menu(PermanenceMenu)
