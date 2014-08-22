# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from cms.toolbar_pool import toolbar_pool
from cms.toolbar.items import Break, SubMenu
from cms.cms_toolbar import ADMIN_MENU_IDENTIFIER, ADMINISTRATION_BREAK
from cms.toolbar_base import CMSToolbar

from const import *


@toolbar_pool.register
class RepanierToolbar(CMSToolbar):
    def populate(self):
        admin_menu = self.toolbar.get_or_create_menu(ADMIN_MENU_IDENTIFIER, _('Manage'))
        position = admin_menu.get_alphabetical_insert_position(
            _('Parameters'),
            SubMenu
        )
        if not position:
            # TODO : Check this part of the code
            position = 0
            admin_menu.add_break('custom-break', position=position)
        office_menu = admin_menu.get_or_create_menu(
            'parameter-menu',
            _('Parameters ...'),
            position=position
        )
        # add_sideframe_item
        url = reverse('admin:repanier_staff_changelist')
        office_menu.add_sideframe_item(_('Staff Member List'), url=url)
        url = reverse('admin:repanier_lut_permanencerole_changelist')
        office_menu.add_sideframe_item(_('Permanence Role List'), url=url)
        url = reverse('admin:repanier_lut_productionmode_changelist')
        office_menu.add_sideframe_item(_('Production Mode List'), url=url)
        url = reverse('admin:repanier_lut_departmentforcustomer_changelist')
        office_menu.add_sideframe_item(_('Departement for Customer List'), url=url)

        position += 1
        url = reverse('admin:repanier_customer_changelist')
        admin_menu.add_sideframe_item(_('Customer List'), url=url, position=position)

        position += 1
        url = reverse('admin:repanier_producer_changelist')
        admin_menu.add_sideframe_item(_('Producer List'), url=url, position=position)

        position += 1
        url = reverse('admin:repanier_permanenceinpreparation_changelist')
        admin_menu.add_sideframe_item(_('Permanence in Preparation List'), url=url, position=position)

        if self.request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            # Not visible for read-only users
            position += 1
            url = reverse('admin:repanier_permanencedone_changelist')
            admin_menu.add_sideframe_item(_('Permanence done List'), url=url, position=position)
            position += 1
            url = reverse('admin:repanier_bankaccount_changelist')
            admin_menu.add_sideframe_item(_('Bank Account List'), url=url, position=position)
