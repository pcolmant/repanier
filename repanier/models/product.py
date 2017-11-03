# -*- coding: utf-8

import uuid

from django.conf import settings
from django.core import urlresolvers
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.fields import TranslatedField
from parler.models import TranslatedFieldsModel

from repanier.const import *
from repanier.models.contract import ContractContent
from repanier.models.item import Item
from repanier.tools import clean_offer_item


class Product(Item):
    long_name = TranslatedField()
    offer_description = TranslatedField()
    production_mode = models.ManyToManyField(
        'LUT_ProductionMode',
        verbose_name=_("Production mode"),
        blank=True)
    permanences = models.ManyToManyField(
        'Permanence',
        through='OfferItem',
        blank=True)
    contracts = models.ManyToManyField(
        'Contract',
        through='ContractContent',
        blank=True)
    is_into_offer = models.BooleanField(_("In offer"), default=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='likes')
    is_updated_on = models.DateTimeField(
        _("Updated on"), auto_now=True, blank=True)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence, reset_add_2_stock=False):

        from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
        from repanier.models.box import BoxContent

        offer_item_qs = OfferItem.objects.filter(
            permanence_id=permanence.id,
            product_id=self.id,
            permanences_dates=EMPTY_STRING
        ).order_by('?')
        if not offer_item_qs.exists():
            OfferItemWoReceiver.objects.create(
                permanence_id=permanence.id,
                product_id=self.id,
                producer_id=self.producer_id,
                permanences_dates=EMPTY_STRING
            )
            clean_offer_item(permanence, offer_item_qs, reset_add_2_stock=reset_add_2_stock)
        else:
            offer_item = offer_item_qs.first()
            offer_item.contract = None
            offer_item.permanences_dates_order = 0
            if reset_add_2_stock:
                offer_item.may_order = True
            offer_item.save(update_fields=["contract", "may_order", "permanences_dates_order"])
        if self.is_box:
            # Add box products
            for box_content in BoxContent.objects.filter(
                box=self.id
            ).order_by('?'):
                box_offer_item_qs = OfferItem.objects.filter(
                    permanence_id=permanence.id,
                    product_id=box_content.product_id,
                    permanences_dates=EMPTY_STRING
                ).order_by('?')
                if not box_offer_item_qs.exists():
                    OfferItemWoReceiver.objects.create(
                        permanence_id=permanence.id,
                        product_id=box_content.product_id,
                        producer_id=box_content.product.producer_id,
                        permanences_dates=EMPTY_STRING,
                        is_box_content=True
                    )
                    clean_offer_item(permanence, box_offer_item_qs, reset_add_2_stock=reset_add_2_stock)
                else:
                    box_offer_item = box_offer_item_qs.first()
                    box_offer_item.is_box_content = True
                    box_offer_item.contract = None
                    box_offer_item.permanences_dates_order = 0
                    if reset_add_2_stock:
                        box_offer_item.may_order = True
                    box_offer_item.save(update_fields=["is_box_content", "contract", "may_order", "permanences_dates_order"])

        offer_item = offer_item_qs.first()
        return offer_item

    def get_is_into_offer(self, contract=None):
        return mark_safe("<div id=\"is_into_offer_{}\">{}</div>".format(
            self.id,
            self.get_is_into_offer_html(contract)
        ))

    get_is_into_offer.short_description = (_("In offer"))

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
            if contract_content is not None and contract_content.permanences_dates is not None:
                all_dates_str = sorted(list(filter(None, contract_content.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR))))
                is_into_offer = len(all_dates_str) > 0
                flexible_dates = contract_content.flexible_dates
            else:
                all_dates_str = []
                is_into_offer = False
                flexible_dates = False

            contract_all_dates_str = sorted(list(filter(None, contract.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR))))
            contract_dates_array = []
            month_save = None
            selected_dates_counter = 0
            # print(all_dates_str)
            for one_date_str in contract_all_dates_str:
                one_date = parse_date(one_date_str)
                if month_save != one_date.month:
                    month_save = one_date.month
                    new_line = "<br/>"
                else:
                    new_line = EMPTY_STRING
                # Important : linked to django.utils.dateparse.parse_date format
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
                if one_date_str in all_dates_str:
                    color = "green"
                    icon = " {}".format(_boolean_icon(True))
                    selected_dates_counter += 1
                else:
                    color = "red"
                    icon = " {}".format(_boolean_icon(False))
                link = """
                        {}<a href="#" onclick="{};return false;" style="color:{} !important;">{}{}</a>
                    """.format(
                        new_line,
                        javascript,
                        color,
                        icon,
                        one_date.strftime(settings.DJANGO_SETTINGS_DAY_MONTH)
                    )
                contract_dates_array.append(
                    link
                )
            contract_dates = ",&nbsp;".join(contract_dates_array)
            if selected_dates_counter > 1:
                switch_flexible_dates = urlresolvers.reverse(
                    'flexible_dates',
                    args=(self.id, contract.id)
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
                    LINK=switch_flexible_dates,
                    PRODUCT_ID=self.id
                )
                if flexible_dates:
                    color = EMPTY_STRING
                    flexible_dates_display = " {}".format(_("Flexible dates"))
                else:
                    color = EMPTY_STRING
                    flexible_dates_display = " {} {}".format(selected_dates_counter, _("fixed dates"))
                flexible_dates_link = """
                        <a href="#" onclick="{};return false;" style="color:{} !important;">{}</a>
                    """.format(
                        javascript,
                        color,
                        flexible_dates_display,
                    )
            else:
                flexible_dates_link = EMPTY_STRING
        else:
            is_into_offer = self.is_into_offer
            contract_dates = EMPTY_STRING
            flexible_dates_link = EMPTY_STRING
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
        link = "<div id=\"is_into_offer_{}\"><a href=\"#\" onclick=\"{};return false;\"{}>{}</a>{}{}</div>".format(
            self.id,
            javascript,
            css_class,
            _boolean_icon(is_into_offer),
            flexible_dates_link,
            contract_dates
        )
        return link

    def get_qty_display(self):
        if self.is_box:
            # To avoid unicode error in email_offer.send_open_order
            qty_display = BOX_UNICODE
        else:
            qty_display = self.get_display(
                qty=1,
                order_unit=self.order_unit,
                for_customer=False,
                without_price_display=True
            )
        return qty_display

    def __str__(self):
        return super(Product, self).get_long_name_with_producer()

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
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
    long_name = models.CharField(_("Long name"), max_length=100)
    offer_description = HTMLField(_("Offer_description"), configuration='CKEDITOR_SETTINGS_MODEL2', blank=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _("Product translation")

