# -*- coding: utf-8
from __future__ import unicode_literals

import uuid

from django.conf import settings
from django.core import urlresolvers
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.fields import TranslatedField
from parler.models import TranslatedFieldsModel

from repanier.models.item import Item
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.picture.const import SIZE_M
from repanier.picture.fields import AjaxPictureField


@python_2_unicode_compatible
class Product(Item):
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
        choices=LUT_ALL_VAT, # settings.LUT_VAT,
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
    is_box_content = models.BooleanField(_("is_box_content"), default=False)
    # is_mandatory = models.BooleanField(_("is_mandatory"), default=False)
    # is_membership_fee = models.BooleanField(_("is_membership_fee"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, blank=True)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    def get_is_into_offer(self):
        from django.contrib.admin.templatetags.admin_list import _boolean_icon
        if self.limit_order_quantity_to_stock:
            link = _boolean_icon(self.is_into_offer)
        else:
            switch_is_into_offer = urlresolvers.reverse(
                'is_into_offer', args=(self.id,)
            )
            javascript = """
            (function($) {{
                var lien = '{LINK}';
                $.ajax({{
                        url: lien,
                        cache: false,
                        async: true,
                        success: function (result) {{
                            $('#is_into_offer_{PRODUCT_ID}').html(result)
                        }}
                    }});
            }})(django.jQuery);
            """.format(
                LINK=switch_is_into_offer,
                PRODUCT_ID=self.id
            )
            # return false; http://stackoverflow.com/questions/1601933/how-do-i-stop-a-web-page-from-scrolling-to-the-top-when-a-link-is-clicked-that-t
            link = '<a id="is_into_offer_%d" href="#" onclick="%s;return false;" class="btn">%s</a>' % (
                self.id,
                javascript,
                _boolean_icon(self.is_into_offer)
            )
        return link

    get_is_into_offer.short_description = (_("is into offer"))
    get_is_into_offer.allow_tags = True

    def get_customer_alert_order_quantity(self):
        if self.limit_order_quantity_to_stock:
            return "%s" % _("Current stock")
        return self.customer_alert_order_quantity

    get_customer_alert_order_quantity.short_description = (_("customer_alert_order_quantity"))
    get_customer_alert_order_quantity.allow_tags = False

    def __str__(self):
        return super(Product, self).display()
        # if self.id is not None:
        #     return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())
        # else:
        #     # Nedeed for django import export since django_import_export-0.4.5
        #     return 'N/A'

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        unique_together = ("producer", "reference",)


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
    if product.order_unit in [
        PRODUCT_ORDER_UNIT_DEPOSIT,
        PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
        PRODUCT_ORDER_UNIT_SUBSCRIPTION
    ]:
        # No VAT on those products
        product.vat_level = VAT_100

    product.recalculate_prices(producer.producer_price_are_wo_vat, producer.is_resale_price_fixed,
                       producer.price_list_multiplier)

    if producer.producer_pre_opening or producer.manage_production:
        product.producer_order_by_quantity = DECIMAL_ZERO
        product.limit_order_quantity_to_stock = True
        if not product.is_box:
            # IMPORTANT : Deactivate offeritem whose stock is not > 0 and product is into offer
            product.is_into_offer = product.stock > DECIMAL_ZERO
    elif not producer.manage_replenishment:
        product.limit_order_quantity_to_stock = False
    if product.is_box:
        product.limit_order_quantity_to_stock = False
    if product.limit_order_quantity_to_stock:
        product.customer_alert_order_quantity = min(999, product.stock)
    elif product.order_unit == PRODUCT_ORDER_UNIT_SUBSCRIPTION:
        product.customer_alert_order_quantity = LIMIT_ORDER_QTY_ITEM
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
    offer_description = HTMLField(_("offer_description"), configuration='CKEDITOR_SETTINGS_MODEL2', blank=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _("Product translation")

