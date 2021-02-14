import datetime
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum, DecimalField
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import (
    DECIMAL_ZERO,
    EMPTY_STRING,
    DECIMAL_ONE,
    SALE_OPENED,
    SALE_SEND,
    REPANIER_MONEY_ZERO,
    PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
    ONE_YEAR,
    SHOP_UNICODE,
)
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanenceboard import PermanenceBoard
from repanier.picture.const import SIZE_S
from repanier.picture.fields import RepanierPictureField


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=models.CASCADE
    )
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"), default=DECIMAL_ZERO, max_digits=2, decimal_places=0
    )

    short_name = models.CharField(
        _("Short name"),
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        # unique=True,
    )
    long_name = models.CharField(
        _("Long name"),
        max_length=100,
        blank=True,
        default=EMPTY_STRING,
    )
    email2 = models.EmailField(_("✉ #2"), null=True, blank=True, default=EMPTY_STRING)
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
        upload_to="customer",
        size=SIZE_S,
    )
    phone1 = models.CharField(
        _("✆ #1"), max_length=25, blank=True, default=EMPTY_STRING
    )
    phone2 = models.CharField(
        _("✆ #2"), max_length=25, blank=True, default=EMPTY_STRING
    )
    bank_account1 = models.CharField(
        _("Bank account #1"), max_length=100, blank=True, default=EMPTY_STRING
    )
    bank_account2 = models.CharField(
        _("Bank account #2"), max_length=100, blank=True, default=EMPTY_STRING
    )
    address = models.TextField(_("Address"), blank=True, default=EMPTY_STRING)
    city = models.CharField(_("City"), max_length=50, blank=True, default=EMPTY_STRING)
    about_me = models.TextField(_("About me"), blank=True, default=EMPTY_STRING)
    memo = models.TextField(_("Memo"), blank=True, default=EMPTY_STRING)
    membership_fee_valid_until = models.DateField(
        _("Membership fee valid until"), default=datetime.date.today
    )
    custom_tariff_margin = models.DecimalField(
        _(
            "Coefficient applied to our pubilc tariff of selling to customers to calculate the personal sales tariff"
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None
    )
    date_balance = models.DateField(_("Date balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    # The initial balance is needed to compute the invoice control list
    initial_balance = ModelMoneyField(
        _("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    is_default = models.BooleanField(_("Represent this buyinggroup"), default=False)
    delivery_point = models.ForeignKey(
        "LUT_DeliveryPoint",
        verbose_name=_("Group"),
        blank=True,
        null=True,
        default=None,
        on_delete=models.CASCADE,
    )
    is_active = models.BooleanField(_("Active"), default=True)
    as_staff = models.ForeignKey(
        "Staff", blank=True, null=True, default=None, on_delete=models.CASCADE
    )
    # This indicate that the user record data have been replaced
    # with anonymous data in application of GDPR
    is_anonymized = models.BooleanField(default=False)
    # A group is a customer that groups several other customers.
    # The value of this field is set in "group_pre_save" signal
    is_group = models.BooleanField(_("Group"), default=False)
    display_group_tariff = models.BooleanField(
        _("Show the personal sales tariff to the customer"), default=False
    )
    # A group may not place an order.
    # The value of this field is set in "group_pre_save" signal
    # or in the admin at customer level.
    may_order = models.BooleanField(_("May order"), default=True)
    zero_waste = models.BooleanField(_("Zero waste"), default=False)
    valid_email = models.BooleanField(_("Valid email"), null=True, default=None)
    subscribe_to_email = models.BooleanField(
        _("Agree to receive mails from this site"), default=True
    )
    preparation_order = models.IntegerField(null=True, blank=True, default=0)
    # TODO TBD
    short_basket_name = models.CharField(
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        unique=True,
    )
    long_basket_name = models.CharField(
        max_length=100,
        blank=True,
        default=EMPTY_STRING,
    )
    represent_this_buyinggroup = models.BooleanField(
        _("Represent this buyinggroup"), default=False
    )
    price_list_multiplier = models.DecimalField(
        _(
            "Coefficient applied to the producer tariff to calculate the consumer tariff"
        ),
        help_text=_(
            "This multiplier is applied to each product ordered by this customer."
        ),
        default=DECIMAL_ONE,
        max_digits=5,
        decimal_places=4,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    vat_id = models.CharField(
        _("VAT id"), max_length=20, blank=True, default=EMPTY_STRING
    )

    @classmethod
    def get_or_create_default(cls):
        default = Customer.objects.filter(is_default=True).order_by("?").first()
        if default is None:
            long_name = settings.REPANIER_SETTINGS_GROUP_NAME
            short_name = long_name[:25]
            user = User.objects.filter(username=short_name).order_by("?").first()
            if user is None:
                user = User.objects.create_user(
                    username=short_name,
                    email=settings.DEFAULT_FROM_EMAIL,
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING,
                    last_name=long_name,
                )
            default = Customer.objects.create(
                user=user,
                short_name=short_name,
                long_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                is_default=True,
            )
        return default

    @classmethod
    def get_or_create_the_very_first_customer(cls):
        very_first_customer = (
            Customer.objects.filter(is_default=False, is_active=True)
            .order_by("id")
            .first()
        )
        if very_first_customer is None:
            long_name = settings.REPANIER_SETTINGS_COORDINATOR_NAME
            # short_name is the first word of long_name, limited to max. 25 characters
            short_name = long_name.split(None, 1)[0][:25]
            user = User.objects.filter(username=short_name).order_by("?").first()
            if user is None:
                user = User.objects.create_user(
                    username=short_name,
                    email=settings.REPANIER_SETTINGS_COORDINATOR_EMAIL,
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING,
                    last_name=long_name,
                )
            very_first_customer = Customer.objects.create(
                user=user,
                short_name=short_name,
                long_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                is_default=False,
            )
        return very_first_customer

    @classmethod
    def get_customer_from_valid_email(cls, email_address):
        # try to find a customer based on user__email or customer__email2
        customer = (
            Customer.objects.filter(
                Q(user__email=email_address) | Q(email2=email_address)
            )
            .exclude(valid_email=False)
            .order_by("?")
            .first()
        )
        return customer

    def get_admin_date_balance(self):
        return timezone.now().strftime(settings.DJANGO_SETTINGS_DATETIME)

    get_admin_date_balance.short_description = _("Date balance")

    def get_admin_date_joined(self):
        # New customer have no user during import of customers in admin.customer.CustomerResource
        try:
            return self.user.date_joined.strftime(settings.DJANGO_SETTINGS_DATE)
        except User.DoesNotExist:  # RelatedObjectDoesNotExist
            return EMPTY_STRING

    get_admin_date_joined.short_description = _("Date joined")

    def get_admin_balance(self):
        return (
            self.balance + self.get_bank_not_invoiced() - self.get_order_not_invoiced()
        )

    get_admin_balance.short_description = _("Balance")

    def get_available_deliveries_qs(self, permanence_id, delivery_board_id=0):
        if delivery_board_id > 0:
            if self.delivery_point is not None:
                # The customer is member of a group
                qs = DeliveryBoard.objects.filter(
                    Q(
                        id=delivery_board_id,
                        permanence_id=permanence_id,
                        delivery_point_id=self.delivery_point_id,
                    )
                    | Q(
                        id=delivery_board_id,
                        permanence_id=permanence_id,
                        delivery_point__customer_responsible__isnull=True,
                    )
                )
            else:
                qs = DeliveryBoard.objects.filter(
                    id=delivery_board_id,
                    permanence_id=permanence_id,
                    delivery_point__customer_responsible__isnull=True,
                )
        else:
            if self.delivery_point is not None:
                # The customer is member of a group
                qs = DeliveryBoard.objects.filter(
                    Q(
                        permanence_id=permanence_id,
                        delivery_point_id=self.delivery_point_id,
                    )
                    | Q(
                        permanence_id=permanence_id,
                        delivery_point__customer_responsible__isnull=True,
                    )
                )
            else:
                qs = DeliveryBoard.objects.filter(
                    permanence_id=permanence_id,
                    delivery_point__customer_responsible__isnull=True,
                )
        return qs

    def get_phone1(self, prefix=EMPTY_STRING, postfix=EMPTY_STRING):
        # return ", phone1" if prefix = ", "
        # return " (phone1)" if prefix = " (" and postfix = ")"
        if not self.phone1:
            return EMPTY_STRING
        return "{}{}{}".format(prefix, self.phone1, postfix)

    def get_phone2(self):
        return self.phone2 or EMPTY_STRING

    def get_phones(self, sep=", "):
        return (
            sep.join([self.phone1, self.phone2, EMPTY_STRING])
            if self.phone2
            else sep.join([self.phone1, EMPTY_STRING])
        )

    def get_email1(self, prefix=EMPTY_STRING):
        if not self.user.email:
            return EMPTY_STRING
        return "{}{}".format(prefix, self.user.email)

    def get_emails(self, sep="; "):
        return (
            sep.join([self.user.email, self.email2, EMPTY_STRING])
            if self.email2
            else sep.join([self.user.email, EMPTY_STRING])
        )

    def get_or_create_invoice(self, permanence_id):
        customer_invoice = CustomerInvoice.objects.filter(
            permanence_id=permanence_id, customer_id=self.id
        ).first()
        if customer_invoice is None:
            customer_invoice = self.create_invoice(permanence_id)
        elif customer_invoice.invoice_sort_order is None:
            # if not already invoiced, update all totals
            customer_invoice.set_total()
            customer_invoice.save()
        return customer_invoice

    def get_order_not_invoiced(self):
        result_set = (
            CustomerInvoice.objects.filter(
                customer_id=self.id,
                status__gte=SALE_OPENED,
                status__lte=SALE_SEND,
                customer_charged_id=self.id,
            )
            .order_by("?")
            .aggregate(
                total_price=Sum(
                    "total_price_with_tax",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
            )
        )
        total_price = result_set["total_price"] or DECIMAL_ZERO
        return RepanierMoney(total_price)

    def get_bank_not_invoiced(self):
        result_set = (
            BankAccount.objects.filter(
                customer_id=self.id, customer_invoice__isnull=True
            )
            .order_by("?")
            .aggregate(
                bank_in=Sum(
                    "bank_amount_in",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
                bank_out=Sum(
                    "bank_amount_out",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
            )
        )
        bank_in = result_set["bank_in"] or DECIMAL_ZERO
        bank_out = result_set["bank_out"] or DECIMAL_ZERO
        return RepanierMoney(bank_in - bank_out)

    def get_balance(self):
        if not settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return EMPTY_STRING
        last_customer_invoice = CustomerInvoice.objects.filter(
            customer_id=self.id, invoice_sort_order__isnull=False
        ).order_by("?")
        balance = self.get_admin_balance()
        if last_customer_invoice.exists():
            if balance.amount >= 30:
                return format_html(
                    '<a href="{}" class="repanier-a-info" target="_blank" ><span style="color:#32CD32">{}</span></a>',
                    reverse("repanier:customer_invoice_view", args=(0, self.id)),
                    balance,
                )
            elif balance.amount >= -10:
                return format_html(
                    '<a href="{}" class="repanier-a-info" target="_blank" ><span style="color:#696969">{}</span></a>',
                    reverse("repanier:customer_invoice_view", args=(0, self.id)),
                    balance,
                )
            else:
                return format_html(
                    '<a href="{}" class="repanier-a-info" target="_blank" ><span style="color:red">{}</span></a>',
                    reverse("repanier:customer_invoice_view", args=(0, self.id)),
                    balance,
                )
        else:
            if balance.amount >= 30:
                return format_html('<span style="color:#32CD32">{}</span>', balance)
            elif balance.amount >= -10:
                return format_html('<span style="color:#696969">{}</span>', balance)
            else:
                return format_html('<span style="color:red">{}</span>', balance)

    get_balance.short_description = _("Balance")
    get_balance.admin_order_field = "balance"

    def get_html_on_hold_movement(
        self,
        bank_not_invoiced=None,
        order_not_invoiced=None,
        total_price_with_tax=REPANIER_MONEY_ZERO,
    ):
        if not settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return EMPTY_STRING
        bank_not_invoiced = (
            bank_not_invoiced
            if bank_not_invoiced is not None
            else self.get_bank_not_invoiced()
        )
        order_not_invoiced = (
            order_not_invoiced
            if order_not_invoiced is not None
            else self.get_order_not_invoiced()
        )
        other_order_not_invoiced = order_not_invoiced - total_price_with_tax

        if other_order_not_invoiced.amount != DECIMAL_ZERO:
            if bank_not_invoiced.amount == DECIMAL_ZERO:
                customer_on_hold_movement = _(
                    "This balance does not take account of any unbilled sales %(other_order)s."
                ) % {"other_order": other_order_not_invoiced}
            else:
                customer_on_hold_movement = _(
                    "This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s."
                ) % {
                    "bank": bank_not_invoiced,
                    "other_order": other_order_not_invoiced,
                }
        else:
            if bank_not_invoiced.amount == DECIMAL_ZERO:
                customer_on_hold_movement = _(
                    "This balance does not take account of any unrecognized payments %(bank)s."
                ) % {"bank": bank_not_invoiced}
            else:
                customer_on_hold_movement = EMPTY_STRING
        customer_on_hold_movement = mark_safe(customer_on_hold_movement)

        return customer_on_hold_movement

    def get_last_membership_fee(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
        ).order_by("-id")
        if last_membership_fee.exists():
            return last_membership_fee.first().selling_price

    get_last_membership_fee.short_description = _("Last membership fee")

    def last_membership_fee_date(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = (
            Purchase.objects.filter(
                customer_id=self.id,
                offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
            )
            .order_by("-id")
            .prefetch_related("customer_invoice")
        )
        if last_membership_fee.exists():
            return last_membership_fee.first().customer_invoice.date_balance

    last_membership_fee_date.short_description = _("Last membership fee date")

    def get_last_membership_fee_date(self):
        # Format it for the admin
        # Don't format it form import/export
        last_membership_fee_date = self.last_membership_fee_date()
        if last_membership_fee_date is not None:
            return last_membership_fee_date.strftime(settings.DJANGO_SETTINGS_DATE)
        return EMPTY_STRING

    get_last_membership_fee_date.short_description = _("Last membership fee date")

    def get_participation_counter(self):
        now = timezone.now()
        return (
            PermanenceBoard.objects.filter(
                customer_id=self.id,
                permanence_date__gte=now - datetime.timedelta(days=ONE_YEAR),
                permanence_date__lt=now,
                permanence_role__is_counted_as_participation=True,
            )
            .order_by("?")
            .count()
        )

    get_participation_counter.short_description = _("Participation")

    def get_purchase_counter(self):
        now = timezone.now()
        # Do not count invoice having only products free of charge
        # or slitted permanences (master_permanence is not NULL)
        return CustomerInvoice.objects.filter(
            customer_id=self.id,
            total_price_with_tax__gt=DECIMAL_ZERO,
            date_balance__gte=now - datetime.timedelta(ONE_YEAR),
            permanence__master_permanence__isnull=True,
        ).count()

    get_purchase_counter.short_description = _("Purchase")

    def my_order_confirmation_email_send_to(self):
        if self.email2:
            to_email = (self.user.email, self.email2)
        else:
            to_email = (self.user.email,)
        sent_to = ", ".join(to_email) if to_email is not None else EMPTY_STRING
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            msg_confirmation = _(
                "Order confirmed. An email containing this order summary has been sent to {}."
            ).format(sent_to)
        else:
            msg_confirmation = _(
                "An email containing this order summary has been sent to {}."
            ).format(sent_to)
        return msg_confirmation

    def get_html_unsubscribe_mail_footer(self):
        return mark_safe(
            '<br><br><hr/><br><a href="{}">{}</a>'.format(
                self._get_unsubscribe_link(),
                _("Stop receiving mails from {}").format(self._get_unsubscribe_site()),
            )
        )

    def get_html_list_unsubscribe(self):
        return mark_safe("<{}>".format(self._get_unsubscribe_link()))

    def _get_unsubscribe_link(self):
        customer_id, token = self.make_token().split(":", 1)
        return "https://{}{}".format(
            self._get_unsubscribe_site(),
            reverse(
                "repanier:unsubscribe_view",
                kwargs={"customer_id": customer_id, "token": token},
            ),
        )

    @staticmethod
    def _get_unsubscribe_site():
        return settings.ALLOWED_HOSTS[0]

    def make_token(self):
        return TimestampSigner().sign(self.id)

    def check_token(self, token):
        try:
            key = "{}:{}".format(self.id, token)
            TimestampSigner().unsign(key, max_age=60 * 60 * 48)  # Valid for 2 days
        except (BadSignature, SignatureExpired):
            return False
        return True

    def anonymize(self, also_group=False):
        if self.is_default or self.is_group:
            # Do not anonymize groups
            return
        self.short_name = "{}-{}".format(_("BASKET"), self.id).lower()
        self.long_name = "{} {}".format(_("Family"), self.id)
        self.email2 = EMPTY_STRING
        self.picture = EMPTY_STRING
        self.phone1 = EMPTY_STRING
        self.phone2 = EMPTY_STRING
        self.bank_account1 = EMPTY_STRING
        self.bank_account1 = EMPTY_STRING
        self.vat_id = EMPTY_STRING
        self.address = EMPTY_STRING
        self.about_me = EMPTY_STRING
        self.memo = EMPTY_STRING
        self.user.username = self.user.email = "{}@repanier.be".format(self.short_name)
        self.user.first_name = EMPTY_STRING
        self.user.last_name = self.short_name
        self.user.set_password(None)
        self.user.save()
        self.is_anonymized = True
        self.valid_email = False
        self.subscribe_to_email = False
        self.save()

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse(
            "repanier:published_customer_view", kwargs={"customer_id": self.id}
        )

    def __str__(self):
        shop = SHOP_UNICODE if self.is_default else EMPTY_STRING
        return " ".join([shop, self.short_name])

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        # ordering = ["-is_default", "short_name"]
        indexes = [
            models.Index(
                fields=["-is_default", "short_name"],
                name="customer_order_idx",
            )
        ]
