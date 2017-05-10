# -*- coding: utf-8
from __future__ import unicode_literals

from decimal import ROUND_HALF_UP, getcontext

from parler.models import TranslatableModel
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from repanier.const import BOX_UNICODE, DECIMAL_ZERO, PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_KG, EMPTY_STRING, \
    DECIMAL_ONE, PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC, \
    TWO_DECIMALS, PRODUCT_ORDER_UNIT_LT, DICT_VAT, DICT_VAT_RATE, FOUR_DECIMALS, PRODUCT_ORDER_UNIT_DEPOSIT
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.tools import get_display


@python_2_unicode_compatible
class Item(TranslatableModel):
    @property
    def producer_unit_price_wo_tax(self):
        if self.producer_price_are_wo_vat:
            return self.producer_unit_price
        else:
            return self.producer_unit_price - self.producer_vat

    @property
    def email_offer_price_with_vat(self):
        offer_price = self.get_reference_price()
        if offer_price == EMPTY_STRING:
            offer_price = self.get_unit_price()
        return offer_price

    def recalculate_prices(self, producer_price_are_wo_vat, is_resale_price_fixed, price_list_multiplier):
        getcontext().rounding = ROUND_HALF_UP
        vat = DICT_VAT[self.vat_level]
        vat_rate = vat[DICT_VAT_RATE]
        if producer_price_are_wo_vat:
            self.producer_vat.amount = (self.producer_unit_price.amount * vat_rate).quantize(FOUR_DECIMALS)
            if not is_resale_price_fixed:
                if self.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                    self.customer_unit_price.amount = (
                        self.producer_unit_price.amount * price_list_multiplier).quantize(
                        TWO_DECIMALS)
                else:
                    self.customer_unit_price = self.producer_unit_price
            self.customer_vat.amount = (self.customer_unit_price.amount * vat_rate).quantize(FOUR_DECIMALS)
            if not is_resale_price_fixed:
                self.customer_unit_price += self.customer_vat
        else:
            self.producer_vat.amount = self.producer_unit_price.amount - (
                self.producer_unit_price.amount / (DECIMAL_ONE + vat_rate)).quantize(
                FOUR_DECIMALS)
            if not is_resale_price_fixed:
                if self.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                    self.customer_unit_price.amount = (
                        self.producer_unit_price.amount * price_list_multiplier).quantize(
                        TWO_DECIMALS)
                else:
                    self.customer_unit_price = self.producer_unit_price

            self.customer_vat.amount = self.customer_unit_price.amount - (
                self.customer_unit_price.amount / (DECIMAL_ONE + vat_rate)).quantize(
                FOUR_DECIMALS)

    def get_unit_price(self, customer_price=True):
        if customer_price:
            unit_price = self.customer_unit_price
        else:
            unit_price = self.producer_unit_price
        if self.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            return "%s %s" % (unit_price, _("/ kg"))
        elif self.order_unit == PRODUCT_ORDER_UNIT_LT:
            return "%s %s" % (unit_price, _("/ l"))
        elif self.order_unit not in [PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                                     PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
            return "%s %s" % (unit_price, _("/ piece"))
        else:
            return "%s" % (unit_price,)

    def get_reference_price(self, customer_price=True):
        if self.order_average_weight > DECIMAL_ZERO and self.order_average_weight != DECIMAL_ONE:
            if self.order_unit in [PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT,
                                   PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
                if customer_price:
                    reference_price = self.customer_unit_price.amount / self.order_average_weight
                else:
                    reference_price = self.producer_unit_price.amount / self.order_average_weight
                reference_price = RepanierMoney(reference_price.quantize(TWO_DECIMALS), 2)
                if self.order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_KG:
                    reference_unit = _("/ kg")
                elif self.order_unit == PRODUCT_ORDER_UNIT_PC_PRICE_LT:
                    reference_unit = _("/ l")
                else:
                    reference_unit = _("/ pc")
                return "%s %s" % (reference_price, reference_unit)
            else:
                return EMPTY_STRING
        else:
            return EMPTY_STRING

    def get_qty_display(self, is_quantity_invoiced=False, box_unicode=BOX_UNICODE):
        if self.is_box:
            # To avoid unicode error in email_offer.send_open_order
            qty_display = box_unicode
        else:
            if is_quantity_invoiced and self.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                qty_display = get_display(
                    qty=1,
                    order_average_weight=self.order_average_weight,
                    order_unit=PRODUCT_ORDER_UNIT_KG,
                    for_customer=False,
                    without_price_display=True
                )
            else:
                qty_display = get_display(
                    qty=1,
                    order_average_weight=self.order_average_weight,
                    order_unit=self.order_unit,
                    for_customer=False,
                    without_price_display=True
                )
        return qty_display

    def get_qty_and_price_display(self, is_quantity_invoiced=False, customer_price=True, box_unicode=BOX_UNICODE):
        qty_display = self.get_qty_display(is_quantity_invoiced, box_unicode)
        unit_price = self.get_unit_price(customer_price=customer_price)
        if len(qty_display) > 0:
            if self.unit_deposit.amount > DECIMAL_ZERO:
                return '%s; %s + ♻ %s' % (
                    qty_display, unit_price, self.unit_deposit)
            else:
                return '%s; %s' % (qty_display, unit_price)
        else:
            if self.unit_deposit.amount > DECIMAL_ZERO:
                return '%s + ♻ %s' % (
                    unit_price, self.unit_deposit)
            else:
                return '%s' % unit_price

    def get_order_name(self, is_quantity_invoiced=False, box_unicode=BOX_UNICODE):

        qty_display = self.get_qty_display(is_quantity_invoiced, box_unicode)
        if qty_display:
            return '%s %s' % (self.long_name, qty_display)
        return '%s' % self.long_name

    def get_long_name_with_producer_price(self):
        return self.get_long_name(customer_price=False)
    get_long_name_with_producer_price.short_description = (_("long_name"))
    get_long_name_with_producer_price.allow_tags = False
    get_long_name_with_producer_price.admin_order_field = 'translations__long_name'

    def get_long_name(self, is_quantity_invoiced=False, customer_price=True, box_unicode=BOX_UNICODE):

        qty_and_price_display = self.get_qty_and_price_display(is_quantity_invoiced, customer_price, box_unicode)
        if qty_and_price_display:
            result = '%s %s' % (self.long_name, qty_and_price_display)
        else:
            result = '%s' % self.long_name
        if self.is_box_content:
            return "%s %s" % (result, BOX_UNICODE)
        else:
            return result

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'translations__long_name'

    def display(self):
        if self.id is not None:
            return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())
        else:
            # Nedeed for django import export since django_import_export-0.4.5
            return 'N/A'

    def __str__(self):
        return self.display()


    class Meta:
        abstract = True