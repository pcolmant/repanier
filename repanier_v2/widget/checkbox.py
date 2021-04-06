from django.forms import CheckboxInput

from repanier_v2.tools import get_repanier_template_name, get_repanier_static_name


class RepanierCheckboxWidget(CheckboxInput):
    template_name = get_repanier_template_name("widgets/checkbox.html")

    def __init__(self, label, attrs=None, check_test=None):
        # the label is rendered by the Widget class rather than by BoundField.label_tag()
        self.repanier_label = label
        super().__init__(attrs=attrs, check_test=check_test)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["repanier_label"] = self.repanier_label
        return context

    class Media:
        css = {"all": (get_repanier_static_name("css/widgets/checkbox.css"),)}
