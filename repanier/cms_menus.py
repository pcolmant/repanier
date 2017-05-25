# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool

from const import *
from models import Permanence
from models import PermanenceBoard


class PermanenceMenu(Menu):
    def get_nodes(self, request):
        from apps import REPANIER_SETTINGS_PERMANENCES_NAME, REPANIER_SETTINGS_INVOICE, REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO
        user = request.user
        if user.is_anonymous or user.is_staff:
            is_anonymous = True
        else:
            is_anonymous = False
        nodes = []
        master_id = 2
        node = NavigationNode(
            "%s" % REPANIER_SETTINGS_PERMANENCES_NAME,
            "/",
            id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id = master_id

        separator = False
        permanence_board_set = PermanenceBoard.objects.filter(permanence__status__lte=PERMANENCE_WAIT_FOR_INVOICED).only(
            "id").order_by('?')
        if permanence_board_set.exists():
            submenu_id += 1
            node = NavigationNode(
                _('Calendar of activities'),
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
                .order_by('permanence_date'):
            displayed_permanence_counter += 1
            if first_pass and separator:
                submenu_id = self.append_separator(nodes, master_id, submenu_id)
            first_pass = False
            separator = True
            submenu_id = self.append_permanence(is_anonymous, permanence, nodes, master_id, submenu_id)

        first_pass = True
        closed_separator = separator
        for permanence in Permanence.objects.filter(status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND]) \
                .only("id", "permanence_date") \
                .order_by('-permanence_date'):
            displayed_permanence_counter += 1
            if first_pass and closed_separator:
                submenu_id = self.append_separator(nodes, master_id, submenu_id)
            first_pass = False
            separator = True
            closed_separator = False
            submenu_id = self.append_permanence(is_anonymous, permanence, nodes, master_id, submenu_id)
            if displayed_permanence_counter > 4:
                break
        # if displayed_permanence_counter < 4:
        #     max_counter = 4 - displayed_permanence_counter
        #     for permanence in Permanence.objects.filter(status__in=[PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]) \
        #             .only("id", "permanence_date") \
        #             .order_by('-permanence_date'):
        #         if permanence.permanence_date >= (
        #             timezone.now() - datetime.timedelta(weeks=LIMIT_DISPLAYED_PERMANENCE)).date():
        #             if first_pass and closed_separator:
        #                 submenu_id = self.append_separator(nodes, master_id, submenu_id)
        #             first_pass = False
        #             separator = True
        #             submenu_id = self.append_permanence(is_anonymous, permanence, nodes, master_id, submenu_id)
        #         max_counter -= 1
        #         if max_counter <= 0:
        #             break

        # if REPANIER_SETTINGS_INVOICE and not request.user.is_staff:
        #     if separator:
        #         submenu_id = self.append_separator(nodes, master_id, submenu_id)
        #     submenu_id += 1
        #     node = NavigationNode(
        #         '<span id="my_balance">%s</span>' % _('My balance'),
        #         reverse('customer_invoice_view', args=(0,)),
        #         id=submenu_id, parent_id=master_id,
        #         visible=True
        #     )
        #     nodes.append(node)

            # for node in nodes:
            #     logging.debug('Node before : %s' % node.get_menu_title())
            #     for attr in (x for x in dir(node) if not x.startswith('__')):
            #         logging.debug('%s => %s' % (attr, getattr(node, attr)))

        # master_id = 3
        # node = NavigationNode(
        #     "%s" % _('Group'),
        #     "/",
        #     id=master_id,
        #     visible=True
        # )
        # nodes.append(node)
        # submenu_id = master_id + 1
        # node = NavigationNode(
        #     _('Send mail to coordinators'),
        #     reverse('send_mail_to_coordinators_view'),
        #     id=submenu_id, parent_id=master_id,
        #     visible=True
        # )
        # nodes.append(node)
        # submenu_id += 1
        # if REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
        #     node = NavigationNode(
        #         _('Send mail to all members'),
        #         reverse('send_mail_to_all_members_view'),
        #         id=submenu_id, parent_id=master_id,
        #         visible=True
        #     )
        #     nodes.append(node)
        #     submenu_id += 1
        #     node = NavigationNode(
        #         _('Who is who'),
        #         reverse('who_is_who_view'),
        #         id=submenu_id, parent_id=master_id,
        #         visible=True
        #     )
        #     nodes.append(node)
        #     submenu_id += 1
        # node = NavigationNode(
        #     _('Me'),
        #     reverse('me_view'),
        #     id=submenu_id, parent_id=master_id,
        #     visible=True
        # )
        # nodes.append(node)

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
