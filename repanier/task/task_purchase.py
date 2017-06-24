# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice, ProducerInvoice, CustomerProducerInvoice
from repanier.models.offeritem import OfferItem
from repanier.models.purchase import Purchase


def admin_delete(permanence_id):
    Purchase.objects.filter(permanence_id=permanence_id).delete()
    OfferItem.objects.filter(permanence_id=permanence_id).delete()
    CustomerInvoice.objects.filter(permanence_id=permanence_id).delete()
    ProducerInvoice.objects.filter(permanence_id=permanence_id).delete()
    CustomerProducerInvoice.objects.filter(permanence_id=permanence_id).delete()
    BankAccount.objects.filter(permanence_id=permanence_id).delete()
    user_message = _(
        "The purchases of this permanence have been deleted. There is no way to restore them automaticaly.")
    user_message_level = messages.INFO
    return user_message, user_message_level
