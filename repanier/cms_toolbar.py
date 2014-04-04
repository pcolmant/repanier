# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from cms.toolbar_pool import toolbar_pool
from cms.toolbar.items import Break, SubMenu
from cms.cms_toolbar import ADMIN_MENU_IDENTIFIER, ADMINISTRATION_BREAK
from cms.toolbar_base import CMSToolbar

@toolbar_pool.register
class RepanierToolbar(CMSToolbar):

	def populate(self):
		admin_menu = self.toolbar.get_or_create_menu(ADMIN_MENU_IDENTIFIER, _('Manage'))
		# _('Administration')
		position = admin_menu.get_alphabetical_insert_position(
			_('Parameters'),
			SubMenu
		)
		if not position:
			position = admin_menu.find_first(
				Break,
				identifier=ADMINISTRATION_BREAK
			) + 1
			position = 0
			admin_menu.add_break('custom-break', position=position)
		office_menu = admin_menu.get_or_create_menu(
			'parameter-menu',
			_('Paramters ...'),
			position=position
		)
		# add_sideframe_item
		url = reverse('admin:repanier_staff_changelist')
		office_menu.add_sideframe_item(_('Staff Member List'), url=url)
		# url = reverse('admin:repanier_staff_add')
		# office_menu.add_modal_item(_('Add New Staff Member'), url=url)
		# office_menu.add_break()
		url = reverse('admin:repanier_lut_permanencerole_changelist')
		office_menu.add_sideframe_item(_('Permanence Role List'), url=url)
		# url = reverse('admin:repanier_lut_permanencerole_add')
		# office_menu.add_modal_item(_('Add New Permanence Role'), url=url)
		# office_menu.add_break()
		url = reverse('admin:repanier_lut_productionmode_changelist')
		office_menu.add_sideframe_item(_('Production Mode List'), url=url)
		# url = reverse('admin:repanier_lut_productionmode_add')
		# office_menu.add_modal_item(_('Add New Production Mode'), url=url)
		# office_menu.add_break()
		url = reverse('admin:repanier_lut_departmentforcustomer_changelist')
		office_menu.add_sideframe_item(_('Departement for Customer List'), url=url)
		# url = reverse('admin:repanier_lut_departmentforcustomer_add')
		# office_menu.add_modal_item(_('Add New Departement for Customer'), url=url)
		# position += 1
		# customer_menu = admin_menu.get_or_create_menu(
		# 	'customer-menu',
		# 	_('Customer ...'),
		# 	position=position
		# )
		position += 1
		url = reverse('admin:repanier_customer_changelist')
		admin_menu.add_sideframe_item(_('Customer List'), url=url, position=position)
		# url = reverse('admin:repanier_customer_add')
		# customer_menu.add_modal_item(_('Add New Customer'), url=url)
		# producer_menu = admin_menu.get_or_create_menu(
		# 	'producer-menu',
		# 	_('Producer ...'),
		# 	position=position
		# )
		position += 1
		url = reverse('admin:repanier_producer_changelist')
		admin_menu.add_sideframe_item(_('Producer List'), url=url, position=position)
		# url = reverse('admin:repanier_producer_add')
		# producer_menu.add_modal_item(_('Add New Producer'), url=url)
		# producer_menu.add_break()
		# url = reverse('admin:repanier_product_changelist')
		# producer_menu.add_sideframe_item(_('Product List'), url=url)
		# url = reverse('admin:repanier_product_add')
		# producer_menu.add_modal_item(_('Add New Product'), url=url)
		position += 1
		# order_menu = admin_menu.get_or_create_menu(
		# 	'order-menu',
		# 	_('Order ...'),
		# 	position=position
		# )
		url = reverse('admin:repanier_permanenceinpreparation_changelist')
		admin_menu.add_sideframe_item(_('Permanence in Preparation List'), url=url, position=position)
		# url = reverse('admin:repanier_permanenceinpreparation_add')
		# order_menu.add_modal_item(_('Add New Permanence in Preparation'), url=url)
		position += 1
		# invoice_menu = admin_menu.get_or_create_menu(
		# 	'invoice-menu',
		# 	_('Invoice ...'),
		# 	position=position
		# )
		url = reverse('admin:repanier_permanencedone_changelist')
		admin_menu.add_sideframe_item(_('Permanence done List'), url=url, position=position)
		position += 1
		url = reverse('admin:repanier_bankaccount_changelist')
		admin_menu.add_sideframe_item(_('Bank Account List'), url=url, position=position)
		# url = reverse('admin:repanier_bankaccount_add')
		# invoice_menu.add_modal_item(_('Add New Bank Account'), url=url)