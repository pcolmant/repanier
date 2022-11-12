from cms.cms_toolbars import ADMIN_MENU_IDENTIFIER, HELP_MENU_IDENTIFIER, HELP_MENU_BREAK, BasicToolbar
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.conf import get_cms_setting
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from repanier.const import *


@toolbar_pool.register
class RepanierToolbar(BasicToolbar):
    def populate(self):
        user = self.request.user
        if user.is_anonymous:
            return
        if ADMIN_MENU_IDENTIFIER in self.toolbar.menus:
            menu = self.toolbar.menus[ADMIN_MENU_IDENTIFIER]
            self.toolbar.remove_item(menu)
        admin_menu = self.toolbar.get_or_create_menu("repanier-menu", _("Manage"), position=0)
        # self.toolbar.add_item(admin_menu, position=0)
        position = 0

        if user.is_order_manager or user.is_invoice_manager:
            office_menu = admin_menu.get_or_create_menu(
                "parameter-menu", _("Parameters ..."), position=position
            )
            position += 1

            if user.is_repanier_admin:
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

            if settings.REPANIER_SETTINGS_DELIVERY_POINT:
                url = "{}?is_active__exact=1".format(
                    reverse("admin:repanier_lut_deliverypoint_changelist")
                )
                office_menu.add_sideframe_item(_("Delivery points"), url=url)

        url = reverse("admin:repanier_notification_change", args=(1,))
        admin_menu.add_sideframe_item(_('"Flash" ad'), url=url, position=position)
        position += 1

        if user.is_repanier_admin:
            url = reverse("admin:repanier_staff_changelist")
            admin_menu.add_sideframe_item(
                _("Management team"), url=url, position=position
            )
            position += 1

        if user.is_order_manager or user.is_invoice_manager:
            if settings.REPANIER_SETTINGS_DELIVERY_POINT:
                url = "{}?is_active__exact=1".format(
                    reverse("admin:repanier_group_changelist")
                )
                admin_menu.add_sideframe_item(_("Groups"), url=url, position=position)
                position += 1

            url = "{}?is_active__exact=1".format(
                reverse("admin:repanier_customer_changelist")
            )
            admin_menu.add_sideframe_item(_("Customers"), url=url, position=position)
            position += 1

            url = "{}?is_active__exact=1".format(
                reverse("admin:repanier_producer_changelist")
            )
            admin_menu.add_sideframe_item(_("Producers"), url=url, position=position)
            position += 1

            # if settings.REPANIER_SETTINGS_BOX:
            #     url = "{}?is_into_offer__exact=1&is_active__exact=1".format(
            #         reverse("admin:repanier_box_changelist")
            #     )
            #     admin_menu.add_sideframe_item(_("Boxes"), url=url, position=position)
            #     position += 1

        if user.is_order_manager:
            url = reverse("admin:repanier_permanenceinpreparation_changelist")
            admin_menu.add_sideframe_item(
                _("Offers in preparation"), url=url, position=position
            )
            position += 1

        if user.is_invoice_manager:
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                url = reverse("admin:repanier_permanencedone_changelist")
                admin_menu.add_sideframe_item(
                    _("Offers in payment"), url=url, position=position
                )
                position += 1
                url = reverse("admin:repanier_bankaccount_changelist")
                admin_menu.add_sideframe_item(
                    _("Bank account transactions"), url=url, position=position
                )
                position += 1
            else:
                url = reverse("admin:repanier_permanencedone_changelist")
                admin_menu.add_sideframe_item(
                    _("Offers in archiving"), url=url, position=position
                )
                position += 1

        admin_menu.add_break("custom-break", position=position)
        position += 1

        # Users
        self.add_users_button(admin_menu)
        # Logout
        self.add_logout_button(admin_menu)
        # Help menu
        self.add_help_menu()


    def add_help_menu(self):
        """ Adds the help menu """
        self._help_menu = self.toolbar.get_or_create_menu(HELP_MENU_IDENTIFIER, _('Help'), position=-1)

        extra_menu_items = get_cms_setting('EXTRA_HELP_MENU_ITEMS')
        if extra_menu_items:
            for label, url in extra_menu_items:
                self._help_menu.add_link_item(label, url=url)
