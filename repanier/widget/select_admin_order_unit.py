# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.forms.utils import flatatt
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import EMPTY_STRING


class SelectAdminOrderUnitWidget(forms.Select):
    selected_choice = None

    def __init__(self, attrs=None, choices=(), disabled=False):
        self.disabled = disabled
        super(SelectAdminOrderUnitWidget, self).__init__(attrs, choices)

    def __setattr__(self, k, value):
        super(SelectAdminOrderUnitWidget, self).__setattr__(k, value)

    def render(self, name, value, attrs=None, choices=()):
        if value is None:
            value = EMPTY_STRING
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
                    $("div.field-box.field-producer_unit_price label").html("{PRODUCER_PRICE_ONE_TRANSPORTATION}");
            }}
        }}(django.jQuery))
    }}
</script>
        """.format(
            final_attrs=flatatt(final_attrs),
            name=name,
            options=self.render_options([value]),
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
            PRODUCER_PRICE_ONE_TRANSPORTATION=_("Producer price for one transportation"),
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
