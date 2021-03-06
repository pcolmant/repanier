from decimal import Decimal
from typing import Dict, Tuple

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from repanier.fields.RepanierMoneyField import RepanierMoney

WEBMASTER_GROUP: str = "webmaster"

EMPTY_STRING: str = ""
ONE_YEAR: int = 365

DECIMAL_ZERO: Decimal = Decimal("0")
DECIMAL_ONE: Decimal = Decimal("1")
DECIMAL_TWO: Decimal = Decimal("2")
DECIMAL_THREE: Decimal = Decimal("3")
DECIMAL_1_02: Decimal = Decimal("1.02")
DECIMAL_1_04: Decimal = Decimal("1.04")
DECIMAL_1_06: Decimal = Decimal("1.06")
DECIMAL_1_10: Decimal = Decimal("1.10")
DECIMAL_1_12: Decimal = Decimal("1.12")
DECIMAL_1_21: Decimal = Decimal("1.21")
DECIMAL_0_02: Decimal = Decimal("0.02")
DECIMAL_0_04: Decimal = Decimal("0.04")
DECIMAL_0_05: Decimal = Decimal("0.05")
DECIMAL_0_021: Decimal = Decimal("0.021")
DECIMAL_0_025: Decimal = Decimal("0.025")
DECIMAL_0_038: Decimal = Decimal("0.038")
DECIMAL_0_055: Decimal = Decimal("0.055")
DECIMAL_0_06: Decimal = Decimal("0.06")
DECIMAL_0_08: Decimal = Decimal("0.08")
DECIMAL_0_10: Decimal = Decimal("0.10")
DECIMAL_0_12: Decimal = Decimal("0.12")
DECIMAL_0_20: Decimal = Decimal("0.20")
DECIMAL_0_21: Decimal = Decimal("0.21")

DECIMAL_MAX_STOCK: Decimal = Decimal("999999")
ZERO_DECIMAL: Decimal = Decimal("0")
ONE_DECIMAL: Decimal = Decimal("0.1")
TWO_DECIMALS: Decimal = Decimal("0.01")
THREE_DECIMALS: Decimal = Decimal("0.001")
FOUR_DECIMALS: Decimal = Decimal("0.0001")

ONE_LEVEL_DEPTH: int = 0
TWO_LEVEL_DEPTH: int = 1

REPANIER_MONEY_ZERO = RepanierMoney()

PERMANENCE_PLANNED: str = "100"
PERMANENCE_WAIT_FOR_OPEN: str = "200"
PERMANENCE_OPENED: str = "300"
PERMANENCE_WAIT_FOR_CLOSED: str = "350"
PERMANENCE_CLOSED: str = "370"
PERMANENCE_WAIT_FOR_SEND: str = "400"
PERMANENCE_SEND: str = "500"
PERMANENCE_WAIT_FOR_INVOICED: str = "600"
PERMANENCE_WAIT_FOR_CANCEL_INVOICE: str = "700"
PERMANENCE_INVOICED: str = "800"
PERMANENCE_ARCHIVED: str = "900"
PERMANENCE_CANCELLED: str = "950"

PERMANENCE_PLANNED_STR: str = _("Scheduled")
PERMANENCE_WAIT_FOR_OPEN_STR: str = _("Being opened")
PERMANENCE_OPENED_STR: str = _("Orders opened")
PERMANENCE_WAIT_FOR_CLOSED_STR: str = _("Being closed (step1)")
PERMANENCE_CLOSED_STR: str = _("Being closed (step 2)")
PERMANENCE_WAIT_FOR_SEND_STR: str = _("Being closed (step 3)")
PERMANENCE_SEND_STR: str = _("Orders closed")
PERMANENCE_WAIT_FOR_INVOICED_STR: str = _("Being invoiced")
PERMANENCE_WAIT_FOR_CANCEL_INVOICE_STR: str = _("Being cancelled")
PERMANENCE_INVOICED_STR: str = _("Invoiced")
PERMANENCE_ARCHIVED_STR: str = _("Archived")
PERMANENCE_CANCELLED_STR: str = _("Cancelled")

LUT_PERMANENCE_STATUS = (
    (PERMANENCE_PLANNED, PERMANENCE_PLANNED_STR),
    (PERMANENCE_WAIT_FOR_OPEN, PERMANENCE_WAIT_FOR_OPEN_STR),
    (PERMANENCE_OPENED, PERMANENCE_OPENED_STR),
    (PERMANENCE_WAIT_FOR_CLOSED, PERMANENCE_WAIT_FOR_CLOSED_STR),
    (PERMANENCE_CLOSED, PERMANENCE_CLOSED_STR),
    (PERMANENCE_WAIT_FOR_SEND, PERMANENCE_WAIT_FOR_SEND_STR),
    (PERMANENCE_SEND, PERMANENCE_SEND_STR),
    (PERMANENCE_WAIT_FOR_INVOICED, PERMANENCE_WAIT_FOR_INVOICED_STR),
    (PERMANENCE_WAIT_FOR_CANCEL_INVOICE, PERMANENCE_WAIT_FOR_CANCEL_INVOICE_STR),
    (PERMANENCE_INVOICED, PERMANENCE_INVOICED_STR),
    (PERMANENCE_ARCHIVED, PERMANENCE_ARCHIVED_STR),
    (PERMANENCE_CANCELLED, PERMANENCE_CANCELLED_STR),
)

PRODUCT_PLACEMENT_FREEZER: str = "100"
PRODUCT_PLACEMENT_FRIDGE: str = "200"
PRODUCT_PLACEMENT_OUT_OF_BASKET: str = "300"
PRODUCT_PLACEMENT_BASKET: str = "400"

PRODUCT_PLACEMENT_FREEZER_STR: str = _("Freezer")
PRODUCT_PLACEMENT_FRIDGE_STR: str = _("Fridge")
PRODUCT_PLACEMENT_OUT_OF_BASKET_STR: str = _("Loose, out of the basket")
PRODUCT_PLACEMENT_BASKET_STR: str = _("Into the basket")

LUT_PRODUCT_PLACEMENT = (
    (PRODUCT_PLACEMENT_FREEZER, PRODUCT_PLACEMENT_FREEZER_STR),
    (PRODUCT_PLACEMENT_FRIDGE, PRODUCT_PLACEMENT_FRIDGE_STR),
    (PRODUCT_PLACEMENT_OUT_OF_BASKET, PRODUCT_PLACEMENT_OUT_OF_BASKET_STR),
    (PRODUCT_PLACEMENT_BASKET, PRODUCT_PLACEMENT_BASKET_STR),
)

LUT_PRODUCT_PLACEMENT_REVERSE = (
    (PRODUCT_PLACEMENT_FREEZER_STR, PRODUCT_PLACEMENT_FREEZER),
    (PRODUCT_PLACEMENT_FRIDGE_STR, PRODUCT_PLACEMENT_FRIDGE),
    (PRODUCT_PLACEMENT_OUT_OF_BASKET_STR, PRODUCT_PLACEMENT_OUT_OF_BASKET),
    (PRODUCT_PLACEMENT_BASKET_STR, PRODUCT_PLACEMENT_BASKET),
)

PRODUCT_ORDER_UNIT_PC: str = "100"
PRODUCT_ORDER_UNIT_PC_PRICE_KG: str = "105"
PRODUCT_ORDER_UNIT_PC_PRICE_LT: str = "110"
PRODUCT_ORDER_UNIT_PC_PRICE_PC: str = "115"
PRODUCT_ORDER_UNIT_KG: str = "120"
PRODUCT_ORDER_UNIT_PC_KG: str = "140"
PRODUCT_ORDER_UNIT_LT: str = "150"
PRODUCT_ORDER_UNIT_DEPOSIT: str = "300"
PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE: str = "400"
PRODUCT_ORDER_UNIT_TRANSPORTATION: str = "500"

PRODUCT_ORDER_UNIT_PC_STR: str = _(
    "Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ..."
)
PRODUCT_ORDER_UNIT_PC_PRICE_KG_STR: str = _(
    "Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ..."
)
PRODUCT_ORDER_UNIT_PC_PRICE_KG_SHORT_STR: str = _("Sold by weight")
PRODUCT_ORDER_UNIT_PC_PRICE_LT_STR: str = _(
    "Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ..."
)
PRODUCT_ORDER_UNIT_PC_PRICE_LT_SHORT_STR: str = _("Sold by l")
PRODUCT_ORDER_UNIT_PC_PRICE_PC_STR: str = _(
    "Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ..."
)
PRODUCT_ORDER_UNIT_PC_PRICE_PC_SHORT_STR: str = _("Sold by piece")
PRODUCT_ORDER_UNIT_KG_STR: str = _(
    "Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ..."
)
PRODUCT_ORDER_UNIT_PC_KG_STR: str = _(
    "Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ..."
)
PRODUCT_ORDER_UNIT_PC_KG_SHORT_STR: str = _(
    "Sold by piece, invoiced following the weight"
)
PRODUCT_ORDER_UNIT_LT_STR: str = _("Sold in volume (in ℓ): non-conditioned liquids")
PRODUCT_ORDER_UNIT_DEPOSIT_STR: str = _("Deposit taken back at the permanence.")
PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE_STR: str = _("Membership fee.")
PRODUCT_ORDER_UNIT_TRANSPORTATION_STR: str = _("Shipping cost.")

LUT_PRODUCT_ORDER_UNIT_WO_SHIPPING_COST = (
    (PRODUCT_ORDER_UNIT_PC, PRODUCT_ORDER_UNIT_PC_STR),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG_STR),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_LT_STR),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, PRODUCT_ORDER_UNIT_PC_PRICE_PC_STR),
    (PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_KG_STR),
    (PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_KG_STR),
    (PRODUCT_ORDER_UNIT_LT, PRODUCT_ORDER_UNIT_LT_STR),
    (PRODUCT_ORDER_UNIT_DEPOSIT, PRODUCT_ORDER_UNIT_DEPOSIT_STR),
)

LUT_PRODUCT_ORDER_UNIT = LUT_PRODUCT_ORDER_UNIT_WO_SHIPPING_COST + (
    (PRODUCT_ORDER_UNIT_TRANSPORTATION, PRODUCT_ORDER_UNIT_TRANSPORTATION_STR),
)

LUT_PRODUCT_ORDER_UNIT_REVERSE = (
    (PRODUCT_ORDER_UNIT_PC_STR, PRODUCT_ORDER_UNIT_PC),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG_STR, PRODUCT_ORDER_UNIT_PC_PRICE_KG),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT_STR, PRODUCT_ORDER_UNIT_PC_PRICE_LT),
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC_STR, PRODUCT_ORDER_UNIT_PC_PRICE_PC),
    (PRODUCT_ORDER_UNIT_KG_STR, PRODUCT_ORDER_UNIT_KG),
    (PRODUCT_ORDER_UNIT_PC_KG_STR, PRODUCT_ORDER_UNIT_PC_KG),
    (PRODUCT_ORDER_UNIT_LT_STR, PRODUCT_ORDER_UNIT_LT),
    (PRODUCT_ORDER_UNIT_DEPOSIT_STR, PRODUCT_ORDER_UNIT_DEPOSIT),
    (PRODUCT_ORDER_UNIT_TRANSPORTATION_STR, PRODUCT_ORDER_UNIT_TRANSPORTATION),
)

LUT_PRODUCER_PRODUCT_ORDER_UNIT = (
    (PRODUCT_ORDER_UNIT_PC_PRICE_PC, PRODUCT_ORDER_UNIT_PC_PRICE_PC_SHORT_STR),
    (PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG_SHORT_STR),
    (PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_LT_SHORT_STR),
    (PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_KG_SHORT_STR),
)

VAT_100: str = "100"
VAT_200: str = "200"
VAT_300: str = "300"
VAT_315: str = "315"
VAT_325: str = "325"
VAT_360: str = "360"
VAT_375: str = "375"
VAT_350: str = "350"
VAT_400: str = "400"
VAT_430: str = "430"
VAT_460: str = "460"
VAT_500: str = "500"
VAT_590: str = "590"
VAT_600: str = "600"

DICT_VAT_LABEL: int = 0
DICT_VAT_RATE: int = 1

DICT_VAT: Dict[str, Tuple[str, Decimal]] = {
    VAT_100: (_("---------"), DECIMAL_ZERO),
    VAT_315: (_("2.1%"), DECIMAL_0_021),
    VAT_325: (_("2.5%"), DECIMAL_0_025),
    VAT_350: (_("3.8%"), DECIMAL_0_038),
    VAT_360: (_("4%"), DECIMAL_0_04),
    VAT_375: (_("5.5%"), DECIMAL_0_055),
    VAT_400: (_("6%"), DECIMAL_0_06),
    VAT_430: (_("8%"), DECIMAL_0_08),
    VAT_460: (_("10%"), DECIMAL_0_10),
    VAT_500: (_("12%"), DECIMAL_0_12),
    VAT_590: (_("20%"), DECIMAL_0_20),
    VAT_600: (_("21%"), DECIMAL_0_21),
}

LUT_ALL_VAT = (
    (VAT_100, _("---------")),
    (VAT_315, _("2.1%")),
    (VAT_325, _("2.5%")),
    (VAT_350, _("3.8%")),
    (VAT_360, _("4%")),
    (VAT_375, _("5.5%")),
    (VAT_400, _("6%")),
    (VAT_430, _("8%")),
    (VAT_460, _("10%")),
    (VAT_500, _("12%")),
    (VAT_590, _("20%")),
    (VAT_600, _("21%")),
)

# Number needed for xlsx_invoice.import_invoice_sheet : vat_level = lut_reverse_vat[vat]
LUT_ALL_VAT_REVERSE = (
    (0, VAT_100),
    (0.021, VAT_315),
    (0.025, VAT_325),
    (0.038, VAT_350),
    (0.04, VAT_360),
    (0.055, VAT_375),
    (0.06, VAT_400),
    (0.08, VAT_430),
    (0.1, VAT_460),
    (0.12, VAT_500),
    (0.2, VAT_590),
    (0.21, VAT_600),
)

##################### REPANIER VAT/RATE

if settings.REPANIER_SETTINGS_COUNTRY == "ch":
    # Switzerland
    DICT_VAT_DEFAULT = VAT_325
    LUT_VAT = (
        (VAT_100, _("---------")),
        (VAT_325, _("2.5%")),
        (VAT_350, _("3.8%")),
        (VAT_430, _("8%")),
    )

    LUT_VAT_REVERSE = (
        (_("---------"), VAT_100),
        (_("2.5%"), VAT_325),
        (_("3.8%"), VAT_350),
        (_("8%"), VAT_430),
    )
elif settings.REPANIER_SETTINGS_COUNTRY == "fr":
    # France
    DICT_VAT_DEFAULT = VAT_375
    LUT_VAT = (
        (VAT_100, _("---------")),
        (VAT_315, _("2.1%")),
        (VAT_375, _("5.5%")),
        (VAT_460, _("10%")),
        (VAT_590, _("20%")),
    )

    LUT_VAT_REVERSE = (
        (_("---------"), VAT_100),
        (_("2.1%"), VAT_315),
        (_("5.5%"), VAT_375),
        (_("10%"), VAT_460),
        (_("20%"), VAT_590),
    )
elif settings.REPANIER_SETTINGS_COUNTRY == "es":
    # Espagne
    DICT_VAT_DEFAULT = VAT_460
    LUT_VAT = (
        (VAT_100, _("---------")),
        (VAT_360, _("4%")),
        (VAT_460, _("10%")),
        (VAT_600, _("21%")),
    )

    LUT_VAT_REVERSE = (
        (_("---------"), VAT_100),
        (_("4%"), VAT_360),
        (_("10%"), VAT_460),
        (_("21%"), VAT_600),
    )
else:
    # Belgium
    DICT_VAT_DEFAULT = VAT_400
    LUT_VAT = (
        (VAT_100, _("---------")),
        (VAT_400, _("6%")),
        (VAT_500, _("12%")),
        (VAT_600, _("21%")),
    )

    LUT_VAT_REVERSE = (
        (_("---------"), VAT_100),
        (_("6%"), VAT_400),
        (_("12%"), VAT_500),
        (_("21%"), VAT_600),
    )

BANK_NOT_LATEST_TOTAL: str = "100"
BANK_MEMBERSHIP_FEE: str = "150"
BANK_PROFIT: str = "210"
BANK_TAX: str = "220"
BANK_CALCULATED_INVOICE: str = "250"
BANK_NEXT_LATEST_TOTAL: str = "300"
BANK_LATEST_TOTAL: str = "400"

LUT_BANK_TOTAL = (
    (BANK_NOT_LATEST_TOTAL, _("This is not the latest total")),
    (BANK_MEMBERSHIP_FEE, BANK_MEMBERSHIP_FEE),
    (BANK_PROFIT, BANK_PROFIT),
    (BANK_TAX, BANK_TAX),
    (BANK_CALCULATED_INVOICE, BANK_CALCULATED_INVOICE),
    (BANK_NEXT_LATEST_TOTAL, _("This is the next latest bank total.")),
    (BANK_LATEST_TOTAL, _("This is the latest bank total.")),
)

PERMANENCE_NAME_PERMANENCE: str = "100"
PERMANENCE_NAME_CLOSURE: str = "200"
PERMANENCE_NAME_DELIVERY: str = "300"
PERMANENCE_NAME_ORDER: str = "400"
PERMANENCE_NAME_OPENING: str = "500"
PERMANENCE_NAME_DISTRIBUTION: str = "600"

LUT_PERMANENCE_NAME = (
    (PERMANENCE_NAME_PERMANENCE, _("Permanence")),
    (PERMANENCE_NAME_CLOSURE, _("Closure")),
    (PERMANENCE_NAME_DELIVERY, _("Delivery")),
    (PERMANENCE_NAME_ORDER, _("Order")),
    (PERMANENCE_NAME_OPENING, _("Opening")),
    (PERMANENCE_NAME_DISTRIBUTION, _("Distribution")),
)

LIMIT_ORDER_QTY_ITEM: int = 25
LIMIT_DISPLAYED_PERMANENCE: int = 25
BOX_VALUE_STR: str = "-1"
BOX_VALUE_INT: int = -1
BOX_UNICODE: str = "📦"  # http://unicode-table.com/fr/1F6CD/

# VALID_UNICODE = "✓"
BANK_NOTE_UNICODE: str = "💶"
LINK_UNICODE: str = "⛓"

# LUT_VALID = (
#     (True, VALID_UNICODE), (False, EMPTY_STRING)
# )

LUT_BANK_NOTE = ((True, BANK_NOTE_UNICODE), (False, EMPTY_STRING))

CURRENCY_EUR: str = "100"
CURRENCY_CHF: str = "200"
CURRENCY_LOC: str = "300"

LUT_CURRENCY = (
    (CURRENCY_EUR, _("Euro")),
    (CURRENCY_CHF, _("Fr.")),
    (CURRENCY_LOC, _("Local")),
)
