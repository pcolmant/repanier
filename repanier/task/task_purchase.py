# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from repanier.const import *
from repanier.models import CustomerInvoice, ProducerInvoice, CustomerProducerInvoice
from repanier.models import OfferItem
from repanier.models import Purchase


def admin_delete(request, queryset):
    user_message = _("The status of this permanence prohibit you to delete the purchases.")
    user_message_level = messages.ERROR
    for permanence in queryset.filter(status=PERMANENCE_SEND)[:1]:
        Purchase.objects.filter(permanence_id=permanence.id).delete()
        OfferItem.objects.filter(permanence_id=permanence.id).delete()
        CustomerInvoice.objects.filter(permanence_id=permanence.id).delete()
        ProducerInvoice.objects.filter(permanence_id=permanence.id).delete()
        CustomerProducerInvoice.objects.filter(permanence_id=permanence.id).delete()
        user_message = _(
            "The purchases of this permanence have been deleted. There is no way to restore them automaticaly.")
        user_message_level = messages.INFO
    return user_message, user_message_level
