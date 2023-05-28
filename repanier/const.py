from decimal import *
from enum import Enum

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from repanier.fields.RepanierMoneyField import RepanierMoney


class AuthGroup(str, Enum):
    WEBMASTER = "webmaster"
    REPANIER = "repanier"


EMPTY_STRING = ""
ONE_YEAR = 365
LIMIT_ORDER_QTY_ITEM = 25
LIMIT_DISPLAYED_PERMANENCE = 25
DECIMAL_MAX_STOCK = Decimal("999999")
REPANIER_MONEY_ZERO = RepanierMoney()

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
DECIMAL_TWO = Decimal("2")
DECIMAL_THREE = Decimal("3")
DECIMAL_1_02 = Decimal("1.02")
DECIMAL_1_04 = Decimal("1.04")
DECIMAL_1_06 = Decimal("1.06")
DECIMAL_1_10 = Decimal("1.10")
DECIMAL_1_12 = Decimal("1.12")
DECIMAL_1_21 = Decimal("1.21")
DECIMAL_0_02 = Decimal("0.02")
DECIMAL_0_04 = Decimal("0.04")
DECIMAL_0_05 = Decimal("0.05")
DECIMAL_0_021 = Decimal("0.021")
DECIMAL_0_025 = Decimal("0.025")
DECIMAL_0_038 = Decimal("0.038")
DECIMAL_0_055 = Decimal("0.055")
DECIMAL_0_06 = Decimal("0.06")
DECIMAL_0_08 = Decimal("0.08")
DECIMAL_0_10 = Decimal("0.10")
DECIMAL_0_12 = Decimal("0.12")
DECIMAL_0_20 = Decimal("0.20")
DECIMAL_0_21 = Decimal("0.21")


class RoundUpTo(Decimal, Enum):
    ZERO_DECIMAL = Decimal("0")
    ONE_DECIMAL = Decimal("0.1")
    TWO_DECIMALS = Decimal("0.01")
    THREE_DECIMALS = Decimal("0.001")
    FOUR_DECIMALS = Decimal("0.0001")


class MpttLevelDepth(int, Enum):
    ONE = 0
    TWO = 1


class SaleStatus(models.TextChoices):
    PLANNED = "100", _("Scheduled")
    WAIT_FOR_OPEN = "200", _("Being opened")
    OPENED = "300", _("Orders opened")
    WAIT_FOR_CLOSED = "350", _("Being closed (step1)")
    CLOSED = "370", _("Being closed (step 2)")
    WAIT_FOR_SEND = "400", _("Being closed (step 3)")
    SEND = "500", _("Orders closed")
    WAIT_FOR_INVOICED = "600", _("Being booked")
    WAIT_FOR_CANCEL_INVOICE = "700", _("Being cancelled")
    INVOICED = "800", _("Booked")
    ARCHIVED = "900", _("Archived")
    CANCELLED = "950", _("Cancelled")


class Placement(models.TextChoices):
    FREEZER = "100", _("Freezer")
    FRIDGE = "200", _("Fridge")
    OUT_OF_BASKET = "300", _("Loose, out of the basket")
    BASKET = "400", _("Into the basket")


class OrderUnit(models.TextChoices):
    PC = "100", _(
        "Sold by the piece without further details (not recommended if the weight or the litter is available): bouquet of thyme, ..."
    )
    PC_PRICE_KG = "105", _(
        "Sold packaged in pack / bag / ravier / ...: 250 gr. of butter, bag of 5 kg of potatoes, lasagne of 200 gr., ..."
    )
    PC_PRICE_LT = "110", _("Sold packaged in cubi of 3 ℓ, bottle of 75 cℓ, ...")
    PC_PRICE_PC = "115", _(
        "Sold packaged in packs without weight or volume: 6 eggs, 12 coffee pads, 6 praline ballotin, ..."
    )
    KG = "120", _("Sold by weight (in kg): bulk vegetables, cheeses / meat cut, ...")
    PC_KG = "140", _(
        "Sold by the piece, charged according to the actual weight: hamburgers, pumpkins, ..."
    )
    LT = "150", _("Sold in volume (in ℓ): non-conditioned liquids")
    DEPOSIT = "300", _("Deposit taken back at the permanence")
    MEMBERSHIP_FEE = "400", _("Membership fee")


##################### REPANIER VAT/RATE


class Vat(models.TextChoices):
    VAT_100 = "100", "---------"
    VAT_200 = "200", "2,5%"
    VAT_300 = "300", "3,8%"
    VAT_400 = "400", "6%"
    VAT_450 = "450", "8%"
    VAT_500 = "500", "12%"
    VAT_600 = "600", "21%"


class VatDecimal(Decimal, Enum):
    VAT_100 = DECIMAL_ZERO
    VAT_200 = DECIMAL_0_025
    VAT_300 = DECIMAL_0_038
    VAT_400 = DECIMAL_0_06
    VAT_450 = DECIMAL_0_08
    VAT_500 = DECIMAL_0_12
    VAT_600 = DECIMAL_0_21


LUT_ALL_VAT = (
    (Vat.VAT_100, VatDecimal.VAT_100),
    (Vat.VAT_200, VatDecimal.VAT_200),
    (Vat.VAT_300, VatDecimal.VAT_300),
    (Vat.VAT_400, VatDecimal.VAT_400),
    (Vat.VAT_450, VatDecimal.VAT_450),
    (Vat.VAT_500, VatDecimal.VAT_500),
    (Vat.VAT_600, VatDecimal.VAT_600),
)

DICT_ALL_VAT = dict(LUT_ALL_VAT)

LUT_ALL_VAT_REVERSE = (
    (VatDecimal.VAT_100, Vat.VAT_100),
    (VatDecimal.VAT_200, Vat.VAT_200),
    (VatDecimal.VAT_300, Vat.VAT_300),
    (VatDecimal.VAT_400, Vat.VAT_400),
    (VatDecimal.VAT_450, Vat.VAT_450),
    (VatDecimal.VAT_500, Vat.VAT_500),
    (VatDecimal.VAT_600, Vat.VAT_600),
)

DICT_ALL_VAT_REVERSE = dict(DICT_ALL_VAT)


if settings.REPANIER_SETTINGS_COUNTRY == "ch":
    # Switzerland
    VAT_DEFAULT = Vat.VAT_200
    LUT_VAT = (
        (Vat.VAT_100, Vat.VAT_100.label),
        (Vat.VAT_200, Vat.VAT_200.label),
        (Vat.VAT_300, Vat.VAT_300.label),
        (Vat.VAT_450, Vat.VAT_450.label),
    )

    LUT_VAT_REVERSE = (
        (Vat.VAT_100.label, Vat.VAT_100),
        (Vat.VAT_200.label, Vat.VAT_200),
        (Vat.VAT_300.label, Vat.VAT_300),
        (Vat.VAT_450.label, Vat.VAT_450),
    )
else:
    # Belgium
    VAT_DEFAULT = Vat.VAT_400
    LUT_VAT = (
        (Vat.VAT_100, Vat.VAT_100.label),
        (Vat.VAT_400, Vat.VAT_400.label),
        (Vat.VAT_500, Vat.VAT_500.label),
        (Vat.VAT_600, Vat.VAT_600.label),
    )

    LUT_VAT_REVERSE = (
        (Vat.VAT_100.label, Vat.VAT_100),
        (Vat.VAT_400.label, Vat.VAT_400),
        (Vat.VAT_500.label, Vat.VAT_500),
        (Vat.VAT_600.label, Vat.VAT_600),
    )


class BankMovement(models.TextChoices):
    NOT_LATEST_TOTAL = "100", _("This is not the latest total")
    MEMBERSHIP_FEE = "150", "N/A 150"
    COMPENSATION = "200", "N/A 200"
    PROFIT = "210", "N/A 210"
    TAX = "220", "N/A 220"
    CALCULATED_INVOICE = "250", "N/A 250"
    NEXT_LATEST_TOTAL = "300", _("This is the next latest bank total.")
    LATEST_TOTAL = "400", _("This is the latest bank total.")


class PermanenceName(models.TextChoices):
    PERMANENCE = "100", _("Permanence")
    CLOSURE = "200", _("Closure")
    DELIVERY = "300", _("Delivery")
    ORDER = "400", _("Order")
    OPENING = "500", _("Opening")
    DISTRIBUTION = "600", _("Distribution")


BANK_NOTE_UNICODE = "💶"


LUT_BANK_NOTE = ((True, BANK_NOTE_UNICODE), (False, EMPTY_STRING))


class Currency(models.TextChoices):
    EUR = "100", "€"
    CHF = "200", "Fr."
    LOC = "300", "SolAToi"
