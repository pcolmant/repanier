from django import forms

from repanier_v2.tools import get_repanier_template_name


class SelectAdminOrderUnitWidget(forms.Select):
    template_name = get_repanier_template_name("widgets/select_admin_order_unit.html")

    class Media:
        js = ("admin/js/jquery.init.js",)
