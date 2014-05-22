# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.utils.formats import number_format
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool

import datetime
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _

from cms.menu_bases import CMSAttachMenu
from repanier.models import Permanence
from repanier.models import CustomerInvoice
from repanier.models import PermanenceBoard

from datetime import date
from django.core.urlresolvers import reverse


import logging


class AccountMenu(Menu):

    def get_nodes(self, request):
        nodes = []
        master_id = 1
        last_customer_invoice_set = CustomerInvoice.objects.filter(customer__user_id=request.user.id).order_by('-id')[:1]
        if last_customer_invoice_set:
            last_customer_invoice = last_customer_invoice_set[0]
            if last_customer_invoice.balance < 0:
                node = NavigationNode(
                    _('My saldo : ') + '<font color="red">' + number_format(last_customer_invoice.balance, 2) + ' &euro;</font>',
                    reverse('invoice_view', args=(0,)),
                    id = master_id,
                    attr={'visible_for_authenticated' : True,
                    'visible_for_anonymous' : True, },
                    visible=True
                )
            else:
                node = NavigationNode(
                    _('My saldo : ') + '<font color="green">' + number_format(last_customer_invoice.balance, 2) + ' &euro;</font>',
                    reverse('invoice_view', args=(0,)),
                    id = master_id,
                    attr={'visible_for_authenticated' : True,
                    'visible_for_anonymous' : True, },
                    visible=True
                )
            nodes.append(node)
            separator = True

        return nodes

menu_pool.register_menu(AccountMenu)

class PermanenceMenu(Menu):

    def get_nodes(self, request):
        nodes = []
        master_id = 2
        node = NavigationNode(
            _('Permanence'), 
            "/", 
            id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
            )
        nodes.append(node)
        submenu_id = master_id + 1


        # node = NavigationNode(
        #     _('My participation'),
        #     "/",
        #     id = submenu_id, parent_id = master_id,
        #     attr={'visible_for_authenticated' : True,
        #     'visible_for_anonymous' : True, },
        #     visible=True
        # )
        # nodes.append(node)
        # submenu_id += 1
        separator = False
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        permanence_board_set = PermanenceBoard.objects.filter(distribution_date__gte=now).order_by()[:1]
        if permanence_board_set:
            node = NavigationNode(
                _('Permanence board '),
                reverse('permanence_view'),
                id = submenu_id, parent_id = master_id,
                attr={'visible_for_authenticated' : True,
                'visible_for_anonymous' : True, },
                visible=True
            )
            nodes.append(node)
            submenu_id += 1
            separator = True

        # node = NavigationNode(
        #     _('Send mail to coordinators'),
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
        for permanence in Permanence.objects.all().is_opened().order_by('distribution_date'):
            if first_pass and separator:
                node = NavigationNode(
                    ('------'),
                    "/",
                    id = submenu_id, parent_id = master_id,
                    attr={'visible_for_authenticated' : True,
                    'visible_for_anonymous' : True, },
                    visible=True
                )
                nodes.append(node)
                submenu_id += 1
                first_pass = False
            node = NavigationNode(
                permanence.__unicode__() + msg,
                reverse('order_view', args=(permanence.id,)),                
                id = submenu_id, parent_id = master_id,
                attr={'visible_for_authenticated' : True,
                'visible_for_anonymous' : True, },
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

        msg = unicode(_(' (closed)'))
        first_pass = True
        for permanence in Permanence.objects.all().is_send().order_by('-distribution_date'):
            if first_pass and separator:
                node = NavigationNode(
                    ('------'),
                    "/",
                    id = submenu_id, parent_id = master_id,
                    attr={'visible_for_authenticated' : True,
                    'visible_for_anonymous' : True, },
                    visible=True
                )
                nodes.append(node)
                submenu_id += 1
                first_pass = False
            node = NavigationNode(
                permanence.__unicode__() + msg,
                reverse('order_view', args=(permanence.id,)),                
                id = submenu_id, parent_id = master_id,
                attr={'visible_for_authenticated' : True,
                'visible_for_anonymous' : True, },
                visible=True
            )
            nodes.append(node)
            submenu_id += 1

            # for node in nodes:
            #     logging.debug('Node before : %s' % node.get_menu_title())
            #     for attr in (x for x in dir(node) if not x.startswith('__')):
            #         logging.debug('%s => %s' % (attr, getattr(node, attr)))
        return nodes

menu_pool.register_menu(PermanenceMenu)

