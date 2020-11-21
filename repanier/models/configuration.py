import logging

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.template import Template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField

logger = logging.getLogger(__name__)


class Configuration(TranslatableModel):
    group_name = models.CharField(
        _("Name of the group"),
        max_length=50,
        default=settings.REPANIER_SETTINGS_GROUP_NAME,
    )
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"), default=DECIMAL_ZERO, max_digits=2, decimal_places=0
    )
    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None
    )
    name = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_NAME,
        default=PERMANENCE_NAME_PERMANENCE,
        verbose_name=_("Offers name"),
    )
    currency = models.CharField(
        max_length=3,
        choices=LUT_CURRENCY,
        default=CURRENCY_EUR,
        verbose_name=_("Currency"),
    )
    max_week_wo_participation = models.DecimalField(
        _("Alert the customer after this number of weeks without participation"),
        help_text=_("0 mean : never display a pop up."),
        default=DECIMAL_ZERO,
        max_digits=2,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    send_abstract_order_mail_to_customer = models.BooleanField(
        _("Send abstract order mail to customers"), default=False
    )
    send_order_mail_to_board = models.BooleanField(
        _("Send an order distribution email to members registered for a task"),
        default=True,
    )
    send_invoice_mail_to_customer = models.BooleanField(
        _("Send invoice mail to customers"), default=True
    )
    send_invoice_mail_to_producer = models.BooleanField(
        _("Send invoice mail to producers"), default=False
    )
    invoice = models.BooleanField(_("Enable accounting module"), default=True)
    display_anonymous_order_form = models.BooleanField(
        _("Allow the anonymous visitor to see the customer order screen"), default=True
    )
    display_who_is_who = models.BooleanField(
        _('Display the "who\'s who"'), default=True
    )
    xlsx_portrait = models.BooleanField(
        _("Always generate XLSX files in portrait mode"), default=False
    )
    bank_account = models.CharField(
        _("Bank account"), max_length=100, blank=True, default=EMPTY_STRING
    )
    vat_id = models.CharField(
        _("VAT id"), max_length=20, blank=True, default=EMPTY_STRING
    )
    page_break_on_customer_check = models.BooleanField(
        _("Page break on customer check"), default=False
    )
    membership_fee = ModelMoneyField(
        _("Membership fee"), default=DECIMAL_ZERO, max_digits=8, decimal_places=2
    )
    membership_fee_duration = models.DecimalField(
        _("Membership fee duration"),
        help_text=_("Number of month(s). 0 mean : no membership fee."),
        default=DECIMAL_ZERO,
        max_digits=3,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    home_site = models.URLField(_("Home site"), blank=True, default="/")
    permanence_of_last_cancelled_invoice = models.ForeignKey(
        "Permanence", on_delete=models.PROTECT, blank=True, null=True
    )
    translations = TranslatedFields(
        group_label=models.CharField(
            _("Label to mention on the invoices of the group"),
            max_length=100,
            default=EMPTY_STRING,
            blank=True,
        ),
        how_to_register=HTMLField(
            _("How to register"),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        offer_customer_mail=HTMLField(
            _(
                "Contents of the order opening email sent to consumers authorized to order"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        order_customer_mail=HTMLField(
            _(
                "Content of the order confirmation email sent to the consumers concerned"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        cancel_order_customer_mail=HTMLField(
            _(
                "Content of the email in case of cancellation of the order sent to the consumers concerned"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        order_staff_mail=HTMLField(
            _(
                "Content of the order distribution email sent to the members enrolled to a task"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        order_producer_mail=HTMLField(
            _(
                "Content of the order confirmation email sent to the producers concerned"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        invoice_customer_mail=HTMLField(
            _(
                "Content of the invoice confirmation email sent to the customers concerned"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
        invoice_producer_mail=HTMLField(
            _(
                "Content of the payment confirmation email sent to the producers concerned"
            ),
            help_text=EMPTY_STRING,
            configuration="CKEDITOR_SETTINGS_MODEL2",
            default=EMPTY_STRING,
            blank=True,
        ),
    )

    def clean(self):
        try:
            template = Template(self.offer_customer_mail)
        except Exception as error_str:
            raise ValidationError(
                mark_safe("{} : {}".format(self.offer_customer_mail, error_str))
            )
        try:
            template = Template(self.order_customer_mail)
        except Exception as error_str:
            raise ValidationError(
                mark_safe("{} : {}".format(self.order_customer_mail, error_str))
            )
        try:
            template = Template(self.order_staff_mail)
        except Exception as error_str:
            raise ValidationError(
                mark_safe("{} : {}".format(self.order_staff_mail, error_str))
            )
        try:
            template = Template(self.order_producer_mail)
        except Exception as error_str:
            raise ValidationError(
                mark_safe("{} : {}".format(self.order_producer_mail, error_str))
            )
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            try:
                template = Template(self.invoice_customer_mail)
            except Exception as error_str:
                raise ValidationError(
                    mark_safe("{} : {}".format(self.invoice_customer_mail, error_str))
                )
            try:
                template = Template(self.invoice_producer_mail)
            except Exception as error_str:
                raise ValidationError(
                    mark_safe("{} : {}".format(self.invoice_producer_mail, error_str))
                )

    @classmethod
    def init_repanier(cls):
        from repanier.const import DECIMAL_ONE, PERMANENCE_NAME_PERMANENCE, CURRENCY_EUR

        site = Site.objects.get_current()
        if site is not None:
            site.name = settings.REPANIER_SETTINGS_GROUP_NAME
            site.domain = settings.ALLOWED_HOSTS[0]
            site.save()

        cls.init_webmaster_group()

        # Create the configuration record managed via the admin UI
        config = Configuration.objects.filter(id=DECIMAL_ONE).first()
        if config is None:
            config = Configuration.objects.create(
                group_name=settings.REPANIER_SETTINGS_GROUP_NAME,
                name=PERMANENCE_NAME_PERMANENCE,
                bank_account="BE99 9999 9999 9999",
                currency=CURRENCY_EUR,
            )
            config.init_email()
            config.save()

            coordinator = cls.init_firsts_users()
            cls.init_home_page(coordinator)
            cls.init_department()
        else:
            # Perform configuration_post_save
            config.save()

        return config

    @classmethod
    def init_webmaster_group(cls):
        # Create WEBMASTER group with correct rights
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        webmaster_group = (
            Group.objects.filter(name=WEBMASTER_GROUP).only("id").order_by("?").first()
        )
        if webmaster_group is None:
            webmaster_group = Group.objects.create(name=WEBMASTER_GROUP)
        content_types = (
            ContentType.objects.exclude(
                app_label__in=[
                    "repanier",
                    "admin",
                    "auth",
                    "contenttypes",
                    "menus",
                    "reversion",
                    "sessions",
                    "sites",
                ]
            )
            .only("id")
            .order_by("?")
        )
        permissions = (
            Permission.objects.filter(content_type__in=content_types)
            .only("id")
            .order_by("?")
        )
        webmaster_group.permissions.set(permissions)

    @classmethod
    def init_firsts_users(cls):
        # Create firsts users

        from repanier.models.producer import Producer
        from repanier.models.bankaccount import BankAccount
        from repanier.models.staff import Staff
        from repanier.models.customer import Customer

        Producer.get_or_create_default()
        customer_buyinggroup = Customer.get_or_create_default()
        BankAccount.open_account(customer_buyinggroup=customer_buyinggroup)
        coordinator = Staff.get_or_create_any_coordinator()
        Staff.get_or_create_order_responsible()
        Staff.get_or_create_invoice_responsible()
        return coordinator

    @classmethod
    def init_home_page(cls, coordinator):
        # Create and publish first web page

        from cms.models import StaticPlaceholder
        from cms.constants import X_FRAME_OPTIONS_DENY
        from cms import api
        from django.contrib.auth.models import Group

        page = api.create_page(
            title=_("Home"),
            soft_root=False,
            template=settings.CMS_TEMPLATE_HOME,
            language=settings.LANGUAGE_CODE,
            published=False,
            parent=None,
            xframe_options=X_FRAME_OPTIONS_DENY,
            in_navigation=True,
        )
        page.set_as_homepage()
        placeholder = page.placeholders.get(slot="home-hero")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type="TextPlugin",
            language=settings.LANGUAGE_CODE,
            body=settings.CMS_TEMPLATE_HOME_HERO,
        )
        placeholder = page.placeholders.get(slot="home-col-1")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type="TextPlugin",
            language=settings.LANGUAGE_CODE,
            body=settings.CMS_TEMPLATE_HOME_COL_1,
        )
        placeholder = page.placeholders.get(slot="home-col-2")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type="TextPlugin",
            language=settings.LANGUAGE_CODE,
            body=settings.CMS_TEMPLATE_HOME_COL_2,
        )
        placeholder = page.placeholders.get(slot="home-col-3")
        api.add_plugin(
            placeholder=placeholder,
            plugin_type="TextPlugin",
            language=settings.LANGUAGE_CODE,
            body=settings.CMS_TEMPLATE_HOME_COL_3,
        )
        static_placeholder = StaticPlaceholder(code="footer")
        static_placeholder.save()
        api.add_plugin(
            placeholder=static_placeholder.draft,
            plugin_type="TextPlugin",
            language=settings.LANGUAGE_CODE,
            body=settings.CMS_TEMPLATE_FOOTER,
        )
        static_placeholder.publish(
            request=None, language=settings.LANGUAGE_CODE, force=True
        )
        user = coordinator.customer_responsible.user
        user.groups.clear()
        group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
        user.groups.add(group_id)
        api.publish_page(page=page, user=user, language=settings.LANGUAGE_CODE)
        user.groups.remove(group_id)

    @classmethod
    def init_department(cls):
        from repanier.models.lut import LUT_DepartmentForCustomer

        if LUT_DepartmentForCustomer.objects.count() == 0:
            # Generate a template of LUT_DepartmentForCustomer
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Vegetable"))
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Fruit"))
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Bakery"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Flour"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Bread"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Pastry"), parent=parent
            )
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Butchery"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Delicatessen"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Chicken"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Pork"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Beef"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Beef and pork"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Lamb"), parent=parent
            )
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Grocery"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Cookie"), parent=parent
            )
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Creamery"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Dairy"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Cow cheese"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Goat cheese"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Sheep cheese"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Mixed cheese"), parent=parent
            )
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Icecream"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Cup of icecream"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Icecream per liter"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Icecream in frisco"), parent=parent
            )
            parent = LUT_DepartmentForCustomer.objects.create(short_name=_("Drink"))
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Juice"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Coffee"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(short_name=_("Tea"), parent=parent)
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Herbal tea"), parent=parent
            )
            LUT_DepartmentForCustomer.objects.create(
                short_name=_("Wine"), parent=parent
            )

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
                self.order_customer_mail = """
                    Bonjour {{ long_name }},<br>
                    <br>
                    En pièce jointe vous trouverez le montant de votre panier {{ short_name }} de la {{ permanence_link }}.<br>
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
                    Bonjour {{ long_name }},<br>
                    <br>
                    La commande ci-jointe de votre panier {{ short_name }} de la {{ permanence_link }} <b>a été annulée</b> car vous ne l'avez pas confirmée.<br>
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
