# -*- coding: utf-8
from __future__ import unicode_literals

from itertools import chain

from django import forms
from django.utils.encoding import force_text
from django.utils.html import escape, conditional_escape
from django.utils.safestring import mark_safe

from repanier.const import EMPTY_STRING


class SelectBootstrapWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectBootstrapWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectBootstrapWidget, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        if value is None:
            value = EMPTY_STRING
        output = """
<div id="{name}_dropdown" class="btn-group pull-left btn-group-form">
    <button id="{name}_button_label" class="btn btn-default dropdown-toggle{disabled}" type="button" data-toggle="dropdown">{label}</button>
    <button class="btn btn-default dropdown-toggle{disabled}" type="button" data-toggle="dropdown"><span class="caret"></span></button>
    <ul class="dropdown-menu">{options}</ul>
    <input type="hidden" name="{name}" value="{value}" class="btn-group-value"/>
    <script type="text/javascript">
        function {name}_select(value, label) {{
            $('input[name={name}]').val(value);
            $('button[id={name}_button_label]').html(label);
        }}
    </script>
</div>
        """.format(
            options=self.render_options2(choices, [value, EMPTY_STRING], name),
            label=self.selected_choice,
            name=name,
            value=value,
            disabled=' disabled' if self.disabled else EMPTY_STRING
        )
        return mark_safe(output)

    def render_option2(self, selected_choices, option_value, option_label, name):
        option_value = force_text(option_value)
        if option_value in selected_choices:
            selected_html = ' selected="selected"'
            self.selected_choice = option_label
        else:
            selected_html = EMPTY_STRING
        return '<li><a href="javascript:%s_select(\'%s\', \'%s\')" data-value="%s"%s>%s</a></li>' % (
            name, option_value, option_label,
            escape(option_value), selected_html,
            conditional_escape(force_text(option_label)))

    def render_options2(self, choices, selected_choices, name):
        # Normalize to strings.
        selected_choices = set([force_text(v) for v in selected_choices])
        output = []
        for option_value, option_label in chain(self.choices, choices):
            output.append(self.render_option2(selected_choices, option_value, option_label, name))
        return u'\n'.join(output)
