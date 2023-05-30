import datetime

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, DecimalField, F
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from repanier.const import (
    EMPTY_STRING,
    DECIMAL_ZERO,
    DECIMAL_ONE,
    REPANIER_MONEY_ZERO,
    SaleStatus,
    OrderUnit,
    Vat,
)
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField, RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import ProducerInvoice
from repanier.models.product import Product
from repanier.models.purchase import PurchaseWoReceiver
from repanier.picture.const import SIZE_L
from repanier.picture.fields import RepanierPictureField


class Producer(models.Model):
    short_profile_name = models.CharField(
        _("Short name"),
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        unique=True,
    )
    long_profile_name = models.CharField(
        _("Long name"), max_length=100, blank=True, default=EMPTY_STRING
    )
    email = models.EmailField(_("Email"), null=True, blank=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("Second email address"), null=True, blank=True, default=EMPTY_STRING
    )
    email3 = models.EmailField(
        _("Third email address"), null=True, blank=True, default=EMPTY_STRING
    )
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("Language"),
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="producer",
        size=SIZE_L,
    )
    phone1 = models.CharField(
        _("Phone1"), max_length=25, blank=True, default=EMPTY_STRING
    )
    phone2 = models.CharField(
        _("Phone2"), max_length=25, blank=True, default=EMPTY_STRING
    )
    bank_account = models.CharField(
        _("Bank account"), max_length=100, blank=True, default=EMPTY_STRING
    )
    vat_id = models.CharField(
        _("VAT id"), max_length=20, blank=True, default=EMPTY_STRING
    )
    fax = models.CharField(_("Fax"), max_length=100, blank=True, default=EMPTY_STRING)
    address = models.TextField(_("Address"), blank=True, default=EMPTY_STRING)
    city = models.CharField(_("City"), max_length=50, blank=True, default=EMPTY_STRING)
    memo = models.TextField(_("Memo"), blank=True, default=EMPTY_STRING)
    reference_site = models.URLField(
        _("Reference site"), null=True, blank=True, default=EMPTY_STRING
    )
    web_services_activated = models.BooleanField(
        _("Web services activated"), default=False
    )
    invoice_by_basket = models.BooleanField(
        _("Billing is done on a consumer-by-consumer basis"), default=False
    )
    producer_price_are_wo_vat = models.BooleanField(
        _("The prices of the products of this producer are encoded excluding VAT"),
        default=False,
    )
    sort_products_by_reference = models.BooleanField(
        _(
            "In the lists sent to the producer, classify the products by reference and not in alphabetical order"
        ),
        default=False,
    )
    checking_stock = models.BooleanField(
        _("In the lists sent to the producer, attach the stock"), default=False
    )

    price_list_multiplier = models.DecimalField(
        _(
            "Coefficient applied to the producer tariff to calculate the customer tariff"
        ),
        help_text=_(
            "This multiplier is applied to each price automatically imported/pushed."
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    minimum_order_value = ModelRepanierMoneyField(
        _("Minimum order value to place an order"),
        help_text=_("0 mean : no minimum order value."),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)],
    )

    date_balance = models.DateField(_("Date_balance"), default=datetime.date.today)
    balance = ModelRepanierMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    initial_balance = ModelRepanierMoneyField(
        _("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    represent_this_buyinggroup = models.BooleanField(
        _("Represent this buyinggroup"), default=False
    )
    is_active = models.BooleanField(_("Active"), default=True)
    # This indicate that the user record data have been replaced with anonymous data in application of GDPR
    is_anonymized = models.BooleanField(default=False)

    @classmethod
    def get_or_create_group(cls):
        producer_buyinggroup = Producer.objects.filter(
            represent_this_buyinggroup=True
        ).first()
        if producer_buyinggroup is None:
            long_name = settings.REPANIER_SETTINGS_GROUP_NAME
            short_name = long_name[:25]
            producer_buyinggroup = Producer.objects.create(
                short_profile_name=short_name,
                long_profile_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                represent_this_buyinggroup=True,
            )
            # Create this to also prevent the deletion of the producer representing the buying group
            membership_fee_product = Product.objects.filter(
                order_unit=OrderUnit.MEMBERSHIP_FEE, is_active=True
            )
            if not membership_fee_product.exists():
                membership_fee_product = Product.objects.create(
                    producer_id=producer_buyinggroup.id,
                    order_unit=OrderUnit.MEMBERSHIP_FEE,
                    vat_level=Vat.VAT_100,
                    long_name_v2="{}".format(_("Membership fee")),
                )
        return producer_buyinggroup

    def get_phone1(self, prefix=EMPTY_STRING):
        # return ", phone1" if prefix = ", "
        if not self.phone1:
            return EMPTY_STRING
        return "{}{}".format(prefix, self.phone1)

    def get_phone2(self):
        return self.phone2 or EMPTY_STRING

    def get_negative_balance(self):
        return -self.balance

    def get_products(self):
        # This producer may have product's list
        if self.is_active:
            changeproductslist_url = reverse("admin:repanier_product_changelist")
            link = '<a href="{}?is_active__exact=1&producer={}" class="repanier-a-info">&nbsp;{}</a>'.format(
                changeproductslist_url, str(self.id), _("Products")
            )
            return format_html(link)

        return EMPTY_STRING

    get_products.short_description = EMPTY_STRING

    def get_admin_date_balance(self):
        return timezone.now().strftime(settings.DJANGO_SETTINGS_DATETIME)

    get_admin_date_balance.short_description = _("Date balance")

    def get_admin_balance(self):
        return (
            self.balance - self.get_bank_not_invoiced() + self.get_order_not_invoiced()
        )

    get_admin_balance.short_description = _("Balance")

    def get_order_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = ProducerInvoice.objects.filter(
                producer_id=self.id,
                status__gte=SaleStatus.OPENED,
                status__lte=SaleStatus.SEND,
            ).aggregate(
                total_price_with_tax=Sum(
                    "total_price_with_tax",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
                delta_price_with_tax=Sum(
                    "delta_price_with_tax",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
                delta_transport=Sum(
                    "delta_transport",
                    output_field=DecimalField(
                        max_digits=5, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
            )
            if result_set["total_price_with_tax"] is not None:
                order_not_invoiced = RepanierMoney(result_set["total_price_with_tax"])
            else:
                order_not_invoiced = REPANIER_MONEY_ZERO
            if result_set["delta_price_with_tax"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_price_with_tax"])
            if result_set["delta_transport"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_transport"])
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = BankAccount.objects.filter(
                producer_id=self.id, producer_invoice__isnull=True
            ).aggregate(
                bank_amount_in=Sum(
                    "bank_amount_in",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
                bank_amount_out=Sum(
                    "bank_amount_out",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
            )

            total_bank_amount_in = (
                result_set["bank_amount_in"]
                if result_set["bank_amount_in"] is not None
                else DECIMAL_ZERO
            )
            total_bank_amount_out = (
                result_set["bank_amount_out"]
                if result_set["bank_amount_out"] is not None
                else DECIMAL_ZERO
            )
            bank_not_invoiced = RepanierMoney(
                total_bank_amount_out - total_bank_amount_in
            )
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO

        return bank_not_invoiced

    def get_calculated_purchases(self, permanence_id):
        # Do not take into account product whose order unit is >= OrderUnit.DEPOSIT

        result_set = (
            PurchaseWoReceiver.objects.filter(
                permanence_id=permanence_id,
                producer_id=self.id,
                purchase_price__gte=F("selling_price"),
            )
            .exclude(offer_item__order_unit__gt=OrderUnit.DEPOSIT)
            .aggregate(
                total_purchase_price_with_tax=Sum(
                    "selling_price",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                )
            )
        )

        payment_needed = (
            result_set["total_purchase_price_with_tax"]
            if result_set["total_purchase_price_with_tax"] is not None
            else DECIMAL_ZERO
        )

        result_set = (
            PurchaseWoReceiver.objects.filter(
                permanence_id=permanence_id,
                producer_id=self.id,
                purchase_price__lt=F("selling_price"),
            )
            .exclude(offer_item__order_unit__gt=OrderUnit.DEPOSIT)
            .aggregate(
                total_selling_price_with_tax=Sum(
                    "purchase_price",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                )
            )
        )

        if result_set["total_selling_price_with_tax"] is not None:
            payment_needed += result_set["total_selling_price_with_tax"]

        return payment_needed

    get_calculated_purchases.short_description = _("Balance")

    def get_balance(self):
        any_producer_invoice = ProducerInvoice.objects.filter(
            producer_id=self.id,
            invoice_sort_order__isnull=False,
            status__lte=SaleStatus.INVOICED,
        )

        balance = self.get_admin_balance()

        if balance.amount < 0:
            color = "#298A08"
        elif balance.amount == 0:
            color = "#32CD32"
        elif balance.amount > 30:
            color = "red"
        else:
            color = "#696969"

        if any_producer_invoice.exists():
            return format_html(
                '<a href="{}?producer={}" class="repanier-a-info" target="_blank"><span style="color:{}">{}</span></a>',
                reverse("repanier:producer_invoice_view", args=(0,)),
                str(self.id),
                color,
                -balance,
            )
        else:
            return format_html('<span style="color:{}">{}</span>', color, -balance)

    get_balance.short_description = _("Balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = "balance"

    def get_last_invoice(self):
        producer_last_invoice = (
            ProducerInvoice.objects.filter(
                producer_id=self.id,
                invoice_sort_order__isnull=False,
                status__lte=SaleStatus.INVOICED,
            )
            .order_by("-id")
            .first()
        )
        if producer_last_invoice is not None:
            total_price_with_tax = producer_last_invoice.get_total_price_with_tax()
            if total_price_with_tax < DECIMAL_ZERO:
                return format_html(
                    '<span style="color:#298A08">{}</span>',
                    number_format(total_price_with_tax, 2),
                )
            elif total_price_with_tax == DECIMAL_ZERO:
                return format_html(
                    '<span style="color:#32CD32">{}</span>',
                    number_format(total_price_with_tax, 2),
                )
            elif total_price_with_tax > 30:
                return format_html(
                    '<span style="color:red">{}</span>',
                    number_format(total_price_with_tax, 2),
                )
            else:
                return format_html(
                    '<span style="color:#696969">{}</span>',
                    number_format(total_price_with_tax, 2),
                )
        else:
            return format_html(
                '<span style="color:#32CD32">{}</span>', number_format(0, 2)
            )

    get_last_invoice.short_description = _("Last accounting entry")

    def get_html_on_hold_movement(self):
        bank_not_invoiced = self.get_bank_not_invoiced()
        order_not_invoiced = self.get_order_not_invoiced()

        if (
            order_not_invoiced.amount != DECIMAL_ZERO
            or bank_not_invoiced.amount != DECIMAL_ZERO
        ):
            if order_not_invoiced.amount != DECIMAL_ZERO:
                if bank_not_invoiced.amount == DECIMAL_ZERO:
                    producer_on_hold_movement = _(
                        "This balance does not take into account orders not yet booked for an amount of %(other_order)s."
                    ) % {"other_order": order_not_invoiced}
                else:
                    producer_on_hold_movement = _(
                        "This balance does not take into account payments made after the last accounting entry (for an amount of %(bank)s), nor does it take into account orders not yet accounted (for an amount of %(other_order)s)"
                    ) % {"bank": bank_not_invoiced, "other_order": order_not_invoiced}
            else:
                producer_on_hold_movement = _(
                    "This balance does not take into account payments made after the last accounting for an amount of %(bank)s."
                ) % {"bank": bank_not_invoiced}
            return mark_safe(producer_on_hold_movement)

        return EMPTY_STRING

    def anonymize(self, also_group=False):
        if self.represent_this_buyinggroup:
            if not also_group:
                return
            self.short_profile_name = "{}-{}".format(_("GROUP"), self.id)
            self.long_profile_name = "{} {}".format(_("Group"), self.id)
        else:
            self.short_profile_name = "{}-{}".format(_("PRODUCER"), self.id)
            self.long_profile_name = "{} {}".format(_("Producer"), self.id)
        self.email = "{}@repanier.be".format(self.short_profile_name)
        self.email2 = EMPTY_STRING
        self.email3 = EMPTY_STRING
        self.phone1 = EMPTY_STRING
        self.phone2 = EMPTY_STRING
        self.bank_account = EMPTY_STRING
        self.vat_id = EMPTY_STRING
        self.fax = EMPTY_STRING
        self.address = EMPTY_STRING
        self.memo = EMPTY_STRING
        self.is_anonymized = True
        self.save()

    def get_filter_display(self, permanence_id):
        pi = ProducerInvoice.objects.filter(
            producer_id=self.id, permanence_id=permanence_id
        ).first()
        if pi is not None:
            return "{} ({})".format(self.short_profile_name, pi.total_price_with_tax)
        else:
            return self.short_profile_name

    def __str__(self):
        if self.producer_price_are_wo_vat:
            return "{} {}".format(self.short_profile_name, _("wo VAT"))
        return self.short_profile_name

    class Meta:
        verbose_name = _("Producer")
        verbose_name_plural = _("Producers")
        ordering = ("-represent_this_buyinggroup", "short_profile_name")
        indexes = [
            models.Index(
                fields=["-represent_this_buyinggroup", "short_profile_name"],
                name="producer_order_idx",
            )
        ]
