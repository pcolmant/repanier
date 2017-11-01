# -*- coding: utf-8
from django.forms import CheckboxInput


class CheckboxWidget(CheckboxInput):
    template_name = 'repanier/widgets/checkbox.html'

    def __init__(self, label, attrs=None, check_test=None):
        # the label is rendered by the Widget class rather than by BoundField.label_tag()
        self.repanier_label = label
        super(CheckboxWidget, self).__init__(attrs=attrs, check_test=check_test)

    def get_context(self, name, value, attrs):
        context = super(CheckboxWidget, self).get_context(name, value, attrs)
        context['repanier_label'] = self.repanier_label
        return context

    class Media:
        css = {
            'all': ('css/checkbox_widget.css',)
        }
