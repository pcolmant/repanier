# -*- coding: utf-8
from __future__ import unicode_literals

import copy

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save, post_init
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.formats import number_format
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields

import invoice
from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.picture.const import SIZE_M
from repanier.picture.fields import AjaxPictureField
from repanier.tools import get_display


@python_2_unicode_compatible
class OfferItem(TranslatableModel):
    translations = TranslatedFields(
        long_name=models.CharField(_("long_name"), max_length=100,
                                   default=EMPTY_STRING, blank=True, null=True),
        cache_part_a=HTMLField(configuration='CKEDITOR_SETTINGS_MODEL2', default=EMPTY_STRING, blank=True),
        cache_part_b=HTMLField(configuration='CKEDITOR_SETTINGS_MODEL2', default=EMPTY_STRING, blank=True),
        cache_part_e=HTMLField(configuration='CKEDITOR_SETTINGS_MODEL2', default=EMPTY_STRING, blank=True),
        order_sort_order=models.IntegerField(
            _("customer sort order for optimization"),
            default=0, db_index=True),
        preparation_sort_order=models.IntegerField(
            _("preparation sort order for optimization"),
            default=0, db_index=True),
        producer_sort_order=models.IntegerField(
            _("producer sort order for optimization"),
            default=0, db_index=True)
    )
    permanence = models.ForeignKey(
        'Permanence', verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT,
        db_index=True
    )
    # Important : Check select_related
    product = models.ForeignKey(
        'Product', verbose_name=_("product"), null=True, blank=True, default=None, on_delete=models.PROTECT)
    picture2 = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="product", size=SIZE_M)

    reference = models.CharField(
        _("reference"), max_length=36, blank=True, null=True)
    department_for_customer = models.ForeignKey(
        'LUT_DepartmentForCustomer',
        verbose_name=_("department_for_customer"), blank=True, null=True, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        'Producer', verbose_name=_("producer"), on_delete=models.PROTECT)

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("order unit"))
    wrapped = models.BooleanField(_('Individually wrapped by the producer'),
                                  default=False)
    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("product_placement"),
        help_text=_('used for helping to determine the order of preparation of this product'))

    producer_unit_price = ModelMoneyField(
        _("producer unit price"),
        help_text=_('producer unit price (/piece or /kg or /l), including vat, without deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    customer_unit_price = ModelMoneyField(
        _("customer unit price"),
        help_text=_('(/piece or /kg or /l), including vat, without deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    producer_price_are_wo_vat = models.BooleanField(_("producer price are wo vat"), default=False)
    producer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    customer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    unit_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add to the unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    vat_level = models.CharField(
        max_length=3,
        choices=settings.LUT_VAT,
        default=settings.DICT_VAT_DEFAULT,
        verbose_name=_("tax"))

    # Calculated with Purchase
    total_purchase_with_tax = ModelMoneyField(
        _("producer amount invoiced"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase
    total_selling_with_tax = ModelMoneyField(
        _("customer amount invoiced"),
        help_text=_('Total selling amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    # Calculated with Purchase.
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via tools.recalculate_order_amount(..., send_to_producer=True)
    quantity_invoiced = models.DecimalField(
        _("quantity invoiced"),
        help_text=_('quantity invoiced to our customer'),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)

    is_box = models.BooleanField(_("is_box"), default=False)
    is_box_content = models.BooleanField(_("is_box_content"), default=False)
    is_membership_fee = models.BooleanField(_("is_membership_fee"), default=False)
    may_order = models.BooleanField(_("may_order"), default=True)
    is_active = models.BooleanField(_("is_active"), default=True)
    limit_order_quantity_to_stock = models.BooleanField(_("limit maximum order qty of the group to stock qty"),
                                                        default=False)
    manage_replenishment = models.BooleanField(_("manage stock"), default=False)
    manage_production = models.BooleanField(_("manage production"), default=False)
    producer_pre_opening = models.BooleanField(_("producer pre-opening"), default=False)

    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=4,
        validators=[MinValueValidator(0)])
    is_resale_price_fixed = models.BooleanField(_("the resale price is set by the producer"),
                                                default=False)

    stock = models.DecimalField(
        _("Current stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=3,
        validators=[MinValueValidator(0)])
    add_2_stock = models.DecimalField(
        _("Add 2 stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    new_stock = models.DecimalField(
        _("Final stock"),
        default=None, max_digits=9, decimal_places=3, null=True)

    customer_minimum_order_quantity = models.DecimalField(
        _("customer_minimum_order_quantity"),
        help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_increment_order_quantity = models.DecimalField(
        _("customer_increment_order_quantity"),
        help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50max 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    producer_order_by_quantity = models.DecimalField(
        _("Producer order by quantity"),
        help_text=_('1,5 Kg [i.e. 1500 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)

    def get_producer(self):
        return self.producer.short_profile_name

    get_producer.short_description = (_("producers"))
    get_producer.allow_tags = False

    def get_product(self):
        return self.product.long_name

    get_product.short_description = (_("products"))
    get_product.allow_tags = False

    def get_vat_level(self):
        return self.get_vat_level_display()

    get_vat_level.short_description = EMPTY_STRING
    get_vat_level.allow_tags = False
    get_vat_level.admin_order_field = 'vat_level'

    def get_producer_qty_stock_invoiced(self):
        # Return quantity to buy to the producer and stock used to deliver the invoiced quantity
        if self.quantity_invoiced > DECIMAL_ZERO:
            if self.manage_replenishment:
                # if RepanierSettings.producer_pre_opening then the stock is the max available qty by the producer,
                # not into our stock
                quantity_for_customer = self.quantity_invoiced - self.add_2_stock
                if self.stock == DECIMAL_ZERO:
                    return self.quantity_invoiced, DECIMAL_ZERO, quantity_for_customer
                else:
                    delta = (quantity_for_customer - self.stock).quantize(FOUR_DECIMALS)
                    if delta <= DECIMAL_ZERO:
                        # i.e. quantity_for_customer <= self.stock
                        return self.add_2_stock, quantity_for_customer, quantity_for_customer
                    else:
                        return delta + self.add_2_stock, self.stock, quantity_for_customer
            else:
                return self.quantity_invoiced, DECIMAL_ZERO, self.quantity_invoiced
        return DECIMAL_ZERO, DECIMAL_ZERO, DECIMAL_ZERO

    def get_html_producer_qty_stock_invoiced(self):
        invoiced_qty, taken_from_stock, customer_qty = self.get_producer_qty_stock_invoiced()
        if invoiced_qty == DECIMAL_ZERO:
            if taken_from_stock == DECIMAL_ZERO:
                return EMPTY_STRING
            else:
                return _("stock %(stock)s") % {'stock': number_format(taken_from_stock, 4)}
        else:
            if taken_from_stock == DECIMAL_ZERO:
                return _("<b>%(qty)s</b>") % {'qty': number_format(invoiced_qty, 4)}
            else:
                return _("<b>%(qty)s</b> + stock %(stock)s") % {'qty'  : number_format(invoiced_qty, 4),
                                                                'stock': number_format(taken_from_stock, 4)}

    get_html_producer_qty_stock_invoiced.short_description = (_("quantity invoiced by the producer"))
    get_html_producer_qty_stock_invoiced.allow_tags = True
    get_html_producer_qty_stock_invoiced.admin_order_field = 'quantity_invoiced'

    def get_producer_qty_invoiced(self):
        invoiced_qty, taken_from_stock, customer_qty = self.get_producer_qty_stock_invoiced()
        return invoiced_qty

    def get_producer_unit_price_invoiced(self):
        if self.producer_unit_price.amount > self.customer_unit_price.amount:
            return self.customer_unit_price
        else:
            return self.producer_unit_price

    def get_producer_row_price_invoiced(self):
        if self.manage_replenishment:
            if self.producer_unit_price.amount > self.customer_unit_price.amount:
                return RepanierMoney((self.customer_unit_price.amount + self.unit_deposit.amount) * self.get_producer_qty_invoiced(), 2)
            else:
                return RepanierMoney((self.producer_unit_price.amount + self.unit_deposit.amount) * self.get_producer_qty_invoiced(), 2)
        else:
            if self.producer_unit_price.amount > self.customer_unit_price.amount:
                return self.total_selling_with_tax
            else:
                return self.total_purchase_with_tax

    def get_html_producer_price_purchased(self):
        if self.manage_replenishment:
            invoiced_qty, taken_from_stock, customer_qty = self.get_producer_qty_stock_invoiced()
            price = RepanierMoney(
                ((self.producer_unit_price.amount + self.unit_deposit.amount) * invoiced_qty).quantize(TWO_DECIMALS))
        else:
            price = self.total_purchase_with_tax
        # price = self.total_purchase_with_tax
        if price != DECIMAL_ZERO:
            return _("<b>%(price)s</b>") % {'price': price}
        return EMPTY_STRING

    get_html_producer_price_purchased.short_description = (_("producer amount invoiced"))
    get_html_producer_price_purchased.allow_tags = True
    get_html_producer_price_purchased.admin_order_field = 'total_purchase_with_tax'

    @property
    def producer_unit_price_wo_tax(self):
        if self.producer_price_are_wo_vat:
            return self.producer_unit_price
        else:
            return self.producer_unit_price - self.producer_vat

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

    @property
    def email_offer_price_with_vat(self):
        offer_price = self.get_reference_price()
        if offer_price == EMPTY_STRING:
            offer_price = self.get_unit_price()
        return offer_price

    def get_like(self, user):
        return '<span class="glyphicon glyphicon-heart%s" onclick="like_ajax(%d);return false;"></span>' % (
            EMPTY_STRING if self.product.likes.filter(id=user.id).only("id").exists() else "-empty", self.id)

    def get_order_name(self, is_quantity_invoiced=False, box_unicode=BOX_UNICODE):
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
        return '%s %s' % (self.long_name, qty_display)

    def get_long_name_with_producer_price(self):
        return self.get_long_name(customer_price=False)
    get_long_name_with_producer_price.short_description = (_("long_name"))
    get_long_name_with_producer_price.allow_tags = False
    get_long_name_with_producer_price.admin_order_field = 'translations__long_name'

    def get_long_name(self, is_quantity_invoiced=False, customer_price=True, box_unicode=BOX_UNICODE):
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
        unit_price = self.get_unit_price(customer_price=customer_price)
        if self.unit_deposit.amount > DECIMAL_ZERO:
            return '%s %s, %s + ♻ %s' % (self.long_name, qty_display, unit_price, self.unit_deposit)
        else:
            return '%s %s, %s' % (self.long_name, qty_display, unit_price)

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'translations__long_name'

    def __str__(self):
        return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())

    class Meta:
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")
        unique_together = ("permanence", "product",)
        index_together = [
            # ["permanence", "product"],
            ["id", "order_unit"]
        ]


@receiver(post_init, sender=OfferItem)
def offer_item_post_init(sender, **kwargs):
    offer_item = kwargs["instance"]
    if offer_item.id is None:
        offer_item.previous_add_2_stock = DECIMAL_ZERO
        offer_item.previous_producer_unit_price = DECIMAL_ZERO
        offer_item.previous_unit_deposit = DECIMAL_ZERO
    else:
        offer_item.previous_add_2_stock = offer_item.add_2_stock
        offer_item.previous_producer_unit_price = offer_item.producer_unit_price.amount
        offer_item.previous_unit_deposit = offer_item.unit_deposit.amount


@receiver(pre_save, sender=OfferItem)
def offer_item_pre_save(sender, **kwargs):
    offer_item = kwargs["instance"]
    if offer_item.manage_replenishment:
        if (offer_item.previous_add_2_stock != offer_item.add_2_stock or
            offer_item.previous_producer_unit_price != offer_item.producer_unit_price.amount or
            offer_item.previous_unit_deposit != offer_item.unit_deposit.amount
        ):
            previous_producer_price = ((offer_item.previous_producer_unit_price +
                                        offer_item.previous_unit_deposit) * offer_item.previous_add_2_stock)
            producer_price = ((offer_item.producer_unit_price.amount +
                               offer_item.unit_deposit.amount) * offer_item.add_2_stock)
            delta_add_2_stock_invoiced = offer_item.add_2_stock - offer_item.previous_add_2_stock
            delta_producer_price = producer_price - previous_producer_price
            invoice.ProducerInvoice.objects.filter(
                producer_id=offer_item.producer_id,
                permanence_id=offer_item.permanence_id
            ).update(
                total_price_with_tax=F('total_price_with_tax') +
                                     delta_producer_price
            )
            offer_item.quantity_invoiced += delta_add_2_stock_invoiced
            offer_item.total_purchase_with_tax.amount += delta_producer_price
            # Do not do it twice
            offer_item.previous_add_2_stock = offer_item.add_2_stock
            offer_item.previous_producer_unit_price = offer_item.producer_unit_price.amount
            offer_item.previous_unit_deposit = offer_item.unit_deposit.amount


@python_2_unicode_compatible
class OfferItemSend(OfferItem):
    def __str__(self):
        return '%s, %s' % (self.producer.short_profile_name, self.get_long_name(is_quantity_invoiced=True))

    class Meta:
        proxy = True
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")


@receiver(post_init, sender=OfferItemSend)
def offer_item_send_post_init(sender, **kwargs):
    offer_item_post_init(sender, **kwargs)


@receiver(pre_save, sender=OfferItemSend)
def offer_item_send_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)


@python_2_unicode_compatible
class OfferItemClosed(OfferItem):
    def __str__(self):
        return '%s, %s' % (self.producer.short_profile_name, self.get_long_name(is_quantity_invoiced=True))

    class Meta:
        proxy = True
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")


@receiver(post_init, sender=OfferItemClosed)
def offer_item_closed_post_init(sender, **kwargs):
    offer_item_post_init(sender, **kwargs)


@receiver(pre_save, sender=OfferItemClosed)
def offer_item_closed_pre_save(sender, **kwargs):
    offer_item_pre_save(sender, **kwargs)
