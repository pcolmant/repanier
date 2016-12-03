# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.forms.utils import flatatt
from django.utils.safestring import mark_safe

from repanier.const import EMPTY_STRING, PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND, PERMANENCE_PLANNED
from repanier.models import DeliveryBoard


class SelectAdminDeliveryWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectAdminDeliveryWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectAdminDeliveryWidget, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        if value is None:
            value = EMPTY_STRING
        final_attrs = self.build_attrs(attrs, name=name)
        case_show_show = 'case "0": '
        case_show_hide = 'case "0": '
        case_hide_show = 'case "0": '
        for option_value, option_label in self.choices:
            status = DeliveryBoard.objects.filter(id=option_value).order_by('?').only('status').first().status
            if status in [PERMANENCE_PLANNED, PERMANENCE_OPENED, PERMANENCE_CLOSED]:
                case_show_hide += 'case "%d": ' % option_value
            elif status == PERMANENCE_SEND:
                case_hide_show += 'case "%d": ' % option_value
            else:
                case_show_show += 'case "%d": ' % option_value
        output = """
            <select{final_attrs} onchange="{name}_select(this.value)">
                {options}
            </select>
            <script type="text/javascript">
                django.jQuery(document).ready(function() {{ {name}_select("{value}");}});
                function {name}_select(value) {{
                    (function($){{
                        switch (value) {{
                            {case_show_show}
                                $("div.form-row.field-quantity_ordered").show();
                                $("div.form-row.field-quantity_invoiced").show();
                                break;
                            {case_show_hide}
                                $("div.form-row.field-quantity_ordered").show();
                                $("div.form-row.field-quantity_invoiced").hide();
                                break;
                            {case_hide_show}
                                $("div.form-row.field-quantity_ordered").hide();
                                $("div.form-row.field-quantity_invoiced").show();
                                break;
                        }}
                    }}(django.jQuery))
                }}
            </script>

        """.format(
            final_attrs=flatatt(final_attrs),
            name=name,
            options=self.render_options(choices, [value]),
            value=value,
            case_show_show=case_show_show,
            case_show_hide=case_show_hide,
            case_hide_show=case_hide_show
        )
        return mark_safe(output)
