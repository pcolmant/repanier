# -*- coding: utf-8

from repanier.tools import get_repanier_template_name
from repanier.widget.select_bootstrap import SelectBootstrapWidget


class SelectProducerOrderUnitWidget(SelectBootstrapWidget):
    template_name = get_repanier_template_name("widgets/select_producer_order_unit.html")
