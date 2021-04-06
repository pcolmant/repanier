import datetime
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, DecimalField
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _lazy, ugettext as _

from repanier_v2.const import (
    EMPTY_STRING,
    DECIMAL_ZERO,
    DECIMAL_ONE,
    VAT_100,
    REPANIER_MONEY_ZERO,
    PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
    ORDER_OPENED,
    ORDER_SEND,
    SHOP_UNICODE,
)
from repanier_v2.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier_v2.models.bank_account import BankAccount
from repanier_v2.models.invoice import ProducerInvoice
from repanier_v2.models.product import Product
from repanier_v2.picture.const import SIZE_L
from repanier_v2.picture.fields import RepanierPictureField


class Producer(models.Model):
    short_name = models.CharField(
        _lazy("Short name"),
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        # unique=True,
        # db_column="short_profile_name"
    )
    long_name = models.CharField(
        _lazy("Long name"),
        max_length=100,
        blank=True,
        default=EMPTY_STRING,
        # db_column="long_profile_name"
    )
    email = models.EmailField(
        _lazy("✉ #1"), null=True, blank=True, default=EMPTY_STRING
    )
    email2 = models.EmailField(
        _lazy("✉ #2"), null=True, blank=True, default=EMPTY_STRING
    )
    email3 = models.EmailField(
        _lazy("✉ #3"), null=True, blank=True, default=EMPTY_STRING
    )
    picture = RepanierPictureField(
        verbose_name=_lazy("Picture"),
        null=True,
        blank=True,
        upload_to="producer",
        size=SIZE_L,
    )
    phone1 = models.CharField(
        _lazy("✆ #1"), max_length=25, blank=True, default=EMPTY_STRING
    )
    phone2 = models.CharField(
        _lazy("✆ #2"), max_length=25, blank=True, default=EMPTY_STRING
    )
    bank_account = models.CharField(
        _lazy("Bank account"), max_length=100, blank=True, default=EMPTY_STRING
    )
    vat_id = models.CharField(
        _lazy("VAT id"), max_length=20, blank=True, default=EMPTY_STRING
    )
    fax = models.CharField(
        _lazy("Fax"), max_length=100, blank=True, default=EMPTY_STRING
    )
    address = models.TextField(_lazy("Address"), blank=True, default=EMPTY_STRING)
    city = models.CharField(
        _lazy("City"), max_length=50, blank=True, default=EMPTY_STRING
    )
    memo = models.TextField(_lazy("Memo"), blank=True, default=EMPTY_STRING)
    reference_site = models.URLField(
        _lazy("Reference site"), null=True, blank=True, default=EMPTY_STRING
    )
    web_services_activated = models.BooleanField(
        _lazy("Web services activated"), default=False
    )
    # uuid used to access to producer invoices without login
    login_uuid = models.UUIDField(
        "uuid",
        # uuid.uuid1() is not a callable but value returned by uuid.uuid1() call when this model class is initialized
        # default=uuid.uuid4 which sets it as callable,
        # and is sets new uuid each time new default value needs to be used
        # The call isn't done when running migration
        default=uuid.uuid4,
        # unique=True, TODO : restore after migration
        db_index=True,
        editable=False
    )
    invoice_by_customer = models.BooleanField(
        _lazy("Invoice each customer separately"), default=False
    )
    producer_tariff_is_wo_tax = models.BooleanField(
        _lazy("The producer's tariff is exclusive of tax"), default=False
    )
    sort_products_by_reference = models.BooleanField(
        _lazy("Sort products by reference"), default=False
    )
    purchase_margin = models.DecimalField(
        _(
            "Coefficient that the producer applies to his tariff to calculate our purchase tariff"
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    customer_margin = models.DecimalField(
        _(
            "Coefficient applied to our purchase price to calculate our public tariff of selling to customers"
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    minimum_order_value = ModelMoneyField(
        _lazy("Minimum order value"),
        help_text=_lazy("0 mean : no minimum order value."),
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        validators=[MinValueValidator(0)],
    )
    date_balance = models.DateField(_lazy("Date_balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _lazy("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    initial_balance = ModelMoneyField(
        _lazy("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    is_default = models.BooleanField(_lazy("Represent this buyinggroup"), default=False)
    is_active = models.BooleanField(_lazy("Active"), default=True)
    # This indicate that the user record data have been replaced with anonymous data in application of GDPR
    is_anonymized = models.BooleanField(default=False)

    ###### TODO BEGIN OF OLD FIELD : TBD
    short_profile_name = models.CharField(
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        unique=True,
    )
    long_profile_name = models.CharField(
        max_length=100,
        blank=True,
        default=EMPTY_STRING,
    )
    uuid = models.CharField("uuid", max_length=36, default=EMPTY_STRING, db_index=True)
    producer_price_are_wo_vat = models.BooleanField(
        _lazy("The producer's tariff is excluding tax"), default=False
    )
    price_list_multiplier = models.DecimalField(
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    invoice_by_basket = models.BooleanField(
        _lazy("Invoice each customer separately"), default=False
    )
    represent_this_buyinggroup = models.BooleanField(
        _lazy("Represent this buyinggroup"), default=False
    )
    ###### TODO END OF OLD FIELD : TBD

    @classmethod
    def get_or_create_default(cls):
        default = Producer.objects.filter(is_default=True).first()
        if default is None:
            long_name = settings.REPANIER_SETTINGS_GROUP_NAME
            short_name = long_name[:25]
            default = Producer.objects.create(
                short_name=short_name,
                long_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                is_default=True,
            )
            # Create this to also prevent the deletion of the producer representing the buying group
            membership_fee_product = Product.objects.filter(
                order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE, is_active=True
            ).order_by("?")
            if not membership_fee_product.exists():
                membership_fee_product = Product.objects.create(
                    producer_id=default.id,
                    order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
                    vat_level=VAT_100,
                )
                cur_language = translation.get_language()
                for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                    language_code = language["code"]
                    translation.activate(language_code)
                    membership_fee_product.set_current_language(language_code)
                    membership_fee_product.long_name = "{}".format(_("Membership fee"))
                    membership_fee_product.save()
                translation.activate(cur_language)
        return default

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
            link = '<a href="{}?is_active__exact=1&producer={}" class="repanier_v2-a-info">&nbsp;{}</a>'.format(
                changeproductslist_url, str(self.id), _("Products")
            )
            return format_html(link)

        return EMPTY_STRING

    get_products.short_description = EMPTY_STRING

    def get_admin_date_balance(self):
        return timezone.now().strftime(settings.DJANGO_SETTINGS_DATETIME)

    get_admin_date_balance.short_description = _lazy("Date balance")

    def get_admin_balance(self):
        return (
            self.balance - self.get_bank_not_invoiced() + self.get_order_not_invoiced()
        )

    get_admin_balance.short_description = _lazy("Balance")

    def get_order_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = (
                ProducerInvoice.objects.filter(
                    producer_id=self.id,
                    status__gte=ORDER_OPENED,
                    status__lte=ORDER_SEND,
                )
                .order_by("?")
                .aggregate(
                    total_price_with_tax=Sum(
                        "total_price_with_tax",
                        output_field=DecimalField(
                            max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                        ),
                    ),
                )
            )
            order_not_invoiced = RepanierMoney(
                result_set["total_price_with_tax"] or DECIMAL_ZERO
            )
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = (
                BankAccount.objects.filter(
                    producer_id=self.id, producer_invoice__isnull=True
                )
                .order_by("?")
                .aggregate(
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
            )

            total_bank_amount_in = result_set["bank_amount_in"] or DECIMAL_ZERO
            total_bank_amount_out = result_set["bank_amount_out"] or DECIMAL_ZERO
            bank_not_invoiced = RepanierMoney(
                total_bank_amount_out - total_bank_amount_in
            )
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO

        return bank_not_invoiced

    def get_balance(self):
        last_producer_invoice_set = ProducerInvoice.objects.filter(
            producer_id=self.id, invoice_sort_order__isnull=False
        ).order_by("?")

        balance = self.get_admin_balance()

        if balance.amount < 0:
            color = "#298A08"
        elif balance.amount == 0:
            color = "#32CD32"
        elif balance.amount > 30:
            color = "red"
        else:
            color = "#696969"

        if last_producer_invoice_set.exists():
            return format_html(
                '<a href="{}" class="repanier_v2-a-info" target="_blank"><span style="color:{}">{}</span></a>',
                reverse("repanier_v2:producer_invoice_view", args=(0, self.login_uuid)),
                color,
                -balance,
            )
        else:
            return format_html('<span style="color:{}">{}</span>', color, -balance)

    get_balance.short_description = _lazy("Balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = "balance"

    def get_last_invoice(self):
        producer_last_invoice = (
            ProducerInvoice.objects.filter(
                producer_id=self.id, invoice_sort_order__isnull=False
            )
            .order_by("-id")
            .first()
        )
        if producer_last_invoice is not None:
            total_price_with_tax = producer_last_invoice.balance_calculated
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

    get_last_invoice.short_description = _lazy("Last invoice")

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
                        "This balance does not take account of any unbilled sales %(other_order)s."
                    ) % {"other_order": order_not_invoiced}
                else:
                    producer_on_hold_movement = _(
                        "This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s."
                    ) % {"bank": bank_not_invoiced, "other_order": order_not_invoiced}
            else:
                producer_on_hold_movement = _(
                    "This balance does not take account of any unrecognized payments %(bank)s."
                ) % {"bank": bank_not_invoiced}
            return mark_safe(producer_on_hold_movement)

        return EMPTY_STRING

    def anonymize(self, also_group=False):
        if self.is_default:
            if not also_group:
                return
            self.short_name = "{}-{}".format(_("GROUP"), self.id)
            self.long_name = "{} {}".format(_("Group"), self.id)
        else:
            self.short_name = "{}-{}".format(_("PRODUCER"), self.id)
            self.long_name = "{} {}".format(_("Producer"), self.id)
        self.email = "{}@repanier_v2.be".format(self.short_name)
        self.email2 = EMPTY_STRING
        self.email3 = EMPTY_STRING
        self.phone1 = EMPTY_STRING
        self.phone2 = EMPTY_STRING
        self.bank_account = EMPTY_STRING
        self.vat_id = EMPTY_STRING
        self.fax = EMPTY_STRING
        self.address = EMPTY_STRING
        self.memo = EMPTY_STRING
        self.login_uuid = uuid.uuid4()
        self.is_anonymized = True
        self.save()

    def __str__(self):
        shop = SHOP_UNICODE if self.is_default else EMPTY_STRING
        tax = _("excl. tax") if self.producer_tariff_is_wo_tax else EMPTY_STRING
        return " ".join([shop, self.short_name, tax])

    class Meta:
        verbose_name = _lazy("Producer")
        verbose_name_plural = _lazy("Producers")
        # ordering = ["-is_default", "short_name"]
        indexes = [
            models.Index(
                fields=["-is_default", "short_name"],
                name="producer_order_idx",
            )
        ]
