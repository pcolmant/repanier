# -*- coding: utf-8 -*-
from decimal import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

DECIMAL_ZERO = Decimal('0')
DECIMAL_ONE = Decimal('1')
DECIMAL_0_01 = Decimal('.01')
DECIMAL_0_001 = Decimal('.001')
DECIMAL_0_0001 = Decimal('.0001')

PERMANENCE_DISABLED = '050'
PERMANENCE_PLANIFIED = '100' 
PERMANENCE_WAIT_FOR_OPEN = '200' 
PERMANENCE_OPENED = '300'
PERMANENCE_WAIT_FOR_SEND = '400'
PERMANENCE_SEND = '500'
PERMANENCE_WAIT_FOR_DONE = '600'
PERMANENCE_INVOICES_VALIDATION_FAILED = '700'
PERMANENCE_DONE = '800'
PERMANENCE_CANCELED = '900'

LUT_PERMANENCE_STATUS = (
	(PERMANENCE_DISABLED, unicode(_('disabled'))),
	(PERMANENCE_PLANIFIED, unicode(_('planified'))),
	(PERMANENCE_WAIT_FOR_OPEN, unicode(_('wait for open'))),
	(PERMANENCE_OPENED, unicode(_('orders opened'))),
	(PERMANENCE_WAIT_FOR_SEND, unicode(_('wait for send'))),
	(PERMANENCE_SEND, unicode(_('orders send to producers'))),
	(PERMANENCE_WAIT_FOR_DONE, unicode(_('wait for done'))),
	(PERMANENCE_INVOICES_VALIDATION_FAILED, unicode(_('invoices validation test failed'))),
	(PERMANENCE_DONE, unicode(_('done')))
)

PRODUCT_PLACEMENT_FREEZER = '100'
PRODUCT_PLACEMENT_FRIDGE = '200'
PRODUCT_PLACEMENT_OUT_OF_BASKET = '300'
PRODUCT_PLACEMENT_BASKET = '400'

LUT_PRODUCT_PLACEMENT = (
	(PRODUCT_PLACEMENT_FREEZER, unicode(_('freezer'))),
	(PRODUCT_PLACEMENT_FRIDGE, unicode(_('fridge'))),
	(PRODUCT_PLACEMENT_OUT_OF_BASKET, unicode(_('loose, out of the basket'))),
	(PRODUCT_PLACEMENT_BASKET, unicode(_('into the basket'))),
)

PRODUCT_ORDER_UNIT_LOOSE_PC = '100'
PRODUCT_ORDER_UNIT_LOOSE_KG = '120'
PRODUCT_ORDER_UNIT_LOOSE_PC_KG = '140'
PRODUCT_ORDER_UNIT_NAMED_PC = '200'
PRODUCT_ORDER_UNIT_NAMED_KG = '220'
PRODUCT_ORDER_UNIT_NAMED_PC_KG = '240'
PRODUCT_ORDER_UNIT_DEPOSIT = '300'
PRODUCT_ORDER_UNIT_SUBSCRIPTION = '400'
PRODUCT_ORDER_UNIT_TRANSPORTATION = '500'

LUT_PRODUCT_ORDER_UNIT = (
	(PRODUCT_ORDER_UNIT_LOOSE_PC, unicode(_("/piece (loose)"))),
	(PRODUCT_ORDER_UNIT_LOOSE_KG, unicode(_("/Kg (loose)"))),
	(PRODUCT_ORDER_UNIT_LOOSE_PC_KG, unicode(_("/piece -> Kg (loose)"))),
	(PRODUCT_ORDER_UNIT_NAMED_PC, unicode(_("/piece (named)"))),
	(PRODUCT_ORDER_UNIT_NAMED_KG, unicode(_("/Kg (named)"))),
	(PRODUCT_ORDER_UNIT_NAMED_PC_KG, unicode(_("/piece -> Kg (named)"))),
	(PRODUCT_ORDER_UNIT_DEPOSIT, unicode(_('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.'))),
	(PRODUCT_ORDER_UNIT_SUBSCRIPTION, unicode(_('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group'))),
	(PRODUCT_ORDER_UNIT_TRANSPORTATION, unicode(_('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.'))),
)

LUT_PRODUCT_ORDER_UNIT_REVERSE = (
	(unicode(_("/piece (loose)")), PRODUCT_ORDER_UNIT_LOOSE_PC),
	(unicode(_("/Kg (loose)")), PRODUCT_ORDER_UNIT_LOOSE_KG),
	(unicode(_("/piece -> Kg (loose)")), PRODUCT_ORDER_UNIT_LOOSE_PC_KG),
	(unicode(_("/piece (named)")), PRODUCT_ORDER_UNIT_NAMED_PC),
	(unicode(_("/Kg (named)")), PRODUCT_ORDER_UNIT_NAMED_KG),
	(unicode(_("/piece -> Kg (named)")), PRODUCT_ORDER_UNIT_NAMED_PC_KG),
	(unicode(_('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')), PRODUCT_ORDER_UNIT_DEPOSIT),
	(unicode(_('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')), PRODUCT_ORDER_UNIT_SUBSCRIPTION),
	(unicode(_('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')), PRODUCT_ORDER_UNIT_TRANSPORTATION),
)

# zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
ADD_PRODUCT_MANUALY = '100'
ADD_PRODUCT_TO_CUSTOMER_BASKET_0 = '200'
ADD_PRODUCT_TO_CUSTOMER_BASKET = '300'
ADD_PRODUCT_TO_GROUP_BASKET = '400'

LUT_ADD_PRODUCT = (
	(ADD_PRODUCT_MANUALY, _("As usual, let customers freely order it.")),
	(ADD_PRODUCT_TO_CUSTOMER_BASKET_0, _('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')),
	(ADD_PRODUCT_TO_CUSTOMER_BASKET, _('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')),
	(ADD_PRODUCT_TO_GROUP_BASKET, _('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')),
)
# zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz

VAT_100 = '100'
VAT_200 = '200' 
VAT_300 = '300'
VAT_400 = '400'
VAT_500 = '500'
VAT_600 = '600'

LUT_VAT = (
	(VAT_100, unicode(_('none'))),
	(VAT_200, unicode(_('compensation 2%'))),
	(VAT_300, unicode(_('compensation 6%'))),
	(VAT_400, unicode(_('vat 6%'))),
	(VAT_500, unicode(_('vat 12%'))),
	(VAT_600, unicode(_('vat 21%'))),
)

LUT_VAT_REVERSE = (
	( unicode(_('none')), VAT_100),
	( unicode(_('compensation 2%')), VAT_200),
	( unicode(_('compensation 6%')), VAT_300),
	( unicode(_('vat 6%')), VAT_400),
	( unicode(_('vat 12%')), VAT_500),
	( unicode(_('vat 21%')), VAT_600),
)

BANK_NOT_LATEST_TOTAL = '100'
# BANK_CALCULTAING_LATEST_TOTAL = '200'
BANK_NEXT_LATEST_TOTAL = '300'
BANK_LATEST_TOTAL = '400'

# update repanier_bankaccount set operation_status = '200' where operation_status = '400';

LUT_BANK_TOTAL = (
	(BANK_NOT_LATEST_TOTAL, unicode(_('This is not the latest total'))),
	# (BANK_CALCULTAING_LATEST_TOTAL, unicode(_('This is the previous latest total. The system is calculating the new one.'))),
	(BANK_NEXT_LATEST_TOTAL, unicode(_('This is the next lastest bank total'))),
	(BANK_LATEST_TOTAL, unicode(_('This is the lastest bank total'))),
)