import repanier.apps
from django.forms import NumberInput
from repanier.tools import get_repanier_template_name, get_repanier_static_name


class StockWidget(NumberInput):
    template_name = get_repanier_template_name("widgets/stock.html")

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        return context


