# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO
from repanier.models import Contract, ContractContent
from repanier.models.product import Product
from repanier.tools import sint


@never_cache
@require_GET
@transaction.atomic
@login_required
def is_into_offer(request, product_id, contract_id):
    if request.is_ajax():
        user = request.user
        if user.is_staff or user.is_superuser:
            product_id = sint(product_id)
            product = Product.objects.filter(id=product_id).order_by('?').first()
            if product is not None:
                contract_id = sint(contract_id)
                contract = None
                contract_content = None
                if contract_id > 0:
                    contract = Contract.objects.filter(id=contract_id).order_by('?').first()
                    if contract is not None:
                        contract_content = ContractContent.objects.filter(
                            product_id=product_id,
                            contract_id=contract_id
                        ).order_by('?').first()
                        if contract_content is not None:
                            if len(contract_content.all_dates) == 0:
                                contract_content.all_dates = contract.all_dates
                            else:
                                contract_content.all_dates = []
                            contract_content.save()
                        else:
                            contract_content = ContractContent.objects.create(
                                contract_id=contract_id,
                                product_id=product_id,
                            )
                            contract_content.all_dates = contract.all_dates
                            contract_content.save()
                else:
                    new_is_into_offer = not product.is_into_offer
                    if product.limit_order_quantity_to_stock:
                        if new_is_into_offer and product.stock <= DECIMAL_ZERO:
                            new_is_into_offer = False
                    Product.objects.filter(id=product_id).update(is_into_offer=new_is_into_offer)
                    product.is_into_offer = new_is_into_offer
                return HttpResponse(product.get_is_into_offer_html(contract=contract, contract_content=contract_content))
    raise Http404


@never_cache
@require_GET
@transaction.atomic
@login_required
def is_into_offer_content(request, product_id, contract_id, one_date_str):
    if request.is_ajax():
        user = request.user
        if user.is_staff or user.is_superuser:
            product_id = sint(product_id)
            product = Product.objects.filter(id=product_id).order_by('?').only(
                'is_into_offer').first()
            if product is not None:
                contract_id = sint(contract_id)
                contract_content = ContractContent.objects.filter(
                    product_id=product_id,
                    contract_id=contract_id
                ).order_by('?').first()
                if contract_content is None:
                    contract_content = ContractContent.objects.create(
                        contract_id=contract_id,
                        product_id=product_id,
                    )
                one_date = parse_date(one_date_str)
                try:
                    contract_content.all_dates.remove(one_date)
                except ValueError:
                    contract_content.all_dates.append(one_date)
                contract_content.save()
                return HttpResponse(product.get_is_into_offer_html(contract=contract_content.contract, contract_content=contract_content))
    raise Http404