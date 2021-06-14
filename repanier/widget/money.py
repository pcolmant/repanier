import repanier.apps
from django.forms import NumberInput
from repanier.tools import get_repanier_template_name, get_repanier_static_name


class MoneyWidget(NumberInput):
    template_name = get_repanier_template_name("widgets/money.html")

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context[
            "repanier_currency_after"
        ] = repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT
        context["repanier_currency_str"] = (
            '<i class="fas fa-euro-sign"></i>'
            if repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY == "€"
            else repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY
        )
        return context

    class Media:
    #     css = {
    #         'all': ('css/checkbox.css',)
    #     }
        js = (get_repanier_static_name("js/admin/calculator-parser.js"),)


