from django import forms

from repanier.const import EMPTY_STRING
from repanier.tools import get_repanier_template_name


class SelectBootstrapWidget(forms.Select):
    template_name = get_repanier_template_name("widgets/select_bootstrap.html")

    def get_context(self, name, value, attrs):
        context = super(SelectBootstrapWidget, self).get_context(name, value, attrs)
        selected_label = EMPTY_STRING
        if value is None:
            # This is the "Empty Value" for ModelChoicesField
            value = EMPTY_STRING
        else:
            value = str(value)
        for choice in self.choices:
            if str(choice[0]) == value:
                selected_label = choice[1]
                break
        context["repanier_selected_label"] = selected_label
        context["repanier_selected_value"] = value
        return context
