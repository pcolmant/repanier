# -*- coding: utf-8
from __future__ import unicode_literals

from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.forms import CheckboxInput
# from djng.styling.bootstrap3.widgets import CheckboxInput


class CheckboxWidget(CheckboxInput):
    # http://bootsnipp.com/snippets/featured/animated-radios-amp-checkboxes-nojs

    def __init__(self, label, attrs=None, check_test=None):
        # the label is rendered by the Widget class rather than by BoundField.label_tag()
        self.choice_label = label
        super(CheckboxWidget, self).__init__(attrs, check_test)

    def render(self, name, value, attrs=None):
        attrs = attrs or self.attrs
        label_attrs = ['class="checkbox-inline"']
        if 'id' in self.attrs:
            label_attrs.append(format_html('for="{}"', self.attrs['id']))
        label_for = mark_safe(' '.join(label_attrs))
        tag = super(CheckboxWidget, self).render(name, value, attrs)
        # return format_html('<div class="checkbox"><label {0}>{1}<span class="cr"><i class="cr-icon glyphicon glyphicon-ok"></i></span> {2}</label></div>', label_for, tag, self.choice_label)
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
            tag=tag,
            choice_label=self.choice_label
        )
        return mark_safe(output)

    class Media:
        css = {
            'all': ('css/checkbox_widget.css',)
        }
