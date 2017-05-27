# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save, post_init
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.formats import number_format
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatedFields

import invoice
from repanier.models.item import Item
from repanier.apps import REPANIER_SETTINGS_PERMANENCE_NAME
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney


@python_2_unicode_compatible
class OfferItem(Item):
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
        'Permanence',
        verbose_name=REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT,
        db_index=True
    )
    product = models.ForeignKey(
        'Product',
        verbose_name=_("product"),
        on_delete=models.PROTECT)

    producer_price_are_wo_vat = models.BooleanField(_("producer price are wo vat"), default=False)
    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=4,
        validators=[MinValueValidator(0)])
    is_resale_price_fixed = models.BooleanField(
        _("the resale price is set by the producer"),
        default=False)

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

    may_order = models.BooleanField(_("may_order"), default=True)

    manage_replenishment = models.BooleanField(_("manage stock"), default=False)
    manage_production = models.BooleanField(_("manage production"), default=False)
    producer_pre_opening = models.BooleanField(_("producer pre-opening"), default=False)

    add_2_stock = models.DecimalField(
        _("Add 2 stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    new_stock = models.DecimalField(
        _("Final stock"),
        default=None, max_digits=9, decimal_places=3, null=True)

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

    def get_like(self, user):
        return '<span class="glyphicon glyphicon-heart%s" onclick="like_ajax(%d);return false;"></span>' % (
            EMPTY_STRING if self.product.likes.filter(id=user.id).only("id").exists() else "-empty", self.id)

    def __str__(self):
        return super(OfferItem, self).display()
        # return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())

    class Meta:
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")
        unique_together = ("permanence", "product",)
        index_together = [
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
    offer_item.recalculate_prices(offer_item.producer_price_are_wo_vat, offer_item.is_resale_price_fixed,
                                  offer_item.price_list_multiplier)
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
class OfferItemWoReceiver(OfferItem):
    def __str__(self):
        return EMPTY_STRING

    class Meta:
        proxy = True
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")


@python_2_unicode_compatible
class OfferItemSend(OfferItem):
    def __str__(self):
        return self.display(is_quantity_invoiced=True)

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
        return self.display(is_quantity_invoiced=True)

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
