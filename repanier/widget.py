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
        if value is None:
            value = ''
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
            options=self.render_options2(choices, [value, ""], name),
            label=self.selected_choice,
            name=name,
            value=value,
            disabled=' disabled' if self.disabled else ''
        )
        return mark_safe(output)

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
        if value is None:
            value = ''
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
            options=self.render_options2(choices, [value, ""], name),
            label=self.selected_choice,
            name=name,
            value=value,
            disabled=' disabled' if self.disabled else '',
            PRODUCT_ORDER_UNIT_PC_PRICE_PC=PRODUCT_ORDER_UNIT_PC_PRICE_PC,
            INCREMENT_ORDER_UNIT_PC_PRICE_PC_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_PC_ADDON=_('pc(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_PC_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_PC_ADDON=_('pc(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_PC_ADDON=_('/pc'),
            PRODUCT_ORDER_UNIT_PC_PRICE_KG=PRODUCT_ORDER_UNIT_PC_PRICE_KG,
            INCREMENT_ORDER_UNIT_PC_PRICE_KG_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_KG_ADDON=_('kg(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_KG_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_KG_ADDON=_('kg(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_KG_ADDON=_('/kg'),
            PRODUCT_ORDER_UNIT_PC_PRICE_LT=PRODUCT_ORDER_UNIT_PC_PRICE_KG,
            INCREMENT_ORDER_UNIT_PC_PRICE_LT_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_PRICE_LT_ADDON=_('l(s)'),
            STOCK_ORDER_UNIT_PC_PRICE_LT_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_PRICE_LT_ADDON=_('l(s)'),
            PRICE_ORDER_UNIT_PC_PRICE_LT_ADDON=_('/l'),
            PRODUCT_ORDER_UNIT_PC_KG=PRODUCT_ORDER_UNIT_PC_KG,
            INCREMENT_ORDER_UNIT_PC_KG_LABEL=_('By multiple of'),
            INCREMENT_ORDER_UNIT_PC_KG_ADDON=_('pc(s)'),
            STOCK_ORDER_UNIT_PC_KG_LABEL=_('Stock'),
            STOCK_ORDER_UNIT_PC_KG_ADDON=_('pc(s)'),
            PRICE_ORDER_UNIT_PC_KG_ADDON=_('/kg'),
        )
        return mark_safe(output)

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
        elif option_value == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
            increment_order_quantity_label = _('By multiple of')
            increment_order_quantity_addon = _('l(s)')
            stock_label = _('Stock')
            stock_addon = _('l(s)')
            price_addon = _('/l')
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
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        output = """
            <select{final_attrs} onchange="{name}_select(this.value)">
                {options}
            </select>
            <script type="text/javascript">
                django.jQuery(document).ready(function() {{ {name}_select("{value}");}});
                function {name}_select(value) {{
                    (function($){{
                        switch (value) {{
                            case "100":
                                $("div.field-box.field-unit_deposit").show();
                                $("div.field-box.field-order_average_weight").hide();
                                $("div.field-box.field-customer_minimum_order_quantity").show();
                                $("div.field-box.field-customer_increment_order_quantity").show();
                                $("div.field-box.field-customer_alert_order_quantity").show();
                                $("div.field-box.field-customer_unit_price").show();
                                $("div.field-box.field-wrapped").show();
                                break;
                            case "105":
                            case "110":
                            case "115":
                                $("div.field-box.field-unit_deposit").show();
                                $("div.field-box.field-order_average_weight").show();
                                $("div.field-box.field-order_average_weight").show();
                                $("div.field-box.field-customer_minimum_order_quantity").show();
                                $("div.field-box.field-customer_alert_order_quantity").show();
                                $("div.field-box.field-customer_unit_price").show();
                                $("div.field-box.field-wrapped").show();
                                break;
                            case "140":
                                $("div.field-box.field-unit_deposit").hide();
                                $("div.field-box.field-order_average_weight").show();
                                $("div.field-box.field-customer_minimum_order_quantity").show();
                                $("div.field-box.field-customer_increment_order_quantity").show();
                                $("div.field-box.field-customer_alert_order_quantity").show();
                                $("div.field-box.field-customer_unit_price").show();
                                $("div.field-box.field-wrapped").show();
                                break;
                            case "120":
                            case "150":
                                $("div.field-box.field-unit_deposit").hide();
                                $("div.field-box.field-order_average_weight").hide();
                                $("div.field-box.field-customer_minimum_order_quantity").show();
                                $("div.field-box.field-customer_increment_order_quantity").show();
                                $("div.field-box.field-customer_alert_order_quantity").show();
                                $("div.field-box.field-customer_unit_price").show();
                                $("div.field-box.field-wrapped").show();
                                break;
                            case "300":
                            case "400":
                            case "500":
                                $("div.field-box.field-unit_deposit").hide();
                                $("div.field-box.field-order_average_weight").hide();
                                $("div.field-box.field-customer_minimum_order_quantity").hide();
                                $("div.field-box.field-customer_increment_order_quantity").hide();
                                $("div.field-box.field-customer_alert_order_quantity").hide();
                                $("div.field-box.field-customer_unit_price").hide();
                                $("div.field-box.field-wrapped").hide();
                                break;
                        }}
                    switch (value) {{
                        case "105":
                            $("div.field-box.field-order_average_weight label").html("{PIECE_WEIGHT_IN_KG}");
                            break;
                        case "110":
                            $("div.field-box.field-order_average_weight label").html("{PIECE_CONTENT_IN_L}");
                            break;
                        case "115":
                            $("div.field-box.field-order_average_weight label").html("{PIECES_IN_A_PACK}");
                            break;
                        case "140":
                            $("div.field-box.field-order_average_weight label").html("{AVERAGE_WEIGHT_IN_KG}");
                            break;
                    }}
                    switch (value) {{
                        case "100":
                        case "105":
                        case "110":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_PIECE}");
                            $("div.field-box.field-customer_unit_price label").html("{CUSTOMER_PRICE_ONE_PIECE}");
                            break;
                        case "115":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_PACK}");
                            $("div.field-box.field-customer_unit_price label").html("{CUSTOMER_PRICE_ONE_PACK}");
                            break;
                        case "120":
                        case "140":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_KG}");
                            $("div.field-box.field-customer_unit_price label").html("{CUSTOMER_PRICE_ONE_KG}");
                            break;
                        case "150":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_L}");
                            $("div.field-box.field-customer_unit_price label").html("{CUSTOMER_PRICE_ONE_L}");
                            break;
                        case "300":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_DEPOSIT}");
                            break;
                        case "400":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_SUBSCRIPTION}");
                            break;
                        case "500":
                            $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_TRASPORTATION}");
                    }}
                }}(django.jQuery))
                }}
            </script>

        """.format(
            final_attrs=flatatt(final_attrs),
            name=name,
            options=self.render_options(choices, [value]),
            value=value,
            PIECE_WEIGHT_IN_KG=_("Piece weight in kg"),
            PIECE_CONTENT_IN_L=_("Piece content in l"),
            PIECES_IN_A_PACK=_("Number of pieces in a pack"),
            AVERAGE_WEIGHT_IN_KG=_("Average weight in kg of a piece"),
            PRODUCER_PRICE_ONE_PIECE=_("Producer price for one piece"),
            PRODUCER_PRICE_ONE_PACK=_("Producer price for one pack"),
            PRODUCER_PRICE_ONE_KG=_("Producer price for one kg"),
            PRODUCER_PRICE_ONE_L=_("Producer price for one l"),
            PRODUCER_PRICE_ONE_DEPOSIT=_("Producer price for one deposit"),
            PRODUCER_PRICE_ONE_SUBSCRIPTION=_("Producer price for one subscription"),
            PRODUCER_PRICE_ONE_TRASPORTATION=_("Producer price for one transportation"),
            CUSTOMER_PRICE_ONE_PIECE=_("Customer price for one piece"),
            CUSTOMER_PRICE_ONE_PACK=_("Customer price for one pack"),
            CUSTOMER_PRICE_ONE_KG=_("Customer price for one kg"),
            CUSTOMER_PRICE_ONE_L=_("Customer price for one l")
        )
        return mark_safe(output)

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

