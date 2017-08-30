# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields
from recurrence.fields import RecurrenceField

from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.product import Product
from repanier.const import *


@python_2_unicode_compatible
class Contract(TranslatableModel):
    translations = TranslatedFields(
        short_name=models.CharField(_("offer name"),
                                    max_length=50,
                                    blank=False, default=EMPTY_STRING),
        offer_description=HTMLField(_("offer_description"),
                                    configuration='CKEDITOR_SETTINGS_MODEL2',
                                    help_text=_(
                                        "This message is send by mail to all customers when opening the order or on top "),
                                    blank=True, default=EMPTY_STRING),
    )
    first_permanence_date = models.DateField(
        verbose_name=_("first permanence date"),
        db_index=True
    )
    recurrences = RecurrenceField()
    producers = models.ManyToManyField(
        'Producer',
        verbose_name=_("producers"),
        blank=True
    )
    customers = models.ManyToManyField(
        'Customer',
        verbose_name=_("customers"),
        blank=True
    )
    status = models.CharField(
        max_length=3,
        choices=LUT_CONTRACT_STATUS,
        default=CONTRACT_IN_WRITING,
        verbose_name=_("contract status"))
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_CONTRACT_STATUS,
        default=CONTRACT_IN_WRITING,
        verbose_name=_("highest contract status"))

    def get_full_status_display(self):
        return self.get_status_display()

    get_full_status_display.short_description = (_("contract status"))
    get_full_status_display.allow_tags = True

    def __str__(self):
        return '%s' % self.long_name

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")


@python_2_unicode_compatible
class ContractContent(models.Model):
    contract = models.ForeignKey(
        'Contract', verbose_name=_("contract"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("product"), related_name='contract_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    content_quantity = models.DecimalField(
        _("fixed content quantity"),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    may_order_more = models.BooleanField(_("may order more"), default=False)
    calculated_customer_content_price = ModelMoneyField(
        _("customer content price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    calculated_content_deposit = ModelMoneyField(
        _("content deposit"),
        help_text=_('deposit to add to the original content price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_calculated_customer_content_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.calculated_customer_content_price + self.calculated_content_deposit

    get_calculated_customer_content_price.short_description = (_("customer content price"))
    get_calculated_customer_content_price.allow_tags = False

    class Meta:
        verbose_name = _("contract content")
        verbose_name_plural = _("contracts content")
        unique_together = ("contract", "product",)
        index_together = [
            ["product", "contract"],
        ]

    def __str__(self):
        return EMPTY_STRING


@receiver(pre_save, sender=ContractContent)
def contract_content_pre_save(sender, **kwargs):
    contract_content = kwargs["instance"]
    product_id = contract_content.product_id
    if product_id is not None:
        product = Product.objects.filter(id=product_id).order_by('?').only(
            'customer_unit_price',
            'unit_deposit'
        ).first()
        if product is not None:
            contract_content.calculated_customer_content_price.amount = contract_content.content_quantity * product.customer_unit_price.amount
            contract_content.calculated_content_deposit.amount = int(contract_content.content_quantity) * product.unit_deposit.amount

