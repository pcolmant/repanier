from cms.api import can_change_page
from cms.cms_toolbars import ADMIN_MENU_IDENTIFIER, BasicToolbar, PAGE_MENU_IDENTIFIER
from cms.utils import page_permissions
from cms.utils.urlutils import admin_reverse, add_url_parameters

try:
    from cms.cms_toolbars import HELP_MENU_IDENTIFIER, HELP_MENU_BREAK
except:
    HELP_MENU_IDENTIFIER = 'help-menu'
    HELP_MENU_BREAK = 'Help Menu Break'
from cms.toolbar_pool import toolbar_pool
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from repanier.const import *

REPANIER_MENU_IDENTIFIER = "repanier-menu"


@toolbar_pool.register
class RepanierToolbar(BasicToolbar):
    def has_page_change_permission(self):
        if not hasattr(self, 'page_change_permission'):
            self.page_change_permission = can_change_page(self.request)
        return self.page_change_permission

    def populate(self):
        user = self.request.user
        if user.is_anonymous:
            return
        if ADMIN_MENU_IDENTIFIER in self.toolbar.menus:
            menu = self.toolbar.menus[ADMIN_MENU_IDENTIFIER]
            self.toolbar.remove_item(menu)
        repanier_menu = self.toolbar.get_or_create_menu(REPANIER_MENU_IDENTIFIER, _("Manage"), position=0)
        # self.toolbar.add_item(admin_menu, position=0)
        position = 0

        office_menu = repanier_menu.get_or_create_menu(
            "parameter-menu", _("Parameters ..."), position=position
        )
        position += 1

        url = reverse("admin:repanier_configuration_change", args=(1,))
        office_menu.add_sideframe_item(_("Configuration"), url=url)

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_lut_permanencerole_changelist")
        )
        office_menu.add_sideframe_item(_("Tasks"), url=url)

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_lut_productionmode_changelist")
        )
        office_menu.add_sideframe_item(_("Labels"), url=url)

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_lut_departmentforcustomer_changelist")
        )
        office_menu.add_sideframe_item(_("Departments"), url=url)

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_lut_deliverypoint_changelist")
        )
        office_menu.add_sideframe_item(_("Delivery points"), url=url)

        url = reverse("admin:repanier_notification_change", args=(1,))
        repanier_menu.add_sideframe_item(_('"Flash" ad'), url=url, position=position)
        position += 1

        url = reverse("admin:repanier_staff_changelist")
        repanier_menu.add_sideframe_item(
            _("Management team"), url=url, position=position
        )
        position += 1

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_group_changelist")
        )
        repanier_menu.add_sideframe_item(_("Groups"), url=url, position=position)
        position += 1

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_customer_changelist")
        )
        repanier_menu.add_sideframe_item(_("Customers"), url=url, position=position)
        position += 1

        url = "{}?is_active__exact=1".format(
            reverse("admin:repanier_producer_changelist")
        )
        repanier_menu.add_sideframe_item(_("Producers"), url=url, position=position)
        position += 1

        url = reverse("admin:repanier_permanenceinpreparation_changelist")
        repanier_menu.add_sideframe_item(
            _("Offers in preparation"), url=url, position=position
        )
        position += 1

        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            url = reverse("admin:repanier_permanencedone_changelist")
            repanier_menu.add_sideframe_item(
                _("Offers in payment"), url=url, position=position
            )
            position += 1
            url = reverse("admin:repanier_bankaccount_changelist")
            repanier_menu.add_sideframe_item(
                _("Bank account transactions"), url=url, position=position
            )
            position += 1
        else:
            url = reverse("admin:repanier_permanencedone_changelist")
            repanier_menu.add_sideframe_item(
                _("Offers in archiving"), url=url, position=position
            )
            position += 1

        repanier_menu.add_break("custom-break", position=position)
        position += 1

        # Pages, copy from
        can_change_page = self.has_page_change_permission()

        if not can_change_page:
            # Check if the user has permissions to change at least one page
            can_change_page = page_permissions.user_can_change_at_least_one_page(
                user=self.request.user,
                site=self.current_site,
            )

        if can_change_page:
            page_menu = self.toolbar.get_or_create_menu(PAGE_MENU_IDENTIFIER, _("Page"), position=1)

            url = admin_reverse('cms_pagecontent_changelist')  # cms page admin
            params = {'language': self.toolbar.request_language}
            if self.page:
                params['page_id'] = self.page.pk
            url = add_url_parameters(url, params)
            page_menu.add_sideframe_item(_('Page Tree'), url=url, position=0)

            url = reverse('admin:filer-directory_listing-root') # filer page admin
            page_menu.add_sideframe_item(_('Files'), url=url, position=1)

        # Users
        self.add_users_button(repanier_menu)
        # Logout
        self.add_logout_button(repanier_menu)
        # Help menu
        self.add_help_menu()


    def add_help_menu(self):
        """ Adds the help menu """
        self._help_menu = self.toolbar.get_or_create_menu(HELP_MENU_IDENTIFIER, _('Help'), position=-1)

        extra_menu_items = getattr(settings, 'CMS_EXTRA_HELP_MENU_ITEMS', False)
        if extra_menu_items:
            for label, url in extra_menu_items:
                self._help_menu.add_link_item(label, url=url)
