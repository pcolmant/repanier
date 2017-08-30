# -*- coding: utf-8
from __future__ import unicode_literals

import json
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from djng.forms.widgets import (
    ChoiceFieldRenderer as DjngChoiceFieldRenderer,
    CheckboxChoiceInput as DjngCheckboxChoiceInput,
    CheckboxSelectMultiple as DjngCheckboxSelectMultiple
)


class ChoiceFieldRenderer(DjngChoiceFieldRenderer):
    def render(self):
        """
        Outputs a <div ng-form="name"> for this set of choice fields to nest an ngForm.
        """
        start_tag = format_html('<div {}>', mark_safe(' '.join(self.field_attrs)))
        output = [start_tag]
        for widget in self:
            output.append(force_text(widget))
        output.append('</div>')
        return mark_safe('\n'.join(output))


class CheckboxFieldRendererMixin(object):
    def __init__(self, name, value, attrs, choices):
        attrs.pop('djng-error', None)
        self.field_attrs = [format_html('ng-form="{0}"', name)]
        field_names = [format_html('{0}.{1}', name, choice) for choice, dummy in choices]
        self.field_attrs.append(format_html('validate-multiple-fields="{0}"', json.dumps(field_names)))
        super(CheckboxFieldRendererMixin, self).__init__(name, value, attrs, choices)


class CheckboxInlineChoiceInput(DjngCheckboxChoiceInput):
    def render(self, name=None, value=None, attrs=None, choices=()):
        label_attrs = ['class="checkbox-inline"']
        if 'id' in self.attrs:
            label_attrs.append(format_html('for="{0}"', self.attrs['id']))
        label_for = mark_safe(' '.join(label_attrs))
        output = """
<div class="checkbox">
    <label {label_for}>
        {tag}
        <span class="cr"><i class="cr-icon glyphicon glyphicon-ok"></i></span>
        {choice_label}
    </label>
</div>
        """.format(
            label_for=label_for,
            tag=self.tag(),
            choice_label=self.choice_label
        )
        return mark_safe(output)


class CheckboxInlineFieldRenderer(CheckboxFieldRendererMixin, ChoiceFieldRenderer):
    choice_input_class = CheckboxInlineChoiceInput


class CheckboxSelectMultipleWidget(DjngCheckboxSelectMultiple):
    renderer = CheckboxInlineFieldRenderer

    class Media:
        css = {
            'all': ('css/checkbox_widget.css',)
        }
