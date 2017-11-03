# -*- coding: utf-8

from django import forms

from repanier.const import PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND, PERMANENCE_PLANNED
from repanier.models.permanence import Permanence


class SelectAdminPermanenceWidget(forms.Select):
    template_name = 'repanier/widgets/select_admin_permanence.html'

    def get_context(self, name, value, attrs):
        context = super(SelectAdminPermanenceWidget, self).get_context(name, value, attrs)
        case_show_hide = 'case "0": '
        case_hide_show = 'case "0": '
        case_hide_hide = 'case "0": '
        for option_value, option_label in self.choices:
            permanence = Permanence.objects.filter(id=option_value).order_by('?').only('status').first()
            if permanence is not None:
                status = permanence.status
                if status in [PERMANENCE_PLANNED, PERMANENCE_OPENED, PERMANENCE_CLOSED]:
                    case_show_hide += "case \"{}\": ".format(option_value)
                elif status == PERMANENCE_SEND:
                    case_hide_show += "case \"{}\": ".format(option_value)
                else:
                    case_hide_hide += "case \"{}\": ".format(option_value)
        context['case_show_hide'] = case_show_hide
        context['case_hide_show'] = case_hide_show
        context['case_hide_hide'] = case_hide_hide
        return context
