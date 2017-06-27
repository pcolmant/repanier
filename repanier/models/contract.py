# -*- coding: utf-8
from __future__ import unicode_literals

from recurrence.fields import RecurrenceField
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.producer import Producer
from repanier.models.product import Product, product_pre_save


@python_2_unicode_compatible
class Contract(Product):
    recurrences = RecurrenceField()

    def get_calculated_stock(self):
        # stock : max_digits=9, decimal_places=3 => 1000000 > max(stock)
        stock = DECIMAL_MAX_STOCK
        for contract_content in ContractContent.objects.filter(
                contract_id=self.id,
                product__limit_order_quantity_to_stock=True,
                content_quantity__gt=DECIMAL_ZERO,
                product__is_contract=False  # Disallow recursivity
        ).prefetch_related(
            "product"
        ).only(
            "content_quantity", "product__stock", "product__limit_order_quantity_to_stock"
        ).order_by('?'):
            stock = min(stock, contract_content.product.stock // contract_content.content_quantity)
        return stock

    def get_calculated_price(self):
        result_set = ContractContent.objects.filter(contract_id=self.id).aggregate(
            Sum('calculated_customer_content_price'),
            Sum('calculated_content_deposit')
        )
        contract_price = result_set["calculated_customer_content_price__sum"] \
            if result_set["calculated_customer_content_price__sum"] is not None else DECIMAL_ZERO
        contract_deposit = result_set["calculated_content_deposit__sum"] \
            if result_set["calculated_content_deposit__sum"] is not None else DECIMAL_ZERO

        return contract_price, contract_deposit

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")

    def __str__(self):
        return '%s' % self.long_name


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, **kwargs):
    contract = kwargs["instance"]
    contract.is_contract = True
    contract.producer_id = Producer.objects.filter(
        represent_this_buyinggroup=True
    ).order_by('?').only('id').first().id
    contract.order_unit = PRODUCT_ORDER_UNIT_PC
    contract.producer_unit_price = contract.customer_unit_price
    contract.producer_vat = contract.customer_vat
    contract.limit_order_quantity_to_stock = True
    # ! Important to initialise all fields of the contract. Remember : a contract is a product.
    product_pre_save(sender, **kwargs)


@python_2_unicode_compatible
class ContractContent(models.Model):
    contract = models.ForeignKey(
        'Contract', verbose_name=_("contract"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("product"), related_name='contract_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    content_quantity = models.DecimalField(
        _("content quantity"),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
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
