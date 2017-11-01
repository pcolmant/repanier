# -*- coding: utf-8
from django.forms import CheckboxSelectMultiple


class CheckboxSelectMultipleWidget(CheckboxSelectMultiple):
    template_name = 'repanier/widgets/checkbox_select.html'

    def __init__(self, label, attrs=None, choices=()):
        # the label is rendered by the Widget class rather than by BoundField.label_tag()
        self.repanier_label = label
        super(CheckboxSelectMultipleWidget, self).__init__(attrs=attrs, choices=choices)

    def get_context(self, name, value, attrs):
        context = super(CheckboxSelectMultipleWidget, self).get_context(name, value, attrs)
        context['repanier_label'] = self.repanier_label
        return context

    class Media:
        css = {
            'all': ('css/checkbox_widget.css',)
        }