# -*- coding: utf-8
from decimal import *
from django.utils.translation import ugettext_lazy as _
from repanier.fields.RepanierMoneyField import RepanierMoney

WEBMASTER_GROUP = "webmaster"
DEMO_EMAIL = "repanier@no-spam.ws"

EMPTY_STRING = ""
ONE_YEAR = 365

DECIMAL_ZERO = Decimal('0')
DECIMAL_ONE = Decimal('1')
DECIMAL_TWO = Decimal('2')
DECIMAL_THREE = Decimal('3')
DECIMAL_1_02 = Decimal('1.02')
DECIMAL_1_04 = Decimal('1.04')
DECIMAL_1_06 = Decimal('1.06')
DECIMAL_1_10 = Decimal('1.10')
DECIMAL_1_12 = Decimal('1.12')
DECIMAL_1_21 = Decimal('1.21')
DECIMAL_0_02 = Decimal('0.02')
DECIMAL_0_04 = Decimal('0.04')
DECIMAL_0_021 = Decimal('0.021')
DECIMAL_0_025 = Decimal('0.025')
DECIMAL_0_038 = Decimal('0.038')
DECIMAL_0_055 = Decimal('0.055')
DECIMAL_0_06 = Decimal('0.06')
DECIMAL_0_08 = Decimal('0.08')
DECIMAL_0_10 = Decimal('0.10')
DECIMAL_0_12 = Decimal('0.12')
DECIMAL_0_20 = Decimal('0.20')
DECIMAL_0_21 = Decimal('0.21')
DECIMAL_MAX_STOCK = Decimal('999999')
ZERO_DECIMAL = Decimal('0')
ONE_DECIMAL = Decimal('0.1')
TWO_DECIMALS = Decimal('0.01')
THREE_DECIMALS = Decimal('0.001')
FOUR_DECIMALS = Decimal('0.0001')

ONE_LEVEL_DEPTH = 0
TWO_LEVEL_DEPTH = 1

REPANIER_MONEY_ZERO = RepanierMoney()

PERMANENCE_PLANNED = '100'
PERMANENCE_WAIT_FOR_PRE_OPEN = '110'
PERMANENCE_PRE_OPEN = '120'
PERMANENCE_WAIT_FOR_OPEN = '200'
PERMANENCE_OPENED = '300'
PERMANENCE_WAIT_FOR_CLOSED = '350'
PERMANENCE_CLOSED = '370'
PERMANENCE_WAIT_FOR_SEND = '400'
PERMANENCE_SEND = '500'
PERMANENCE_WAIT_FOR_INVOICED = '600'
PERMANENCE_INVOICED = '800'
PERMANENCE_ARCHIVED = '900'
PERMANENCE_CANCELLED = '950'

LUT_PERMANENCE_STATUS = (
    (PERMANENCE_PLANNED, _('Scheduled')),
    (PERMANENCE_WAIT_FOR_PRE_OPEN, _('Wait for pre-open')),
    (PERMANENCE_PRE_OPEN, _('Orders pre-opened')),
    (PERMANENCE_WAIT_FOR_OPEN, _('Wait for open')),
    (PERMANENCE_OPENED, _('Orders opened')),
    (PERMANENCE_WAIT_FOR_CLOSED, _('Wait for close')),
    (PERMANENCE_CLOSED, _('Orders closed')),
    (PERMANENCE_WAIT_FOR_SEND, _('Wait for send')),
    (PERMANENCE_SEND, _('Orders send')),
    (PERMANENCE_WAIT_FOR_INVOICED, _('Wait for done')),
    (PERMANENCE_INVOICED, _('Invoiced')),
    (PERMANENCE_ARCHIVED, _('Archived')),
    (PERMANENCE_CANCELLED, _('Cancelled'))
)

PRODUCT_PLACEMENT_FREEZER = '100'
PRODUCT_PLACEMENT_FRIDGE = '200'
PRODUCT_PLACEMENT_OUT_OF_BASKET = '300'
PRODUCT_PLACEMENT_BASKET = '400'

LUT_PRODUCT_PLACEMENT = (
    (PRODUCT_PLACEMENT_FREEZER, _('Freezer')),
    (PRODUCT_PLACEMENT_FRIDGE, _('Fridge')),
    (PRODUCT_PLACEMENT_OUT_OF_BASKET, _('Loose, out of the basket')),
    (PRODUCT_PLACEMENT_BASKET, _('Into the basket')),
)

LUT_PRODUCT_PLACEMENT_REVERSE = (
    (_('Freezer'), PRODUCT_PLACEMENT_FREEZER),
    (_('Fridge'), PRODUCT_PLACEMENT_FRIDGE),
    (_('Loose, out of the basket'), PRODUCT_PLACEMENT_OUT_OF_BASKET),
    (_('Into the basket'), PRODUCT_PLACEMENT_BASKET),
)

PRODUCT_ORDER_UNIT_PC = '100'
PRODUCT_ORDER_UNIT_PC_PRICE_KG = '105'
PRODUCT_ORDER_UNIT_PC_PRICE_LT = '110'
PRODUCT_ORDER_UNIT_PC_PRICE_PC = '115'
PRODUCT_ORDER_UNIT_KG = '120'
PRODUCT_ORDER_UNIT_PC_KG = '140'
PRODUCT_ORDER_UNIT_LT = '150'
PRODUCT_ORDER_UNIT_DEPOSIT = '300'
PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE = '400'
PRODUCT_ORDER_UNIT_TRANSPORTATION = '500'
PRODUCT_ORDER_UNIT_SUBSCRIPTION = '600'

LUT_PRODUCT_ORDER_UNIT = (
    (PRODUCT_ORDER_UNIT_PC, _("Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, _("Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, _("Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, _("Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ...")),
    (PRODUCT_ORDER_UNIT_KG, _("Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ...")),
    (PRODUCT_ORDER_UNIT_PC_KG, _("Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ...")),
    (PRODUCT_ORDER_UNIT_LT, _("Sold in volume (in ℓ): non-conditioned liquids")),
    (PRODUCT_ORDER_UNIT_DEPOSIT,
     _('Deposit taken back at the permanence.')),
    (PRODUCT_ORDER_UNIT_SUBSCRIPTION, _(
        'Subscription')),
    (PRODUCT_ORDER_UNIT_TRANSPORTATION, _(
        'Shipping cost.')),
)

LUT_PRODUCT_ORDER_UNIT_REVERSE = (
    (_("Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ..."), PRODUCT_ORDER_UNIT_PC),
    (_("Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ..."), PRODUCT_ORDER_UNIT_PC_PRICE_KG),
    (_("Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ..."), PRODUCT_ORDER_UNIT_PC_PRICE_LT),
    (_("Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ..."), PRODUCT_ORDER_UNIT_PC_PRICE_PC),
    (_("Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ..."), PRODUCT_ORDER_UNIT_KG),
    (_("Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ..."), PRODUCT_ORDER_UNIT_PC_KG),
    (_("Sold in volume (in ℓ): non-conditioned liquids"), PRODUCT_ORDER_UNIT_LT),
    (_('Deposit taken back at the permanence.'),
     PRODUCT_ORDER_UNIT_DEPOSIT),
    (_(
        'Subscription'),
     PRODUCT_ORDER_UNIT_SUBSCRIPTION),
    (_(
        'Shipping cost.'),
     PRODUCT_ORDER_UNIT_TRANSPORTATION),
)

LUT_PRODUCT_ORDER_UNIT_WO_SUBSCRIPTION = (
    (PRODUCT_ORDER_UNIT_PC, _("Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, _("Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, _("Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, _("Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ...")),
    (PRODUCT_ORDER_UNIT_KG, _("Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ...")),
    (PRODUCT_ORDER_UNIT_PC_KG, _("Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ...")),
    (PRODUCT_ORDER_UNIT_LT, _("Sold in volume (in ℓ): non-conditioned liquids")),
    (PRODUCT_ORDER_UNIT_DEPOSIT,
     _('Deposit taken back at the permanence.')),
    (PRODUCT_ORDER_UNIT_TRANSPORTATION, _(
        'Shipping cost.')),
)

LUT_PRODUCT_ORDER_UNIT_W_SUBSCRIPTION = (
    (PRODUCT_ORDER_UNIT_PC, _("Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, _("Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, _("Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ...")),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, _("Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ...")),
    (PRODUCT_ORDER_UNIT_KG, _("Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ...")),
    (PRODUCT_ORDER_UNIT_PC_KG, _("Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ...")),
    (PRODUCT_ORDER_UNIT_LT, _("Sold in volume (in ℓ): non-conditioned liquids")),
    (PRODUCT_ORDER_UNIT_DEPOSIT,
     _("Deposit taken back at the permanence.")),
    (PRODUCT_ORDER_UNIT_SUBSCRIPTION, _(
        "Subscription")),
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
VAT_315 = '315'
VAT_325 = '325'
VAT_360 = '360'
VAT_375 = '375'
VAT_350 = '350'
VAT_400 = '400'
VAT_430 = '430'
VAT_460 = '460'
VAT_500 = '500'
VAT_590 = '590'
VAT_600 = '600'

DICT_VAT_LABEL = 0
DICT_VAT_RATE = 1

DICT_VAT = {
    VAT_100: (_('---------'), DECIMAL_ZERO),
    VAT_315: (_('VAT 2.1%'), DECIMAL_0_021),
    VAT_325: (_('VAT 2.5%'), DECIMAL_0_025),
    VAT_350: (_('VAT 3.8%'), DECIMAL_0_038),
    VAT_360: (_('VAT 4%'), DECIMAL_0_04),
    VAT_375: (_('VAT 5.5%'), DECIMAL_0_055),
    VAT_400: (_('VAT 6%'), DECIMAL_0_06),
    VAT_430: (_('VAT 8%'), DECIMAL_0_08),
    VAT_460: (_('VAT 10%'), DECIMAL_0_10),
    VAT_500: (_('VAT 12%'), DECIMAL_0_12),
    VAT_590: (_('VAT 20%'), DECIMAL_0_20),
    VAT_600: (_('VAT 21%'), DECIMAL_0_21),
}

LUT_ALL_VAT = (
    (VAT_100, _('---------')),
    (VAT_315, _('VAT 2.1%')),
    (VAT_325, _('VAT 2.5%')),
    (VAT_350, _('VAT 3.8%')),
    (VAT_360, _('VAT 4%')),
    (VAT_375, _('VAT 5.5%')),
    (VAT_400, _('VAT 6%')),
    (VAT_430, _('VAT 8%')),
    (VAT_460, _('VAT 10%')),
    (VAT_500, _('VAT 12%')),
    (VAT_590, _('VAT 20%')),
    (VAT_600, _('VAT 21%')),
)

LUT_ALL_VAT_REVERSE = (
    (_('---------'), VAT_100),
    (_('VAT 2.1%'), VAT_315),
    (_('VAT 2.5%'), VAT_325),
    (_('VAT 3.8%'), VAT_350),
    (_('VAT 4%'), VAT_360),
    (_('VAT 5.5%'), VAT_375),
    (_('VAT 6%'), VAT_400),
    (_('VAT 8%'), VAT_430),
    (_('VAT 10%'), VAT_460),
    (_('VAT 12%'), VAT_500),
    (_('VAT 20%'), VAT_590),
    (_('VAT 21%'), VAT_600),
)

BANK_NOT_LATEST_TOTAL = '100'
BANK_MEMBERSHIP_FEE = '150'
BANK_COMPENSATION = '200' # BANK_COMPENSATION may occurs in previous release of Repanier
BANK_PROFIT = '210'
BANK_TAX = '220'
BANK_CALCULATED_INVOICE = '250'
BANK_NEXT_LATEST_TOTAL = '300'
BANK_LATEST_TOTAL = '400'

LUT_BANK_TOTAL = (
    (BANK_NOT_LATEST_TOTAL, _('This is not the latest total')),
    (BANK_MEMBERSHIP_FEE, BANK_MEMBERSHIP_FEE),
    (BANK_PROFIT, BANK_PROFIT),
    (BANK_TAX, BANK_TAX),
    (BANK_CALCULATED_INVOICE, BANK_CALCULATED_INVOICE),
    (BANK_NEXT_LATEST_TOTAL, _('This is the next latest bank total')),
    (BANK_LATEST_TOTAL, _('This is the latest bank total')),
)

PERMANENCE_NAME_PERMANENCE = '100'
PERMANENCE_NAME_CLOSURE = '200'
PERMANENCE_NAME_DELIVERY = '300'
PERMANENCE_NAME_ORDER = '400'
PERMANENCE_NAME_OPENING = '500'
PERMANENCE_NAME_DISTRIBUTION = '600'

LUT_PERMANENCE_NAME = (
    (PERMANENCE_NAME_PERMANENCE, _('Permanence')),
    (PERMANENCE_NAME_CLOSURE, _('Closure')),
    (PERMANENCE_NAME_DELIVERY, _('Delivery')),
    (PERMANENCE_NAME_ORDER, _('Order')),
    (PERMANENCE_NAME_OPENING, _('Opening')),
    (PERMANENCE_NAME_DISTRIBUTION, _('Distribution')),
)

LIMIT_ORDER_QTY_ITEM = 25
LIMIT_DISPLAYED_PERMANENCE = 25
BOX_VALUE_STR = "-1"
BOX_VALUE_INT = -1
BOX_UNICODE = "📦"  # http://unicode-table.com/fr/1F6CD/
LOCK_UNICODE = "✓🔐"
VALID_UNICODE = "✓"
BANK_NOTE_UNICODE = "💶"
CONTRACT_VALUE_STR = "-1"
CONTRACT_VALUE_INT = -1
CONTRACT_UNICODE = "🤝"
LINK_UNICODE = "⛓"

LUT_CONFIRM = (
    (True, LOCK_UNICODE), (False, EMPTY_STRING)
)

LUT_VALID = (
    (True, VALID_UNICODE), (False, EMPTY_STRING)
)

LUT_BANK_NOTE = (
    (True, BANK_NOTE_UNICODE), (False, EMPTY_STRING)
)

CURRENCY_EUR = '100'
CURRENCY_CHF = '200'
CURRENCY_LOC = '300'

LUT_CURRENCY = (
    (CURRENCY_EUR, _('Euro')),
    (CURRENCY_CHF, _('Franc')),
    (CURRENCY_LOC, _('Local')),
)
