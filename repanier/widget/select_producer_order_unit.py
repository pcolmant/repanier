# -*- coding: utf-8
from __future__ import unicode_literals

from itertools import chain

from django import forms
from django.utils.encoding import force_text
from django.utils.html import escape, conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import *


class SelectProducerOrderUnitWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectProducerOrderUnitWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectProducerOrderUnitWidget, self).__setattr__(k, value)

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
    switch($('input[name={name}]').val()) {{
     case '{PRODUCT_ORDER_UNIT_PC_PRICE_PC}':
         $('span[id=customer_increment_order_quantity_label]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_PC_LABEL}');
         $('span[id=customer_increment_order_quantity_addon]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_PC_ADDON}');
         $('span[id=stock_label]').html('{STOCK_ORDER_UNIT_PC_PRICE_PC_LABEL}');
         $('span[id=stock_addon]').html('{STOCK_ORDER_UNIT_PC_PRICE_PC_ADDON}');
         $('span[id=producer_unit_price_addon]').html('{PRICE_ORDER_UNIT_PC_PRICE_PC_ADDON}');
         $('div[id=div_id_order_average_weight]').hide();
         break;
     case '{PRODUCT_ORDER_UNIT_PC_PRICE_KG}':
         $('span[id=customer_increment_order_quantity_label]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_KG_LABEL}');
         $('span[id=customer_increment_order_quantity_addon]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_KG_ADDON}');
         $('span[id=stock_label]').html('{STOCK_ORDER_UNIT_PC_PRICE_KG_LABEL}');
         $('span[id=stock_addon]').html('{STOCK_ORDER_UNIT_PC_PRICE_KG_ADDON}');
         $('span[id=producer_unit_price_addon]').html('{PRICE_ORDER_UNIT_PC_PRICE_KG_ADDON}');
         $('div[id=div_id_order_average_weight]').hide();
         break;
     case '{PRODUCT_ORDER_UNIT_PC_PRICE_LT}':
         $('span[id=customer_increment_order_quantity_label]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_LT_LABEL}');
         $('span[id=customer_increment_order_quantity_addon]').html('{INCREMENT_ORDER_UNIT_PC_PRICE_LT_ADDON}');
         $('span[id=stock_label]').html('{STOCK_ORDER_UNIT_PC_PRICE_LT_LABEL}');
         $('span[id=stock_addon]').html('{STOCK_ORDER_UNIT_PC_PRICE_LT_ADDON}');
         $('span[id=producer_unit_price_addon]').html('{PRICE_ORDER_UNIT_PC_PRICE_LT_ADDON}');
         $('div[id=div_id_order_average_weight]').hide();
         break;
     case '{PRODUCT_ORDER_UNIT_PC_KG}':
         $('span[id=customer_increment_order_quantity_label]').html('{INCREMENT_ORDER_UNIT_PC_KG_LABEL}');
         $('span[id=customer_increment_order_quantity_addon]').html('{INCREMENT_ORDER_UNIT_PC_KG_ADDON}');
         $('span[id=stock_label]').html('{STOCK_ORDER_UNIT_PC_KG_LABEL}');
         $('span[id=stock_addon]').html('{STOCK_ORDER_UNIT_PC_KG_ADDON}');
         $('span[id=producer_unit_price_addon]').html('{PRICE_ORDER_UNIT_PC_KG_ADDON}');
         $('div[id=div_id_order_average_weight]').show();
         break;
    }};
    function {name}_select(value, label, customer_increment_order_quantity_label, stock_label,
    increment_order_quantity_addon, stock_addon, price_addon) {{
         $('input[name={name}]').val(value);
         $('button[id={name}_button_label]').html(label);
         $('span[id=customer_increment_order_quantity_label]').html(customer_increment_order_quantity_label);
         $('span[id=customer_increment_order_quantity_addon]').html(increment_order_quantity_addon);
         $('span[id=stock_label]').html(stock_label);
         $('span[id=stock_addon]').html(stock_addon);
         $('span[id=producer_unit_price_addon]').html(price_addon);
         switch(value) {{
             case '{PRODUCT_ORDER_UNIT_PC_PRICE_PC}':
                 $('div[id=div_id_order_average_weight]').hide();
                 break;
             case '{PRODUCT_ORDER_UNIT_PC_PRICE_KG}':
                 $('div[id=div_id_order_average_weight]').hide();
                 break;
             case '{PRODUCT_ORDER_UNIT_PC_PRICE_LT}':
                 $('div[id=div_id_order_average_weight]').hide();
                 break;
             case '{PRODUCT_ORDER_UNIT_PC_KG}':
                 $('div[id=div_id_order_average_weight]').show();
                 break;
         }};
    }}
    </script>
</div>
        """.format(
            options=self.render_options2(choices, [value, EMPTY_STRING], name),
            label=self.selected_choice,
            name=name,
            value=value,
            disabled=' disabled' if self.disabled else EMPTY_STRING,
            PRODUCT_ORDER_UNIT_PC_PRICE_PC=PRODUCT_ORDER_UNIT_PC_PRICE_PC,
            INCREMENT_ORDER_UNIT_PC_PRICE_PC_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_PC_ADDON=_('pc(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_PC_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_PC_ADDON=_('pc(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_PC_ADDON=_('/ pc'),
            PRODUCT_ORDER_UNIT_PC_PRICE_KG=PRODUCT_ORDER_UNIT_PC_PRICE_KG,
            INCREMENT_ORDER_UNIT_PC_PRICE_KG_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_KG_ADDON=_('kg(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_KG_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_KG_ADDON=_('kg(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_KG_ADDON=_('/ kg'),
            PRODUCT_ORDER_UNIT_PC_PRICE_LT=PRODUCT_ORDER_UNIT_PC_PRICE_KG,
            INCREMENT_ORDER_UNIT_PC_PRICE_LT_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_LT_ADDON=_('l(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_LT_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_LT_ADDON=_('l(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_LT_ADDON=_('/ l'),
            PRODUCT_ORDER_UNIT_PC_KG=PRODUCT_ORDER_UNIT_PC_KG,
            INCREMENT_ORDER_UNIT_PC_KG_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_KG_ADDON=_('pc(s)'),
            STOCK_ORDER_UNIT_PC_KG_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_KG_ADDON=_('pc(s)'),
            PRICE_ORDER_UNIT_PC_KG_ADDON=_('/ kg'),
        )
        return mark_safe(output)

    def render_option2(self, selected_choices, option_value, option_label, name):
        option_value = force_text(option_value)
        if option_value in selected_choices:
            selected_html = ' selected="selected"'
            self.selected_choice = option_label
        else:
            selected_html = EMPTY_STRING
        if option_value == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('pc(s)')
            stock_label = _('Stock')
            stock_addon = _('pc(s)')
            price_addon = _('/ pc')
        elif option_value == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('kg(s)')
            stock_label = _('Stock')
            stock_addon = _('kg(s)')
            price_addon = _('/ kg')
        elif option_value == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('l(s)')
            stock_label = _('Stock')
            stock_addon = _('l(s)')
            price_addon = _('/ l')
        elif option_value == PRODUCT_ORDER_UNIT_PC_KG:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('pc(s)')
            stock_label = _('Stock')
            stock_addon = _('pc(s)')
            price_addon = _('/ kg')
        else:
            increment_order_quantity_label = _('?')
            increment_order_quantity_addon = _('?')
            stock_label = _('?')
            stock_addon = _('?')
            price_addon = _('?')
        return "<li><a href=\"javascript:{}_select('{}', '{}', '{}', '{}'," \
               " '{}', '{}', '{}')\" data-value=\"{}\"{}>{}</a></li>".format(
                   name, option_value, option_label, increment_order_quantity_label,
                   stock_label, increment_order_quantity_addon, stock_addon, price_addon,
                   escape(option_value), selected_html,
                   conditional_escape(force_text(option_label)))

    def render_options2(self, choices, selected_choices, name):
        # Normalize to strings.
        selected_choices = set([force_text(v) for v in selected_choices])
        output = []
        for option_value, option_label in chain(self.choices, choices):
            output.append(self.render_option2(selected_choices, option_value, option_label, name))
        return "\n".join(output)
