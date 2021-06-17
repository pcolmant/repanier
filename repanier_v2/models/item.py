from django.core.validators import MinValueValidator
from django.db import models
from django.utils.formats import number_format
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslatableModel

from repanier_v2.const import (
    DECIMAL_ZERO,
    PRODUCT_ORDER_UNIT_PC_KG,
    PRODUCT_ORDER_UNIT_KG,
    EMPTY_STRING,
    DECIMAL_ONE,
    PRODUCT_ORDER_UNIT_PC_PRICE_KG,
    PRODUCT_ORDER_UNIT_PC_PRICE_LT,
    PRODUCT_ORDER_UNIT_PC_PRICE_PC,
    TWO_DECIMALS,
    PRODUCT_ORDER_UNIT_LT,
    DICT_VAT,
    DICT_VAT_RATE,
    PRODUCT_ORDER_UNIT_DEPOSIT,
    LUT_PRODUCT_ORDER_UNIT,
    PRODUCT_ORDER_UNIT_PC,
    LUT_PRODUCT_PLACEMENT,
    PRODUCT_PLACEMENT_BASKET,
    LUT_ALL_VAT,
    LIMIT_ORDER_QTY_ITEM,
    DECIMAL_MAX_STOCK,
    DICT_VAT_DEFAULT,
)
from repanier_v2.fields.RepanierMoneyField import RepanierMoney, ModelMoneyField
from repanier_v2.picture.const import SIZE_L
from repanier_v2.picture.fields import RepanierPictureField


class Item(TranslatableModel):
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        "Department",
        related_name="+",
        verbose_name=_("Department"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )
    caption = (
        models.CharField(
            _("Caption"), max_length=100, default=EMPTY_STRING, blank=True
        ),
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="product",
        size=SIZE_L,
    )
    reference = models.CharField(
        _("Reference"), max_length=36, blank=True, default=EMPTY_STRING
    )

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("Order unit"),
    )
    average_weight = models.DecimalField(
        _("Average weight / capacity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    producer_price = ModelMoneyField(
        _("Producer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    purchase_price = ModelMoneyField(
        _("Purchase tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    customer_price = ModelMoneyField(
        _("Customer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    tax_level = models.CharField(
        max_length=3,
        choices=LUT_ALL_VAT,
        default=DICT_VAT_DEFAULT,
        verbose_name=_("Tax rate"),
    )
    wrapped = models.BooleanField(
        _("Individually wrapped by the producer"), default=False
    )
    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("Product placement"),
    )
    is_box = models.BooleanField(default=False)
    is_fixed_price = models.BooleanField(default=False)

    ###### TODO BEGIN OF OLD FIELD : TBD
    department_for_customer = models.ForeignKey(
        "LUT_DepartmentForCustomer",
        verbose_name=_("Department"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )

    picture2 = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="product",
        size=SIZE_L,
    )

    order_average_weight = models.DecimalField(
        _("Average weight / capacity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    producer_unit_price = ModelMoneyField(
        _("Producer unit price"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    customer_unit_price = ModelMoneyField(
        _("Customer unit price"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    producer_vat = ModelMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    customer_vat = ModelMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    unit_deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_ALL_VAT,
        default=DICT_VAT_DEFAULT,
        verbose_name=_("VAT rate"),
    )

    customer_minimum_order_quantity = models.DecimalField(
        _("Minimum order quantity"),
        default=DECIMAL_ONE,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    customer_increment_order_quantity = models.DecimalField(
        _("Then quantity of"),
        default=DECIMAL_ONE,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    customer_alert_order_quantity = models.DecimalField(
        _("Alert quantity"),
        default=LIMIT_ORDER_QTY_ITEM,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    producer_order_by_quantity = models.DecimalField(
        _("Producer order by quantity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    stock = models.DecimalField(
        _("Inventory"),
        default=DECIMAL_MAX_STOCK,
        max_digits=9,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    limit_order_quantity_to_stock = models.BooleanField(
        _("Limit maximum order qty of the group to stock qty"), default=False
    )

    is_active = models.BooleanField(_("Active"), default=True)
    ###### TODO END OF OLD FIELD : TBD

    @property
    def email_offer_price_with_vat(self):
        offer_price = self.get_reference_price()
        if offer_price == EMPTY_STRING:
            offer_price = self.get_unit_price()
        return offer_price

    def set_from(self, source):
        self.is_active = source.is_active
        self.picture2 = source.picture2
        self.reference = source.reference
        self.department_id = source.department_id
        self.producer_id = source.producer_id
        self.order_unit = source.order_unit
        self.wrapped = source.wrapped
        self.order_average_weight = source.order_average_weight
        self.placement = source.placement
        self.vat_level = source.vat_level
        self.customer_unit_price = source.customer_unit_price
        self.customer_vat = source.customer_vat
        self.producer_unit_price = source.producer_unit_price
        self.producer_vat = source.producer_vat
        self.unit_deposit = source.unit_deposit
        self.is_box = source.is_box

    def recalculate_prices(self, producer):
        tax_rate = (DICT_VAT[self.tax_level])[DICT_VAT_RATE]
        self.purchase_price.amount = (
            self.producer_price.amount * producer.purchase_margin
        ).quantize(TWO_DECIMALS)
        if producer.producer_tariff_is_wo_tax:
            self.purchase_price.amount = (
                self.purchase_price.amount * (DECIMAL_ONE + tax_rate)
            ).quantize(TWO_DECIMALS)
        if self.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
            self.customer_price.amount = (
                self.purchase_price.amount * producer.customer_margin
            ).quantize(TWO_DECIMALS)
        else:
            self.customer_price.amount = self.purchase_price.amount
        # self.tax_at_purchase_tariff.amount = (
        #         self.at_purchase_tariff.amount * tax_rate
        # ).quantize(FOUR_DECIMALS)
        # self.tax_at_customer_tariff.amount = (
        #         self.at_customer_tariff.amount * tax_rate
        # ).quantize(FOUR_DECIMALS)

    def get_unit_price(self, customer_price=True):
        if customer_price:
            unit_price = self.customer_unit_price
        else:
            unit_price = self.producer_unit_price
        if self.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            return "{} {}".format(unit_price, _("/ kg"))
        elif self.order_unit == PRODUCT_ORDER_UNIT_LT:
            return "{} {}".format(unit_price, _("/ l"))
        elif self.order_unit not in [
            PRODUCT_ORDER_UNIT_PC_PRICE_KG,
            PRODUCT_ORDER_UNIT_PC_PRICE_LT,
            PRODUCT_ORDER_UNIT_PC_PRICE_PC,
        ]:
            return "{} {}".format(unit_price, _("/ piece"))
        else:
            return "{}".format(unit_price)

    def get_reference_price(self, customer_price=True):
        if (
            self.order_average_weight > DECIMAL_ZERO
            and self.order_average_weight != DECIMAL_ONE
        ):
            if self.order_unit in [
                PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                PRODUCT_ORDER_UNIT_PC_PRICE_PC,
            ]:
                if customer_price:
                    reference_price = (
                        self.customer_unit_price.amount / self.order_average_weight
                    )
                else:
                    reference_price = (
                        self.producer_unit_price.amount / self.order_average_weight
                    )
                reference_price = RepanierMoney(
                    reference_price.quantize(TWO_DECIMALS), 2
                )
                if self.order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
                    reference_unit = _("/ kg")
                elif self.order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
                    reference_unit = _("/ l")
                else:
                    reference_unit = _("/ pc")
                return "{} {}".format(reference_price, reference_unit)
            else:
                return EMPTY_STRING
        else:
            return EMPTY_STRING

    def get_display(
        self,
        qty=0,
        order_unit=PRODUCT_ORDER_UNIT_PC,
        unit_price_amount=None,
        with_qty_display=True,
        with_price_display=True,
    ):
        magnitude = 1
        if qty == DECIMAL_ZERO:
            unit = EMPTY_STRING
        else:
            if order_unit == PRODUCT_ORDER_UNIT_KG:
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                elif qty < 1:
                    unit = "{}".format(_("gr"))
                    magnitude = 1000
                else:
                    unit = "{}".format(_("kg"))
            elif order_unit == PRODUCT_ORDER_UNIT_LT:
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                elif qty < 1:
                    unit = "{}".format(_("cl"))
                    magnitude = 100
                else:
                    unit = "{}".format(_("l"))
            elif order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                average_weight = self.order_average_weight
                average_weight *= qty
                if average_weight < 1:
                    average_weight_unit = _("gr")
                    average_weight *= 1000
                else:
                    average_weight_unit = _("kg")
                decimal = 3
                if average_weight == int(average_weight):
                    decimal = 0
                elif average_weight * 10 == int(average_weight * 10):
                    decimal = 1
                elif average_weight * 100 == int(average_weight * 100):
                    decimal = 2
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                else:
                    unit = "~{} {}".format(
                        number_format(average_weight, decimal),
                        average_weight_unit,
                    )
            elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
                average_weight = self.order_average_weight
                if average_weight < 1:
                    average_weight_unit = _("gr")
                    average_weight *= 1000
                else:
                    average_weight_unit = _("kg")
                decimal = 3
                if average_weight == int(average_weight):
                    decimal = 0
                elif average_weight * 10 == int(average_weight * 10):
                    decimal = 1
                elif average_weight * 100 == int(average_weight * 100):
                    decimal = 2
                if qty > DECIMAL_ZERO:
                    unit = "* {}{}".format(
                        number_format(average_weight, decimal), average_weight_unit
                    )
                else:
                    unit = EMPTY_STRING
            elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
                average_weight = self.order_average_weight
                if average_weight < 1:
                    average_weight_unit = _("cl")
                    average_weight *= 100
                else:
                    average_weight_unit = _("l")
                decimal = 3
                if average_weight == int(average_weight):
                    decimal = 0
                elif average_weight * 10 == int(average_weight * 10):
                    decimal = 1
                elif average_weight * 100 == int(average_weight * 100):
                    decimal = 2
                if qty > DECIMAL_ZERO:
                    unit = "* {}{}".format(
                        number_format(average_weight, decimal), average_weight_unit
                    )
                else:
                    unit = EMPTY_STRING
            elif order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_PC:
                average_weight = self.order_average_weight
                if average_weight > 1:
                    unit = "* {}{}".format(number_format(average_weight, 0), _("pcs"))
                else:
                    unit = EMPTY_STRING
            else:
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                elif qty < 2:
                    unit = "{}".format(_("pc"))
                else:
                    unit = "{}".format(_("pcs"))

        qty_display = qty * magnitude
        if qty_display == int(qty_display):
            decimal = 0
        elif qty_display * 10 == int(qty_display * 10):
            decimal = 1
        elif qty_display * 100 == int(qty_display * 100):
            decimal = 2
        else:
            decimal = 3

        if with_qty_display:
            if unit:
                if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                    if qty_display == DECIMAL_ZERO:
                        pcs = EMPTY_STRING
                    elif qty_display < 2:
                        pcs = "{}".format(_("pc"))
                    else:
                        pcs = "{}".format(_("pcs"))
                    unit_display = "{} ({}{})".format(
                        unit, number_format(qty_display, decimal), pcs
                    )
                else:
                    unit_display = "{} {}".format(
                        number_format(qty_display, decimal), unit
                    )
            else:
                unit_display = "{}".format(number_format(qty_display, decimal))
        else:
            if unit:
                unit_display = " ({})".format(unit)
            else:
                unit_display = EMPTY_STRING

        if not with_price_display or unit_price_amount is None:
            return unit_display
        else:
            if order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                unit_price_amount *= self.order_average_weight
            price_display = " = {}".format(RepanierMoney(unit_price_amount * qty))
            display = "{}{}".format(unit_display, price_display)
            return display

    def get_long_name_with_producer_price(self):
        return self.get_long_name(customer_price=False)

    get_long_name_with_producer_price.short_description = _("Long name")
    get_long_name_with_producer_price.admin_order_field = "translations__long_name"

    def get_qty_display(self):
        raise NotImplementedError

    def get_qty_and_price_display(self, customer_price=True):
        qty_display = self.get_qty_display()
        unit_price = self.get_unit_price(customer_price=customer_price)
        if len(qty_display) > 0:
            if self.unit_deposit.amount > DECIMAL_ZERO:
                return "{}; {} + ♻ {}".format(
                    qty_display, unit_price, self.unit_deposit
                )
            else:
                return "{}; {}".format(qty_display, unit_price)
        else:
            if self.unit_deposit.amount > DECIMAL_ZERO:
                return "; {} + ♻ {}".format(unit_price, self.unit_deposit)
            else:
                return "; {}".format(unit_price)

    def get_long_name(self, customer_price=True):
        qty_and_price_display = self.get_qty_and_price_display(customer_price)
        if qty_and_price_display:
            result = "{}{}".format(
                self.safe_translation_getter("long_name", any_language=True),
                qty_and_price_display,
            )
        else:
            result = "{}".format(
                self.safe_translation_getter("long_name", any_language=True)
            )
        return result

    get_long_name.short_description = _("Long name")
    get_long_name.admin_order_field = "translations__long_name"

    def get_long_name_with_producer(self):
        if self.id is not None:
            return "{}, {}".format(self.producer.short_name, self.get_long_name())
        else:
            # Nedeed for django import export since django_import_export-0.4.5
            return "N/A"

    get_long_name_with_producer.short_description = _("Long name")
    get_long_name_with_producer.admin_order_field = "translations__long_name"

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        abstract = True