# -*- coding: utf-8
from __future__ import unicode_literals
from itertools import chain
from django import forms
from django.forms.utils import flatatt
from django.template.loader import render_to_string
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from const import *

class SelectWidgetBootstrap(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectWidgetBootstrap, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectWidgetBootstrap, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        output = ["""<div id="%(name)s_dropdown" class="btn-group pull-left btn-group-form">"""
                  """    <button id="%(name)s_button_label" class="btn btn-default dropdown-toggle%(disabled)s" type="button" data-toggle="dropdown">%(label)s</button>"""
                  """    <button class="btn btn-default dropdown-toggle%(disabled)s" type="button" data-toggle="dropdown">"""
                  """        <span class="caret"></span>"""
                  """    </button>"""
                  """    <ul class="dropdown-menu">"""
                  """        %(options)s"""
                  """    </ul>"""
                  """    <input type="hidden" name="%(name)s" value="%(value)s" class="btn-group-value"/>"""
                  """<script type="text/javascript">"""
                  # """    $(document).ready(function() {"""
                  # """        $('#%(name)s_dropdown').on('show.bs.dropdown', function () {"""
                  # """            $("#%(name)s_dropdown ul").empty();"""
                  # """            $("#%(name)s_dropdown ul").append('<li><a href="#">Hello</a></li>');"""
                  # """        });"""
                  # """    });"""
                  """    function %(name)s_select(value, label) {"""
                  """        $('input[name=%(name)s]').val(value);"""
                  """        $('button[id=%(name)s_button_label]').html(label);"""
                  """    }"""
                  """</script>"""
                  """</div>"""
                   % {'options': self.render_options2(choices, [value, ""], name),
                      'label': self.selected_choice,
                      'name': name,
                      'value': value,
                      'disabled': ' disabled' if self.disabled else ''
                      }]
        return mark_safe(u'\n'.join(output))

    def render_option2(self, selected_choices, option_value, option_label, name):
        option_value = force_unicode(option_value)
        if option_value in selected_choices:
            selected_html = ' selected="selected"'
            self.selected_choice = option_label
        else:
            selected_html = ''
        return '<li><a href="javascript:%s_select(\'%s\', \'%s\')" data-value="%s"%s>%s</a></li>' % (
            name, option_value, option_label,
            escape(option_value), selected_html,
            conditional_escape(force_unicode(option_label)))

    def render_options2(self, choices, selected_choices, name):
        # Normalize to strings.
        selected_choices = set([force_unicode(v) for v in selected_choices])
        output = []
        for option_value, option_label in chain(self.choices, choices):
            output.append(self.render_option2(selected_choices, option_value, option_label, name))
        return u'\n'.join(output)

    # class Media:
    #     css = {
    #         "all": ("bootstrap/css/bootstrap.css",
    #                 "bootstrap/css/custom.css"
    #         )
    #     }
    #     js = ("https://ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js",
    #           "//netdna.bootstrapcdn.com/bootstrap/3.1.1/js/bootstrap.min.js"
    #     )


class SelectProducerOrderUnitWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectProducerOrderUnitWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectProducerOrderUnitWidget, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        output = ["""<div id="%(name)s_dropdown" class="btn-group pull-left btn-group-form">"""
                  """    <button id="%(name)s_button_label" class="btn btn-default dropdown-toggle%(disabled)s" type="button" data-toggle="dropdown">%(label)s</button>"""
                  """    <button class="btn btn-default dropdown-toggle%(disabled)s" type="button" data-toggle="dropdown">"""
                  """        <span class="caret"></span>"""
                  """    </button>"""
                  """    <ul class="dropdown-menu">"""
                  """        %(options)s"""
                  """    </ul>"""
                  """    <input type="hidden" name="%(name)s" value="%(value)s" class="btn-group-value"/>"""
                  """<script type="text/javascript">"""
                  """switch($('input[name=%(name)s]').val()) {"""
                  """   case '%(PRODUCT_ORDER_UNIT_PC_PRICE_PC)s':"""
                  """       $('span[id=customer_increment_order_quantity_label]').html('%(INCREMENT_ORDER_UNIT_PC_PRICE_PC_LABEL)s');"""
                  """       $('span[id=customer_increment_order_quantity_addon]').html('%(INCREMENT_ORDER_UNIT_PC_PRICE_PC_ADDON)s');"""
                  """       $('span[id=stock_label]').html('%(STOCK_ORDER_UNIT_PC_PRICE_PC_LABEL)s');"""
                  """       $('span[id=stock_addon]').html('%(STOCK_ORDER_UNIT_PC_PRICE_PC_ADDON)s');"""
                  """       $('span[id=producer_unit_price_addon]').html('%(PRICE_ORDER_UNIT_PC_PRICE_PC_ADDON)s');"""
                  """       $('div[id=div_id_order_average_weight]').hide();"""
                  """       break;"""
                  """   case '%(PRODUCT_ORDER_UNIT_PC_PRICE_KG)s':"""
                  """       $('span[id=customer_increment_order_quantity_label]').html('%(INCREMENT_ORDER_UNIT_PC_PRICE_KG_LABEL)s');"""
                  """       $('span[id=customer_increment_order_quantity_addon]').html('%(INCREMENT_ORDER_UNIT_PC_PRICE_KG_ADDON)s');"""
                  """       $('span[id=stock_label]').html('%(STOCK_ORDER_UNIT_PC_PRICE_KG_LABEL)s');"""
                  """       $('span[id=stock_addon]').html('%(STOCK_ORDER_UNIT_PC_PRICE_KG_ADDON)s');"""
                  """       $('span[id=producer_unit_price_addon]').html('%(PRICE_ORDER_UNIT_PC_PRICE_KG_ADDON)s');"""
                  """       $('div[id=div_id_order_average_weight]').hide();"""
                  """       break;"""
                  """   case '%(PRODUCT_ORDER_UNIT_PC_KG)s':"""
                  """       $('span[id=customer_increment_order_quantity_label]').html('%(INCREMENT_ORDER_UNIT_PC_KG_LABEL)s');"""
                  """       $('span[id=customer_increment_order_quantity_addon]').html('%(INCREMENT_ORDER_UNIT_PC_KG_ADDON)s');"""
                  """       $('span[id=stock_label]').html('%(STOCK_ORDER_UNIT_PC_KG_LABEL)s');"""
                  """       $('span[id=stock_addon]').html('%(STOCK_ORDER_UNIT_PC_KG_ADDON)s');"""
                  """       $('span[id=producer_unit_price_addon]').html('%(PRICE_ORDER_UNIT_PC_KG_ADDON)s');"""
                  """       $('div[id=div_id_order_average_weight]').show();"""
                  """       break;"""
                  """};"""
                  """function %(name)s_select(value, label, customer_increment_order_quantity_label, stock_label, increment_order_quantity_addon, stock_addon, price_addon) {"""
                  """       $('input[name=%(name)s]').val(value);"""
                  """       $('button[id=%(name)s_button_label]').html(label);"""
                  """       $('span[id=customer_increment_order_quantity_label]').html(customer_increment_order_quantity_label);"""
                  """       $('span[id=customer_increment_order_quantity_addon]').html(increment_order_quantity_addon);"""
                  """       $('span[id=stock_label]').html(stock_label);"""
                  """       $('span[id=stock_addon]').html(stock_addon);"""
                  """       $('span[id=producer_unit_price_addon]').html(price_addon);"""
                  """       switch(value) {"""
                  """           case '%(PRODUCT_ORDER_UNIT_PC_PRICE_PC)s':"""
                  """               $('div[id=div_id_order_average_weight]').hide();"""
                  """               break;"""
                  """           case '%(PRODUCT_ORDER_UNIT_PC_PRICE_KG)s':"""
                  """               $('div[id=div_id_order_average_weight]').hide();"""
                  """               break;"""
                  """           case '%(PRODUCT_ORDER_UNIT_PC_KG)s':"""
                  """               $('div[id=div_id_order_average_weight]').show();"""
                  """               break;"""
                  """       };"""
                  """}"""
                  """</script>"""
                  """</div>"""
                   % {'options': self.render_options2(choices, [value, ""], name),
                      'label': self.selected_choice,
                      'name': name,
                      'value': value,
                      'disabled': ' disabled' if self.disabled else '',
                      'PRODUCT_ORDER_UNIT_PC_PRICE_PC': PRODUCT_ORDER_UNIT_PC_PRICE_PC,
                      'INCREMENT_ORDER_UNIT_PC_PRICE_PC_LABEL': _('By multiple of'),
                      'INCREMENT_ORDER_UNIT_PC_PRICE_PC_ADDON': _('pc(s)'),
                      'STOCK_ORDER_UNIT_PC_PRICE_PC_LABEL': _('Stock'),
                      'STOCK_ORDER_UNIT_PC_PRICE_PC_ADDON': _('pc(s)'),
                      'PRICE_ORDER_UNIT_PC_PRICE_PC_ADDON': _('/pc'),
                      'PRODUCT_ORDER_UNIT_PC_PRICE_KG': PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                      'INCREMENT_ORDER_UNIT_PC_PRICE_KG_LABEL': _('By multiple of'),
                      'INCREMENT_ORDER_UNIT_PC_PRICE_KG_ADDON': _('kg(s)'),
                      'STOCK_ORDER_UNIT_PC_PRICE_KG_LABEL': _('Stock'),
                      'STOCK_ORDER_UNIT_PC_PRICE_KG_ADDON': _('kg(s)'),
                      'PRICE_ORDER_UNIT_PC_PRICE_KG_ADDON': _('/kg'),
                      'PRODUCT_ORDER_UNIT_PC_KG': PRODUCT_ORDER_UNIT_PC_KG,
                      'INCREMENT_ORDER_UNIT_PC_KG_LABEL': _('By multiple of'),
                      'INCREMENT_ORDER_UNIT_PC_KG_ADDON': _('pc(s)'),
                      'STOCK_ORDER_UNIT_PC_KG_LABEL': _('Stock'),
                      'STOCK_ORDER_UNIT_PC_KG_ADDON': _('pc(s)'),
                      'PRICE_ORDER_UNIT_PC_KG_ADDON': _('/kg'),
                      }]
        return mark_safe(u'\n'.join(output))

    def render_option2(self, selected_choices, option_value, option_label, name):
        option_value = force_unicode(option_value)
        if option_value in selected_choices:
            selected_html = ' selected="selected"'
            self.selected_choice = option_label
        else:
            selected_html = ''
        if option_value == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('pc(s)')
            stock_label = _('Stock')
            stock_addon = _('pc(s)')
            price_addon = _('/pc')
        elif option_value == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('kg(s)')
            stock_label = _('Stock')
            stock_addon = _('kg(s)')
            price_addon = _('/kg')
        elif option_value == PRODUCT_ORDER_UNIT_PC_KG:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('pc(s)')
            stock_label = _('Stock')
            stock_addon = _('pc(s)')
            price_addon = _('/kg')
        else:
            increment_order_quantity_label = _('?')
            increment_order_quantity_addon = _('?')
            stock_label = _('?')
            stock_addon = _('?')
            price_addon = _('?')
        return '<li><a href="javascript:%s_select(\'%s\', \'%s\', \'%s\', \'%s\', \'%s\', \'%s\', \'%s\')" data-value="%s"%s>%s</a></li>' % (
            name, option_value, option_label, increment_order_quantity_label, stock_label, increment_order_quantity_addon, stock_addon, price_addon,
            escape(option_value), selected_html,
            conditional_escape(force_unicode(option_label)))

    def render_options2(self, choices, selected_choices, name):
        # Normalize to strings.
        selected_choices = set([force_unicode(v) for v in selected_choices])
        output = []
        for option_value, option_label in chain(self.choices, choices):
            output.append(self.render_option2(selected_choices, option_value, option_label, name))
        return u'\n'.join(output)


class SelectAdminOrderUnitWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectAdminOrderUnitWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectAdminOrderUnitWidget, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        final_attrs = self.build_attrs(attrs, name=name)
        output = [format_html('<select{} onchange="%(name)s_select(this.value)">' % {'name': name, }, flatatt(final_attrs))]
        options = self.render_options(choices, [value])
        if options:
            output.append(options)
        output.append('</select>')
        output.append('<script type="text/javascript">')
        output.append('django.jQuery(document).ready(function() {%(name)s_select("%(value)s");});' % {'name': name, 'value': value})
        output.append('function %(name)s_select(value) {' % {'name': name, })
        output.append('(function($){')
        output.append('    switch (value) {')
        output.append('        case "100":')
        output.append('            $("div.field-box.field-unit_deposit").show();')
        output.append('            $("div.field-box.field-order_average_weight").hide();')
        output.append('            $("div.field-box.field-customer_minimum_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_increment_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_alert_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_unit_price").show();')
        output.append('            $("div.field-box.field-wrapped").show();')
        output.append('            break;')
        output.append('        case "105":')
        output.append('        case "110":')
        output.append('        case "115":')
        output.append('            $("div.field-box.field-unit_deposit").show();')
        output.append('            $("div.field-box.field-order_average_weight").show();')
        output.append('            $("div.field-box.field-order_average_weight").show();')
        output.append('            $("div.field-box.field-customer_minimum_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_alert_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_unit_price").show();')
        output.append('            $("div.field-box.field-wrapped").show();')
        output.append('            break;')
        output.append('        case "140":')
        output.append('            $("div.field-box.field-unit_deposit").hide();')
        output.append('            $("div.field-box.field-order_average_weight").show();')
        output.append('            $("div.field-box.field-customer_minimum_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_increment_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_alert_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_unit_price").show();')
        output.append('            $("div.field-box.field-wrapped").show();')
        output.append('            break;')
        output.append('        case "120":')
        output.append('        case "150":')
        output.append('            $("div.field-box.field-unit_deposit").hide();')
        output.append('            $("div.field-box.field-order_average_weight").hide();')
        output.append('            $("div.field-box.field-customer_minimum_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_increment_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_alert_order_quantity").show();')
        output.append('            $("div.field-box.field-customer_unit_price").show();')
        output.append('            $("div.field-box.field-wrapped").show();')
        output.append('            break;')
        output.append('        case "300":')
        output.append('        case "400":')
        output.append('        case "500":')
        output.append('            $("div.field-box.field-unit_deposit").hide();')
        output.append('            $("div.field-box.field-order_average_weight").hide();')
        output.append('            $("div.field-box.field-customer_minimum_order_quantity").hide();')
        output.append('            $("div.field-box.field-customer_increment_order_quantity").hide();')
        output.append('            $("div.field-box.field-customer_alert_order_quantity").hide();')
        output.append('            $("div.field-box.field-customer_unit_price").hide();')
        output.append('            $("div.field-box.field-wrapped").hide();')
        output.append('            break;')
        output.append('    }')
        output.append('    switch (value) {')
        output.append('        case "105":')
        output.append('            $("div.field-box.field-order_average_weight label").html("%s");'
                      % _("Piece weight in kg"))
        output.append('            break;')
        output.append('        case "110":')
        output.append('            $("div.field-box.field-order_average_weight label").html("%s");'
                      % _("Piece content in l"))
        output.append('            break;')
        output.append('        case "115":')
        output.append('            $("div.field-box.field-order_average_weight label").html("%s");'
                      % _("Number of pieces in a pack"))
        output.append('            break;')
        output.append('        case "140":')
        output.append('            $("div.field-box.field-order_average_weight label").html("%s");'
                      % _("Average weight in kg of a piece"))
        output.append('            break;')
        output.append('    }')
        output.append('    switch (value) {')
        output.append('        case "100":')
        output.append('        case "105":')
        output.append('        case "110":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one piece"))
        output.append('            $("div.field-box.field-customer_unit_price label").html("%s");'
                      % _("Customer price for one piece"))
        output.append('            break;')
        output.append('        case "115":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one pack"))
        output.append('            $("div.field-box.field-customer_unit_price label").html("%s");'
                      % _("Customer price for one pack"))
        output.append('            break;')
        output.append('        case "120":')
        output.append('        case "140":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one kg"))
        output.append('            $("div.field-box.field-customer_unit_price label").html("%s");'
                      % _("Customer price for one kg"))
        output.append('            break;')
        output.append('        case "150":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one l"))
        output.append('            $("div.field-box.field-customer_unit_price label").html("%s");'
                      % _("Customer price for one l"))
        output.append('            break;')
        output.append('        case "300":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one deposit"))
        output.append('            break;')
        output.append('        case "400":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one subscription"))
        output.append('            break;')
        output.append('        case "500":')
        output.append('            $("div.field-box.field-producer_unit_price label").html("%s");'
                      % _("Producer price for one transportation"))
        output.append('    }')
        output.append('}(django.jQuery))')
        output.append('}')
        output.append('</script>')
        return mark_safe('\n'.join(output))

# COLORPICKER_COLORS = [
#     'b4da35',
#     '37af68',
#     '64cf00',
#     'cfcc00',
#     'fdb735',
# ]

class PreviewProductOrderWidget(forms.Widget):
    template_name = 'repanier/widget/order_product_preview.html'

    class Media:
        css = {
            'all': (
                'bootstrap/css/bootstrap.css',
                'admin/css/base.css',
                'admin/css/forms.css',
                'djangocms_admin_style/css/djangocms-admin.css',
            )
        }

    def render(self, name, value, attrs=None):
        context = {
            'url': '/'
        }
        return mark_safe(render_to_string(self.template_name, context))