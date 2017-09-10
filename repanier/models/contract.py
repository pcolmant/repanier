# -*- coding: utf-8
from __future__ import unicode_literals

from django.core import urlresolvers
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields
from recurrence.fields import RecurrenceField

from repanier.picture.const import SIZE_L
from repanier.picture.fields import AjaxPictureField
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.product import Product
from repanier.const import *
from repanier.tools import get_recurrence_dates


@python_2_unicode_compatible
class Contract(TranslatableModel):
    translations = TranslatedFields(
        long_name=models.CharField(
            _("Long name"), max_length=100,
            default=EMPTY_STRING, blank=True, null=True
        ),
        offer_description=HTMLField(
            _("Offer description"),
            configuration='CKEDITOR_SETTINGS_MODEL2',
            help_text=_(
                "This message is send by mail to all customers when opening the order or on top "),
            blank=True, default=EMPTY_STRING
        ),
    )
    first_permanence_date = models.DateField(
        verbose_name=_("First permanence date"),
        db_index=True
    )
    recurrences = RecurrenceField()
    producers = models.ManyToManyField(
        'Producer',
        verbose_name=_("Producers"),
        blank=True
    )
    customers = models.ManyToManyField(
        'Customer',
        verbose_name=_("Customers"),
        blank=True
    )
    picture2 = AjaxPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="contract", size=SIZE_L)
    status = models.CharField(
        max_length=3,
        choices=LUT_CONTRACT_STATUS,
        default=CONTRACT_IN_WRITING,
        verbose_name=_("status"))
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_CONTRACT_STATUS,
        default=CONTRACT_IN_WRITING,
        verbose_name=_("Highest status"))
    dates = []
    dates_counter = 0

    @cached_property
    def get_producers(self):
        if self.status == CONTRACT_IN_WRITING:
            if len(self.producers.all()) > 0:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_product_changelist',
                )
                link = []
                for p in self.producers.all():
                    link.append(
                        '<a href="%s?producer=%d">&nbsp;%s</a>' % (
                            changelist_url, p.id, p.short_profile_name))
                return mark_safe('<div class="wrap-text">%s</div>' % ", ".join(link))
            else:
                return mark_safe('<div class="wrap-text">%s</div>' % _("No offer"))
        else:
            return mark_safe('<div class="wrap-text">%s</div>' % ", ".join([p.short_profile_name
                                   for p in self.producers.all()]))

    get_producers.short_description = (_("Offers from"))
    # get_producers.allow_tags = True

    @cached_property
    def get_dates(self):
        self.dates, self.dates_counter, display = get_recurrence_dates(self.first_permanence_date, self.recurrences)
        return display

    get_dates.short_description = (_("Permanences"))
    get_dates.allow_tags = True

    def get_full_status_display(self):
        return self.get_status_display()

    get_full_status_display.short_description = (_("Contract status"))
    get_full_status_display.allow_tags = True

    def get_contract_admin_display(self):
        return self.long_name

    get_contract_admin_display.short_description = _("Commitments")
    get_contract_admin_display.allow_tags = False

    def __str__(self):
        return '%s' % self.long_name

    class Meta:
        verbose_name = _("Commitment")
        verbose_name_plural = _("Commitments")


@python_2_unicode_compatible
class ContractContent(models.Model):
    contract = models.ForeignKey(
        'Contract', verbose_name=_("contract"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("product"), related_name='contract_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    content_quantity = models.DecimalField(
        _("Fixed content quantity"),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0)])
    may_order_more = models.BooleanField(_("may order more"), default=False)
    calculated_customer_content_price = ModelMoneyField(
        _("Customer content price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    calculated_content_deposit = ModelMoneyField(
        _("Content deposit"),
        help_text=_('deposit to add to the original content price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_calculated_customer_content_price(self):
        # workaround for a display problem with Money field in the admin list_display
        return self.calculated_customer_content_price + self.calculated_content_deposit

    get_calculated_customer_content_price.short_description = (_("customer content price"))
    get_calculated_customer_content_price.allow_tags = False

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        verbose_name = _("Commitment content")
        verbose_name_plural = _("Commitments content")
        unique_together = ("contract", "product",)
        index_together = [
            ["product", "contract"],
        ]


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

