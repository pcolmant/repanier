from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField

from repanier_v2.const import *
from repanier_v2.fields.RepanierMoneyField import ModelMoneyField
from repanier_v2.picture.const import SIZE_L
from repanier_v2.picture.fields import RepanierPictureField
from repanier_v2.tools import clean_offer_item


class LiveItem(models.Model):
    name = models.CharField(_("Long name"), default=EMPTY_STRING, max_length=100)
    description = HTMLField(
        _("Description"), configuration="CKEDITOR_SETTINGS_MODEL2", blank=True
    )
    label = models.ManyToManyField("Label", verbose_name=_("Label"), blank=True)
    order = models.ManyToManyField("Order", through="FrozenItem", blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    can_be_ordered = models.BooleanField(_("In offer"), default=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL) # , related_name="likes")
    is_updated_on = models.DateTimeField(_("Updated on"), auto_now=True, blank=True)
    min_order_qty = models.DecimalField(
        _("Minimum order qty"),
        default=DECIMAL_ONE,
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    inc_order_qty = models.DecimalField(
        _("Then qty of"),
        default=DECIMAL_ONE,
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    max_order_qty = models.DecimalField(
        _("Qty on sales"),
        default=DECIMAL_MAX_STOCK,
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    producer = models.ForeignKey(
        "Producer", verbose_name=_("Producer"), on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        "Department",
        related_name="+",
        verbose_name=_("Department"),
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )
    caption = (
        models.CharField(
            _("Caption"), max_length=100, default=EMPTY_STRING, blank=True
        ),
    )
    picture = RepanierPictureField(
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
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("Order unit"),
    )
    average_weight = models.DecimalField(
        _("Average weight / capacity"),
        default=DECIMAL_ZERO,
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    producer_price = ModelMoneyField(
        _("Producer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    purchase_price = ModelMoneyField(
        _("Purchase tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    customer_price = ModelMoneyField(
        _("Customer tariff"), default=DECIMAL_ZERO, max_digits=7, decimal_places=2
    )
    deposit = ModelMoneyField(
        _("Deposit"),
        help_text=_("Deposit to add to the original unit price"),
        default=DECIMAL_ZERO,
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    tax_level = models.CharField(
        max_length=3,
        choices=LUT_ALL_VAT,
        default=DICT_VAT_DEFAULT,
        verbose_name=_("Tax rate"),
    )
    wrapped = models.BooleanField(
        _("Individually wrapped by the producer"), default=False
    )
    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("Product placement"),
    )
    is_box = models.BooleanField(default=False)
    is_fixed_price = models.BooleanField(default=False)

    @property
    def total_likes(self):
        """
        Likes for the product
        :return: Integer: Likes for the product
        """
        return self.likes.count()

    def get_customer_alert_order_quantity(self):
        q_alert = (
            self.customer_minimum_order_quantity
            + self.customer_increment_order_quantity * (LIMIT_ORDER_QTY_ITEM - 1)
        )
        q_available = self.max_sale_qty
        if q_available < DECIMAL_ZERO:
            # Thi should never occurs, but...
            q_available = DECIMAL_ZERO
        q_alert = min(q_alert, q_available)
        return q_alert

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence):

        from repanier_v2.models.offeritem import OfferItem, OfferItemWoReceiver
        from repanier_v2.models.box import BoxContent

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

        css_class = ' class = "repanier_v2-a-info"'
        is_into_offer = self.is_for_sale
        switch_is_into_offer = reverse("repanier_v2:is_into_offer", args=(self.id,))
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
            qty_display = BOX_UNICODE
        else:
            qty_display = self.get_display(
                qty=1,
                order_unit=self.order_unit,
                with_qty_display=False,
                with_price_display=False,
            )
        return qty_display

    def __str__(self):
        return super().get_long_name_with_producer()

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        db_table = "repanier_live_item"
        unique_together = (("producer", "reference"),)
