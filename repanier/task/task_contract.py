# -*- coding: utf-8 -*-
from django.contrib import messages
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.models.contract import ContractContent
from repanier.models.product import Product_Translation
from repanier.tools import cap


def admin_duplicate(queryset):
    user_message = _("The contract is duplicated.")
    user_message_level = messages.INFO
    contract_count = 0
    long_name_postfix = "{}".format(_(" (COPY)"))
    max_length = Product_Translation._meta.get_field('long_name').max_length - len(long_name_postfix)
    for contract in queryset:
        contract_count += 1
        new_long_name = "{}{}".format(cap(contract.long_name, max_length), _(" (COPY)"))
        old_product_production_mode = contract.production_mode.all()
        previous_contract_id = contract.id
        contract.id = None
        contract.reference = None
        contract.save()
        for production_mode in old_product_production_mode:
            contract.production_mode.add(production_mode.id)
        Product_Translation.objects.create(
            master_id=contract.id,
            long_name=new_long_name,
            offer_description=EMPTY_STRING,
            language_code=translation.get_language()
        )
        for contract_content in ContractContent.objects.filter(
            contract_id=previous_contract_id
        ):
            contract_content.id = None
            contract_content.contract_id=contract.id
            contract_content.save()
    if contract_count > 1:
        user_message = _("The contractes are duplicated.")
    return user_message, user_message_level
