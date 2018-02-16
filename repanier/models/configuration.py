# -*- coding: utf-8
from cms.toolbar_pool import toolbar_pool
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.db.models.signals import post_save, pre_save, post_init
from django.dispatch import receiver
from django.template import Template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField


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
    send_order_mail_to_board = models.BooleanField(
        _("Send an order distribution email to members registered for a task"), default=True)
    send_invoice_mail_to_customer = models.BooleanField(_("Send invoice mail to customers"), default=True)
    send_invoice_mail_to_producer = models.BooleanField(_("Send invoice mail to producers"), default=False)
    invoice = models.BooleanField(_("Enable accounting module"), default=True)
    display_anonymous_order_form = models.BooleanField(
        _("Allow the anonymous visitor to see the customer order screen"), default=True)
    display_producer_on_order_form = models.BooleanField(
        _("Display the list of producers in the customer order screen"), default=True)
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
    db_version = models.PositiveSmallIntegerField(default=0)
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
        cancel_order_customer_mail=HTMLField(
            _("Content of the email in case of cancellation of the order sent to the consumers concerned"),
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

    @classmethod
    def init_repanier(cls):
        from repanier.const import DECIMAL_ONE, PERMANENCE_NAME_PERMANENCE, CURRENCY_EUR
        from repanier.models.producer import Producer
        from repanier.models.bankaccount import BankAccount
        from repanier.models.staff import Staff
        from repanier.models.customer import Customer

        # Create the configuration record managed via the admin UI
        config = Configuration.objects.filter(id=DECIMAL_ONE).first()
        if config is not None:
            return config
        group_name = settings.DJANGO_SETTINGS_GROUP_NAME
        site = Site.objects.get_current()
        if site is not None:
            site.name = group_name
            site.domain = group_name
            site.save()
        config = Configuration.objects.create(
            group_name=group_name,
            name=PERMANENCE_NAME_PERMANENCE,
            bank_account="BE99 9999 9999 9999",
            currency=CURRENCY_EUR
        )
        config.init_email()
        config.save()
        
        # Create firsts users
        Producer.get_or_create_group()
        customer_buyinggroup = Customer.get_or_create_group()
        very_first_customer = Customer.get_or_create_the_very_first_customer()

        BankAccount.open_account(
            customer_buyinggroup=customer_buyinggroup,
            very_first_customer=very_first_customer
        )

        coordinator = Staff.get_or_create_any_coordinator()
        Staff.get_or_create_order_responsible()
        Staff.get_or_create_invoice_responsible()
        # Create and publish first web page
        if not coordinator.is_webmaster:
            # This should not be the case...
            return

        from cms.models import StaticPlaceholder
        from cms.constants import X_FRAME_OPTIONS_DENY
        from cms import api
        page = api.create_page(
            title=_("Home"),
            soft_root=True,
            template=settings.CMS_TEMPLATE_HOME,
            language=settings.LANGUAGE_CODE,
            published=True,
            parent=None,
            xframe_options=X_FRAME_OPTIONS_DENY,
            in_navigation=True
        )
        page.set_as_homepage()
        placeholder = page.placeholders.get(slot="home-hero")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type='TextPlugin',
            language=settings.LANGUAGE_CODE,
            body='hello world 1')
        placeholder = page.placeholders.get(slot="home-col-1")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type='TextPlugin',
            language=settings.LANGUAGE_CODE,
            body='hello world 2')
        placeholder = page.placeholders.get(slot="home-col-2")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type='TextPlugin',
            language=settings.LANGUAGE_CODE,
            body='hello world 3')
        placeholder = page.placeholders.get(slot="home-col-3")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type='TextPlugin',
            language=settings.LANGUAGE_CODE,
            body='hello world 4')
        # static_placeholder = StaticPlaceholder(code=str(uuid.uuid4()), site_id=1)
        # static_placeholder.save()
        # add_plugin(static_placeholder.draft, "TextPlugin", lang, body="example content")
        static_placeholder = StaticPlaceholder(
            code="footer",
            # site_id=1
        )
        static_placeholder.save()
        api.add_plugin(
            placeholder=static_placeholder.draft,
            plugin_type='TextPlugin',
            language=settings.LANGUAGE_CODE,
            body='hello footer world'
        )
        # TODO : Check why this doesn't pubish the static placeholder. Try with a superuser.
        api.publish_page(
            page=page,
            user=coordinator.user,
            language=settings.LANGUAGE_CODE)

        return config

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

    def upgrade_db(self):
        if self.db_version == 0:
            from repanier.models import Product, OfferItemWoReceiver, BankAccount, Permanence, Staff
            # Staff.objects.rebuild()
            Product.objects.filter(
                is_box=True
            ).order_by('?').update(
                limit_order_quantity_to_stock=True
            )
            OfferItemWoReceiver.objects.filter(
                permanence__status__gte=PERMANENCE_SEND,
                order_unit=PRODUCT_ORDER_UNIT_PC_KG
            ).order_by('?').update(
                use_order_unit_converted=True
            )
            for bank_account in BankAccount.objects.filter(
                    permanence__isnull=False,
                    producer__isnull=True,
                    customer__isnull=True
            ).order_by('?').only("id", "permanence_id"):
                Permanence.objects.filter(
                    id=bank_account.permanence_id,
                    invoice_sort_order__isnull=True
                ).order_by('?').update(invoice_sort_order=bank_account.id)
            for permanence in Permanence.objects.filter(
                    status__in=[PERMANENCE_CANCELLED, PERMANENCE_ARCHIVED],
                    invoice_sort_order__isnull=True
            ).order_by('?'):
                bank_account = BankAccount.get_closest_to(permanence.permanence_date)
                if bank_account is not None:
                    permanence.invoice_sort_order = bank_account.id
                    permanence.save(update_fields=['invoice_sort_order'])
            Staff.objects.order_by('?').update(
                is_order_manager=F('is_reply_to_order_email'),
                is_invoice_manager=F('is_reply_to_invoice_email'),
                is_order_referent=F('is_contributor')
            )
            self.db_version = 1
        if self.db_version == 1:
            User.objects.filter(is_staff=False).order_by('?').update(
                first_name=EMPTY_STRING,
                last_name=F('username')[:30]
            )
            User.objects.filter(is_staff=True, is_superuser=False).order_by('?').update(
                first_name=EMPTY_STRING,
                last_name=F('email')[:30]
            )
            self.db_version = 2

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

    config = kwargs["instance"]
    if config.id is not None:
        repanier.apps.REPANIER_SETTINGS_CONFIG = config
        if settings.DJANGO_SETTINGS_TEST_MODE:
            repanier.apps.REPANIER_SETTINGS_TEST_MODE = config.test_mode
        else:
            repanier.apps.REPANIER_SETTINGS_TEST_MODE = False
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

        menu_pool.clear()
        toolbar_pool.unregister(repanier.cms_toolbar.RepanierToolbar)
        toolbar_pool.register(repanier.cms_toolbar.RepanierToolbar)
        cache.clear()
