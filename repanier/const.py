# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _

PERMANENCE_DISABLED = '005'
PERMANENCE_PLANIFIED = '010' 
PERMANENCE_OPEN = '030'
PERMANENCE_CLOSED = '040'
PERMANENCE_SEND = '050'
PERMANENCE_PREPARED = '060'
PERMANENCE_DONE = '090'

LUT_PERMANENCE_STATUS = (
	(PERMANENCE_DISABLED, _('disabled')),
	(PERMANENCE_PLANIFIED, _('planified')),
	(PERMANENCE_OPEN, _('orders opened')),
	(PERMANENCE_CLOSED, _('orders closed')),
	(PERMANENCE_SEND, _('orders send to producers')),
	(PERMANENCE_PREPARED, _('orders prepared')),
	(PERMANENCE_DONE, _('done')),
)

SITE_ID_REPANIER = 1
SITE_ID_PRODUCER = 2
