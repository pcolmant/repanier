# -*- coding: utf-8

from django.db import models, transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from parler.models import TranslatableModel, TranslatedFields
from recurrence.fields import RecurrenceField

from repanier.const import *
from repanier.picture.const import SIZE_L
from repanier.picture.fields import RepanierPictureField
from repanier.tools import get_recurrence_dates, clean_offer_item


class Contract(TranslatableModel):
    translations = TranslatedFields(
        long_name=models.CharField(
            _("Long name"), max_length=100,
            default=EMPTY_STRING, blank=True,
        ),
    )
    first_permanence_date = models.DateField(
        verbose_name=_("Date of the first permanence"),
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
    picture2 = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="contract", size=SIZE_L)
    is_active = models.BooleanField(_("Active"), default=True)
    permanences_dates = models.TextField(
        null=True, blank=True, default=None)

    @transaction.atomic()
    def get_or_create_offer_item(self, permanence, reset_add_2_stock=False):
        from repanier.models.offeritem import OfferItem, OfferItemWoReceiver

        # In case of contract
        # -1, generate eventually several offer's items if dates are flexible
        # -2, boxes may not be used in contracts
        OfferItemWoReceiver.objects.filter(permanence_id=permanence.id).update(may_order=False)
        for contract_content in ContractContent.objects.filter(
                contract_id=self.id,
                permanences_dates__isnull=False
        ).order_by('?'):
            all_dates_str = sorted(
                list(filter(None, contract_content.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR))))
            if contract_content.flexible_dates:
                permanences_dates_order = 0
                for one_date_str in all_dates_str:
                    permanences_dates_order += 1
                    offer_item_qs = OfferItem.objects.filter(
                        permanence_id=permanence.id,
                        product_id=contract_content.product_id,
                        permanences_dates=one_date_str,
                    )
                    if not offer_item_qs.exists():
                        not_permanences_dates = (
                            contract_content.not_permanences_dates
                            if contract_content.not_permanences_dates is not None
                            else EMPTY_STRING
                        )
                        OfferItemWoReceiver.objects.create(
                            permanence_id=permanence.id,
                            product_id=contract_content.product_id,
                            producer_id=contract_content.product.producer_id,
                            contract_id=self.id,
                            permanences_dates=one_date_str,
                            not_permanences_dates=not_permanences_dates,
                            permanences_dates_counter=1,
                            permanences_dates_order=permanences_dates_order,
                        )
                        clean_offer_item(
                            permanence,
                            offer_item_qs,
                            reset_add_2_stock=reset_add_2_stock,
                        )
                    else:
                        offer_item = offer_item_qs.first()
                        offer_item.contract_id = self.id
                        offer_item.permanences_dates_order = permanences_dates_order
                        offer_item.not_permanences_dates = (
                            contract_content.not_permanences_dates
                        )
                        if reset_add_2_stock:
                            offer_item.may_order = True
                        offer_item.save(
                            update_fields=[
                                "contract",
                                "may_order",
                                "permanences_dates_order",
                                "not_permanences_dates",
                            ]
                        )
                        clean_offer_item(
                            permanence,
                            offer_item_qs,
                            reset_add_2_stock=reset_add_2_stock,
                        )
            else:
                offer_item_qs = OfferItem.objects.filter(
                    permanence_id=permanence.id,
                    product_id=contract_content.product_id,
                    permanences_dates=contract_content.permanences_dates,
                )
                if not offer_item_qs.exists():
                    OfferItemWoReceiver.objects.create(
                        permanence_id=permanence.id,
                        product_id=contract_content.product_id,
                        producer_id=contract_content.product.producer_id,
                        contract_id=self.id,
                        permanences_dates=contract_content.permanences_dates,
                        not_permanences_dates=contract_content.not_permanences_dates,
                        permanences_dates_counter=len(all_dates_str)
                    )
                    clean_offer_item(permanence, offer_item_qs, reset_add_2_stock=reset_add_2_stock)
                else:
                    offer_item = offer_item_qs.first()
                    offer_item.contract_id = self.id
                    offer_item.permanences_dates_order = 0
                    offer_item.not_permanences_dates = contract_content.not_permanences_dates
                    if reset_add_2_stock:
                        offer_item.may_order = True
                    offer_item.save(update_fields=[
                        "contract", "may_order", "permanences_dates_order", "not_permanences_dates"
                    ])
                    clean_offer_item(permanence, offer_item_qs, reset_add_2_stock=reset_add_2_stock)

    @cached_property
    def get_producers(self):
        if len(self.producers.all()) > 0:
            changelist_url = reverse(
                'admin:repanier_product_changelist',
            )
            link = []
            for p in self.producers.all():
                link.append(
                    "<a href=\"{}?producer={}&commitment={}\">&nbsp;{}&nbsp;{}</a>".format(
                        changelist_url, p.id, self.id, LINK_UNICODE, p.short_profile_name.replace(" ", "&nbsp;")))
            return mark_safe("<div class=\"wrap-text\">{}</div>".format(", ".join(link)))
        else:
            return mark_safe("<div class=\"wrap-text\">{}</div>".format(_("No offer")))

    get_producers.short_description = (_("Offers from"))

    @cached_property
    def get_dates(self):
        if self.permanences_dates:
            all_dates_str = sorted(
                list(filter(None, self.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR))))
            all_dates = []
            for one_date_str in all_dates_str:
                one_date = parse_date(one_date_str)
                all_dates.append(one_date)
            return '{} : {}'.format(
                len(all_dates),
                ", ".join(date.strftime(settings.DJANGO_SETTINGS_DAY_MONTH) for date in all_dates)
            )
        return EMPTY_STRING

    get_dates.short_description = (_("Permanences"))

    def get_contract_admin_display(self):
        return "{} ({})".format(self.safe_translation_getter('long_name', any_language=True), self.get_dates)

    get_contract_admin_display.short_description = _("Commitments")

    def __str__(self):
        return "{}".format(self.safe_translation_getter('long_name', any_language=True))

    class Meta:
        verbose_name = _("Commitment")
        verbose_name_plural = _("Commitments")


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, **kwargs):
    contract = kwargs["instance"]

    # Save old permanences date for futher adjustement of contract content dates
    old_permanences_dates = contract.permanences_dates

    # Calculate new contract dates
    new_dates = get_recurrence_dates(
        contract.first_permanence_date,
        contract.recurrences
    )
    if len(new_dates) > 0:
        contract.permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
            # Important : linked to django.utils.dateparse.parse_date format
            one_date.strftime("%Y-%m-%d") for one_date in new_dates
        )
        contract.last_permanence_date = new_dates[-1]
    else:
        contract.permanences_dates = None
        contract.last_permanence_date = None

    # Adjust contract content dates if an occurence has been removed
    if old_permanences_dates:
        old_dates_str = old_permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)
    else:
        old_dates_str = []
    if contract.permanences_dates:
        new_dates_str = contract.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)
    else:
        new_dates_str = []

    dates_to_remove_str = []
    for one_date_str in old_dates_str:
        if one_date_str not in new_dates_str:
            dates_to_remove_str.append(one_date_str)

    dates_to_add_str = []
    for one_date_str in new_dates_str:
        if one_date_str not in old_dates_str:
            dates_to_add_str.append(one_date_str)

    if len(dates_to_remove_str) > 0 or len(dates_to_add_str) > 0:
        for contract_content in ContractContent.objects.filter(
                contract=contract,
        ).order_by('?'):
            if contract_content.permanences_dates:
                all_dates_str = list(
                    filter(None, contract_content.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR)))
            else:
                all_dates_str = []
            if contract_content.not_permanences_dates:
                all_not_dates_str = list(filter(None, contract_content.not_permanences_dates.split(
                    settings.DJANGO_SETTINGS_DATES_SEPARATOR)))
            else:
                all_not_dates_str = []
            for one_dates_to_remove_str in dates_to_remove_str:
                if one_dates_to_remove_str in all_dates_str:
                    all_dates_str.remove(one_dates_to_remove_str)
                if one_dates_to_remove_str in all_not_dates_str:
                    all_not_dates_str.remove(one_dates_to_remove_str)
            for one_dates_to_add_str in dates_to_add_str:
                # if one_dates_to_add_str not in all_not_dates_str: --> should be always True
                all_not_dates_str.append(one_dates_to_add_str)
            if len(all_dates_str) > 0:
                contract_content.permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(all_dates_str)
            else:
                contract_content.permanences_dates = None
            if len(all_not_dates_str) > 0:
                contract_content.not_permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
                    all_not_dates_str)
            else:
                contract_content.not_permanences_dates = None
            contract_content.save()


class ContractContent(models.Model):
    contract = models.ForeignKey(
        'Contract', verbose_name=_("Commitment"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    product = models.ForeignKey(
        'Product', verbose_name=_("Product"), related_name='contract_content',
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanences_dates = models.TextField(
        null=True, blank=True, default=None)
    # Opposite of permaneces_date used to quickly know when this product is not into offer
    not_permanences_dates = models.TextField(
        null=True, blank=True, default=None)
    # Flexible permanences dates
    flexible_dates = models.BooleanField(default=False)

    @property
    def get_permanences_dates(self):
        if self.permanences_dates:
            all_dates_str = sorted(
                list(filter(None, self.permanences_dates.split(settings.DJANGO_SETTINGS_DATES_SEPARATOR))))
            all_days = []
            for one_date_str in all_dates_str:
                one_date = parse_date(one_date_str)
                all_days.append("{}".format(one_date.strftime(settings.DJANGO_SETTINGS_DAY_MONTH)))
            return mark_safe(", ".join(all_days))
        return EMPTY_STRING

    def __str__(self):
        return EMPTY_STRING

    class Meta:
        verbose_name = _("Commitment content")
        verbose_name_plural = _("Commitments content")
        unique_together = ("contract", "product",)
        index_together = [
            ["product", "contract"],
        ]
