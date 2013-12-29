# -*- coding: utf-8 -*-
from const import *
from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool
from django.utils.translation import ugettext_lazy as _
from cms.menu_bases import CMSAttachMenu
from repanier.models import Permanence

from menus.base import Menu, NavigationNode
from menus.menu_pool import menu_pool
from datetime import date
from django.core.urlresolvers import reverse
from django.conf import settings

import logging

class PermanenceMenu(Menu):

    def get_nodes(self, request):
        nodes = []
        # site = Site.objects.get_current()
        master_id = 1
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


        node = NavigationNode(
            _('My orders'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)
        submenu_id += 1

        node = NavigationNode(
            _('My participation'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)
        submenu_id += 1

        node = NavigationNode(
            _('My finance'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)

        submenu_id += 1
        node = NavigationNode(
            _('My deliveries pending for invoicing'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)
        submenu_id += 1

        node = NavigationNode(
            _('Send mail to coordinators'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)
        submenu_id += 1

        node = NavigationNode(
            _('Send mail to all members'),
            "/",
            id = submenu_id, parent_id = master_id,
            attr={'visible_for_authenticated' : True,
            'visible_for_anonymous' : True, },
            visible=True
        )
        nodes.append(node)
        submenu_id += 1

        separator = False
        for permanence in Permanence.objects.all().filter(
            status=PERMANENCE_OPEN, 
            site = settings.SITE_ID
            ).order_by("distribution_date"):
            if(not separator):
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
                separator = True
            node = NavigationNode(
                # _("Permanence on ") + permanence.distribution_date.strftime('%d-%m-%Y'),
                # reverse('order_view', args=(permanence.distribution_date.year,
                #     permanence.distribution_date.month, 
                #     permanence.distribution_date.day)),
                permanence,
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

