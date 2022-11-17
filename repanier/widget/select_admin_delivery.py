from django import forms
from django.utils.safestring import mark_safe

from repanier.const import (
    SaleStatus,
)
from repanier.models.deliveryboard import DeliveryBoard
from repanier.tools import get_repanier_template_name


class SelectAdminDeliveryWidget(forms.Select):
    template_name = get_repanier_template_name("widgets/select_admin_purchase_qty.html")

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        case_show_show = 'case "0": '
        case_show_hide = 'case "0": '
        case_hide_show = 'case "0": '
        for option_value, option_label in self.choices:
            status = (
                DeliveryBoard.objects.filter(id=option_value)
                .only("status")
                .first()
                .status
            )
            if status in [SaleStatus.PLANNED.value, SaleStatus.OPENED.value, SaleStatus.CLOSED.value]:
                case_show_hide += 'case "{}": '.format(option_value)
            elif status == SaleStatus.SEND.value:
                case_hide_show += 'case "{}": '.format(option_value)
            else:
                case_show_show += 'case "{}": '.format(option_value)
        context["case_show_show"] = mark_safe(case_show_show)
        context["case_show_hide"] = mark_safe(case_show_hide)
        context["case_hide_show"] = mark_safe(case_hide_show)
        return context

    class Media:
        js = ("admin/js/jquery.init.js",)
