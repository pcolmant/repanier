# -*- coding: utf-8
from __future__ import unicode_literals

from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from djng.forms.widgets import (
    ChoiceFieldRenderer as DjngChoiceFieldRenderer, CheckboxChoiceInput as DjngCheckboxChoiceInput,
    CheckboxFieldRendererMixin, CheckboxSelectMultiple as DjngCheckboxSelectMultiple)


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


class CheckboxInlineChoiceInput(DjngCheckboxChoiceInput):
    def render(self, name=None, value=None, attrs=None, choices=()):
        label_attrs = ['class="checkbox-inline"']
        if 'id' in self.attrs:
            label_attrs.append(format_html('for="{0}_{1}"', self.attrs['id'], self.index))
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
