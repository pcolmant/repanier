# -*- coding: utf-8

import datetime
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core import urlresolvers
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField, RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanenceboard import PermanenceBoard
from repanier.picture.const import SIZE_S
from repanier.picture.fields import AjaxPictureField


class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, db_index=True)
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)

    short_basket_name = models.CharField(
        _("Short name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_basket_name = models.CharField(
        _("Long name"), max_length=100, null=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("Secondary email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("Language"))

    picture = AjaxPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="customer", size=SIZE_S)
    phone1 = models.CharField(
        _("Phone1"),
        max_length=25,
        null=True, blank=True, default=EMPTY_STRING)
    phone2 = models.CharField(
        _("Phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    bank_account1 = models.CharField(_("Main bank account"), max_length=100, null=True, blank=True,
                                     default=EMPTY_STRING)
    bank_account2 = models.CharField(_("Secondary bank account"), max_length=100, null=True, blank=True,
                                     default=EMPTY_STRING)
    vat_id = models.CharField(
        _("VAT id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(
        _("Address"), null=True, blank=True, default=EMPTY_STRING)
    city = models.CharField(
        _("City"), max_length=50, null=True, blank=True, default=EMPTY_STRING)
    about_me = models.TextField(
        _("About me"), null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("Memo"), null=True, blank=True, default=EMPTY_STRING)
    show_mails_to_members = models.BooleanField(
        _("Show my mail to other members"), default=False)
    show_phones_to_members = models.BooleanField(
        _("Show my phone to other members"), default=False)
    membership_fee_valid_until = models.DateField(
        _("Membership fee valid until"),
        default=datetime.date.today
    )
    # If this customer is member of a closed group, the customer.price_list_multiplier is not used
    # Invoices are sent to the consumer responsible of the group who is
    # also responsible for collecting the payments.
    # The LUT_DeliveryPoint.price_list_multiplier will be used when invoicing the consumer responsible
    # At this stage, the link between the customer invoice and this customer responsible is made with
    # CustomerInvoice.customer_charged
    price_list_multiplier = models.DecimalField(
        _("Coefficient applied to the producer tariff to calculate the consumer tariff"),
        help_text=_("This multiplier is applied to each product ordered by this customer."),
        default=DECIMAL_ONE, max_digits=5, decimal_places=4, blank=True,
        validators=[MinValueValidator(0)])

    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None)
    date_balance = models.DateField(
        _("Date balance"), default=datetime.date.today)
    balance = ModelMoneyField(
        _("Balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # The initial balance is needed to compute the invoice control list
    initial_balance = ModelMoneyField(
        _("Initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("Represent_this_buyinggroup"), default=False)
    delivery_point = models.ForeignKey(
        'LUT_DeliveryPoint',
        verbose_name=_("Delivery point"),
        blank=True, null=True, default=None)
    is_active = models.BooleanField(_("Active"), default=True)
    as_staff = models.ForeignKey(
        'Staff',
        blank=True, null=True, default=None)
    # This indicate that the user record data have been replaced with anonymous data in application of GDPR
    is_anonymized = models.BooleanField(default=False)
    is_group = models.BooleanField(_("Group"), default=False)
    may_order = models.BooleanField(_("May order"), default=True)
    zero_waste = models.BooleanField(_("Zero waste"), default=False)
    valid_email = models.NullBooleanField(_("Valid email"), default=None)
    subscribe_to_email = models.BooleanField(_("Agree to receive unsolicited mails from this site"), default=True)
    preparation_order = models.IntegerField(null=True, blank=True, default=0)

    @classmethod
    def get_or_create_group(cls):
        customer_buyinggroup = Customer.objects.filter(represent_this_buyinggroup=True).order_by('?').first()
        if customer_buyinggroup is None:
            long_name = settings.REPANIER_SETTINGS_GROUP_NAME
            short_name = long_name[:25]
            user = User.objects.filter(username=short_name).order_by('?').first()
            if user is None:
                user = User.objects.create_user(
                    username=short_name,
                    email="{}{}".format(long_name, settings.REPANIER_SETTINGS_ALLOWED_MAIL_EXTENSION),
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING, last_name=long_name)
            customer_buyinggroup = Customer.objects.create(
                user=user,
                short_basket_name=short_name,
                long_basket_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                represent_this_buyinggroup=True
            )
        return customer_buyinggroup

    @classmethod
    def get_or_create_the_very_first_customer(cls):
        very_first_customer = Customer.objects.filter(
            represent_this_buyinggroup=False,
            is_active=True
        ).order_by('id').first()
        if very_first_customer is None:
            long_name = settings.REPANIER_SETTINGS_COORDINATOR_NAME
            # short_name is the first word of long_name, limited to max. 25 characters
            short_name = long_name.split(None, 1)[0][:25]
            user = User.objects.filter(username=short_name).order_by('?').first()
            if user is None:
                user = User.objects.create_user(
                    username=short_name,
                    email=settings.REPANIER_SETTINGS_COORDINATOR_EMAIL,
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING, last_name=long_name)
            very_first_customer = Customer.objects.create(
                user=user,
                short_basket_name=short_name,
                long_basket_name=long_name,
                phone1=settings.REPANIER_SETTINGS_COORDINATOR_PHONE,
                represent_this_buyinggroup=False
            )
        return very_first_customer

    def get_admin_date_balance(self):
        return timezone.now().date().strftime(settings.DJANGO_SETTINGS_DATE)

    get_admin_date_balance.short_description = (_("Date balance"))
    get_admin_date_balance.allow_tags = False

    def get_admin_date_joined(self):
        # New customer have no user during import of customers in admin.customer.CustomerResource
        try:
            return self.user.date_joined.strftime(settings.DJANGO_SETTINGS_DATE)
        except User.DoesNotExist: # RelatedObjectDoesNotExist
            return EMPTY_STRING

    get_admin_date_joined.short_description = _("Date joined")
    get_admin_date_joined.allow_tags = False

    def get_admin_balance(self):
        return self.balance + self.get_bank_not_invoiced() - self.get_order_not_invoiced()

    get_admin_balance.short_description = (_("Balance"))
    get_admin_balance.allow_tags = False

    def get_order_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = CustomerInvoice.objects.filter(
                customer_id=self.id,
                status__gte=PERMANENCE_OPENED,
                status__lte=PERMANENCE_SEND,
                customer_charged_id=self.id
            ).order_by('?').aggregate(Sum('total_price_with_tax'), Sum('delta_price_with_tax'), Sum('delta_transport'))
            if result_set["total_price_with_tax__sum"] is not None:
                order_not_invoiced = RepanierMoney(result_set["total_price_with_tax__sum"])
            else:
                order_not_invoiced = REPANIER_MONEY_ZERO
            if result_set["delta_price_with_tax__sum"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_price_with_tax__sum"])
            if result_set["delta_transport__sum"] is not None:
                order_not_invoiced += RepanierMoney(result_set["delta_transport__sum"])
        else:
            order_not_invoiced = REPANIER_MONEY_ZERO
        return order_not_invoiced

    def get_bank_not_invoiced(self):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            result_set = BankAccount.objects.filter(
                customer_id=self.id, customer_invoice__isnull=True
            ).order_by('?').aggregate(Sum('bank_amount_in'), Sum('bank_amount_out'))
            if result_set["bank_amount_in__sum"] is not None:
                bank_in = RepanierMoney(result_set["bank_amount_in__sum"])
            else:
                bank_in = REPANIER_MONEY_ZERO
            if result_set["bank_amount_out__sum"] is not None:
                bank_out = RepanierMoney(result_set["bank_amount_out__sum"])
            else:
                bank_out = REPANIER_MONEY_ZERO
            bank_not_invoiced = bank_in - bank_out
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO
        return bank_not_invoiced

    def get_balance(self):
        last_customer_invoice = CustomerInvoice.objects.filter(
            customer_id=self.id, invoice_sort_order__isnull=False
        ).order_by('?')
        balance = self.get_admin_balance()
        if last_customer_invoice.exists():
            if balance.amount >= 30:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:#32CD32\">{}</span>".format(balance)) + '</a>'
            elif balance.amount >= -10:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:#696969\">{}</span>".format(balance)) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" class="btn" target="_blank" >' + (
                           "<span style=\"color:red\">{}</span>".format(balance)) + '</a>'
        else:
            if balance.amount >= 30:
                return "<span style=\"color:#32CD32\">{}</span>".format(balance)
            elif balance.amount >= -10:
                return "<span style=\"color:#696969\">{}</span>".format(balance)
            else:
                return "<span style=\"color:red\">{}</span>".format(balance)

    get_balance.short_description = _("Balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_html_on_hold_movement(self, bank_not_invoiced=None, order_not_invoiced=None,
                                  total_price_with_tax=REPANIER_MONEY_ZERO):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            bank_not_invoiced = bank_not_invoiced if bank_not_invoiced is not None else self.get_bank_not_invoiced()
            order_not_invoiced = order_not_invoiced if order_not_invoiced is not None else self.get_order_not_invoiced()
            other_order_not_invoiced = order_not_invoiced - total_price_with_tax
        else:
            bank_not_invoiced = REPANIER_MONEY_ZERO
            other_order_not_invoiced = REPANIER_MONEY_ZERO

        if other_order_not_invoiced.amount != DECIMAL_ZERO or bank_not_invoiced.amount != DECIMAL_ZERO:
            if other_order_not_invoiced.amount != DECIMAL_ZERO:
                if bank_not_invoiced.amount == DECIMAL_ZERO:
                    customer_on_hold_movement = \
                        _('This balance does not take account of any unbilled sales %(other_order)s.') % {
                            'other_order': other_order_not_invoiced
                        }
                else:
                    customer_on_hold_movement = \
                        _(
                            'This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s.') \
                        % {
                            'bank': bank_not_invoiced,
                            'other_order': other_order_not_invoiced
                        }
            else:
                customer_on_hold_movement = \
                    _(
                        'This balance does not take account of any unrecognized payments %(bank)s.') % {
                        'bank': bank_not_invoiced
                    }
            customer_on_hold_movement = mark_safe(customer_on_hold_movement)
        else:
            customer_on_hold_movement = EMPTY_STRING

        return customer_on_hold_movement

    def get_last_membership_fee(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE
        ).order_by("-id")
        if last_membership_fee.exists():
            return last_membership_fee.first().selling_price

    get_last_membership_fee.short_description = _("Last membership fee")
    get_last_membership_fee.allow_tags = False

    def last_membership_fee_date(self):
        from repanier.models.purchase import Purchase

        last_membership_fee = Purchase.objects.filter(
            customer_id=self.id,
            offer_item__order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE
        ).order_by("-id").prefetch_related("customer_invoice")
        if last_membership_fee.exists():
            return last_membership_fee.first().customer_invoice.date_balance

    last_membership_fee_date.short_description = _("Last membership fee date")
    last_membership_fee_date.allow_tags = False

    def get_last_membership_fee_date(self):
        # Format it for the admin
        # Don't format it form import/export
        last_membership_fee_date = self.last_membership_fee_date()
        if last_membership_fee_date is not None:
            return last_membership_fee_date.strftime(settings.DJANGO_SETTINGS_DATE)
        return EMPTY_STRING

    get_last_membership_fee_date.short_description = _("Last membership fee date")
    get_last_membership_fee_date.allow_tags = False

    def get_participation(self):
        now = timezone.now()
        return PermanenceBoard.objects.filter(
            customer_id=self.id,
            permanence_date__gte=now - datetime.timedelta(days=ONE_YEAR),
            permanence_date__lt=now,
            permanence_role__is_counted_as_participation=True
        ).order_by('?').count()

    get_participation.short_description = _("Participation")
    get_participation.allow_tags = False

    def get_purchase(self):
        now = timezone.now()
        # Do not count invoice having only products free of charge
        return CustomerInvoice.objects.filter(
            customer_id=self.id,
            total_price_with_tax__gt=DECIMAL_ZERO,
            date_balance__gte=now - datetime.timedelta(ONE_YEAR)
        ).count()

    get_purchase.short_description = _("Purchase")
    get_purchase.allow_tags = False

    def my_order_confirmation_email_send_to(self):
        if self.email2:
            to_email = (self.user.email, self.email2)
        else:
            to_email = (self.user.email,)
        sent_to = ", ".join(to_email) if to_email is not None else EMPTY_STRING
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            msg_confirmation = _(
                "Order confirmed. An email containing this order summary has been sent to {}.").format(sent_to)
        else:
            msg_confirmation = _("An email containing this order summary has been sent to {}.").format(sent_to)
        return msg_confirmation

    @property
    def who_is_who_display(self):
        return self.picture or self.show_mails_to_members or self.show_phones_to_members \
               or (self.about_me is not None and len(self.about_me.strip()) > 1)

    def get_html_unsubscribe_mail_footer(self):
        return mark_safe(
            "<br><br><hr/><br><a href=\"{}\">{}</a>".format(
                self._get_unsubscribe_link(),
                _("Stop receiving unsolicited mails from {}").format(self._get_unsubscribe_site())
            )
        )

    def _get_unsubscribe_link(self):
        customer_id, token = self.make_token().split(":", 1)
        return "https://{}{}".format(
            self._get_unsubscribe_site(),
            reverse(
                'unsubscribe_view',
                kwargs={'customer_id': customer_id, 'token': token, }
            )
        )

    def _get_unsubscribe_site(self):
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
        if self.represent_this_buyinggroup:
            if not also_group:
                return
            self.short_basket_name = "{}-{}".format(_("GROUP"), self.id).lower()
            self.long_basket_name = "{} {}".format(_("Group"), self.id)
        else:
            self.short_basket_name = "{}-{}".format(_("BASKET"), self.id).lower()
            self.long_basket_name = "{} {}".format(_("Family"), self.id)
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
        self.user.username = self.user.email = "{}@repanier.be".format(self.short_basket_name)
        self.user.first_name = EMPTY_STRING
        self.user.last_name = self.short_basket_name
        self.user.set_password(None)
        self.user.save()
        self.is_anonymized = True
        self.valid_email = False
        self.subscribe_to_email = False
        self.show_mails_to_members = False
        self.show_phones_to_members = False
        self.save()

    def __str__(self):
        if self.delivery_point is None:
            return self.short_basket_name
        else:
            return "{} - {}".format(self.delivery_point, self.short_basket_name)

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ("-represent_this_buyinggroup", "short_basket_name",)
        indexes = [
            models.Index(fields=["-represent_this_buyinggroup", "short_basket_name"], name='customer_order_idx'),
        ]


@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, **kwargs):
    customer = kwargs["instance"]

    if customer.represent_this_buyinggroup:
        # The buying group may not be de activated
        customer.is_active = True
        customer.is_group = False
    if customer.email2 is not None:
        customer.email2 = customer.email2.lower()
    if customer.vat_id is not None and len(customer.vat_id.strip()) == 0:
        customer.vat_id = None
    if customer.bank_account1 is not None and len(customer.bank_account1.strip()) == 0:
        customer.bank_account1 = None
    if customer.bank_account1:
        # Prohibit to have two customers with same bank account
        other_bank_account1 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account1) | Q(bank_account2=customer.bank_account1)
        ).order_by("?")
        if customer.id is not None:
            other_bank_account1 = other_bank_account1.exclude(id=customer.id)
        if other_bank_account1.exists():
            customer.bank_account1 = None
    if customer.bank_account2 is not None and len(customer.bank_account2.strip()) == 0:
        customer.bank_account2 = None
    if customer.bank_account2:
        # Prohibit to have two customers with same bank account
        other_bank_account2 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account2) | Q(bank_account2=customer.bank_account2)
        ).order_by("?")
        if customer.id is not None:
            other_bank_account2 = other_bank_account2.exclude(id=customer.id)
        if other_bank_account2.exists():
            customer.bank_account2 = None
    if not customer.is_active:
        customer.may_order = False
    if settings.REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE and customer.price_list_multiplier <= DECIMAL_ZERO:
        customer.price_list_multiplier = DECIMAL_ONE
    customer.city = ("{}".format(customer.city).upper())
    customer.login_attempt_counter = DECIMAL_ZERO
    customer.valid_email = None


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs["instance"]
    user = customer.user
    if user is not None and user.id is not None:
        user.delete()
