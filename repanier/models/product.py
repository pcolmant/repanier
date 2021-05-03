from django.db import models, transaction
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.fields import TranslatedField
from parler.models import TranslatedFieldsModel

from repanier.const import *
from repanier.models.item import Item
from repanier.tools import clean_offer_item


class Product(Item):
    long_name = TranslatedField()
    offer_description = TranslatedField()
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
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="likes")
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True, blank=True)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence):

        from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
        from repanier.models.box import BoxContent

        offer_item_qs = OfferItem.objects.filter(
            permanence_id=permanence.id, product_id=self.id
        ).order_by("?")
        if not offer_item_qs.exists():
            OfferItemWoReceiver.objects.create(
                permanence_id=permanence.id,
                product_id=self.id,
                producer_id=self.producer_id,
            )
        clean_offer_item(permanence, offer_item_qs)
        if self.is_box:
            # Add box products
            for box_content in BoxContent.objects.filter(box=self.id).order_by("?"):
                box_offer_item_qs = OfferItem.objects.filter(
                    permanence_id=permanence.id, product_id=box_content.product_id
                ).order_by("?")
                if not box_offer_item_qs.exists():
                    OfferItemWoReceiver.objects.create(
                        permanence_id=permanence.id,
                        product_id=box_content.product_id,
                        producer_id=box_content.product.producer_id,
                        is_box_content=True,
                    )
                else:
                    box_offer_item = box_offer_item_qs.first()
                    box_offer_item.is_box_content = True
                    box_offer_item.save(update_fields=["is_box_content"])
                clean_offer_item(permanence, box_offer_item_qs)

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
        if self.is_box:
            # To avoid unicode error in email_offer.send_open_order
            qty_display = EMPTY_STRING # BOX_UNICODE
        else:
            qty_display = self.get_display(
                qty=1,
                order_unit=self.order_unit,
                with_qty_display=False,
                with_price_display=False,
            )
        return qty_display

    def __str__(self):
        return super(Product, self).get_long_name_with_producer()

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        unique_together = (("producer", "reference"),)


class Product_Translation(TranslatedFieldsModel):
    master = models.ForeignKey(
        "Product", related_name="translations", null=True, on_delete=models.CASCADE
    )
    long_name = models.CharField(_("Long name"), max_length=100)
    offer_description = HTMLField(
        _("Offer_description"), configuration="CKEDITOR_SETTINGS_MODEL2", blank=True
    )

    class Meta:
        unique_together = ("language_code", "master")
