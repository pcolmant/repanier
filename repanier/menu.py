# -*- coding: utf-8
from __future__ import unicode_literals
import datetime

from django.conf import settings
from models import repanier_settings
from django.utils.formats import number_format
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse


from const import *
from models import Permanence
from models import CustomerInvoice
from models import PermanenceBoard


class PermanenceMenu(Menu):
    def get_nodes(self, request):
        nodes = []
        # if request.user.is_authenticated():
        master_id = 2
        node = NavigationNode(
            "%s" % repanier_settings['PERMANENCE_NAME'],
            "/",
            id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id = master_id + 1

        separator = False
        # now = datetime.datetime.utcnow().replace(tzinfo=utc)
        permanence_board_set = PermanenceBoard.objects.filter(permanence__status__lte=PERMANENCE_WAIT_FOR_DONE).only("id").order_by()
        if permanence_board_set.exists():
            node = NavigationNode(
                _('Permanence board '),
                reverse('permanence_view'),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1
            separator = True

        msg = _(' (opened)')
        first_pass = True
        for permanence in Permanence.objects.filter(status=PERMANENCE_OPENED)\
                .only("id", "permanence_date")\
                .order_by('permanence_date'):
            if first_pass and separator:
                node = NavigationNode(
                    '------',
                    "/",
                    id=submenu_id, parent_id=master_id,
                    visible=True
                )
                nodes.append(node)
                submenu_id += 1
            first_pass = False
            if repanier_settings['DISPLAY_ANONYMOUS_ORDER_FORM']:
                path = reverse('basket_view', args=(permanence.id,))
            else:
                path = reverse('order_view', args=(permanence.id,))
            node = NavigationNode(
                '%s %s' % (permanence, msg),
                path,
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

        msg = _(' (closed)')
        first_pass = True
        for permanence in Permanence.objects.filter(status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND])\
                .only("id", "permanence_date")\
                .order_by('-permanence_date'):
            if first_pass and separator:
                node = NavigationNode(
                    '------',
                    "/",
                    id=submenu_id, parent_id=master_id,
                    visible=True
                )
                nodes.append(node)
                submenu_id += 1
            first_pass = False
            node = NavigationNode(
                '%s %s' % (permanence, msg),
                reverse('basket_view', args=(permanence.id,)),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

        if request.user.is_authenticated():
            last_customer_invoice = CustomerInvoice.objects.filter(
                customer__user_id=request.user.id,
                invoice_sort_order__isnull=False)\
                .only("balance", "date_balance")\
                .order_by('-invoice_sort_order')
            if last_customer_invoice.exists():
                if separator:
                    node = NavigationNode(
                        '------',
                        "/",
                        id=submenu_id, parent_id=master_id,
                        visible=True
                    )
                    nodes.append(node)
                    submenu_id += 1
                node = NavigationNode(
                    '<span id="my_balance">%s</span>' % _('My balance'),
                    reverse('customer_invoice_view', args=(0,)),
                    id=submenu_id, parent_id=master_id,
                    visible=True
                )
                nodes.append(node)

                # for node in nodes:
                #     logging.debug('Node before : %s' % node.get_menu_title())
                #     for attr in (x for x in dir(node) if not x.startswith('__')):
                #         logging.debug('%s => %s' % (attr, getattr(node, attr)))

        master_id = 3
        node = NavigationNode(
            "%s" % _('Group'),
            "/",
            id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id = master_id + 1
        node = NavigationNode(
        _('Send mail to coordinators'),
            reverse('send_mail_to_coordinators_view'),
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id += 1
        node = NavigationNode(
            _('Send mail to all members'),
            reverse('send_mail_to_all_members_view'),
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id += 1
        node = NavigationNode(
            _('Who is who'),
            reverse('who_is_who_view'),
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id += 1
        node = NavigationNode(
            _('Me'),
            reverse('me_view'),
            id=submenu_id, parent_id=master_id,
            visible=True
        )
        nodes.append(node)

        return nodes


menu_pool.register_menu(PermanenceMenu)

