# -*- coding: utf-8

from django import forms


class SelectAdminOrderUnitWidget(forms.Select):
    template_name = 'repanier/widgets/select_admin_order_unit.html'

# COLORPICKER_COLORS = [
#     'b4da35',
#     '37af68',
#     '64cf00',
#     'cfcc00',
#     'fdb735',
# ]
