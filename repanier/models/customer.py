import datetime
import uuid

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.validators import MinValueValidator
from django.db import connection
from django.db.models import Sum, DecimalField
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField, RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.picture.const import SIZE_S
from repanier.picture.fields import RepanierPictureField


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=models.CASCADE
    )
    login_attempt_counter = models.DecimalField(
        _("Sign in attempt counter"),
        default=DECIMAL_ZERO,
        max_digits=2,
        decimal_places=0,
    )

    short_basket_name = models.CharField(
        _("Short name"),
        max_length=25,
        blank=False,
        default=EMPTY_STRING,
        db_index=True,
        unique=True,
    )
    long_basket_name = models.CharField(
        _("Long name"), max_length=100, blank=True, default=EMPTY_STRING
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
        upload_to="customer",
        size=SIZE_S,
    )
    phone1 = models.CharField(
        _("Phone1"), max_length=25, blank=True, default=EMPTY_STRING
    )
    phone2 = models.CharField(
        _("Phone2"), max_length=25, blank=True, default=EMPTY_STRING
    )
    bank_account1 = models.CharField(
        _("Main bank account"), max_length=100, blank=True, default=EMPTY_STRING
    )
    bank_account2 = models.CharField(
        _("Secondary bank account"), max_length=100, blank=True, default=EMPTY_STRING
    )
    vat_id = models.CharField(
        _("VAT id"), max_length=20, blank=True, default=EMPTY_STRING
    )
    address = models.TextField(_("Address"), blank=True, default=EMPTY_STRING)
    city = models.CharField(_("City"), max_length=50, blank=True, default=EMPTY_STRING)
    about_me = models.TextField(_("About me"), blank=True, default=EMPTY_STRING)
    memo = models.TextField(_("Memo"), blank=True, default=EMPTY_STRING)
    membership_fee_valid_until = models.DateField(
        _("Membership fee valid until"), default=datetime.date.today
    )
    price_list_multiplier = models.DecimalField(
        _(
            "Coefficient applied to the producer tariff to calculate the customer tariff"
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

    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None
    )
    date_balance = models.DateField(_("Date balance"), default=datetime.date.today)
    balance = ModelRepanierMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    # The initial balance is needed to compute the invoice control list
    initial_balance = ModelRepanierMoneyField(
        _("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO
    )
    represent_this_buyinggroup = models.BooleanField(
        _("Represent_this_buyinggroup"), default=False
    )
    group = models.ForeignKey(
        "Group",
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

    @classmethod
    def get_or_create_group(cls):
        customer_buyinggroup = Customer.objects.filter(
            represent_this_buyinggroup=True
        ).first()
        if customer_buyinggroup is None:
            long_name = settings.REPANIER_SETTINGS_GROUP_NAME
            short_name = long_name[:25]
            user = User.objects.filter(username=short_name).first()
            if user is None:
                user = User.objects.create_user(
                    username=short_name,
                    email=settings.DEFAULT_FROM_EMAIL,
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING,
                    last_name=long_name,
                )
            customer_buyinggroup = Customer.objects.create(
                user=user,
                short_basket_name=short_name,
                long_basket_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                represent_this_buyinggroup=True,
            )
        return customer_buyinggroup

    @classmethod
    def get_or_create_the_very_first_customer(cls):
        very_first_customer = (
            Customer.objects.filter(represent_this_buyinggroup=False, is_active=True)
            .order_by("id")
            .first()
        )
        if very_first_customer is None:
            long_name = settings.REPANIER_SETTINGS_COORDINATOR_NAME
            # short_name is the first word of long_name, limited to max. 25 characters
            short_name = long_name.split(None, 1)[0][:25]
            user = User.objects.filter(username=short_name).first()
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
                short_basket_name=short_name,
                long_basket_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                represent_this_buyinggroup=False,
            )
        return very_first_customer

    @classmethod
    def get_customer_from_valid_email(cls, email_address):
        # try to find a customer based on user__email
        customer = Customer.objects.filter(user__email=email_address).first()
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

    def get_phone1(self, prefix=EMPTY_STRING, postfix=EMPTY_STRING):
        # return ", phone1" if prefix = ", "
        # return " (phone1)" if prefix = " (" and postfix = ")"
        if not self.phone1:
            return EMPTY_STRING
        return "{}{}{}".format(prefix, self.phone1, postfix)

    def get_phone2(self):
        return self.phone2 or EMPTY_STRING

    def get_phones(self, sep=", "):
        return sep.join([self.phone1, self.phone2]) if self.phone2 else self.phone1

    def get_email_prefixed(self, prefix=EMPTY_STRING):
        if not self.user.email:
            return EMPTY_STRING
        return "{}{}".format(prefix, self.user.email)

    def get_email_postfixed(self, postfix="; "):
        if not self.user.email:
            return EMPTY_STRING
        return "{}{}".format(self.user.email, postfix)

    def get_order_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = CustomerInvoice.objects.filter(
                customer_id=self.id,
                status__lte=SaleStatus.SEND,
                customer_charged_id=self.id,
            ).aggregate(
                total_price=Sum(
                    "total_price_with_tax",
                    output_field=DecimalField(
                        max_digits=8, decimal_places=2, default=DECIMAL_ZERO
                    ),
                ),
                delta_price=Sum(
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
            total_price = (
                result_set["total_price"]
                if result_set["total_price"] is not None
                else DECIMAL_ZERO
            )
            delta_price = (
                result_set["delta_price"]
                if result_set["delta_price"] is not None
                else DECIMAL_ZERO
            )
            delta_transport = (
                result_set["delta_transport"]
                if result_set["delta_transport"] is not None
                else DECIMAL_ZERO
            )
            order_not_invoiced = RepanierMoney(
                total_price + delta_price + delta_transport
            )
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = BankAccount.objects.filter(
                customer_id=self.id, customer_invoice__isnull=True
            ).aggregate(
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
            bank_in = (
                result_set["bank_in"]
                if result_set["bank_in"] is not None
                else DECIMAL_ZERO
            )
            bank_out = (
                result_set["bank_out"]
                if result_set["bank_out"] is not None
                else DECIMAL_ZERO
            )
            bank_not_invoiced = bank_in - bank_out
        else:
            bank_not_invoiced = DECIMAL_ZERO
        return RepanierMoney(bank_not_invoiced)

    def get_balance(self):
        any_customer_invoice = CustomerInvoice.objects.filter(
            customer_id=self.id, invoice_sort_order__isnull=False
        )

        balance = self.get_admin_balance()

        if balance.amount >= 30:
            color = "#32CD32"
        elif balance.amount >= -10:
            color = "#696969"
        else:
            color = "red"

        if any_customer_invoice.exists():
            return format_html(
                '<a href="{}" class="repanier-a-info" target="_blank" ><span style="color:{}">{}</span></a>',
                reverse(
                    "repanier:customer_invoice_view_with_customer",
                    args=(
                        0,
                        self.id,
                    ),
                ),
                color,
                balance,
            )
        else:
            return format_html('<span style="color:{}">{}</span>', color, balance)

    get_balance.short_description = _("Balance")
    get_balance.admin_order_field = "balance"

    def get_html_on_hold_movement(
        self,
        bank_not_invoiced=None,
        order_not_invoiced=None,
        total_price_with_tax=REPANIER_MONEY_ZERO,
    ):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
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
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO
            other_order_not_invoiced = REPANIER_MONEY_ZERO

        if (
            other_order_not_invoiced.amount != DECIMAL_ZERO
            or bank_not_invoiced.amount != DECIMAL_ZERO
        ):
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
                customer_on_hold_movement = _(
                    "This balance does not take account of any unrecognized payments %(bank)s."
                ) % {"bank": bank_not_invoiced}
            customer_on_hold_movement = mark_safe(customer_on_hold_movement)
        else:
            customer_on_hold_movement = EMPTY_STRING

        return customer_on_hold_movement

    def get_last_membership_fee(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=OrderUnit.MEMBERSHIP_FEE,
        ).order_by("-id")
        if last_membership_fee.exists():
            return last_membership_fee.first().selling_price

    get_last_membership_fee.short_description = _("Last membership fee")

    def last_membership_fee_date(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = (
            Purchase.objects.filter(
                customer_id=self.id,
                offer_item__order_unit=OrderUnit.MEMBERSHIP_FEE,
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
        since = (timezone.now() - datetime.timedelta(ONE_YEAR)).date()
        now = timezone.now().date()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS participation_counter "
                    "  FROM repanier_permanenceboard INNER JOIN repanier_lut_permanencerole "
                    "    ON (repanier_permanenceboard.permanence_role_id = repanier_lut_permanencerole.id) "
                    "  WHERE repanier_permanenceboard.customer_id = %s "
                    "    AND repanier_permanenceboard.permanence_date BETWEEN %s AND %s ",
                    [self.id, since, now],
                )
                result = cursor.fetchone()
                return Decimal(result[0])
        except:
            return DECIMAL_ZERO

    get_participation_counter.short_description = _(
        "Participations in the last 12 months"
    )

    def get_purchase_counter(self):
        since = (timezone.now() - datetime.timedelta(ONE_YEAR)).date()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(DISTINCT repanier_permanence.permanence_date) AS purchase_counter "
                    "  FROM repanier_customerinvoice INNER JOIN repanier_permanence "
                    "    ON (repanier_customerinvoice.permanence_id = repanier_permanence.id) "
                    "  WHERE repanier_customerinvoice.permanence_id = repanier_permanence.id "
                    "    AND repanier_customerinvoice.customer_id = %s "
                    "    AND repanier_permanence.permanence_date >= %s ",
                    [self.id, since],
                )
                result = cursor.fetchone()
                return Decimal(result[0])
        except:
            return DECIMAL_ZERO

    get_purchase_counter.short_description = _("Purchases in the last 12 months")

    def my_order_confirmation_email_send_to(self):
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
        if self.represent_this_buyinggroup or self.is_group or self.may_order:
            # Do not anonymize
            return
        self.long_basket_name = self.short_basket_name = "{}({})".format(
            _("nameless"), self.id
        ).lower()
        self.group = None
        self.picture = EMPTY_STRING
        self.phone1 = EMPTY_STRING
        self.phone2 = EMPTY_STRING
        self.bank_account1 = EMPTY_STRING
        self.bank_account1 = EMPTY_STRING
        self.vat_id = EMPTY_STRING
        self.address = EMPTY_STRING
        self.about_me = EMPTY_STRING
        self.memo = EMPTY_STRING
        self.user.username = self.user.email = "{}@repanier.be".format(
            self.short_basket_name
        )
        self.user.first_name = EMPTY_STRING
        self.user.last_name = self.short_basket_name
        self.user.is_active = False
        self.user.set_password(None)
        self.user.save()
        self.is_active = False
        self.is_anonymized = True
        self.valid_email = False
        self.subscribe_to_email = False
        self.save()

    def get_filter_display(self, permanence_id):
        ci = CustomerInvoice.objects.filter(
            customer_id=self.id, permanence_id=permanence_id
        ).first()
        if ci is not None:
            if ci.is_order_confirm_send:
                return "{} {} ({})".format(
                    settings.LOCK_UNICODE,
                    self.short_basket_name,
                    ci.total_price_with_tax,
                )
            else:
                return "{} ({})".format(self.short_basket_name, ci.total_price_with_tax)
        else:
            return self.short_basket_name

    def __str__(self):
        if self.group is None:
            return self.short_basket_name
        else:
            return "{} - {}".format(self.group, self.short_basket_name)

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ("-represent_this_buyinggroup", "short_basket_name")
        indexes = [
            models.Index(
                fields=["-represent_this_buyinggroup", "short_basket_name"],
                name="customer_order_idx",
            )
        ]
