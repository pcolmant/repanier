# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.core import urlresolvers
from django.db import models
from django.db.models.signals import pre_save, post_init, post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields
from recurrence.fields import RecurrenceField

from repanier.const import *
from repanier.models import product
from repanier.picture.const import SIZE_L
from repanier.picture.fields import AjaxPictureField
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
    last_permanence_date = models.DateField(
        verbose_name=_("Last permanence date"),
        null=True, blank=True,
        db_index=True
    )
    recurrences = RecurrenceField()
    producers = models.ManyToManyField(
        'Producer',
        verbose_name=_("Producers"),
        related_name='contracts',
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
    all_dates = []
    dates_display = EMPTY_STRING

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
                        '<a href="%s?producer=%d&commitment=%d">&nbsp;%s</a>' % (
                            changelist_url, p.id, self.id, p.short_profile_name.replace(" ", "&nbsp;")))
                return mark_safe('<div class="wrap-text">%s</div>' % ", ".join(link))
            else:
                return mark_safe('<div class="wrap-text">%s</div>' % _("No offer"))
        else:
            return mark_safe('<div class="wrap-text">%s</div>' % ", ".join([p.short_profile_name.replace(" ", "&nbsp;")
                                   for p in self.producers.all()]))

    get_producers.short_description = (_("Offers from"))

    @cached_property
    def get_dates(self):
        return self.dates_display

    get_dates.short_description = (_("Permanences"))
    get_dates.allow_tags = True

    def get_full_status_display(self):
        return self.get_status_display()

    get_full_status_display.short_description = (_("Contract status"))
    get_full_status_display.allow_tags = True

    def get_contract_admin_display(self):
        return "%s (%s)" % (self.long_name, self.dates_display)

    get_contract_admin_display.short_description = _("Commitments")
    get_contract_admin_display.allow_tags = False

    def __str__(self):
        return '%s' % self.long_name

    class Meta:
        verbose_name = _("Commitment")
        verbose_name_plural = _("Commitments")


@receiver(post_init, sender=Contract)
def contract_post_init(sender, **kwargs):
    contract = kwargs["instance"]
    if contract.id is not None:
        contract.all_dates, contract.dates_display = get_recurrence_dates(
            contract.first_permanence_date,
            contract.recurrences
        )


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, **kwargs):
    contract = kwargs["instance"]
    if contract.all_dates:
        # Adjust contract content if an occurence has been removed
        new_dates, _ = get_recurrence_dates(
            contract.first_permanence_date,
            contract.recurrences
        )
        if len(new_dates) > 0:
            contract.last_permanence_date = new_dates[-1]
        else:
            contract.last_permanence_date = None
        dates_to_remove = []
        for one_date in contract.all_dates:
            if one_date not in new_dates:
                dates_to_remove.append(one_date)
        if dates_to_remove:
            for contract_content in ContractContent.objects.filter(
                contract=contract
            ).exclude(
                permanences_dates=EMPTY_STRING
            ).order_by('?'):
                updated = False
                for one_date in contract_content.all_dates:
                    if one_date in dates_to_remove:
                        contract_content.all_dates.remove(one_date)
                        updated = True
                if updated:
                    contract_content.save()


@python_2_unicode_compatible
class ContractContent(models.Model):
    contract = models.ForeignKey(
        'Contract', verbose_name=_("contract"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("product"), related_name='contract_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanences_dates = models.TextField(
        _("Deliveries dates"), null=True, blank=True, default=EMPTY_STRING)
    all_dates = []

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        verbose_name = _("Commitment content")
        verbose_name_plural = _("Commitments content")
        unique_together = ("contract", "product",)
        index_together = [
            ["product", "contract"],
        ]


@receiver(post_init, sender=ContractContent)
def contract_content_post_init(sender, **kwargs):
    contract_content = kwargs["instance"]
    contract_content.all_dates = []
    if contract_content.id is not None and contract_content.permanences_dates:
        # Splitting an empty string with a specified separator returns ['']
        all_dates_str = contract_content.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)
        for one_date_str in all_dates_str:
            one_date = parse_date(one_date_str)
            contract_content.all_dates.append(one_date)


@receiver(pre_save, sender=ContractContent)
def contract_content_pre_save(sender, **kwargs):
    contract_content = kwargs["instance"]
    if contract_content.all_dates:
        contract_content.permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
            # Important : linked to django.utils.dateparse.parse_date format
            one_date.strftime("%Y-%m-%d") for one_date in contract_content.all_dates
        )
    else:
        contract_content.permanences_dates = EMPTY_STRING

