# -*- coding: utf-8
from __future__ import unicode_literals
from decimal import *
from django.utils.translation import ugettext_lazy as _

ORDER_GROUP = "order"
INVOICE_GROUP = "invoice"
COORDINATION_GROUP = "coordination"
WEBMASTER_GROUP = "webmaster"

EMPTY_STRING = ''

DECIMAL_ZERO = Decimal('0')
DECIMAL_ONE = Decimal('1')
DECIMAL_TWO = Decimal('2')
DECIMAL_THREE = Decimal('3')
DECIMAL_1_02 = Decimal('1.02')
DECIMAL_1_06 = Decimal('1.06')
DECIMAL_1_12 = Decimal('1.12')
DECIMAL_1_21 = Decimal('1.21')
DECIMAL_0_02 = Decimal('0.02')
DECIMAL_0_06 = Decimal('0.06')
DECIMAL_0_12 = Decimal('0.12')
DECIMAL_0_21 = Decimal('0.21')
ZERO_DECIMAL = Decimal('0')
ONE_DECIMAL = Decimal('0.1')
TWO_DECIMALS = Decimal('0.01')
THREE_DECIMALS = Decimal('0.001')
FOUR_DECIMALS = Decimal('0.0001')

PERMANENCE_DISABLED = '050'
PERMANENCE_PLANNED = '100'
PERMANENCE_WAIT_FOR_PRE_OPEN = '110'
PERMANENCE_PRE_OPEN = '120'
PERMANENCE_WAIT_FOR_OPEN = '200'
PERMANENCE_OPENED = '300'
PERMANENCE_WAIT_FOR_CLOSED = '350'
PERMANENCE_CLOSED = '370'
PERMANENCE_WAIT_FOR_SEND = '400'
PERMANENCE_SEND = '500'
PERMANENCE_WAIT_FOR_DONE = '600'
PERMANENCE_INVOICES_VALIDATION_FAILED = '700'
PERMANENCE_DONE = '800'
PERMANENCE_ARCHIVED = '900'

LUT_PERMANENCE_STATUS = (
    (PERMANENCE_DISABLED, _('disabled')),
    (PERMANENCE_PLANNED, _('planned')),
    (PERMANENCE_WAIT_FOR_PRE_OPEN, _('wait for pre-open')),
    (PERMANENCE_PRE_OPEN, _('orders pre-opened')),
    (PERMANENCE_WAIT_FOR_OPEN, _('wait for open')),
    (PERMANENCE_OPENED, _('orders opened')),
    (PERMANENCE_WAIT_FOR_CLOSED, _('wait for close')),
    (PERMANENCE_CLOSED, _('orders closed')),
    (PERMANENCE_WAIT_FOR_SEND, _('wait for send')),
    (PERMANENCE_SEND, _('orders send to producers')),
    (PERMANENCE_WAIT_FOR_DONE, _('wait for done')),
    (PERMANENCE_INVOICES_VALIDATION_FAILED, _('invoices validation test failed')),
    (PERMANENCE_DONE, _('done')),
    (PERMANENCE_ARCHIVED, _('archived'))
)

PRODUCT_PLACEMENT_FREEZER = '100'
PRODUCT_PLACEMENT_FRIDGE = '200'
PRODUCT_PLACEMENT_OUT_OF_BASKET = '300'
PRODUCT_PLACEMENT_BASKET = '400'

LUT_PRODUCT_PLACEMENT = (
    (PRODUCT_PLACEMENT_FREEZER, _('freezer')),
    (PRODUCT_PLACEMENT_FRIDGE, _('fridge')),
    (PRODUCT_PLACEMENT_OUT_OF_BASKET, _('loose, out of the basket')),
    (PRODUCT_PLACEMENT_BASKET, _('into the basket')),
)

PRODUCT_ORDER_UNIT_PC = '100'
PRODUCT_ORDER_UNIT_PC_PRICE_KG = '105'
PRODUCT_ORDER_UNIT_PC_PRICE_LT = '110'
PRODUCT_ORDER_UNIT_PC_PRICE_PC = '115'
PRODUCT_ORDER_UNIT_KG = '120'
PRODUCT_ORDER_UNIT_PC_KG = '140'
PRODUCT_ORDER_UNIT_LT = '150'
PRODUCT_ORDER_UNIT_DEPOSIT = '300'
PRODUCT_ORDER_UNIT_SUBSCRIPTION = '400'
PRODUCT_ORDER_UNIT_TRANSPORTATION = '500'

LUT_PRODUCT_ORDER_UNIT = (
    (PRODUCT_ORDER_UNIT_PC, _("bought per piece")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, _("bought per piece (price /kg)")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, _("bought per piece (price /l)")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, _("bought per piece (price /pc)")),
    (PRODUCT_ORDER_UNIT_KG, _("bought per kg")),
    (PRODUCT_ORDER_UNIT_PC_KG, _("bought per piece, invoiced following the weight")),
    (PRODUCT_ORDER_UNIT_LT, _("bought per l")),
    (PRODUCT_ORDER_UNIT_DEPOSIT,
        _('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')),
    (PRODUCT_ORDER_UNIT_SUBSCRIPTION, _(
        'As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')),
    (PRODUCT_ORDER_UNIT_TRANSPORTATION, _(
        'As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')),
)

LUT_PRODUCT_ORDER_UNIT_REVERSE = (
    (_("bought per piece"), PRODUCT_ORDER_UNIT_PC),
    (_("bought per piece (price /kg)"), PRODUCT_ORDER_UNIT_PC_PRICE_KG),
    (_("bought per piece (price /l)"), PRODUCT_ORDER_UNIT_PC_PRICE_LT),
    (_("bought per piece (price /pc)"), PRODUCT_ORDER_UNIT_PC_PRICE_PC),
    (_("bought per kg"), PRODUCT_ORDER_UNIT_KG),
    (_("bought per piece, invoiced following the weight"), PRODUCT_ORDER_UNIT_PC_KG),
    (_("bought per l"), PRODUCT_ORDER_UNIT_LT),
    (_('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.'),
     PRODUCT_ORDER_UNIT_DEPOSIT),
    (_('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group'),
     PRODUCT_ORDER_UNIT_SUBSCRIPTION),
    (_('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.'),
     PRODUCT_ORDER_UNIT_TRANSPORTATION),
)

LUT_PRODUCER_PRODUCT_ORDER_UNIT = (
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, _("Sold by piece")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, _("Sold by weight")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, _("Sold by l")),
    (PRODUCT_ORDER_UNIT_PC_KG, _("Sold by piece, invoiced following the weight")),
)

VAT_100 = '100'
VAT_200 = '200'
VAT_300 = '300'
VAT_400 = '400'
VAT_500 = '500'
VAT_600 = '600'

LUT_VAT = (
    (VAT_100, _('none')),
    (VAT_200, _('compensation 2%')),
    (VAT_300, _('compensation 6%')),
    (VAT_400, _('vat 6%')),
    (VAT_500, _('vat 12%')),
    (VAT_600, _('vat 21%')),
)

LUT_VAT_REVERSE = (
    ( _('none'), VAT_100),
    ( _('compensation 2%'), VAT_200),
    ( _('compensation 6%'), VAT_300),
    ( _('vat 6%'), VAT_400),
    ( _('vat 12%'), VAT_500),
    ( _('vat 21%'), VAT_600),
)

BANK_NOT_LATEST_TOTAL = '100'
BANK_COMPENSATION = '200'
BANK_NEXT_LATEST_TOTAL = '300'
BANK_LATEST_TOTAL = '400'

LUT_BANK_TOTAL = (
    (BANK_NOT_LATEST_TOTAL, _('This is not the latest total')),
    (BANK_NEXT_LATEST_TOTAL, _('This is the next latest bank total')),
    (BANK_LATEST_TOTAL, _('This is the latest bank total')),
)

PERMANENCE_NAME_PERMANENCE = '100'
PERMANENCE_NAME_CLOSURE = '200'
PERMANENCE_NAME_DELIVERY = '300'
PERMANENCE_NAME_ORDER = '400'

LUT_PERMANENCE_NAME = (
    (PERMANENCE_NAME_PERMANENCE, _('Permanence')),
    (PERMANENCE_NAME_CLOSURE, _('Closure')),
    (PERMANENCE_NAME_DELIVERY, _('Delivery')),
    (PERMANENCE_NAME_ORDER, _('Order')),
)

LIMIT_ORDER_QTY_ITEM = 50
LIMIT_DISPLAYED_PERMANENCE = 25