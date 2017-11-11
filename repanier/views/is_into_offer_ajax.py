# -*- coding: utf-8

import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, EMPTY_STRING
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
                        if contract_content is None:
                            contract_content = ContractContent.objects.create(
                                contract_id=contract_id,
                                product_id=product_id,
                                permanences_dates=contract.permanences_dates
                            )
                        else:
                            if contract_content.permanences_dates is not None:
                                contract_content.permanences_dates = None
                                contract_content.not_permanences_dates = contract.permanences_dates
                            else:
                                contract_content.permanences_dates = contract.permanences_dates
                                contract_content.not_permanences_dates = None
                            contract_content.save(update_fields=['permanences_dates', 'not_permanences_dates'])
                else:
                    product.is_into_offer = not product.is_into_offer
                    product.save(update_fields=['is_into_offer'])
                return HttpResponse(
                    product.get_is_into_offer_html(contract=contract, contract_content=contract_content))
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
                contract = Contract.objects.filter(id=contract_id).order_by('?').first()
                if contract is not None:
                    contract_content = ContractContent.objects.filter(
                        product_id=product_id,
                        contract_id=contract_id
                    ).order_by('?').first()
                    if contract_content is None or contract_content.permanences_dates is None:
                        all_not_dates_str = contract.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)
                        all_not_dates_str.remove(one_date_str)
                        if len(all_not_dates_str) > 0:
                            not_permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(all_not_dates_str)
                        else:
                            not_permanences_dates = None
                        if contract_content is None:
                            contract_content = ContractContent.objects.create(
                                contract_id=contract_id,
                                product_id=product_id,
                                permanences_dates=one_date_str,
                                not_permanences_dates=not_permanences_dates
                            )
                        else:
                            contract_content.permanences_dates = one_date_str
                            contract_content.not_permanences_dates = not_permanences_dates
                            contract_content.save(update_fields=['permanences_dates', 'not_permanences_dates'])
                    else:
                        all_dates_str = list(filter(None, contract_content.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)))
                        if contract_content.not_permanences_dates is not None:
                            all_not_dates_str = list(filter(None, contract_content.not_permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)))
                        else:
                            all_not_dates_str = []
                        if one_date_str in all_dates_str:
                            all_dates_str.remove(one_date_str)
                            all_not_dates_str.append(one_date_str)
                        else:
                            all_dates_str.append(one_date_str)
                            all_not_dates_str.remove(one_date_str)
                        if len(all_dates_str) > 0:
                            permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(all_dates_str)
                        else:
                            permanences_dates = None
                        if len(all_not_dates_str) > 0:
                            not_permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(all_not_dates_str)
                        else:
                            not_permanences_dates = None
                        contract_content.permanences_dates = permanences_dates
                        contract_content.not_permanences_dates = not_permanences_dates
                        contract_content.save(update_fields=['permanences_dates', 'not_permanences_dates'])

                    return HttpResponse(product.get_is_into_offer_html(contract=contract,
                                                                   contract_content=contract_content))
    raise Http404
