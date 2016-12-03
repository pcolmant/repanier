# -*- coding: utf-8
from __future__ import unicode_literals

from cms.cms_toolbars import ADMIN_MENU_IDENTIFIER
from cms.toolbar.items import SubMenu
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from const import *
from models import Configuration


@toolbar_pool.register
class RepanierToolbar(CMSToolbar):
    def populate(self):
        from apps import REPANIER_SETTINGS_PERMANENCES_NAME, REPANIER_SETTINGS_INVOICE
        if settings.DJANGO_SETTINGS_DEMO:
            self.toolbar.get_or_create_menu("demo-menu", _('Demo (%s)') % (DEMO_EMAIL,))
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
        config = Configuration.objects.filter(id=DECIMAL_ONE).only('id').first()
        url = reverse('admin:repanier_configuration_change', args=(config.id,))
        office_menu.add_sideframe_item(_('Configuration'), url=url)
        url = reverse('admin:repanier_staff_changelist')
        office_menu.add_sideframe_item(_('Staff Member List'), url=url)
        url = reverse('admin:repanier_lut_permanencerole_changelist')
        office_menu.add_sideframe_item(_('Permanence Role List'), url=url)
        url = reverse('admin:repanier_lut_productionmode_changelist')
        office_menu.add_sideframe_item(_('Production Mode List'), url=url)
        url = reverse('admin:repanier_lut_deliverypoint_changelist')
        office_menu.add_sideframe_item(_('Delivery Point List'), url=url)
        url = reverse('admin:repanier_lut_departmentforcustomer_changelist')
        office_menu.add_sideframe_item(_('Departement for Customer List'), url=url)

        position += 1
        url = reverse('admin:repanier_customer_changelist')
        admin_menu.add_sideframe_item(_('Customer List'), url=url, position=position)

        position += 1
        url = reverse('admin:repanier_producer_changelist')
        admin_menu.add_sideframe_item(_('Producer List'), url=url, position=position)

        position += 1
        url = "%s?is_into_offer__exact=1" % reverse('admin:repanier_box_changelist')
        admin_menu.add_sideframe_item(_('Box List'), url=url, position=position)

        position += 1
        url = reverse('admin:repanier_permanenceinpreparation_changelist')
        admin_menu.add_sideframe_item(
            _("%(name)s in preparation list") % {'name': REPANIER_SETTINGS_PERMANENCES_NAME},
            url=url, position=position)

        if REPANIER_SETTINGS_INVOICE:
            position += 1
            url = reverse('admin:repanier_permanencedone_changelist')
            admin_menu.add_sideframe_item(
                _("%(name)s done list") % {'name': REPANIER_SETTINGS_PERMANENCES_NAME},
                url=url, position=position)

            position += 1
            url = reverse('admin:repanier_bankaccount_changelist')
            admin_menu.add_sideframe_item(_('Bank Account List'), url=url, position=position)
        else:
            position += 1
            url = reverse('admin:repanier_permanencedone_changelist')
            admin_menu.add_sideframe_item(
                _("%(name)s archived list") % {'name': REPANIER_SETTINGS_PERMANENCES_NAME},
                url=url, position=position)
