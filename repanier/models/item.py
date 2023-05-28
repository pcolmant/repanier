from django.core.validators import MinValueValidator
from django.db import models
from django.utils.formats import number_format
from django.utils.translation import gettext_lazy as _

from repanier.const import (
    DECIMAL_ZERO,
    EMPTY_STRING,
    DECIMAL_ONE,
    DICT_ALL_VAT,
    RoundUpTo,
    Placement,
    OrderUnit,
    Vat,
    VAT_DEFAULT,
)
from repanier.fields.RepanierMoneyField import RepanierMoney, ModelRepanierMoneyField
from repanier.picture.const import SIZE_L
from repanier.picture.fields import RepanierPictureField


class Item(models.Model):
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
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
    reference = models.CharField(
        _("Reference"), max_length=36, blank=True, default=EMPTY_STRING
    )

    order_unit = models.CharField(
        max_length=3,
        choices=OrderUnit.choices,
        default=OrderUnit.PC,
        verbose_name=_("Order unit"),
    )
    order_average_weight = models.DecimalField(
        _("Average weight / capacity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    producer_unit_price = ModelRepanierMoneyField(
        _("Producer unit price"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    customer_unit_price = ModelRepanierMoneyField(
        _("Customer unit price"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    producer_vat = ModelRepanierMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    customer_vat = ModelRepanierMoneyField(
        _("VAT"), default=DECIMAL_ZERO, max_digits=8, decimal_places=4
    )
    unit_deposit = ModelRepanierMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    vat_level = models.CharField(
        max_length=3,
        choices=Vat.choices,
        default=VAT_DEFAULT,
        verbose_name=_("VAT rate"),
    )

    wrapped = models.BooleanField(
        _("Individually wrapped by the producer"), default=False
    )
    placement = models.CharField(
        max_length=3,
        choices=Placement.choices,
        default=Placement.BASKET,
        verbose_name=_("Product placement"),
    )

    stock = models.DecimalField(
        _("Maximum quantity"),
        help_text=_("0 mean : do not limit the quantity on sale."),
        default=DECIMAL_ZERO,
        max_digits=9,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    is_box = models.BooleanField(default=False)
    is_active = models.BooleanField(_("Active"), default=True)

    def set_from(self, source):
        self.is_active = source.is_active
        self.picture2 = source.picture2
        self.reference = source.reference
        self.department_for_customer_id = source.department_for_customer_id
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
        self.stock = source.stock

    def recalculate_prices(self):
        vat_rate = DICT_ALL_VAT[self.vat_level]
        producer = self.producer
        if producer.producer_price_are_wo_vat:
            self.producer_vat.amount = (
                self.producer_unit_price.amount * vat_rate
            ).quantize(RoundUpTo.FOUR_DECIMALS)
            if self.order_unit < OrderUnit.DEPOSIT:
                self.customer_unit_price.amount = (
                    self.producer_unit_price.amount * producer.price_list_multiplier
                ).quantize(RoundUpTo.TWO_DECIMALS)
            else:
                self.customer_unit_price = self.producer_unit_price
            self.customer_vat.amount = (
                self.customer_unit_price.amount * vat_rate
            ).quantize(RoundUpTo.FOUR_DECIMALS)
            self.customer_unit_price += self.customer_vat
        else:
            self.producer_vat.amount = self.producer_unit_price.amount - (
                self.producer_unit_price.amount / (DECIMAL_ONE + vat_rate)
            ).quantize(RoundUpTo.FOUR_DECIMALS)
            if self.order_unit < OrderUnit.DEPOSIT:
                self.customer_unit_price.amount = (
                    self.producer_unit_price.amount * producer.price_list_multiplier
                ).quantize(RoundUpTo.TWO_DECIMALS)
            else:
                self.customer_unit_price = self.producer_unit_price
            self.customer_vat.amount = self.customer_unit_price.amount - (
                self.customer_unit_price.amount / (DECIMAL_ONE + vat_rate)
            ).quantize(RoundUpTo.FOUR_DECIMALS)

    def get_unit_price(self, customer_price=True):
        if customer_price:
            unit_price = self.customer_unit_price
        else:
            unit_price = self.producer_unit_price
        if self.order_unit in [OrderUnit.KG, OrderUnit.PC_KG]:
            return "{} {}".format(unit_price, _("/ kg"))
        elif self.order_unit == OrderUnit.LT:
            return "{} {}".format(unit_price, _("/ l"))
        elif self.order_unit not in [
            OrderUnit.PC_PRICE_KG,
            OrderUnit.PC_PRICE_LT,
            OrderUnit.PC_PRICE_PC,
        ]:
            return "{} {}".format(unit_price, _("/ piece"))
        else:
            return "{}".format(unit_price)

    def get_display(
        self,
        qty=0,
        order_unit=OrderUnit.PC,
        unit_price_amount=None,
        with_qty_display=True,
        with_price_display=True,
    ):
        magnitude = 1
        if qty == DECIMAL_ZERO:
            unit = EMPTY_STRING
        else:
            if order_unit == OrderUnit.KG:
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                elif qty < 1:
                    unit = "{}".format(_("gr"))
                    magnitude = 1000
                else:
                    unit = "{}".format(_("kg"))
            elif order_unit == OrderUnit.LT:
                if qty == DECIMAL_ZERO:
                    unit = EMPTY_STRING
                elif qty < 1:
                    unit = "{}".format(_("cl"))
                    magnitude = 100
                else:
                    unit = "{}".format(_("l"))
            elif order_unit == OrderUnit.PC_KG:
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
            elif order_unit == OrderUnit.PC_PRICE_KG:
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
            elif order_unit == OrderUnit.PC_PRICE_LT:
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
            elif order_unit == OrderUnit.PC_PRICE_PC:
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
                if order_unit == OrderUnit.PC_KG:
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
            if order_unit == OrderUnit.PC_KG:
                unit_price_amount *= self.order_average_weight
            price_display = " = {}".format(RepanierMoney(unit_price_amount * qty))
            display = "{}{}".format(unit_display, price_display)
            return display

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

    def get_long_name(self, customer_price=False, producer_price=False):
        if customer_price or producer_price:
            qty_and_price_display = self.get_qty_and_price_display(customer_price)
            if qty_and_price_display:
                result = "{}{}".format(self.long_name_v2, qty_and_price_display)
            else:
                result = "{}".format(self.long_name_v2)
        else:
            result = "{}".format(self.long_name_v2)
        return result

    get_long_name.short_description = _("Long name")
    get_long_name.admin_order_field = "long_name_v2"

    def get_long_name_with_customer_price(self):
        if self.id is not None:
            return self.get_long_name(customer_price=True)
        else:
            # Needed for django import export since django_import_export-0.4.5
            return "N/A"

    get_long_name_with_customer_price.short_description = _("Customer tariff")
    get_long_name_with_customer_price.admin_order_field = "long_name_v2"

    def get_long_name_with_producer_price(self):
        if self.id is not None:
            return self.get_long_name(producer_price=True)
        else:
            # Needed for django import export since django_import_export-0.4.5
            return "N/A"

    get_long_name_with_producer_price.short_description = _("Producer tariff")
    get_long_name_with_producer_price.admin_order_field = "long_name_v2"

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        abstract = True
