# -*- coding: utf-8
from __future__ import unicode_literals

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.fields import TranslatedField
from parler.models import TranslatableModel
from parler.models import TranslatedFieldsModel

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.picture.const import SIZE_M
from repanier.picture.fields import AjaxPictureField
from repanier.tools import get_display, recalculate_prices


@python_2_unicode_compatible
class Product(TranslatableModel):
    producer = models.ForeignKey(
        'Producer', verbose_name=_("producer"), on_delete=models.PROTECT)
    long_name = TranslatedField()
    offer_description = TranslatedField()
    production_mode = models.ManyToManyField(
        'LUT_ProductionMode',
        verbose_name=_("production mode"),
        blank=True)
    picture2 = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="product", size=SIZE_M)

    reference = models.CharField(
        _("reference"), max_length=36, blank=True, null=True)

    department_for_customer = models.ForeignKey(
        'LUT_DepartmentForCustomer', null=True, blank=True,
        verbose_name=_("department_for_customer"),
        on_delete=models.PROTECT)

    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("product_placement"),
        help_text=_('used for helping to determine the order of preparation of this product'))

    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])

    producer_unit_price = ModelMoneyField(
        _("producer unit price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    customer_unit_price = ModelMoneyField(
        _("customer unit price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    producer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    customer_vat = ModelMoneyField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    unit_deposit = ModelMoneyField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)])

    vat_level = models.CharField(
        max_length=3,
        choices=settings.LUT_VAT,
        default=settings.DICT_VAT_DEFAULT,
        verbose_name=_("tax"))
    stock = models.DecimalField(
        _("Current stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=3,
        validators=[MinValueValidator(0)])
    limit_order_quantity_to_stock = models.BooleanField(_("limit maximum order qty of the group to stock qty"),
                                                        default=False)

    customer_minimum_order_quantity = models.DecimalField(
        _("customer_minimum_order_quantity"),
        help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ONE, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    customer_increment_order_quantity = models.DecimalField(
        _("customer_increment_order_quantity"),
        help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50max 1 piece, 3 Kg)'),
        default=DECIMAL_ONE, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=LIMIT_ORDER_QTY_ITEM, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    producer_order_by_quantity = models.DecimalField(
        _("Producer order by quantity"),
        help_text=_('1,5 Kg [i.e. 1500 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])

    permanences = models.ManyToManyField(
        'Permanence', through='OfferItem',
        blank=True)
    is_into_offer = models.BooleanField(_("is_into_offer"), default=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='likes')

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("order unit"),
    )
    wrapped = models.BooleanField(_('Individually wrapped by the producer'),
                                  default=False)

    is_box = models.BooleanField(_("is_box"), default=False)
    # is_mandatory = models.BooleanField(_("is_mandatory"), default=False)
    is_membership_fee = models.BooleanField(_("is_membership_fee"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, blank=True)
    external_id_producer = models.BigIntegerField(null=True, blank=True, default=None)
    external_id_product = models.BigIntegerField(null=True, blank=True, default=None)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    def get_customer_alert_order_quantity(self):
        if self.limit_order_quantity_to_stock:
            return "%s" % _("Current stock")
        return self.customer_alert_order_quantity

    get_customer_alert_order_quantity.short_description = (_("customer_alert_order_quantity"))
    get_customer_alert_order_quantity.allow_tags = False

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

    @property
    def unit_price_with_vat(self, customer_price=True):
        return self.get_unit_price(customer_price=customer_price)

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
    def reference_price_with_vat(self):
        return self.get_reference_price()

    @property
    def email_offer_price_with_vat(self):
        offer_price = self.get_reference_price()
        if offer_price == EMPTY_STRING:
            offer_price = self.get_unit_price()
        return offer_price

    def get_long_name(self, box_unicode=BOX_UNICODE, customer_price=True):
        if self.id:
            if self.is_box:
                # To avoid unicode error when print
                qty_display = box_unicode
            else:
                qty_display = get_display(
                    qty=1,
                    order_average_weight=self.order_average_weight,
                    order_unit=self.order_unit,
                    for_customer=False,
                    without_price_display=True
                )
            unit_price = self.get_unit_price(customer_price=customer_price)
            unit_deposit = self.unit_deposit
            if len(qty_display) > 0:
                if unit_deposit.amount > DECIMAL_ZERO:
                    return '%s %s, %s ♻ %s' % (self.long_name, qty_display, unit_price, unit_deposit)
                else:
                    return '%s %s, %s' % (self.long_name, qty_display, unit_price)
            else:
                if unit_deposit.amount > DECIMAL_ZERO:
                    return '%s, %s ♻ %s' % (self.long_name, unit_price, unit_deposit)
                else:
                    return '%s, %s' % (self.long_name, unit_price)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = True
    get_long_name.admin_order_field = 'translations__long_name'

    def __str__(self):
        if self.id is not None:
            return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())
        else:
            # Nedeed for django import export since django_import_export-0.4.5
            return 'N/A'

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        # ordering = ("producer", "long_name",)
        unique_together = ("producer", "reference",)
        # index_together = [
        #     ["producer", "reference"],
        # ]


@receiver(pre_save, sender=Product)
def product_pre_save(sender, **kwargs):
    getcontext().rounding = ROUND_HALF_UP
    product = kwargs["instance"]
    producer = product.producer
    if not product.is_active:
        product.is_into_offer = False
    if product.order_unit not in [PRODUCT_ORDER_UNIT_PC, PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                                  PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        product.unit_deposit = DECIMAL_ZERO
    if product.order_unit == PRODUCT_ORDER_UNIT_PC:
        product.order_average_weight = 1
    elif product.order_unit not in [PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                                    PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        product.order_average_weight = DECIMAL_ZERO
    if product.order_unit in [PRODUCT_ORDER_UNIT_DEPOSIT, PRODUCT_ORDER_UNIT_SUBSCRIPTION]:
        # No VAT on those products
        product.vat_level = VAT_100

    recalculate_prices(product, producer.producer_price_are_wo_vat, producer.is_resale_price_fixed,
                       producer.price_list_multiplier)

    if producer.producer_pre_opening or producer.manage_production:
        product.producer_order_by_quantity = DECIMAL_ZERO
        product.limit_order_quantity_to_stock = True
        if not product.is_box:
            # IMPORTANT : Deactivate offeritem whose stock is not > 0
            product.is_into_offer = product.stock > DECIMAL_ZERO
    elif not producer.manage_replenishment:
        product.limit_order_quantity_to_stock = False
    if product.is_box:
        product.limit_order_quantity_to_stock = False
    if product.limit_order_quantity_to_stock:
        product.customer_alert_order_quantity = min(999, product.stock)

    if product.customer_increment_order_quantity <= DECIMAL_ZERO:
        product.customer_increment_order_quantity = DECIMAL_ONE
    if product.customer_minimum_order_quantity <= DECIMAL_ZERO:
        product.customer_minimum_order_quantity = product.customer_increment_order_quantity
    if product.order_average_weight <= DECIMAL_ZERO:
        product.order_average_weight = DECIMAL_ONE
    if not product.reference:
        product.reference = uuid.uuid4()
    # Update stock of boxes containing this product
    for box_content in product.box_content.all():
        if box_content.box is not None:
            box_content.box.save_update_stock()


@receiver(post_save, sender=Product)
def product_post_save(sender, **kwargs):
    product = kwargs["instance"]
    from repanier.models.box import BoxContent
    BoxContent.objects.filter(product_id=product.id).update(
        calculated_customer_content_price=F('content_quantity') * product.customer_unit_price.amount,
        calculated_content_deposit=F('content_quantity') * product.unit_deposit.amount,
    )


class Product_Translation(TranslatedFieldsModel):
    master = models.ForeignKey('Product', related_name='translations', null=True)
    long_name = models.CharField(_("long_name"), max_length=100)
    offer_description = HTMLField(_("offer_description"), blank=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _("Product translation")

