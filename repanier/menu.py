# -*- coding: utf-8 -*-
import datetime

from django.utils.formats import number_format
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from const import *
from settings import *
from models import Permanence
from models import CustomerInvoice
from models import PermanenceBoard


class PermanenceMenu(Menu):
    def get_nodes(self, request):
        nodes = []
        # if request.user.is_authenticated():
        master_id = 2
        node = NavigationNode(
            REPANIER_PERMANENCE_NAME,
            "/",
            id=master_id,
            visible=True
        )
        nodes.append(node)
        submenu_id = master_id + 1

        separator = False
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        permanence_board_set = PermanenceBoard.objects.filter(distribution_date__gte=now).order_by()[:1]
        if permanence_board_set:
            node = NavigationNode(
                _('Permanence board '),
                reverse('permanence_view'),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1
            separator = True

        # node = NavigationNode(
        # _('Send mail to coordinators'),
        #     "/",
        #     id = submenu_id, parent_id = master_id,
        #     attr={'visible_for_authenticated' : True,
        #     'visible_for_anonymous' : True, },
        #     visible=True
        # )
        # nodes.append(node)
        # submenu_id += 1

        # node = NavigationNode(
        #     _('Send mail to all members'),
        #     "/",
        #     id = submenu_id, parent_id = master_id,
        #     attr={'visible_for_authenticated' : True,
        #     'visible_for_anonymous' : True, },
        #     visible=True
        # )
        # nodes.append(node)
        # submenu_id += 1

        msg = unicode(_(' (opened)'))
        first_pass = True
        for permanence in Permanence.objects.filter(status=PERMANENCE_OPENED).order_by('distribution_date'):
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
                permanence.__unicode__() + msg,
                reverse('order_view', args=(permanence.id,)),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

        msg = unicode(_(' (closed)'))
        first_pass = True
        for permanence in Permanence.objects.filter(status=PERMANENCE_SEND).order_by('-distribution_date'):
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
                permanence.__unicode__() + msg,
                reverse('order_view', args=(permanence.id,)),
                id=submenu_id, parent_id=master_id,
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

        if request.user.is_authenticated():
            last_customer_invoice = CustomerInvoice.objects.filter(customer__user_id=request.user.id).order_by(
                '-id').first()
            if last_customer_invoice:
                if separator:
                    node = NavigationNode(
                        '------',
                        "/",
                        id=submenu_id, parent_id=master_id,
                        visible=True
                    )
                    nodes.append(node)
                    submenu_id += 1
                if last_customer_invoice.balance < 0:
                    node = NavigationNode(
                        unicode(_('My balance : <font color="red">%(balance)s &euro;</font> at %(date)s') % {
                            'balance': number_format(last_customer_invoice.balance, 2),
                            'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}),
                        reverse('invoice_view', args=(0,)),
                        id=submenu_id, parent_id=master_id,
                        visible=True
                    )
                else:
                    node = NavigationNode(
                        unicode(_('My balance : <font color="green">%(balance)s &euro;</font> at %(date)s') % {
                            'balance': number_format(last_customer_invoice.balance, 2),
                            'date': last_customer_invoice.date_balance.strftime('%d-%m-%Y')}),
                        reverse('invoice_view', args=(0,)),
                        id=submenu_id, parent_id=master_id,
                        visible=True
                    )
                nodes.append(node)

                # for node in nodes:
                #     logging.debug('Node before : %s' % node.get_menu_title())
                #     for attr in (x for x in dir(node) if not x.startswith('__')):
                #         logging.debug('%s => %s' % (attr, getattr(node, attr)))
        return nodes


menu_pool.register_menu(PermanenceMenu)

