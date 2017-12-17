# -*- coding: utf-8

import datetime
import uuid

from cms.toolbar_pool import toolbar_pool
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save, pre_save, post_init
from django.dispatch import receiver
from django.template import Template
from django.utils import timezone
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.product import Product


class Configuration(TranslatableModel):
    group_name = models.CharField(_("Name of the group"), max_length=50, default=EMPTY_STRING)
    test_mode = models.BooleanField(_("Test mode"), default=False)
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None)
    name = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_NAME,
        default=PERMANENCE_NAME_PERMANENCE,
        verbose_name=_("Offers name"))
    currency = models.CharField(
        max_length=3,
        choices=LUT_CURRENCY,
        default=CURRENCY_EUR,
        verbose_name=_("Currency"))
    max_week_wo_participation = models.DecimalField(
        _("Alert the customer after this number of weeks without participation"),
        help_text=_("0 mean : never display a pop up."),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0,
        validators=[MinValueValidator(0)])
    send_abstract_order_mail_to_customer = models.BooleanField(_("Send abstract order mail to customers"),
                                                               default=False)
    send_abstract_order_mail_to_producer = models.BooleanField(_("Send abstract order mail to producers"),
                                                               default=False)
    send_order_mail_to_board = models.BooleanField(_("Send an order distribution email to members registered for a task"), default=True)
    send_invoice_mail_to_customer = models.BooleanField(_("Send invoice mail to customers"), default=True)
    send_invoice_mail_to_producer = models.BooleanField(_("Send invoice mail to producers"), default=False)
    invoice = models.BooleanField(_("Enable accounting module"), default=True)
    display_anonymous_order_form = models.BooleanField(_("Allow the anonymous visitor to see the customer order screen"), default=True)
    display_producer_on_order_form = models.BooleanField(_("Display the list of producers in the customer order screen"), default=True)
    display_who_is_who = models.BooleanField(_("Display the \"who's who\""), default=True)
    xlsx_portrait = models.BooleanField(_("Always generate XLSX files in portrait mode"), default=False)
    bank_account = models.CharField(_("Bank account"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    vat_id = models.CharField(
        _("VAT id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    page_break_on_customer_check = models.BooleanField(_("Page break on customer check"), default=False)
    sms_gateway_mail = models.EmailField(
        _("Sms gateway email"),
        help_text=_(
            "To actually send sms, use for e.g. on a GSM : https://play.google.com/store/apps/details?id=eu.apksoft.android.smsgateway"),
        max_length=50, null=True, blank=True, default=EMPTY_STRING)
    customers_must_confirm_orders = models.BooleanField(_("⚠ Customers must confirm orders"), default=False)
    membership_fee = ModelMoneyField(
        _("Membership fee"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    membership_fee_duration = models.DecimalField(
        _("Membership fee duration"),
        help_text=_("Number of month(s). 0 mean : no membership fee."),
        default=DECIMAL_ZERO, max_digits=3, decimal_places=0,
        validators=[MinValueValidator(0)])
    home_site = models.URLField(_("Home site"), null=True, blank=True, default=EMPTY_STRING)
    permanence_of_last_cancelled_invoice = models.ForeignKey(
        'Permanence',
        on_delete=models.PROTECT, blank=True, null=True)
    transport = ModelMoneyField(
        _("Shipping cost"),
        help_text=_("This amount is added to order less than min_transport."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    min_transport = ModelMoneyField(
        _("Minium order amount for free shipping cost"),
        help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    email_is_custom = models.BooleanField(
        _("Email is customised"), default=False)
    email_host = models.CharField(
        _("Email host"),
        help_text=_("For @gmail.com, see: https://mail.google.com/mail/u/0/#settings/fwdandpop and activate POP"),
        max_length=50, null=True, blank=True, default="smtp.gmail.com")
    email_port = models.IntegerField(
        _("Email port"),
        help_text=_("Usually 587 for @gmail.com, otherwise 25"),
        blank=True, null=True,
        default=587)
    email_use_tls = models.BooleanField(
        _("Email use tls"),
        help_text=_("TLS is used otherwise SSL is used"),
        default=True
    )
    email_host_user = models.EmailField(
        _("Email host user"),
        help_text=_("For @gmail.com : username@gmail.com"),
        max_length=50, null=True, blank=True, default="username@gmail.com")
    email_host_password = models.CharField(
        _("Email host password"),
        help_text=_(
            "For @gmail.com, you must generate an application password, see: https://security.google.com/settings/security/apppasswords"),
        max_length=25, null=True, blank=True, default=EMPTY_STRING)
    translations = TranslatedFields(
        group_label=models.CharField(_("Label to mention on the invoices of the group"),
                                     max_length=100,
                                     default=EMPTY_STRING,
                                     blank=True),
        how_to_register=HTMLField(_("How to register"),
                                  help_text=EMPTY_STRING,
                                  configuration='CKEDITOR_SETTINGS_MODEL2',
                                  default=EMPTY_STRING,
                                  blank=True),
        offer_customer_mail=HTMLField(_("Contents of the order opening email sent to consumers authorized to order"),
                                      help_text=EMPTY_STRING,
                                      configuration='CKEDITOR_SETTINGS_MODEL2',
                                      default=EMPTY_STRING,
                                      blank=True),
        offer_producer_mail=HTMLField(_("Email content"),
                                      help_text=EMPTY_STRING,
                                      configuration='CKEDITOR_SETTINGS_MODEL2',
                                      default=EMPTY_STRING,
                                      blank=True),
        order_customer_mail=HTMLField(_("Content of the order confirmation email sent to the consumers concerned"),
                                      help_text=EMPTY_STRING,
                                      configuration='CKEDITOR_SETTINGS_MODEL2',
                                      default=EMPTY_STRING,
                                      blank=True),
        cancel_order_customer_mail=HTMLField(_("Content of the email in case of cancellation of the order sent to the consumers concerned"),
                                             help_text=EMPTY_STRING,
                                             configuration='CKEDITOR_SETTINGS_MODEL2',
                                             default=EMPTY_STRING,
                                             blank=True),
        order_staff_mail=HTMLField(_("Content of the order distribution email sent to the members enrolled to a task"),
                                   help_text=EMPTY_STRING,
                                   configuration='CKEDITOR_SETTINGS_MODEL2',
                                   default=EMPTY_STRING,
                                   blank=True),
        order_producer_mail=HTMLField(_("Content of the order confirmation email sent to the producers concerned"),
                                      help_text=EMPTY_STRING,
                                      configuration='CKEDITOR_SETTINGS_MODEL2',
                                      default=EMPTY_STRING,
                                      blank=True),
        invoice_customer_mail=HTMLField(_("Content of the invoice confirmation email sent to the customers concerned"),
                                        help_text=EMPTY_STRING,
                                        configuration='CKEDITOR_SETTINGS_MODEL2',
                                        default=EMPTY_STRING,
                                        blank=True),
        invoice_producer_mail=HTMLField(_("Content of the payment confirmation email sent to the producers concerned"),
                                        help_text=EMPTY_STRING,
                                        configuration='CKEDITOR_SETTINGS_MODEL2',
                                        default=EMPTY_STRING,
                                        blank=True),
    )

    def clean(self):
        try:
            template = Template(self.offer_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.offer_customer_mail, error_str)))
        try:
            template = Template(self.offer_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.offer_producer_mail, error_str)))
        try:
            template = Template(self.order_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.order_customer_mail, error_str)))
        try:
            template = Template(self.order_staff_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.order_staff_mail, error_str)))
        try:
            template = Template(self.order_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.order_producer_mail, error_str)))
        try:
            template = Template(self.invoice_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.invoice_customer_mail, error_str)))
        try:
            template = Template(self.invoice_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("{} : {}".format(self.invoice_producer_mail, error_str)))

    def init_email(self):
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            self.set_current_language(language_code)
            try:
                self.offer_customer_mail = """
                    Bonjour,<br />
                    <br />
                    Les commandes de la {{ permanence_link }} sont maintenant ouvertes auprès de : {{ offer_producer }}.<br />
                    {% if offer_description %}<br />{{ offer_description }}<br />
                    {% endif %} {% if offer_recent_detail %}<br />
                    Nouveauté(s) :<br />
                    {{ offer_recent_detail }}{% endif %}<br />
                    <br />
                    {{ signature }}
                    """
                self.offer_producer_mail = """
                    Cher/Chère {{ long_profile_name }},<br>
                    <br>
                    {% if offer_description != "" %}Voici l'annonce consommateur :<br>
                    {{ offer_description }}<br>
                    <br>
                    {% endif %} Veuillez vérifier votre <strong>{{ offer_link }}</strong>.<br>
                    <br>
                    {{ signature }}
                    """
                self.order_customer_mail = """
                    Bonjour {{ long_basket_name }},<br>
                    <br>
                    En pièce jointe vous trouverez le montant de votre panier {{ short_basket_name }} de la {{ permanence_link }}.<br>
                    <br>
                    {{ last_balance }}<br>
                    {{ order_amount }}<br>
                    {% if on_hold_movement %}{{ on_hold_movement }}<br>
                    {% endif %} {% if payment_needed %}{{ payment_needed }}<br>
                    {% endif %}<br>
                    <br>
                    {{ signature }}
                    """
                self.cancel_order_customer_mail = """
                    Bonjour {{ long_basket_name }},<br>
                    <br>
                    La commande ci-jointe de votre panier {{ short_basket_name }} de la {{ permanence_link }} <b>a été annulée</b> car vous ne l'avez pas confirmée.<br>
                    <br>
                    {{ signature }}
                    """
                self.order_staff_mail = """
                    Cher/Chère membre de l'équipe de préparation,<br>
                    <br>
                    En pièce jointe vous trouverez la liste de préparation pour la {{ permanence_link }}.<br>
                    <br>
                    L'équipe de préparation est composée de :<br>
                    {{ board_composition_and_description }}<br>
                    <br>
                    {{ signature }}
                    """
                self.order_producer_mail = """
                    Cher/Chère {{ name }},<br>
                    <br>
                    {% if order_empty %}Le groupe ne vous a rien acheté pour la {{ permanence_link }}.{% else %}En pièce jointe, vous trouverez la commande du groupe pour la {{ permanence }}.{% if duplicate %}<br>
                    <strong>ATTENTION </strong>: La commande est présente en deux exemplaires. Le premier exemplaire est classé par produit et le duplicata est classé par panier.{% else %}{% endif %}{% endif %}<br>
                    <br>
                    {{ signature }}
                    """
                self.invoice_customer_mail = """
                    Bonjour {{ name }},<br>
                    <br>
                    En cliquant sur ce lien vous trouverez votre facture pour la {{ permanence_link }}.{% if invoice_description %}<br>
                    <br>
                    {{ invoice_description }}{% endif %}
                    <br>
                    {{ order_amount }}<br>
                    {{ last_balance_link }}<br>
                    {% if payment_needed %}{{ payment_needed }}<br>
                    {% endif %}<br>
                    <br>
                    {{ signature }}
                    """
                self.invoice_producer_mail = """
                    Cher/Chère {{ profile_name }},<br>
                    <br>
                    En cliquant sur ce lien vous trouverez le détail de notre paiement pour la {{ permanence_link }}.<br>
                    <br>
                    {{ signature }}
                    """
                self.save_translations()
            except TranslationDoesNotExist:
                pass

    def __str__(self):
        return self.group_name

    class Meta:
        verbose_name = _("Configuration")
        verbose_name_plural = _("Configurations")


@receiver(post_init, sender=Configuration)
def configuration_post_init(sender, **kwargs):
    config = kwargs["instance"]
    if config.id is not None:
        config.previous_email_host_password = config.email_host_password
    else:
        config.previous_email_host_password = EMPTY_STRING
    config.email_host_password = EMPTY_STRING


@receiver(pre_save, sender=Configuration)
def configuration_pre_save(sender, **kwargs):
    config = kwargs["instance"]
    if not config.bank_account:
        config.bank_account = None
    if config.email_is_custom and not config.email_host_password:
        config.email_host_password = config.previous_email_host_password


@receiver(post_save, sender=Configuration)
def configuration_post_save(sender, **kwargs):
    import repanier.cms_toolbar
    from repanier.models.bankaccount import BankAccount
    from repanier.models.producer import Producer
    from repanier.models.customer import Customer

    config = kwargs["instance"]
    if config.id is not None:
        repanier.apps.REPANIER_SETTINGS_CONFIG = config
        repanier.apps.REPANIER_SETTINGS_TEST_MODE = config.test_mode
        site = Site.objects.get_current()
        if site is not None:
            site.name = config.group_name
            site.domain = settings.ALLOWED_HOSTS[0]
            site.save()
        repanier.apps.REPANIER_SETTINGS_GROUP_NAME = config.group_name
        if config.name == PERMANENCE_NAME_PERMANENCE:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Permanence")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Permanences")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Permanence of ")
        elif config.name == PERMANENCE_NAME_CLOSURE:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Closure")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Closures")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Closure of ")
        elif config.name == PERMANENCE_NAME_DELIVERY:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Delivery")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Deliveries")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Delivery of ")
        elif config.name == PERMANENCE_NAME_ORDER:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Order")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Orders")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Order of ")
        elif config.name == PERMANENCE_NAME_OPENING:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Opening")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Openings")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Opening of ")
        else:
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Distribution")
            repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Distributions")
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Distribution of ")
        repanier.apps.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = config.max_week_wo_participation
        repanier.apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = config.send_abstract_order_mail_to_customer
        repanier.apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER = config.send_abstract_order_mail_to_producer
        repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = config.send_order_mail_to_board
        repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = config.send_invoice_mail_to_customer
        repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = config.send_invoice_mail_to_producer
        repanier.apps.REPANIER_SETTINGS_INVOICE = config.invoice
        repanier.apps.REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = config.display_anonymous_order_form
        repanier.apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM = config.display_producer_on_order_form
        repanier.apps.REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO = config.display_who_is_who
        repanier.apps.REPANIER_SETTINGS_XLSX_PORTRAIT = config.xlsx_portrait
        if config.bank_account is not None and len(config.bank_account.strip()) == 0:
            repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT = None
        else:
            repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT = config.bank_account
        if config.vat_id is not None and len(config.vat_id.strip()) == 0:
            repanier.apps.REPANIER_SETTINGS_VAT_ID = None
        else:
            repanier.apps.REPANIER_SETTINGS_VAT_ID = config.vat_id
        repanier.apps.REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = config.page_break_on_customer_check
        repanier.apps.REPANIER_SETTINGS_SMS_GATEWAY_MAIL = config.sms_gateway_mail
        repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS = config.customers_must_confirm_orders
        repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE = config.membership_fee
        repanier.apps.REPANIER_SETTINGS_MEMBERSHIP_FEE_DURATION = config.membership_fee_duration
        if config.currency == CURRENCY_LOC:
            repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY = "✿"
            repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT = False
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX = "_ ✿ * #,##0.00_ ;_ ✿ * -#,##0.00_ ;_ ✿ * \"-\"??_ ;_ @_ "
        elif config.currency == CURRENCY_CHF:
            repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY = 'Fr.'
            repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT = False
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX = "_ Fr\. * #,##0.00_ ;_ Fr\. * -#,##0.00_ ;_ Fr\. * \"-\"??_ ;_ @_ "
        else:
            repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY = "€"
            repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT = True
            repanier.apps.REPANIER_SETTINGS_CURRENCY_XLSX = "_ € * #,##0.00_ ;_ € * -#,##0.00_ ;_ € * \"-\"??_ ;_ @_ "
        if config.home_site is not None and len(config.home_site.strip()) == 0:
            repanier.apps.REPANIER_SETTINGS_HOME_SITE = "/"
        else:
            repanier.apps.REPANIER_SETTINGS_HOME_SITE = config.home_site
        repanier.apps.REPANIER_SETTINGS_TRANSPORT = config.transport
        repanier.apps.REPANIER_SETTINGS_MIN_TRANSPORT = config.min_transport

        bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by('?').first()
        if bank_account is None:
            # If not latest total exists, create it with operation date before all movements
            bank_account = BankAccount.objects.all().order_by("operation_date").first()
            if bank_account is None:
                BankAccount.objects.create(operation_status=BANK_LATEST_TOTAL,
                                           operation_date=timezone.now().date(),
                                           operation_comment=_("Account opening"))
            else:
                if bank_account.producer is None and bank_account.customer is None:
                    bank_account.operation_status = BANK_LATEST_TOTAL
                    bank_account.save(update_fields=['operation_status'])
                else:
                    BankAccount.objects.create(operation_status=BANK_LATEST_TOTAL,
                                               operation_date=bank_account.operation_date + datetime.timedelta(
                                                   days=-1),
                                               operation_comment=_("Account opening"))

        producer_buyinggroup = Producer.objects.filter(represent_this_buyinggroup=True).order_by('?').first()
        if producer_buyinggroup is None:
            producer_buyinggroup = Producer.objects.create(
                short_profile_name="z-{}".format(repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
                long_profile_name=repanier.apps.REPANIER_SETTINGS_GROUP_NAME,
                represent_this_buyinggroup=True
            )
        if producer_buyinggroup is not None:
            # Create this to also prevent the deletion of the producer representing the buying group
            membership_fee_product = Product.objects.filter(
                order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
                is_active=True
            ).order_by('?').first()
            if membership_fee_product is None:
                membership_fee_product = Product.objects.create(
                    producer_id=producer_buyinggroup.id,
                    order_unit=PRODUCT_ORDER_UNIT_MEMBERSHIP_FEE,
                    vat_level=VAT_100
                )
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)
                membership_fee_product.set_current_language(language_code)
                membership_fee_product.long_name = "{}".format(_("Membership fee"))
                membership_fee_product.save()
            translation.activate(cur_language)
        repanier.apps.REPANIER_SETTINGS_GROUP_PRODUCER_ID = producer_buyinggroup.id

        customer_buyinggroup = Customer.objects.filter(represent_this_buyinggroup=True).order_by('?').first()
        if customer_buyinggroup is None:
            user = User.objects.create_user(
                username="z-{}".format(repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
                email="{}{}".format(
                    repanier.apps.REPANIER_SETTINGS_GROUP_NAME, settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION),
                password=uuid.uuid1().hex,
                first_name=EMPTY_STRING, last_name=repanier.apps.REPANIER_SETTINGS_GROUP_NAME)
            customer_buyinggroup = Customer.objects.create(
                user=user,
                short_basket_name="z-{}".format(repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
                long_basket_name=repanier.apps.REPANIER_SETTINGS_GROUP_NAME,
                phone1='0499/96.64.32',
                represent_this_buyinggroup=True
            )
        repanier.apps.REPANIER_SETTINGS_GROUP_CUSTOMER_ID = customer_buyinggroup.id

        if not BankAccount.objects.filter(customer=customer_buyinggroup).order_by('?').exists():
            # Create this to also prevent the deletion of the customer representing the buying group
            BankAccount.objects.create(operation_date=timezone.now().date(),
                                       customer=customer_buyinggroup,
                                       operation_comment=_("Initial balance"))

        menu_pool.clear()
        toolbar_pool.unregister(repanier.cms_toolbar.RepanierToolbar)
        toolbar_pool.register(repanier.cms_toolbar.RepanierToolbar)
        cache.clear()
