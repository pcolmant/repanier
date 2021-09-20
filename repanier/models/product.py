from django.core.validators import MinValueValidator

from django.db import models, transaction
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField

from repanier.const import *
from repanier.models.item import Item


class Product(Item):
    long_name_v2 = models.CharField(
        _("Long name"), max_length=100, default=EMPTY_STRING
    )
    offer_description_v2 = HTMLField(
        _("Offer_description"), configuration="CKEDITOR_SETTINGS_MODEL2", blank=True
    )
    production_mode = models.ManyToManyField(
        "LUT_ProductionMode", verbose_name=_("Production mode"), blank=True
    )
    permanences = models.ManyToManyField("Permanence", through="OfferItem", blank=True)
    is_into_offer = models.BooleanField(_("In offer"), default=True)
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
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="likes")
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True, blank=True)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    def get_q_alert(self, quantity_invoiced=DECIMAL_ZERO):
        if self.stock > DECIMAL_ZERO:
            available = self.stock - quantity_invoiced
            if available < DECIMAL_ZERO:
                available = DECIMAL_ZERO
            q_alert = min(LIMIT_ORDER_QTY_ITEM, available)
        else:
            if self.order_unit not in [
                PRODUCT_ORDER_UNIT_PC_KG,
                PRODUCT_ORDER_UNIT_KG,
                PRODUCT_ORDER_UNIT_LT,
            ]:
                if self.order_unit == PRODUCT_ORDER_UNIT_PC:
                    q_alert = LIMIT_ORDER_QTY_ITEM
                else:
                    q_alert = (
                        self.customer_minimum_order_quantity * LIMIT_ORDER_QTY_ITEM
                    ).quantize(THREE_DECIMALS)
            else:
                q_alert = (
                    self.customer_minimum_order_quantity
                    + (
                        self.customer_increment_order_quantity
                        * (LIMIT_ORDER_QTY_ITEM - 1)
                    )
                ).quantize(THREE_DECIMALS)
        return q_alert

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence):

        from repanier.models.offeritem import OfferItem, OfferItemReadOnly

        offer_item_qs = OfferItem.objects.filter(
            permanence_id=permanence.id, product_id=self.id
        )
        if not offer_item_qs.exists():
            OfferItemReadOnly.objects.create(
                permanence_id=permanence.id,
                product_id=self.id,
                producer_id=self.producer_id,
            )

        permanence.clean_offer_item(offer_item_qs=offer_item_qs)
        offer_item = offer_item_qs.first()
        return offer_item

    def get_html_admin_is_into_offer(self):
        return mark_safe(
            '<div id="is_into_offer_{}">{}</div>'.format(
                self.id, self.get_html_is_into_offer()
            )
        )

    get_html_admin_is_into_offer.short_description = _("In offer")
    get_html_admin_is_into_offer.admin_order_field = "is_into_offer"

    def get_html_is_into_offer(self):
        from django.contrib.admin.templatetags.admin_list import _boolean_icon

        css_class = ' class = "repanier-a-info"'
        is_into_offer = self.is_into_offer
        switch_is_into_offer = reverse("repanier:is_into_offer", args=(self.id,))
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
            LINK=switch_is_into_offer, PRODUCT_ID=self.id
        )
        # return false; http://stackoverflow.com/questions/1601933/how-do-i-stop-a-web-page-from-scrolling-to-the-top-when-a-link-is-clicked-that-t
        link = '<div id="is_into_offer_{}"><a href="#" onclick="{};return false;"{}>{}</a></div>'.format(
            self.id, javascript, css_class, _boolean_icon(is_into_offer)
        )
        return mark_safe(link)

    def get_qty_display(self):
        qty_display = self.get_display(
            qty=1,
            order_unit=self.order_unit,
            with_qty_display=False,
            with_price_display=False,
        )
        return qty_display

    def __str__(self):
        return super().get_long_name_with_customer_price()

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        unique_together = (("producer", "reference"),)
