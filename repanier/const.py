# -*- coding: utf-8 -*-
from decimal import *

from django.utils.translation import ugettext_lazy as _

READ_ONLY_GROUP = "read_only"
ORDER_GROUP = "order"
INVOICE_GROUP = "invoice"

DECIMAL_ZERO = Decimal('0')
DECIMAL_ONE = Decimal('1')
DECIMAL_1_02 = Decimal('1.02')
DECIMAL_1_06 = Decimal('1.06')
DECIMAL_0_06 = Decimal('0.06')
DECIMAL_0_12 = Decimal('0.12')
DECIMAL_0_21 = Decimal('0.21')
ZERO_DECIMAL = Decimal('0')
TWO_DECIMALS = Decimal('0.00')
THREE_DECIMALS = Decimal('0.000')
FOUR_DECIMALS = Decimal('0.0000')

PERMANENCE_DISABLED = '050'
PERMANENCE_PLANNED = '100'
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
    (PERMANENCE_PLANNED, unicode(_('planned'))),
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
PRODUCT_ORDER_UNIT_LOOSE_LT = '150'
PRODUCT_ORDER_UNIT_LOOSE_BT_LT = '160'
PRODUCT_ORDER_UNIT_NAMED_PC = '200'
PRODUCT_ORDER_UNIT_NAMED_KG = '220'
PRODUCT_ORDER_UNIT_NAMED_PC_KG = '240'
PRODUCT_ORDER_UNIT_DEPOSIT = '300'
PRODUCT_ORDER_UNIT_SUBSCRIPTION = '400'
PRODUCT_ORDER_UNIT_TRANSPORTATION = '500'

LUT_PRODUCT_ORDER_UNIT = (
    (PRODUCT_ORDER_UNIT_LOOSE_PC, unicode(_("/piece (loose)"))),
    (PRODUCT_ORDER_UNIT_NAMED_PC, unicode(_("/piece (named)"))),
    (PRODUCT_ORDER_UNIT_LOOSE_KG, unicode(_("/Kg (loose)"))),
    (PRODUCT_ORDER_UNIT_NAMED_KG, unicode(_("/Kg (named)"))),
    (PRODUCT_ORDER_UNIT_LOOSE_PC_KG, unicode(_("/piece -> Kg (loose)"))),
    (PRODUCT_ORDER_UNIT_NAMED_PC_KG, unicode(_("/piece -> Kg (named)"))),
    (PRODUCT_ORDER_UNIT_LOOSE_LT, unicode(_("/L (loose)"))),
    (PRODUCT_ORDER_UNIT_LOOSE_BT_LT, unicode(_("/piece -> L (loose)"))),
    (PRODUCT_ORDER_UNIT_DEPOSIT, unicode(
        _(
            'As a deposit, a bag : always add this product to preparation list when the customer has purchased something.'))),
    (PRODUCT_ORDER_UNIT_SUBSCRIPTION, unicode(_(
        'As a subscription, common expense : add the minimal order quantity of this product to each customer of the group'))),
    (PRODUCT_ORDER_UNIT_TRANSPORTATION, unicode(_(
        'As a transportation cost : add the minimal order quantity of this product to the basket representing the group.'))),
)

LUT_PRODUCT_ORDER_UNIT_REVERSE = (
    (unicode(_("/piece (loose)")), PRODUCT_ORDER_UNIT_LOOSE_PC),
    (unicode(_("/Kg (loose)")), PRODUCT_ORDER_UNIT_LOOSE_KG),
    (unicode(_("/piece -> Kg (loose)")), PRODUCT_ORDER_UNIT_LOOSE_PC_KG),
    (unicode(_("/piece -> L (loose)")), PRODUCT_ORDER_UNIT_LOOSE_BT_LT),
    (unicode(_("/piece (named)")), PRODUCT_ORDER_UNIT_NAMED_PC),
    (unicode(_("/Kg (named)")), PRODUCT_ORDER_UNIT_NAMED_KG),
    (unicode(_("/L (loose)")), PRODUCT_ORDER_UNIT_LOOSE_LT),
    (unicode(_("/piece -> Kg (named)")), PRODUCT_ORDER_UNIT_NAMED_PC_KG),
    (unicode(
        _(
            'As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')),
     PRODUCT_ORDER_UNIT_DEPOSIT),
    (unicode(_(
        'As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')),
     PRODUCT_ORDER_UNIT_SUBSCRIPTION),
    (unicode(_(
        'As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')),
     PRODUCT_ORDER_UNIT_TRANSPORTATION),
)

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
BANK_NEXT_LATEST_TOTAL = '300'
BANK_LATEST_TOTAL = '400'

LUT_BANK_TOTAL = (
    (BANK_NOT_LATEST_TOTAL, unicode(_('This is not the latest total'))),
    (BANK_NEXT_LATEST_TOTAL, unicode(_('This is the next latest bank total'))),
    (BANK_LATEST_TOTAL, unicode(_('This is the latest bank total'))),
)