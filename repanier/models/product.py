# -*- coding: utf-8
from __future__ import unicode_literals

import uuid

from django.conf import settings
from django.core import urlresolvers
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.fields import TranslatedField
from parler.models import TranslatedFieldsModel

from repanier.const import *
from repanier.models.contract import ContractContent
from repanier.models.item import Item
from repanier.tools import clean_offer_item


@python_2_unicode_compatible
class Product(Item):
    long_name = TranslatedField()
    offer_description = TranslatedField()
    production_mode = models.ManyToManyField(
        'LUT_ProductionMode',
        verbose_name=_("production mode"),
        blank=True)
    permanences = models.ManyToManyField(
        'Permanence',
        through='OfferItem',
        blank=True)
    contracts = models.ManyToManyField(
        'Contract',
        through='ContractContent',
        blank=True)
    is_into_offer = models.BooleanField(_("is_into_offer"), default=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='likes')
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, blank=True)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence):
        from repanier.models.offeritem import OfferItem

        offer_item_qs = OfferItem.objects.filter(
            permanence_id=permanence.id,
            product_id=self.id,
        ).order_by('?')
        if not offer_item_qs.exists():
            OfferItem.objects.create(
                permanence=permanence,
                product_id=self.id,
                producer=self.producer,
            )
            clean_offer_item(permanence, offer_item_qs)
        offer_item = offer_item_qs.first()
        return offer_item

    def get_is_into_offer(self, contract=None):
        return mark_safe('<div id="is_into_offer_%d">{}</div>'.format(
            self.get_is_into_offer_html(contract)
        ))

    get_is_into_offer.short_description = (_("is into offer"))

    def get_is_into_offer_html(self, contract=None, contract_content=None):
        from django.contrib.admin.templatetags.admin_list import _boolean_icon
        css_class = ' class = "btn"'
        if contract is not None or contract_content is not None:
            css_class = EMPTY_STRING
            if contract_content is None:
                contract_content = ContractContent.objects.filter(
                    product=self,
                    contract=contract
                ).order_by('?').first()
            if contract_content is not None:
                all_dates = contract_content.all_dates
                is_into_offer = len(all_dates) > 0
            else:
                all_dates = []
                is_into_offer = False

            contract_icons = []
            month_save = None
            print(all_dates)
            for one_date in contract.all_dates:
                if month_save != one_date.month:
                    month_save = one_date.month
                    if month_save is not None:
                        new_line = "<br/>"
                    else:
                        new_line = EMPTY_STRING
                else:
                    new_line = EMPTY_STRING
                # Important : linked to django.utils.dateparse.parse_date format
                one_date_str = one_date.strftime("%Y-%m-%d")
                switch_is_into_offer = urlresolvers.reverse(
                    'is_into_offer_content',
                    args=(self.id, contract.id, one_date_str)
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
                color = "green" if one_date in all_dates else "red"
                link = '%s<a href="#" onclick="%s;return false;" style="color:%s !important;">%s</a>' % (
                    new_line,
                    javascript,
                    color,
                    one_date.strftime(settings.DJANGO_SETTINGS_DAY)
                )
                contract_icons.append(
                    link
                )
            contract_icon = ",&nbsp;".join(contract_icons)
        else:
            is_into_offer = self.is_into_offer
            contract_icon = EMPTY_STRING
        switch_is_into_offer = urlresolvers.reverse(
            'is_into_offer', args=(self.id, contract.id if contract is not None else 0)
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
        link = '<div id="is_into_offer_%d"><a href="#" onclick="%s;return false;"%s>%s</a>%s</div>' % (
            self.id,
            javascript,
            css_class,
            _boolean_icon(is_into_offer),
            contract_icon
        )
        return link


    def __str__(self):
        return super(Product, self).get_long_name_with_producer()

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

    product.recalculate_prices(
        producer.producer_price_are_wo_vat,
        producer.is_resale_price_fixed,
        producer.price_list_multiplier
    )

    if producer.producer_pre_opening or producer.represent_this_buyinggroup:
        product.producer_order_by_quantity = DECIMAL_ZERO
        product.limit_order_quantity_to_stock = True
        # IMPORTANT : Deactivate offeritem whose stock is not > 0 and product is into offer
        product.is_into_offer = product.stock > DECIMAL_ZERO
    elif not producer.manage_replenishment:
        product.limit_order_quantity_to_stock = False
    if product.is_box:
        product.limit_order_quantity_to_stock = True
    if product.limit_order_quantity_to_stock:
        product.customer_alert_order_quantity = min(999, product.stock)
    elif settings.DJANGO_SETTINGS_IS_MINIMALIST:
        product.customer_alert_order_quantity = LIMIT_ORDER_QTY_ITEM
    if product.customer_increment_order_quantity <= DECIMAL_ZERO:
        product.customer_increment_order_quantity = DECIMAL_ONE
    if product.customer_minimum_order_quantity <= DECIMAL_ZERO:
        product.customer_minimum_order_quantity = product.customer_increment_order_quantity
    if product.order_average_weight <= DECIMAL_ZERO:
        product.order_average_weight = DECIMAL_ONE
    if not product.reference:
        product.reference = uuid.uuid1()
    # Update stock of boxes containing this product
    # for box_content in product.box_content.all():
    #     if box_content.box is not None:
    #         box_content.box.save_update_stock()


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

