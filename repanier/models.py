# -*- coding: utf-8
from __future__ import unicode_literals
from django.core.exceptions import ValidationError
from django.template import Template, Context as djangoContext
from django.core.cache import cache
from django.utils.safestring import mark_safe
from picture.const import SIZE_XS, SIZE_M, SIZE_S
from picture.fields import AjaxPictureField
from cms.toolbar_pool import toolbar_pool
from django.contrib.sites.models import Site
from django.core.validators import MinLengthValidator
from django.utils.encoding import python_2_unicode_compatible
import uuid
from django.db.models import F

from const import *
import apps
from django.conf import settings
from django.db import models
from django.db import transaction
from django.db.models.signals import pre_save
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields
from parler.managers import TranslatableManager, TranslatableQuerySet
from parler.models import TranslatedFieldsModel
from parler.models import TranslationDoesNotExist
from parler.fields import TranslatedField

from mptt.managers import TreeManager
from mptt.models import MPTTModel, TreeForeignKey

from django.contrib.auth.models import Group
from django.dispatch import receiver
from djangocms_text_ckeditor.fields import HTMLField
from django.utils.translation import ugettext_lazy as _
from django.utils.formats import number_format
from django.utils import timezone
# from filer.fields.image import FilerImageField
from django.core import urlresolvers
import datetime
from tools import get_display

# try:
#     from south.modelsinspector import add_introspection_rules
#
#     add_introspection_rules([],
#                               ['^djangocms_text_ckeditor\.fields\.HTMLField'])
# except ImportError:
#     pass


class Configuration(TranslatableModel):

    group_name = models.CharField(_("group name"), max_length=50, default=EMPTY_STRING)
    test_mode = models.BooleanField(_("test mode"), default=True)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True, default=None)
    name = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_NAME,
        default=PERMANENCE_NAME_PERMANENCE,
        verbose_name=_("order name"))
    max_week_wo_participation = models.DecimalField(
        _("display a pop up on the order form after this max week wo participation"),
        help_text=_("0 mean : never display a pop up."),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    send_opening_mail_to_customer = models.BooleanField(_("send opening mail to customers"), default=False)
    send_abstract_order_mail_to_customer = models.BooleanField(_("send abstract order mail to customers"), default=False)
    send_order_mail_to_customer = models.BooleanField(_("send order mail to customers"), default=False)
    send_abstract_order_mail_to_producer = models.BooleanField(_("send abstract order mail to producers"), default=False)
    send_order_mail_to_producer = models.BooleanField(_("send order mail to producers"), default=False)
    send_order_mail_to_board = models.BooleanField(_("send order mail to board"), default=False)
    send_invoice_mail_to_customer = models.BooleanField(_("send invoice mail to customers"), default=False)
    send_invoice_mail_to_producer = models.BooleanField(_("send invoice mail to producers"), default=False)
    invoice = models.BooleanField(_("activate invoice"), default=True)
    display_anonymous_order_form = models.BooleanField(_("display anonymous order form"), default=True)
    display_producer_on_order_form = models.BooleanField(_("display producers on order form"), default=True)
    bank_account = models.CharField(_("bank account"), max_length=100, default=EMPTY_STRING)
    delivery_point = models.BooleanField(_("display deliveries point"), default=False)
    display_vat = models.BooleanField(_("display vat"), default=False)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    page_break_on_customer_check = models.BooleanField(_("page break on customer check"), default=False)
    translations = TranslatedFields(
        offer_customer_mail=HTMLField(_("offer customer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Bonjour,<br/>
                <br/>
                Les commandes de la {{ permanence }} sont maintenant ouvertes.<br/>
                {% if offer_description %}{{ offer_description }}<br/>{% endif %}
                Les commandes sont ouvertes auprès de : {{ offer_producer }}.<br/>
                Les produits suivants sont en offre :<br/>{{ offer_detail }}
                <br/>
                {{ signature }}
                """,
            blank=False),
        offer_producer_mail=HTMLField(_("offer producer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Cher/Chère {{ name }},<br/>
                <br />
                Les commandes de la {{ permanence }} vont bientôt être ouvertes.{% if offer_description %}<br/>
                Voici l'annonce consommateur :<br/>
                <br/>
                {{ offer_description }}{% endif %}<br/>
                <br/>
                Veuillez vérifier votre <strong>{{ offer }}</strong>.<br/>
                <br/>
                {{ signature }}
                """,
            blank=False),

        order_customer_mail=HTMLField(_("order customer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Bonjour {{ long_basket_name }},<br/>
                <br/>
                En pièce jointe vous trouverez le détail de votre pannier {{ short_basket_name }} de la {{ permanence }}.<br/>
                {{ last_balance }}.<br/>
                Le montant de votre commande s'élève à {{ order_amount }} €.<br/>
                {% if customer_on_hold_movement != "" %}{{ customer_on_hold_movement }}<br/>{% endif %}
                {% if payment_needed != "" %}{{ payment_needed }}<br/>{% endif %}
                {% if delivery_point %}Votre point d'enlèvement est : {{ delivery_point }}.<br/>{% endif %}
                <br/>
                {{ signature }}
                """,
            blank=False),
        order_staff_mail=HTMLField(_("order staff mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Cher/Chère membre de l'équipe de préparation,<br/>
                <br/>
                En pièce jointe vous trouverez la liste de préparation pour la {{ permanence }}.<br/>
                <br/>
                L'équipe de préparation est composée de :<br/>
                {{ board_composition }}<br/>
                ou de<br/>
                {{ board_composition_and_description }}<br/>
                <br/>
                {{ signature }}
                """,
            blank=False),
        order_producer_mail=HTMLField(_("order producer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Cher/Chère {{ name }},<br/>
                <br/>
                {% if order_empty %}Le groupe ne vous a rien acheté pour la {{ permanence }}.{% else %}En pièce jointe, vous trouverez la commande du groupe pour la {{  permanence  }}.{% if duplicate %}<br/>
                <strong>ATTENTION </strong>: La commande est présente en deux exemplaires. Le premier exemplaire est classé par produit et le duplicata est classé par panier.{% else %}{% endif %}{% endif %}<br/>
                <br/>
                {{ signature }}
                """,
              blank=False),

        invoice_customer_mail=HTMLField(_("invoice customer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Bonjour {{ name }},<br/>
                <br/>
                En pièce jointe vous trouverez votre facture pour la {{ permanence }}.{% if invoice_description %}<br/>
                <br/>
                {{ invoice_description }}{% endif %}<br/>
                <br/>
                {{ signature }}
                """,
            blank=False),
        invoice_producer_mail=HTMLField(_("invoice producer mail"),
            help_text="",
            configuration='CKEDITOR_SETTINGS_MODEL2',
            default=
                """
                Cher/Chère {{ profile_name }},<br/>
                <br/>
                En pièce jointe vous trouverez le détail de notre paiement pour la {{ permanence }}.<br/>
                <br/>
                {{ signature }}
                """,
            blank=False),
    )

    def clean(self):
        try:
            template = Template(self.offer_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.offer_customer_mail,error_str)))
        try:
            template = Template(self.offer_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.offer_producer_mail,error_str)))
        try:
            template = Template(self.order_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.order_customer_mail,error_str)))
        try:
            template = Template(self.order_staff_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.order_staff_mail,error_str)))
        try:
            template = Template(self.order_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.order_producer_mail,error_str)))
        try:
            template = Template(self.invoice_customer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.invoice_customer_mail,error_str)))
        try:
            template = Template(self.invoice_producer_mail)
        except Exception as error_str:
            raise ValidationError(mark_safe("%s : %s" % (self.invoice_producer_mail,error_str)))

    class Meta:
        verbose_name = _("configuration")
        verbose_name_plural = _("configurations")

@receiver(post_save, sender=Configuration)
def configuration_post_save(sender, instance=None, **kwargs):
    from cms_toolbar import RepanierToolbar

    config = instance
    if config.id is not None:
        apps.REPANIER_SETTINGS_CONFIG = config
        apps.REPANIER_SETTINGS_TEST_MODE = config.test_mode
        site = Site.objects.get_current()
        if site is not None:
            site.name = config.group_name
            site.domain = settings.ALLOWED_HOSTS[0]
            site.save()
        apps.REPANIER_SETTINGS_GROUP_NAME = config.group_name
        if config.name == PERMANENCE_NAME_PERMANENCE:
            apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Permanence")
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Permanences")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Permanence on ")
        elif config.name == PERMANENCE_NAME_CLOSURE:
            apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Closure")
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Closures")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Closure on ")
        elif config.name == PERMANENCE_NAME_DELIVERY:
            apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Delivery")
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Deliveries")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Delivery on ")
        else:
            apps.REPANIER_SETTINGS_PERMANENCE_NAME = _("Order")
            apps.REPANIER_SETTINGS_PERMANENCES_NAME = _("Orders")
            apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME = _("Order on ")
        apps.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION = config.max_week_wo_participation
        apps.REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER = config.send_opening_mail_to_customer
        apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER = config.send_order_mail_to_customer
        apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER = config.send_abstract_order_mail_to_customer
        apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER = config.send_order_mail_to_producer
        apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER = config.send_abstract_order_mail_to_producer
        apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD = config.send_order_mail_to_board
        apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER = config.send_invoice_mail_to_customer
        apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER = config.send_invoice_mail_to_producer
        apps.REPANIER_SETTINGS_INVOICE = config.invoice
        apps.REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM = config.display_anonymous_order_form
        apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM = config.display_producer_on_order_form
        # print('----------------------------- set REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM')
        # print(apps.REPANIER_SETTINGS_DISPLAY_PRODUCER_ON_ORDER_FORM)
        apps.REPANIER_SETTINGS_BANK_ACCOUNT = config.bank_account
        apps.REPANIER_SETTINGS_DELIVERY_POINT = config.delivery_point
        apps.REPANIER_SETTINGS_DISPLAY_VAT = config.display_vat
        apps.REPANIER_SETTINGS_VAT_ID = config.vat_id
        apps.REPANIER_SETTINGS_PAGE_BREAK_ON_CUSTOMER_CHECK = config.page_break_on_customer_check

        menu_pool.clear()
        toolbar_pool.unregister(RepanierToolbar)
        toolbar_pool.register(RepanierToolbar)
        cache.clear()


class LUT_ProductionModeQuerySet(TranslatableQuerySet):
    pass


class LUT_ProductionModeManager(TreeManager, TranslatableManager):
    queryset_class = LUT_ProductionModeQuerySet


@python_2_unicode_compatible
class LUT_ProductionMode(MPTTModel, TranslatableModel):

    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    translations = TranslatedFields(
        short_name=models.CharField(_("short_name"), max_length=50, db_index=True, unique=True, default=EMPTY_STRING),
        description=HTMLField(_("description"), blank=True, default=EMPTY_STRING),
    )
    # picture = FilerImageField(
    #     verbose_name=_("picture"), related_name="production_mode_picture",
    #     null=True, blank=True)
    picture2 = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="label", size=SIZE_XS)

    is_active = models.BooleanField(_("is_active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("production mode")
        verbose_name_plural = _("production modes")


class LUT_DeliveryPointQuerySet(TranslatableQuerySet):
    pass


class LUT_DeliveryPointManager(TreeManager, TranslatableManager):
    queryset_class = LUT_DeliveryPointQuerySet


@python_2_unicode_compatible
class LUT_DeliveryPoint(MPTTModel, TranslatableModel):
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    translations = TranslatedFields(
        short_name=models.CharField(_("short_name"), max_length=50, db_index=True, unique=True, default=EMPTY_STRING),
        description=HTMLField(_("description"), blank=True, default=EMPTY_STRING),
    )
    is_active = models.BooleanField(_("is_active"), default=True)
    objects = LUT_DeliveryPointManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("delivery point")
        verbose_name_plural = _("deliveries points")


class LUT_DepartmentForCustomerQuerySet(TranslatableQuerySet):
    pass


class LUT_DepartmentForCustomerManager(TreeManager, TranslatableManager):
    queryset_class = LUT_DepartmentForCustomerQuerySet


@python_2_unicode_compatible
class LUT_DepartmentForCustomer(MPTTModel, TranslatableModel):
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    translations = TranslatedFields(
        short_name=models.CharField(_("short_name"), max_length=50, db_index=True, unique=True, default=EMPTY_STRING),
        description=HTMLField(_("description"), blank=True, default=EMPTY_STRING),
    )
    is_active = models.BooleanField(_("is_active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("department for customer")
        verbose_name_plural = _("departments for customer")


class LUT_PermanenceRoleQuerySet(TranslatableQuerySet):
    pass


class LUT_PermanenceRoleManager(TreeManager, TranslatableManager):
    queryset_class = LUT_PermanenceRoleQuerySet


@python_2_unicode_compatible
class LUT_PermanenceRole(MPTTModel, TranslatableModel):
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    translations = TranslatedFields(
        short_name=models.CharField(_("short_name"), max_length=50, db_index=True, unique=True, default=EMPTY_STRING),
        description=HTMLField(_("description"), blank=True, default=EMPTY_STRING),
    )
    delivery_points = models.ManyToManyField(
        LUT_DeliveryPoint,
        verbose_name=_("delivery points"),
        blank=True)

    is_active = models.BooleanField(_("is_active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("permanence role")
        verbose_name_plural = _("permanences roles")


@receiver(pre_save, sender=LUT_PermanenceRole)
def lut_permanence_role_pre_save(sender, **kwargs):
    lut_permanence_role = kwargs['instance']
    if not lut_permanence_role.is_active:
        lut_permanence_role.automatically_added = False


@python_2_unicode_compatible
class Producer(models.Model):
    short_profile_name = models.CharField(
        _("short_profile_name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_profile_name = models.CharField(
        _("long_profile_name"), max_length=100, null=True, default=EMPTY_STRING)
    email = models.EmailField(
        _("email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("language"))
    phone1 = models.CharField(
        _("phone1"),
        max_length=25,
        validators=[MinLengthValidator(2)],
        null=True, default=EMPTY_STRING)
    phone2 = models.CharField(
        _("phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    fax = models.CharField(
        _("fax"), max_length=100, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(_("address"), null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("memo"), null=True, blank=True, default=EMPTY_STRING)
    # uuid used to access to producer invoices without login
    uuid = models.CharField(
        _("uuid"), max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_uuid = models.CharField(
        _("uuid"), max_length=36, null=True, default=EMPTY_STRING,
        db_index=True
    )
    offer_filled = models.BooleanField(_("offer filled"), default=False)
    invoice_by_basket = models.BooleanField(_("invoice by basket"), default=False)
    manage_stock = models.BooleanField(_("manage stock"), default=False)
    producer_pre_opening = models.BooleanField(_("producer pre-opening"), default=False)
    producer_price_are_wo_vat = models.BooleanField(_("producer price are wo vat"), default=False)

    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ZERO, max_digits=4, decimal_places=2)
    is_resale_price_fixed = models.BooleanField(_("the resale price is set by the producer"),
        default=False)
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("Default tax"))

    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # The initial balance is needed to compute the invoice control list
    initial_balance = models.DecimalField(
        _("initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)

    def natural_key(self):
        return self.short_profile_name

    def get_products(self):
        link = ''
        if self.id:
            # This producer may have product's list
            changeproductslist_url = urlresolvers.reverse(
                'admin:repanier_product_changelist',
            )
            link = '<a href="%s?is_active__exact=1&producer=%s" target="_blank" class="addlink">&nbsp;%s</a>' \
                   % (changeproductslist_url, str(self.id), _("his_products"))
        return link

    get_products.short_description = (_("link to his products"))
    get_products.allow_tags = True

    def get_balance(self):
        last_producer_invoice_set = ProducerInvoice.objects.filter(
            producer_id=self.id, invoice_sort_order__isnull=False
        ).order_by()
        if last_producer_invoice_set.exists():
            if self.balance < DECIMAL_ZERO:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#298A08">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance == DECIMAL_ZERO:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#32CD32">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance > 30:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#FF0000">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('producer_invoice_view', args=(0,)) + '?producer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#696969">%s</span>' % (number_format(self.balance, 2))) + '</a>'
        else:
            if self.balance < DECIMAL_ZERO:
                return '<span style="color:#298A08">%s</span>' % (number_format(self.balance, 2))
            elif self.balance == DECIMAL_ZERO:
                return '<span style="color:#32CD32">%s</span>' % (number_format(self.balance, 2))
            elif self.balance > 30:
                return '<span style="color:#FF0000">%s</span>' % (number_format(self.balance, 2))
            else:
                return '<span style="color:#696969">%s</span>' % (number_format(self.balance, 2))

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_last_invoice(self):
        producer_last_invoice = ProducerInvoice.objects.filter(producer_id=self.id).order_by("-id").first()
        if producer_last_invoice:
            if producer_last_invoice.total_price_with_tax < DECIMAL_ZERO:
                return '<span style="color:#298A08">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax == DECIMAL_ZERO:
                return '<span style="color:#32CD32">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            elif producer_last_invoice.total_price_with_tax > 30:
                return '<span style="color:#FF0000">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
            else:
                return '<span style="color:#696969">%s</span>' % (
                    number_format(producer_last_invoice.total_price_with_tax, 2))
        else:
            return '<span style="color:#32CD32">%s</span>' % (number_format(0, 2))

    get_last_invoice.short_description = _("last invoice")
    get_last_invoice.allow_tags = True

    def __str__(self):
        # if self.producer_price_are_wo_vat :
        #     return "%s %s" % (self.short_profile_name, _("wo tax"))
        return self.short_profile_name

    class Meta:
        verbose_name = _("producer")
        verbose_name_plural = _("producers")
        ordering = ("short_profile_name",)


@receiver(pre_save, sender=Producer)
def producer_pre_save(sender, **kwargs):
    producer = kwargs['instance']
    if producer.email is not None:
        producer.email = producer.email.lower()
    if producer.producer_pre_opening:
        # Important to make difference between the stock of the group and the stock of the producer
        producer.manage_stock = False
        producer.is_resale_price_fixed = False
    if producer.manage_stock:
        # Important to compute ProducerInvoice.total_price_with_tax
        producer.invoice_by_basket = False
    if producer.price_list_multiplier <= DECIMAL_ZERO:
        producer.price_list_multiplier = DECIMAL_ONE
    if producer.uuid is None or producer.uuid == "":
        producer.uuid = uuid.uuid4()
    if producer.id is None:
        producer.balance = producer.initial_balance
        bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
        if bank_account is not None:
            producer.date_balance = bank_account.operation_date
        else:
            producer.date_balance = datetime.date.today()
    else:
        last_producer_invoice_set = ProducerInvoice.objects.filter(
            producer_id=producer.id, invoice_sort_order__isnull=False
        ).order_by()
        if last_producer_invoice_set.exists():
            # Do not modify the balance, an invoice already exist
            pass
        else:
            producer.balance = producer.initial_balance
            bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
            if bank_account:
                producer.date_balance = bank_account.operation_date
            else:
                producer.date_balance = datetime.date.today()


@python_2_unicode_compatible
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)

    short_basket_name = models.CharField(
        _("short_basket_name"), max_length=25, null=False, default=EMPTY_STRING,
        db_index=True, unique=True)
    long_basket_name = models.CharField(
        _("long_basket_name"), max_length=100, null=True, default=EMPTY_STRING)
    email2 = models.EmailField(
        _("secondary email"), null=True, blank=True, default=EMPTY_STRING)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("language"))
    delivery_point = models.ForeignKey(
        LUT_DeliveryPoint, verbose_name=_("delivery point"),
        null=True, blank=True, default=None,
        on_delete=models.PROTECT)
    picture = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="customer", size=SIZE_S)
    phone1 = models.CharField(
        _("phone1"),
        max_length=25,
        validators=[MinLengthValidator(2)],
        null=True, default=EMPTY_STRING)

    phone2 = models.CharField(
        _("phone2"), max_length=25, null=True, blank=True, default=EMPTY_STRING)
    vat_id = models.CharField(
        _("vat_id"), max_length=20, null=True, blank=True, default=EMPTY_STRING)
    address = models.TextField(
        _("address"), null=True, blank=True, default=EMPTY_STRING)
    city = models.CharField(
        _("city"), max_length=50, null=True, blank=True, default=EMPTY_STRING)
    about_me = models.TextField(
        _("about me"), null=True, blank=True, default=EMPTY_STRING)
    memo = models.TextField(
        _("memo"), null=True, blank=True, default=EMPTY_STRING)
    accept_mails_from_members = models.BooleanField(
        _("show my mail to other members"), default=False)
    accept_phone_call_from_members = models.BooleanField(
        _("show my phone to other members"), default=False)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True, default=None)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # The initial balance is needed to compute the invoice control list
    initial_balance = models.DecimalField(
        _("initial balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    represent_this_buyinggroup = models.BooleanField(
        _("represent_this_buyinggroup"), default=False)
    is_active = models.BooleanField(_("is_active"), default=True)
    may_order = models.BooleanField(_("may_order"), default=True)

    def get_balance(self):
        last_customer_invoice_set = CustomerInvoice.objects.filter(
            customer_id=self.id, invoice_sort_order__isnull=False
        ).order_by()
        if last_customer_invoice_set.exists():
            if self.balance >= 30:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#32CD32">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            elif self.balance >= -10:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#696969">%s</span>' % (number_format(self.balance, 2))) + '</a>'
            else:
                return '<a href="' + urlresolvers.reverse('customer_invoice_view', args=(0,)) + '?customer=' + str(
                    self.id) + '" target="_blank" >' + (
                           '<span style="color:#FF0000">%s</span>' % (number_format(self.balance, 2))) + '</a>'
        else:
            if self.balance >= 30:
                return '<span style="color:#32CD32">%s</span>' % (number_format(self.balance, 2))
            elif self.balance >= -10:
                return '<span style="color:#696969">%s</span>' % (number_format(self.balance, 2))
            else:
                return '<span style="color:#FF0000">%s</span>' % (number_format(self.balance, 2))

    get_balance.short_description = _("balance")
    get_balance.allow_tags = True
    get_balance.admin_order_field = 'balance'

    def get_participation(self):
        now = timezone.now()
        return PermanenceBoard.objects.filter(
            customer_id=self.id,
            permanence_date__gte=now - datetime.timedelta(
            days=float(apps.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION) * 7 * 4),
            permanence_date__lt=now
        ).count()
    get_participation.short_description = _("participation")
    get_participation.allow_tags = True

    def get_purchase(self):
        now = timezone.now()
        return CustomerInvoice.objects.filter(
            customer_id=self.id,
            total_price_with_tax__gt=DECIMAL_ZERO,
            date_balance__gte=now - datetime.timedelta(
            days=float(apps.REPANIER_SETTINGS_MAX_WEEK_WO_PARTICIPATION) * 7 * 4)
        ).count()
    get_purchase.short_description = _("purchase")
    get_purchase.allow_tags = True

    @property
    def who_is_who_display(self):
        return self.picture or self.accept_mails_from_members or self.accept_phone_call_from_members \
               or (self.about_me and len(self.about_me) > 1)

    def natural_key(self):
        return self.short_basket_name

    natural_key.dependencies = ['repanier.customer']

    def __str__(self):
        return self.short_basket_name

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        ordering = ("short_basket_name",)
        index_together = [
            ["user", "is_active", "may_order"],
        ]


@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, **kwargs):
    customer = kwargs['instance']
    if customer.email2 is not None:
        customer.email2 = customer.email2.lower()
    if customer.vat_id is not None and len(customer.vat_id) == 0:
        customer.vat_id = None
    if not customer.is_active:
        customer.may_order = False
    if customer.id is None:
        customer.balance = customer.initial_balance
        bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
        if bank_account is not None:
            customer.date_balance = bank_account.operation_date
        else:
            customer.date_balance = datetime.date.today()
    else:
        customer_invoice_set = CustomerInvoice.objects.filter(
            customer_id=customer.id, invoice_sort_order__isnull=False
        ).order_by()
        if customer_invoice_set.exists():
            # Do not modify the balance, an invoice already exist
            pass
        else:
            customer.balance = customer.initial_balance
            bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
            if bank_account:
                customer.date_balance = bank_account.operation_date
            else:
                customer.date_balance = datetime.date.today()
    customer.city = customer.city.upper()
    customer.login_attempt_counter = DECIMAL_ZERO


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs['instance']
    user = customer.user
    user.delete()


@python_2_unicode_compatible
class Staff(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("login"))
    customer_responsible = models.ForeignKey(
        Customer, verbose_name=_("customer_responsible"),
        on_delete=models.PROTECT, blank=True, null=True, default=None)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    long_name = models.CharField(
        _("long_name"), max_length=100, null=True, default=EMPTY_STRING)
    function_description = HTMLField(
        _("function_description"),
        blank=True, default=EMPTY_STRING)
    is_reply_to_order_email = models.BooleanField(_("is_reply_to_order_email"),
                                                  default=False)
    is_reply_to_invoice_email = models.BooleanField(_("is_reply_to_invoice_email"),
                                                    default=False)
    is_webmaster = models.BooleanField(_("is_webmaster"),
                                                    default=False)
    is_coordinator = models.BooleanField(_("is_coordinator"),
                                                    default=False)
    password_reset_on = models.DateTimeField(
        _("password_reset_on"), null=True, blank=True, default=None)
    is_active = models.BooleanField(_("is_active"), default=True)

    def natural_key(self):
        return self.user.natural_key()

    natural_key.dependencies = ['auth.user']

    def get_customer_phone1(self):
        try:
            return self.customer_responsible.phone1
        except:
            return "----"

    get_customer_phone1.short_description = (_("phone1"))
    get_customer_phone1.allow_tags = False

    def __str__(self):
        return self.long_name

    class Meta:
        verbose_name = _("staff member")
        verbose_name_plural = _("staff members")
        ordering = ("long_name",)


@receiver(pre_save, sender=Staff)
def staff_pre_save(sender, **kwargs):
    staff = kwargs['instance']
    staff.login_attempt_counter = DECIMAL_ZERO


@receiver(post_save, sender=Staff)
def staff_post_save(sender, **kwargs):
    staff = kwargs['instance']
    if staff.id is not None:
        user = staff.user
        user.groups.clear()
        if staff.is_reply_to_order_email:
            group_id = Group.objects.filter(name=ORDER_GROUP).first()
            user.groups.add(group_id)
        if staff.is_reply_to_invoice_email:
            group_id = Group.objects.filter(name=INVOICE_GROUP).first()
            user.groups.add(group_id)
        if staff.is_webmaster:
            group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
            user.groups.add(group_id)
        if staff.is_coordinator:
            group_id = Group.objects.filter(name=COORDINATION_GROUP).first()
            user.groups.add(group_id)


@receiver(post_delete, sender=Staff)
def staff_post_delete(sender, **kwargs):
    staff = kwargs['instance']
    user = staff.user
    user.delete()


@python_2_unicode_compatible
class Product(TranslatableModel):
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"), on_delete=models.PROTECT)
    long_name = TranslatedField()
    offer_description = TranslatedField()
    production_mode = models.ManyToManyField(
        LUT_ProductionMode,
        verbose_name=_("production mode"),
        blank=True)
    # picture = FilerImageField(
    #     verbose_name=_("picture"), related_name="product_picture",
    #     null=True, blank=True)
    picture2 = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="product", size=SIZE_M)

    reference = models.CharField(
        _("reference"), max_length=36, blank=True, null=True)

    department_for_customer = models.ForeignKey(
        LUT_DepartmentForCustomer, null=True, blank=True,
        verbose_name=_("department_for_customer"),
        on_delete=models.PROTECT)

    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("product_placement"),
        help_text=_('used for helping to determine the order of preparation of this product'))

    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)

    producer_unit_price = models.DecimalField(
        _("producer unit price"),
        # help_text=_('producer unit price (/piece or /kg or /l), including vat'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    customer_unit_price = models.DecimalField(
        _("customer unit price"),
        # help_text=_('(/piece or /kg or /l), with vat, without compensation nor deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    producer_vat = models.DecimalField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    customer_vat = models.DecimalField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    compensation = models.DecimalField(
        _("compensation"),
        help_text=_("compensation to add to the customer unit price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    unit_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("tax"))
    stock = models.DecimalField(
        _("Current stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=3)
    limit_order_quantity_to_stock = models.BooleanField(_("limit maximum order qty of the group to stock qty"), default=False)

    customer_minimum_order_quantity = models.DecimalField(
        _("customer_minimum_order_quantity"),
        help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_increment_order_quantity = models.DecimalField(
        _("customer_increment_order_quantity"),
        help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50max 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    producer_order_by_quantity = models.DecimalField(
        _("Producer order by quantity"),
        help_text=_('1,5 Kg [i.e. 1500 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)

    permanences = models.ManyToManyField(
        'Permanence', through='OfferItem')
    is_into_offer = models.BooleanField(_("is_into_offer"), default=True)

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("order unit"),
    )
    wrapped = models.BooleanField(_('Individually wrapped by the producer'),
        default=False)
    is_active = models.BooleanField(_("is_active"), default=True)
    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True, blank=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True, blank=True)

    def get_long_name(self):
        if self.id:
            qty_display, price_display = get_display(
                1,
                self.order_average_weight,
                self.order_unit,
                self.customer_unit_price,
                False
            )
            return '%s %s' % (self.long_name, qty_display)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = True
    get_long_name.admin_order_field = 'translations__long_name'

    def natural_key(self):
        return '%s%s' % (self.long_name, self.producer.natural_key())

    natural_key.dependencies = ['repanier.producer']

    def __str__(self):
        qty_display, price_display = get_display(
            1,
            self.order_average_weight,
            self.order_unit,
            self.customer_unit_price,
            False
        )
        return '%s, %s%s' % (self.producer.short_profile_name, self.long_name, qty_display)

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        # ordering = ("producer", "long_name",)
        unique_together = ("producer", "reference",)
        index_together = [
            ["producer", "reference"],
        ]


@receiver(pre_save, sender=Product)
def product_pre_save(sender, **kwargs):
    product = kwargs['instance']
    producer = product.producer
    if not product.is_active:
        product.is_into_offer = False
    if product.order_unit not in [PRODUCT_ORDER_UNIT_PC, PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                                  PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        product.unit_deposit = DECIMAL_ZERO
    if product.order_unit == PRODUCT_ORDER_UNIT_PC:
        product.order_average_weight = 1
    elif product.order_unit not in [PRODUCT_ORDER_UNIT_PC_KG, PRODUCT_ORDER_UNIT_PC_PRICE_KG,
                                    PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
        product.order_average_weight = DECIMAL_ZERO
    if product.order_unit in [PRODUCT_ORDER_UNIT_DEPOSIT, PRODUCT_ORDER_UNIT_SUBSCRIPTION]:
        # No VAT on those products
        product.vat_level = VAT_100

    product.producer_vat = DECIMAL_ZERO
    if producer.producer_price_are_wo_vat:
        if product.vat_level == VAT_400:
            product.producer_vat = (product.producer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_500:
            product.producer_vat = (product.producer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_600:
            product.producer_vat = (product.producer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)

        if not producer.is_resale_price_fixed:
            if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                product.customer_unit_price = (product.producer_unit_price * producer.price_list_multiplier).quantize(
                    TWO_DECIMALS)
            else:
                if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT and product.producer_unit_price > DECIMAL_ZERO:
                    product.producer_unit_price = -product.producer_unit_price
                product.customer_unit_price = product.producer_unit_price

        product.customer_vat = DECIMAL_ZERO
        if product.vat_level == VAT_400:
            product.customer_vat = (product.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_500:
            product.customer_vat = (product.customer_unit_price * DECIMAL_0_12).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_600:
            product.customer_vat = (product.customer_unit_price * DECIMAL_0_21).quantize(FOUR_DECIMALS)
        product.compensation = DECIMAL_ZERO
        if product.vat_level == VAT_200:
            product.compensation = (product.customer_unit_price * DECIMAL_0_02).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_300:
            product.compensation = (product.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)

        if not producer.is_resale_price_fixed:
            product.customer_unit_price += product.customer_vat
    else:
        if product.vat_level == VAT_400:
            product.producer_vat = product.producer_unit_price - (product.producer_unit_price / DECIMAL_1_06).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_500:
            product.producer_vat = product.producer_unit_price - (product.producer_unit_price / DECIMAL_1_12).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_600:
            product.producer_vat = product.producer_unit_price - (product.producer_unit_price / DECIMAL_1_21).quantize(FOUR_DECIMALS)

        if not producer.is_resale_price_fixed:
            if product.order_unit < PRODUCT_ORDER_UNIT_DEPOSIT:
                product.customer_unit_price = (product.producer_unit_price * producer.price_list_multiplier).quantize(
                    TWO_DECIMALS)
            else:
                product.customer_unit_price = product.producer_unit_price

        product.customer_vat = DECIMAL_ZERO
        if product.vat_level == VAT_400:
            product.customer_vat = product.customer_unit_price - (product.customer_unit_price / DECIMAL_1_06).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_500:
            product.customer_vat = product.customer_unit_price - (product.customer_unit_price / DECIMAL_1_12).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_600:
            product.customer_vat = product.customer_unit_price - (product.customer_unit_price / DECIMAL_1_21).quantize(FOUR_DECIMALS)
        product.compensation = DECIMAL_ZERO
        if product.vat_level == VAT_200:
            product.compensation = (product.customer_unit_price * DECIMAL_0_02).quantize(FOUR_DECIMALS)
        elif product.vat_level == VAT_300:
            product.compensation = (product.customer_unit_price * DECIMAL_0_06).quantize(FOUR_DECIMALS)
    if producer.producer_pre_opening:
        product.limit_order_quantity_to_stock = True
    # print("----------------------")
    # print("Producer price wo tax : " + str(producer.producer_price_wotax))
    # print("vat_level : %s" % product.vat_level)
    # print("producer_unit_price : %f" % product.producer_unit_price)
    # print("producer_vat : %f" % product.producer_vat)
    # print("customer_unit_price : %f" % product.customer_unit_price)
    # print("customer_vat : %f" % product.customer_vat)

    if product.customer_increment_order_quantity <= DECIMAL_ZERO:
        product.customer_increment_order_quantity = DECIMAL_ONE
    if product.customer_minimum_order_quantity <= DECIMAL_ZERO:
        product.customer_minimum_order_quantity = product.customer_increment_order_quantity
    # if product.customer_alert_order_quantity <= product.customer_minimum_order_quantity:
    #     product.customer_alert_order_quantity = product.customer_minimum_order_quantity
    if product.order_average_weight <= DECIMAL_ZERO:
        product.order_average_weight = DECIMAL_ONE
    if product.reference is None or product.reference == "":
        product.reference = uuid.uuid4()


class Product_Translation(TranslatedFieldsModel):
    master = models.ForeignKey(Product, related_name='translations', null=True)
    long_name = models.CharField(_("long_name"), max_length=100)
    offer_description=HTMLField(_("offer_description"), blank=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _("Product translation")

# import sys
# import traceback


@python_2_unicode_compatible
class Permanence(TranslatableModel):
    translations = TranslatedFields(
        short_name=models.CharField(_("short_name"), max_length=50, blank=True),
        offer_description=HTMLField(_("offer_description"),
              help_text=_(
                  "This message is send by mail to all customers when opening the order or on top "),
              blank=True),
        invoice_description=HTMLField(
            _("invoice_description"),
            help_text=_(
                'This message is send by mail to all customers having bought something when closing the permanence.'),
            blank=True),
        cache_part_d = HTMLField(default="", blank=True)
    )

    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))
    permanence_date = models.DateField(_("permanence_date"), db_index=True)
    payment_date = models.DateField(_("payment_date"), blank=True, null=True, db_index=True)
    producers = models.ManyToManyField(
        Producer,
        verbose_name=_("producers"),
        blank=True
    )
    automatically_closed = models.BooleanField(
        _("automatically_closed"), default=False)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("highest permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))

    def natural_key(self):
        return self.permanence_date, self.short_name

    def get_producers(self):
        if self.id is not None:
            if len(self.producers.all()) > 0:
                if self.status == PERMANENCE_PLANNED:
                    changelist_url = urlresolvers.reverse(
                        'admin:repanier_product_changelist',
                    )
                    return ", ".join(['<a href="' + changelist_url +
                                       '?producer=' + str(p.id) + '" target="_blank" class="addlink">&nbsp;' +
                                       p.short_profile_name + '</a>' for p in self.producers.all()])
                elif self.status == PERMANENCE_PRE_OPEN:
                    return ", ".join([p.short_profile_name + " (" + p.phone1 + ")" for p in self.producers.all()])
                elif self.status == PERMANENCE_CLOSED:
                    offeritem_changelist_url = urlresolvers.reverse(
                        'admin:repanier_offeritemclosed_changelist',
                    )
                    link = []
                    for p in self.producers.filter(is_active=True).only("id", "short_profile_name", "manage_stock"):
                        if p.manage_stock:
                            link.append('<a href="' + offeritem_changelist_url +
                               '?permanence=' + str(self.id) +
                               '&producer=' + str(p.id) +
                               '" target="_blank" class="addlink">' +
                               p.short_profile_name + '</a>'
                            )
                        else:
                            link.append('&nbsp;' + p.short_profile_name)
                    return ", ".join(link)
                elif self.status == PERMANENCE_SEND:
                    offeritem_changelist_url = urlresolvers.reverse(
                        'admin:repanier_offeritemsend_changelist',
                    )
                    customer_changelist_url = urlresolvers.reverse(
                        'admin:repanier_customersend_changelist',
                    )
                    link = []
                    for p in self.producers.filter(is_active=True).only("id", "short_profile_name", "invoice_by_basket"):
                        if p.invoice_by_basket:
                            changelist_url = customer_changelist_url
                        else:
                            changelist_url = offeritem_changelist_url
                        pi = ProducerInvoice.objects.filter(producer_id=p.id, permanence_id=self.id)\
                            .only("total_price_with_tax").order_by().first()
                        if pi is not None:
                            link.append('<a href="' + changelist_url +
                               '?permanence=' + str(self.id) +
                               '&producer=' + str(p.id) +
                               '" target="_blank" class="addlink">' +
                               p.short_profile_name.replace(' ', '&nbsp;') + '&nbsp;(' + number_format(pi.total_price_with_tax,2).replace(' ', '&nbsp;') + '&nbsp;&euro;)</a>'
                            )
                        else:
                            link.append('<a href="' + changelist_url +
                               '?permanence=' + str(self.id) +
                               '&producer=' + str(p.id)+ '" target="_blank" class="addlink">&nbsp;' +
                               p.short_profile_name.replace(' ', '&nbsp;') + '</a>'
                            )
                    return ", ".join(link)
                else:
                    producers = "<button onclick=\"django.jQuery('#id_get_producers_%d').toggle();" \
                                "if(django.jQuery(this).html()=='%s'){" \
                                "django.jQuery(this).html('%s')" \
                                "}else{" \
                                "django.jQuery(this).html('%s')" \
                                "};" \
                                "return false;\">%s</button><div id=\"id_get_producers_%d\" style=\"display:none;\">" % (self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id)

                    producers += ", ".join([
                        p.short_profile_name.replace(' ', '&nbsp;') for p in self.producers.all()
                    ])
                    producers += "</div>"
                    return producers
            else:
                return _("No offer")
        return "?"

    get_producers.short_description = (_("producers in this permanence"))
    get_producers.allow_tags = True

    def get_customers(self):
        if self.id is not None:
            customers = ""
            if self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_purchaseopenedorclosedforupdate_changelist',
                )
                customers += ", ".join(['<a href="' + changelist_url + \
                                   '?permanence=' + str(self.id) + \
                                   '&customer=' + str(c.id) + '" target="_blank"  class="addlink">&nbsp;' + \
                                   c.short_basket_name + '</a>'
                                   for c in Customer.objects.filter(purchase__permanence_id=self.id).distinct()])
            elif self.status == PERMANENCE_SEND:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_purchasesendforupdate_changelist',
                )
                customers += ", ".join(['<a href="' + changelist_url + \
                                   '?permanence=' + str(self.id) + \
                                   '&customer=' + str(c.id) + '" target="_blank"  class="addlink">&nbsp;' + \
                                   c.short_basket_name + '</a>'
                                   for c in Customer.objects.filter(purchase__permanence_id=self.id).distinct()])
            elif self.status in [PERMANENCE_DONE, PERMANENCE_ARCHIVED]:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_purchaseinvoiced_changelist',
                )
                customers += ", ".join(['<a href="' + changelist_url + \
                                   '?permanence=' + str(self.id) + \
                                   '&customer=' + str(c.id) + '" target="_blank"  class="addlink">&nbsp;' + \
                                   c.short_basket_name + '</a>'
                                   for c in Customer.objects.filter(purchase__permanence_id=self.id).distinct()])
            else:
                customers += ", ".join([c.short_basket_name
                                   for c in Customer.objects.filter(purchase__permanence_id=self.id).distinct()])
            if len(customers) > 0:
                return "<button onclick=\"django.jQuery('#id_get_customers_%d').toggle();" \
                            "if(django.jQuery(this).html()=='%s'){" \
                            "django.jQuery(this).html('%s')" \
                            "}else{" \
                            "django.jQuery(this).html('%s')" \
                            "};" \
                            "return false;\">%s</button><div id=\"id_get_customers_%d\" style=\"display:none;\">" %\
                       (self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id) + customers + "</div>"
            else:
                return _("No purchase")
        return "?"

    get_customers.short_description = (_("customers in this permanence"))
    get_customers.allow_tags = True

    def get_board(self):
        if self.id is not None:
            permanenceboard_set = PermanenceBoard.objects.filter(
                permanence=self)
            first_board = True
            board = ""
            if permanenceboard_set:
                for permanenceboard in permanenceboard_set:
                    r_link = ''
                    r = permanenceboard.permanence_role
                    if r:
                        r_url = urlresolvers.reverse(
                            'admin:repanier_lut_permanencerole_change',
                            args=(r.id,)
                        )
                        r_link = '<a href="' + r_url + \
                                 '" target="_blank">' + r.short_name.replace(' ', '&nbsp;') + '</a>'
                    c_link = ''
                    c = permanenceboard.customer
                    if c:
                        c_url = urlresolvers.reverse(
                            'admin:repanier_customer_change',
                            args=(c.id,)
                        )
                        c_link = '&nbsp;->&nbsp;<a href="' + c_url + \
                                 '" target="_blank">' + c.short_basket_name.replace(' ', '&nbsp;') + '</a>'
                    if not first_board:
                        board += '<br/>'
                    board += r_link + c_link
                    first_board = False
            if not first_board:
                # At least one role is defined in the permanence board
                return "<button onclick=\"django.jQuery('#id_get_board_%d').toggle();" \
                            "if(django.jQuery(this).html()=='%s'){" \
                            "django.jQuery(this).html('%s')" \
                            "}else{" \
                            "django.jQuery(this).html('%s')" \
                            "};" \
                            "return false;\">%s</button><div id=\"id_get_board_%d\" style=\"display:none;\">" % \
                        (self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id) + \
                        board + "</div>"
            else:
                return _("Empty board")
        return "?"

    get_board.short_description = (_("permanence board"))
    get_board.allow_tags = True

    def set_status(self, new_status, update_payment_date=False):
        now = timezone.now()
        self.is_updated_on = now
        self.status = new_status
        if self.highest_status < new_status:
            self.highest_status = new_status
        if update_payment_date:
            self.payment_date = now
            self.save(update_fields=['status', 'is_updated_on', 'highest_status', 'payment_date'])
        else:
            self.save(update_fields=['status', 'is_updated_on', 'highest_status'])
        menu_pool.clear()


    def __str__(self):
        result = ""
        try:
            if self.short_name is not None and len(self.short_name) > 0:
                result = '%s%s (%s)' % (
                    apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME, self.permanence_date.strftime('%d-%m-%Y'), self.short_name)
        except TranslationDoesNotExist:
            pass
        if len(result) == 0:
            result = '%s%s' % (
                apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME, self.permanence_date.strftime('%d-%m-%Y'))
        return result
        # except:
        #     exc_type, exc_value, exc_traceback = sys.exc_info()
        #     lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        #     print ''.join('!! ' + line for line in lines)

    def get_permanence_display(self):
        return ("%s - %s" % (self, self.get_status_display()))

    class Meta:
        verbose_name = apps.REPANIER_SETTINGS_PERMANENCE_NAME
        verbose_name_plural = apps.REPANIER_SETTINGS_PERMANENCES_NAME
        index_together = [
            ["permanence_date"],
        ]


class PermanenceInPreparation(Permanence):

    class Meta:
        proxy = True
        verbose_name = _("permanence in preparation")
        verbose_name_plural = _("permanences in preparation")


class PermanenceDone(Permanence):

    class Meta:
        proxy = True
        verbose_name = _("permanence done")
        verbose_name_plural = _("permanences done")


class PermanenceBoard(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        null=True, blank=True, db_index=True, on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME)
    # permanence_date duplicated to quickly calculate # participation of lasts 12 months
    permanence_date = models.DateField(_("permanence_date"), db_index=True)
    permanence_role = models.ForeignKey(
        LUT_PermanenceRole, verbose_name=_("permanence_role"),
        on_delete=models.PROTECT)

    class Meta:
        verbose_name = _("permanence board")
        verbose_name_plural = _("permanences board")
        ordering = ("permanence", "permanence_role", "customer",)
        unique_together = ("permanence", "permanence_role", "customer",)
        index_together = [
            ["permanence", "permanence_role", "customer"],
            ["permanence_date", "permanence", "permanence_role"],
        ]

    def __str__(self):
        return ""

@receiver(pre_save, sender=PermanenceBoard)
def permanence_board_pre_save(sender, **kwargs):
    permanence_board = kwargs['instance']
    permanence_board.permanence_date = permanence_board.permanence.permanence_date


@python_2_unicode_compatible
class CustomerInvoice(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, db_index=True)
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = models.DecimalField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # Calculated with Purchase
    total_price_with_tax = models.DecimalField(
        _("Total amount"),
        help_text=_('Total purchase amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_vat = models.DecimalField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_compensation = models.DecimalField(
        _("Total compensation"),
        help_text=_('Compensation part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)

    def __str__(self):
        return '%s, %s' % (self.customer, self.permanence)

    class Meta:
        verbose_name = _("customer invoice")
        verbose_name_plural = _("customers invoices")
        unique_together = ("permanence", "customer",)
        index_together = [
            ["permanence", "customer", ]
        ]


@python_2_unicode_compatible
class ProducerInvoice(models.Model):
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, db_index=True)
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True, db_index=True)
    date_previous_balance = models.DateField(
        _("date_previous_balance"), default=datetime.date.today)
    previous_balance = models.DecimalField(
        _("previous_balance"), max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    # Calculated with Purchase
    total_price_with_tax = models.DecimalField(
        _("Total amount"),
        help_text=_('Total purchase amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_vat = models.DecimalField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_compensation = models.DecimalField(
        _("Total compensation"),
        help_text=_('Compensation part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the original unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    date_balance = models.DateField(
        _("date_balance"), default=datetime.date.today)
    balance = models.DecimalField(
        _("balance"),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)

    def __str__(self):
        return '%s, %s' % (self.producer, self.permanence)

    class Meta:
        verbose_name = _("producer invoice")
        verbose_name_plural = _("producers invoices")
        unique_together = ("permanence", "producer",)
        index_together = [
            ["permanence", "producer", ]
        ]


class CustomerProducerInvoice(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"),
        on_delete=models.PROTECT)
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT, db_index=True)
    # Calculated with Purchase
    total_purchase_with_tax = models.DecimalField(
        _("producer amount invoiced"),
        help_text=_('Total selling amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase
    total_selling_with_tax = models.DecimalField(
        _("customer amount invoiced"),
        help_text=_('Total selling amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    def get_HTML_producer_price_purchased(self):
        if self.total_purchase_with_tax != DECIMAL_ZERO:
            return _("<b>%(price)s &euro;</b>") % {'price': number_format(self.total_purchase_with_tax, 2)}
        return ""

    get_HTML_producer_price_purchased.short_description = (_("producer amount invoiced"))
    get_HTML_producer_price_purchased.allow_tags = True
    get_HTML_producer_price_purchased.admin_order_field = 'total_purchase_with_tax'

    class Meta:
        verbose_name = _("customer x producer invoice")
        verbose_name_plural = _("customers x producers invoices")
        unique_together = ("permanence", "customer", "producer",)
        index_together = [
            ["permanence", "customer", "producer", ]
        ]


class CustomerSend(CustomerProducerInvoice):

    class Meta:
        proxy = True
        verbose_name = _("customer")
        verbose_name_plural = _("customers")


@python_2_unicode_compatible
class OfferItem(TranslatableModel):

    translations = TranslatedFields(
        long_name=models.CharField(_("long_name"), max_length=100,
            default='', blank=True, null=True),
        cache_part_a=HTMLField(default="", blank=True),
        cache_part_b=HTMLField(default="", blank=True),
        cache_part_c=HTMLField(default="", blank=True),
        cache_part_e=HTMLField(default="", blank=True),
        order_sort_order=models.IntegerField(
            _("order sort order for optimization of order view rendering"),
            default=0, db_index=True)
    )
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT,
         db_index=True
    )
    product = models.ForeignKey(
        Product, verbose_name=_("product"), blank=True, null=True, on_delete=models.PROTECT)
    # picture = FilerImageField(
    #     verbose_name=_("picture"), related_name="offeritem_picture",
    #     null=True, blank=True)
    picture2 = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="product", size=SIZE_M)

    reference = models.CharField(
        _("reference"), max_length=36, blank=True, null=True)
    department_for_customer = models.ForeignKey(
        LUT_DepartmentForCustomer,
        verbose_name=_("department_for_customer"), blank=True, null=True, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"), blank=True, null=True, on_delete=models.PROTECT)
    producer_invoice = models.ForeignKey(
        ProducerInvoice, verbose_name=_("producer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)

    order_unit = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_ORDER_UNIT,
        default=PRODUCT_ORDER_UNIT_PC,
        verbose_name=_("order unit"))
    wrapped = models.BooleanField(_('Individually wrapped by the producer'),
        default=False)
    order_average_weight = models.DecimalField(
        _("order_average_weight"),
        help_text=_('if useful, average order weight (eg : 0,1 Kg [i.e. 100 gr], 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    placement = models.CharField(
        max_length=3,
        choices=LUT_PRODUCT_PLACEMENT,
        default=PRODUCT_PLACEMENT_BASKET,
        verbose_name=_("product_placement"),
        help_text=_('used for helping to determine the order of preparation of this product'))

    producer_unit_price = models.DecimalField(
        _("producer unit price"),
        help_text=_('producer unit price (/piece or /kg or /l), including vat, without deposit'),
                    default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    customer_unit_price = models.DecimalField(
        _("customer unit price"),
        help_text=_('(/piece or /kg or /l), , including vat, without compensation, without deposit'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    producer_price_are_wo_vat = models.BooleanField(_("producer price are wo vat"), default=False)
    producer_vat = models.DecimalField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    customer_vat = models.DecimalField(
        _("vat"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    compensation = models.DecimalField(
        _("compensation"),
        help_text=_("compensation to add to the customer unit price"),
                    default=DECIMAL_ZERO, max_digits=8, decimal_places=4)
    unit_deposit = models.DecimalField(
        _("deposit"),
        help_text=_('deposit to add to the unit price'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    vat_level = models.CharField(
        max_length=3,
        choices=LUT_VAT,
        default=VAT_400,
        verbose_name=_("tax"))

    # Calculated with Purchase
    total_purchase_with_tax = models.DecimalField(
        _("producer amount invoiced"),
        help_text=_('Total purchase amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase
    total_selling_with_tax = models.DecimalField(
        _("customer amount invoiced"),
        help_text=_('Total selling amount vat or compensation if applicable included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    # Calculated with Purchase.
    # If Permanence.status < SEND this is the order quantity
    # During sending the orders to the producer this become the invoiced quantity
    # via tools.recalculate_order_amount(..., send_to_producer=True)
    quantity_invoiced = models.DecimalField(
        _("quantity invoiced"),
        help_text=_('quantity invoiced to our customer'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)

    is_active = models.BooleanField(_("is_active"), default=True)
    limit_order_quantity_to_stock = models.BooleanField(_("limit maximum order qty of the group to stock qty"), default=False)
    manage_stock = models.BooleanField(_("manage stock"), default=False)
    producer_pre_opening = models.BooleanField(_("producer pre-opening"), default=False)

    price_list_multiplier = models.DecimalField(
        _("price_list_multiplier"),
        help_text=_("This multiplier is applied to each price automatically imported/pushed."),
        default=DECIMAL_ZERO, max_digits=4, decimal_places=2)
    is_resale_price_fixed = models.BooleanField(_("the resale price is set by the producer"),
        default=False)

    stock = models.DecimalField(
        _("Current stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=3)
    add_2_stock = models.DecimalField(
        _("Add 2 stock"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    new_stock = models.DecimalField(
        _("Final stock"),
        default=None, max_digits=9, decimal_places=3, null=True)

    customer_minimum_order_quantity = models.DecimalField(
        _("customer_minimum_order_quantity"),
        help_text=_('minimum order qty (eg : 0,1 Kg [i.e. 100 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_increment_order_quantity = models.DecimalField(
        _("customer_increment_order_quantity"),
        help_text=_('increment order qty (eg : 0,05 Kg [i.e. 50max 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    customer_alert_order_quantity = models.DecimalField(
        _("customer_alert_order_quantity"),
        help_text=_('maximum order qty before alerting the customer to check (eg : 1,5 Kg, 12 pieces, 9 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)
    producer_order_by_quantity = models.DecimalField(
        _("Producer order by quantity"),
        help_text=_('1,5 Kg [i.e. 1500 gr], 1 piece, 3 Kg)'),
        default=DECIMAL_ZERO, max_digits=6, decimal_places=3)

    def __init__(self, *args, **kwargs):
        super(OfferItem, self).__init__(*args, **kwargs)
        if self.id is not None and self.manage_stock:
            # self.previous_stock = self.stock
            self.previous_add_2_stock = self.add_2_stock
            self.previous_producer_unit_price = self.producer_unit_price
            self.previous_unit_deposit = self.unit_deposit
        else:
            # self.previous_stock = DECIMAL_ZERO
            self.previous_add_2_stock = DECIMAL_ZERO
            self.previous_producer_unit_price =  DECIMAL_ZERO
            self.previous_unit_deposit = DECIMAL_ZERO

    def save(self, *args, **kwargs):
        if self.manage_stock:
            if(self.previous_add_2_stock != self.add_2_stock or
                self.previous_producer_unit_price != self.producer_unit_price or
                self.previous_unit_deposit != self.unit_deposit
            ):
                if self.producer_invoice is None:
                    producer_invoice = ProducerInvoice.objects.filter(
                        permanence_id=self.permanence_id,
                        producer_id=self.producer_id).only("id").order_by().first()
                    if producer_invoice is not None:
                        self.producer_invoice_id = producer_invoice.id
                    else:
                        self.producer_invoice = ProducerInvoice.objects.create(
                            permanence_id=self.permanence_id,
                            producer_id=self.producer_id
                        )
                # delta_stock = self.stock - self.previous_stock
                previous_purchase_price = ((self.previous_producer_unit_price +
                    self.previous_unit_deposit) * self.previous_add_2_stock).quantize(TWO_DECIMALS)
                purchase_price = ((self.producer_unit_price +
                    self.unit_deposit) * self.add_2_stock).quantize(TWO_DECIMALS)
                delta_add_2_stock_invoiced = self.add_2_stock - self.previous_add_2_stock
                delta_purchase_price = purchase_price - previous_purchase_price
                ProducerInvoice.objects.filter(id=self.producer_invoice_id).update(
                    total_price_with_tax=F('total_price_with_tax') +
                    delta_purchase_price
                )
                self.quantity_invoiced += delta_add_2_stock_invoiced
                self.total_purchase_with_tax += delta_purchase_price
                # Do not do it twice
                # self.previous_stock = self.stock
                self.previous_add_2_stock = self.add_2_stock
                self.previous_producer_unit_price = self.producer_unit_price
                self.previous_unit_deposit = self.unit_deposit
        super(OfferItem, self).save(*args, **kwargs)

    def get_producer(self):
        return self.producer.short_profile_name

    get_producer.short_description = (_("producers"))
    get_producer.allow_tags = False

    def get_product(self):
        return self.product.long_name

    get_product.short_description = (_("products"))
    get_product.allow_tags = False

    def get_producer_qty_stock_invoiced(self):
        # Return quantity to buy to the producer and stock used to deliver the invoiced quantity
        if self.quantity_invoiced > DECIMAL_ZERO:
            if self.manage_stock:
                # if RepanierSettings.producer_pre_opening then the stock is the max available qty by the producer,
                # not into our stock
                if self.stock == DECIMAL_ZERO:
                    return self.quantity_invoiced, DECIMAL_ZERO
                else:
                    quantity_for_customer = self.quantity_invoiced - self.add_2_stock
                    delta = (quantity_for_customer - self.stock).quantize(FOUR_DECIMALS)
                    if delta <= DECIMAL_ZERO:
                        # i.e. quantity_for_customer <= self.stock
                        if self.add_2_stock == DECIMAL_ZERO:
                            return DECIMAL_ZERO, self.quantity_invoiced
                        else:
                            return self.add_2_stock, quantity_for_customer
                    else:
                        return delta + self.add_2_stock, self.stock
            else:
                return self.quantity_invoiced, DECIMAL_ZERO
        return DECIMAL_ZERO, DECIMAL_ZERO

    def get_HTML_producer_qty_stock_invoiced(self):
        qty, stock = self.get_producer_qty_stock_invoiced()
        if qty == DECIMAL_ZERO:
            if stock == DECIMAL_ZERO:
                return ""
            else:
                return _("stock %(stock)s") % {'stock': number_format(stock, 4)}
        else:
            if stock == DECIMAL_ZERO:
                return _("<b>%(qty)s</b>") % {'qty': number_format(qty, 4)}
            else:
                return _("<b>%(qty)s</b> + stock %(stock)s") % {'qty': number_format(qty, 4),
                                                                'stock': number_format(stock, 4)}

    get_HTML_producer_qty_stock_invoiced.short_description = (_("quantity invoiced"))
    get_HTML_producer_qty_stock_invoiced.allow_tags = True
    get_HTML_producer_qty_stock_invoiced.admin_order_field = 'quantity_invoiced'

    def get_producer_qty_invoiced(self):
        qty, stock = self.get_producer_qty_stock_invoiced()
        return qty

    def get_producer_price_invoiced(self):
        qty, stock = self.get_producer_qty_stock_invoiced()
        if self.customer_unit_price < self.producer_unit_price:
            return ((self.customer_unit_price + self.unit_deposit) * qty).quantize(TWO_DECIMALS)
        else:
            return ((self.producer_unit_price + self.unit_deposit) * qty).quantize(TWO_DECIMALS)

    def get_HTML_producer_price_purchased(self):
        qty, stock = self.get_producer_qty_stock_invoiced()
        price = ((self.producer_unit_price + self.unit_deposit) * qty).quantize(TWO_DECIMALS)
        if price != DECIMAL_ZERO:
            return _("<b>%(price)s &euro;</b>") % {'price': number_format(price, 2)}
        return ""

    get_HTML_producer_price_purchased.short_description = (_("producer amount invoiced"))
    get_HTML_producer_price_purchased.allow_tags = True
    get_HTML_producer_price_purchased.admin_order_field = 'total_purchase_with_tax'

    def get_long_name(self, is_quantity_invoiced=False):
        if is_quantity_invoiced and self.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            qty_display, price_display = get_display(
                1,
                self.order_average_weight,
                PRODUCT_ORDER_UNIT_KG,
                0,
                False
            )
        else:
            qty_display, price_display = get_display(
                1,
                self.order_average_weight,
                self.order_unit,
                0,
                False
            )
        return '%s %s' % (self.long_name, qty_display)

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'translations__long_name'

    def get_qty_display(self):
        qty_display, price_display = get_display(
            1,
            self.order_average_weight,
            self.order_unit,
            0,
            False
        )
        if self.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            return " (%s) %s/%s)" % (_('kg'), qty_display[:-1], _('piece'))
        return qty_display

    get_qty_display.short_description = (_("qty_display"))
    get_qty_display.allow_tags = False

    @property
    def producer_unit_price_wo_tax(self):
        if self.producer_price_are_wo_vat:
            return self.producer_unit_price
        else:
            return self.producer_unit_price - self.producer_vat

    @property
    def unit_price_with_compensation(self):
        return (self.customer_unit_price + self.compensation).quantize(TWO_DECIMALS)

    @property
    def reference_price_with_compensation(self):
        if self.order_average_weight > DECIMAL_ZERO:
            if self.order_unit in [PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
                reference_price = ((self.customer_unit_price + self.compensation) / self.order_average_weight).quantize(TWO_DECIMALS)
                return number_format(reference_price, 2)
            else:
                return ""
        else:
            return ""

    @property
    def reference_price_with_vat(self):
        if self.order_average_weight > DECIMAL_ZERO:
            if self.order_unit in [PRODUCT_ORDER_UNIT_PC_PRICE_KG, PRODUCT_ORDER_UNIT_PC_PRICE_LT, PRODUCT_ORDER_UNIT_PC_PRICE_PC]:
                reference_price = (self.customer_unit_price / self.order_average_weight).quantize(TWO_DECIMALS)
                return number_format(reference_price, 2)
            else:
                return ""
        else:
            return ""

    def __str__(self):
        return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())

    class Meta:
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")
        unique_together = ("permanence", "product",)
        index_together = [
            ["permanence", "product"],
        ]


class OfferItemSend(OfferItem):

    class Meta:
        proxy = True
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")


@python_2_unicode_compatible
class OfferItemClosed(OfferItem):

    def __str__(self):
        return '%s, %s' % (self.producer.short_profile_name, self.get_long_name(is_quantity_invoiced=True))

    class Meta:
        proxy = True
        verbose_name = _("offer's item")
        verbose_name_plural = _("offer's items")


@python_2_unicode_compatible
class Purchase(models.Model):
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME, on_delete=models.PROTECT, db_index=True)
    permanence_date = models.DateField(_("permanence_date"))
    offer_item = models.ForeignKey(
        OfferItem, verbose_name=_("offer_item"), blank=True, null=True, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"), blank=True, null=True, on_delete=models.PROTECT)
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT,
        db_index=True)
    customer_producer_invoice = models.ForeignKey(
        CustomerProducerInvoice, verbose_name=_("customer_producer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    producer_invoice = models.ForeignKey(
        ProducerInvoice, verbose_name=_("producer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    customer_invoice = models.ForeignKey(
        CustomerInvoice, verbose_name=_("customer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)

    quantity_ordered = models.DecimalField(
        _("quantity ordered"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
    # 0 if this is not a KG product -> the preparation list for this product will be produced by family
    # qty if not -> the preparation list for this product will be produced by qty then by family
    quantity_for_preparation_sort_order = models.DecimalField(
        _("quantity for preparation order_by"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO)
    quantity_invoiced = models.DecimalField(
        _("quantity invoiced"),
        max_digits=9, decimal_places=4, default=DECIMAL_ZERO, blank=True)
    invoiced_price_with_compensation = models.BooleanField(
        _("Set if the invoiced price is the price with compensation, otherwise it's the price with vat"), default=True)
    purchase_price = models.DecimalField(
        _("producer row price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    selling_price = models.DecimalField(
        _("customer row price"),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)

    comment = models.CharField(
        _("comment"), max_length=100, default='', blank=True, null=True)

    def get_customer_unit_price(self):
        if self.offer_item is not None:
            compensation = self.offer_item.compensation \
                if self.invoiced_price_with_compensation else DECIMAL_ZERO
            return (self.offer_item.customer_unit_price + compensation).quantize(TWO_DECIMALS)
        else:
            raise AttributeError

    get_customer_unit_price.short_description = (_("customer unit price"))
    get_customer_unit_price.allow_tags = False

    def get_unit_deposit(self):
        if self.offer_item is not None:
            return self.offer_item.unit_deposit
        else:
            raise AttributeError

    get_unit_deposit.short_description = (_("deposit"))
    get_unit_deposit.allow_tags = False

    def get_producer_unit_price(self):
        if self.offer_item is not None:
            compensation = self.offer_item.compensation \
                if self.invoiced_price_with_compensation else DECIMAL_ZERO
            return (self.offer_item.producer_unit_price + compensation).quantize(TWO_DECIMALS)
        else:
            raise AttributeError

    get_producer_unit_price.short_description = (_("producer unit price"))
    get_producer_unit_price.allow_tags = False

    def get_HTML_producer_unit_price(self):
        if self.quantity_invoiced > DECIMAL_ZERO and self.offer_item is not None:
            return _("<b>%(price)s &euro;</b>") % {'price': number_format(self.get_producer_unit_price(), 2)}
        return ""

    get_HTML_producer_unit_price.short_description = (_("producer unit price"))
    get_HTML_producer_unit_price.allow_tags = True

    def get_HTML_unit_deposit(self):
        if self.quantity_invoiced > DECIMAL_ZERO and self.offer_item is not None:
            return _("<b>%(price)s &euro;</b>") % {'price': number_format(self.offer_item.deposit, 2)}
        return ""

    get_HTML_unit_deposit.short_description = (_("deposit"))
    get_HTML_unit_deposit.allow_tags = True

    def __str__(self):
        # Use to not display label (inline_admin_form.original) into the inline form (tabular.html)
        return ""
        # return '%s, %s' % (self.producer.short_profile_name, self.get_long_name())

    class Meta:
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")
        ordering = ("permanence", "customer", "offer_item")
        unique_together = ("permanence", "offer_item", "customer",)
        index_together = [
            ["offer_item", "customer"],
        ]


class PurchaseOpenedOrClosed(Purchase):

    def get_quantity(self):
        return self.quantity_ordered

    get_quantity.short_description = (_("quantity ordered"))
    get_quantity.allow_tags = False

    def get_long_name(self):
        if self.offer_item is not None:
            return self.offer_item.get_long_name(is_quantity_invoiced=False)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'offer_item__translations__long_name'

    class Meta:
        proxy = True
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")


class PurchaseOpenedOrClosedForUpdate(Purchase):

    def __init__(self, *args, **kwargs):
        super(PurchaseOpenedOrClosedForUpdate, self).__init__(*args, **kwargs)
        if self.id is not None:
            self.previous_quantity_ordered = self.quantity_ordered
            self.previous_selling_price = self.selling_price
            self.previous_comment = self.comment
        else:
            self.previous_quantity_ordered = DECIMAL_ZERO
            self.previous_selling_price = DECIMAL_ZERO
            self.previous_comment = ""

    def get_quantity(self):
        return self.quantity_ordered

    get_quantity.short_description = (_("quantity ordered"))
    get_quantity.allow_tags = False

    def set_quantity(self, quantity):
        self.quantity_ordered = quantity
        return quantity

    # @transaction.atomic
    def save(self, *args, **kwargs):
        if self.offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
            self.selling_price = (self.get_customer_unit_price() *
                    self.offer_item.order_average_weight * self.quantity_ordered).quantize(TWO_DECIMALS)
        else:
            self.selling_price = ((self.get_customer_unit_price() +
                        self.offer_item.unit_deposit) * self.quantity_ordered).quantize(TWO_DECIMALS)
        if (self.previous_quantity_ordered != self.quantity_ordered or
            self.previous_selling_price != self.selling_price):

            if self.customer_invoice is None:
                self.customer_invoice = CustomerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_id).only("id").order_by().first()
                if self.customer_invoice is None:
                    self.customer_invoice = CustomerInvoice.objects.create(
                        permanence_id=self.permanence_id,
                        customer_id=self.customer_id
                    )

            delta_quantity_ordered = self.quantity_ordered - self.previous_quantity_ordered
            delta_selling_price = self.selling_price - self.previous_selling_price

            CustomerInvoice.objects.filter(id=self.customer_invoice.id).update(
                total_price_with_tax=F('total_price_with_tax') +
                delta_selling_price
            )
            OfferItem.objects.filter(id=self.offer_item_id).update(
                quantity_invoiced=F('quantity_invoiced') +
                delta_quantity_ordered,
            )
            # Do not do it twice
            self.previous_quantity_ordered = self.quantity_ordered
            self.previous_selling_price = self.selling_price
            super(PurchaseOpenedOrClosedForUpdate, self).save(*args, **kwargs)
        elif self.previous_comment != self.comment:
            super(PurchaseOpenedOrClosedForUpdate, self).save(*args, **kwargs)

    @property
    def is_quantity_invoiced(self):
        return False

    def get_long_name(self):
        if self.offer_item is not None:
            return self.offer_item.get_long_name(is_quantity_invoiced=False)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'offer_item__translations__long_name'

    class Meta:
        proxy = True
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")


class PurchaseSend(Purchase):

    def get_quantity(self):
        return self.quantity_invoiced

    get_quantity.short_description = (_("quantity invoiced"))
    get_quantity.allow_tags = False

    def get_long_name(self):
        if self.offer_item is not None:
            return self.offer_item.get_long_name(is_quantity_invoiced=True)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'offer_item__translations__long_name'

    class Meta:
        proxy = True
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")


class PurchaseSendForUpdate(Purchase):

    def __init__(self, *args, **kwargs):
        super(PurchaseSendForUpdate, self).__init__(*args, **kwargs)
        if self.id is not None:
            self.previous_quantity_invoiced = self.quantity_invoiced
            self.previous_purchase_price = self.purchase_price
            self.previous_selling_price = self.selling_price
            self.previous_comment = self.comment
            self.previous_customer_unit_price = self.offer_item.customer_unit_price
            self.previous_producer_unit_price = self.offer_item.producer_unit_price
            self.previous_unit_deposit = self.offer_item.unit_deposit
        else:
            self.previous_quantity_invoiced = DECIMAL_ZERO
            self.previous_purchase_price = DECIMAL_ZERO
            self.previous_selling_price = DECIMAL_ZERO
            self.previous_comment = ""
            self.previous_customer_unit_price = DECIMAL_ZERO
            self.previous_producer_unit_price = DECIMAL_ZERO
            self.previous_unit_deposit = DECIMAL_ZERO

    def get_quantity(self):
        return self.quantity_invoiced

    get_quantity.short_description = (_("quantity invoiced"))
    get_quantity.allow_tags = False

    def set_quantity(self, quantity):
        self.quantity_invoiced = quantity
        return quantity

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.purchase_price = ((self.get_producer_unit_price() +
                self.offer_item.unit_deposit) * self.quantity_invoiced).quantize(TWO_DECIMALS)
        self.selling_price = ((self.get_customer_unit_price() +
                self.offer_item.unit_deposit) * self.quantity_invoiced).quantize(TWO_DECIMALS)
        if (self.previous_quantity_invoiced != self.quantity_invoiced or
            self.previous_purchase_price != self.purchase_price or
            self.previous_selling_price != self.selling_price):

            if self.customer_invoice is None:
                self.customer_invoice = CustomerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_id).only("id").order_by().first()
                if self.customer_invoice is None:
                    self.customer_invoice = CustomerInvoice.objects.create(
                        permanence_id=self.permanence_id,
                        customer_id=self.customer_id
                    )
            if self.producer_invoice is None:
                producer_invoice = ProducerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    producer_id=self.producer_id).only("id").order_by().first()
                if producer_invoice is not None:
                    self.producer_invoice_id = producer_invoice.id
                else:
                    self.producer_invoice = ProducerInvoice.objects.create(
                        permanence_id=self.permanence_id,
                        producer_id=self.producer_id
                    )
            if self.customer_producer_invoice is None:
                customer_producer_invoice = CustomerProducerInvoice.objects.filter(
                    permanence_id=self.permanence_id,
                    customer_id=self.customer_id,
                    producer_id=self.producer_id).only("id").order_by().first()
                if customer_producer_invoice is not None:
                    self.customer_producer_invoice_id = customer_producer_invoice.id
                else:
                    self.customer_producer_invoice = CustomerProducerInvoice.objects.create(
                        permanence_id=self.permanence_id,
                        customer_id=self.customer_id,
                        producer_id=self.producer_id
                    )

            delta_quantity_invoiced = self.quantity_invoiced - self.previous_quantity_invoiced
            delta_purchase_price = self.purchase_price - self.previous_purchase_price
            delta_selling_price = self.selling_price - self.previous_selling_price

            CustomerInvoice.objects.filter(id=self.customer_invoice.id).update(
                total_price_with_tax=F('total_price_with_tax') +
                delta_selling_price
            )
            CustomerProducerInvoice.objects.filter(id=self.customer_producer_invoice_id).update(
                total_purchase_with_tax=F('total_purchase_with_tax') +
                delta_purchase_price,
                total_selling_with_tax=F('total_selling_with_tax') +
                delta_selling_price
            )

            self.offer_item = OfferItem.objects.select_for_update().filter(id=self.offer_item_id).order_by().first()

            if self.offer_item.manage_stock:
                previous_qty, previous_stock = self.offer_item.get_producer_qty_stock_invoiced()
                if self.previous_customer_unit_price < self.previous_producer_unit_price:
                    previous_total_price_with_tax = (
                        (self.previous_customer_unit_price + self.previous_unit_deposit) * previous_qty
                    ).quantize(TWO_DECIMALS)
                else:
                    previous_total_price_with_tax = (
                        (self.previous_producer_unit_price + self.previous_unit_deposit) * previous_qty
                    ).quantize(TWO_DECIMALS)

                self.offer_item.quantity_invoiced += delta_quantity_invoiced
                self.offer_item.total_purchase_with_tax += delta_purchase_price
                self.offer_item.total_selling_with_tax += delta_selling_price

                qty, stock = self.offer_item.get_producer_qty_stock_invoiced()
                if self.offer_item.customer_unit_price < self.offer_item.producer_unit_price:
                    delta_total_price_with_tax = (
                        (self.offer_item.customer_unit_price + self.offer_item.unit_deposit) * qty
                    ).quantize(TWO_DECIMALS) - previous_total_price_with_tax
                else:
                    delta_total_price_with_tax = (
                        (self.offer_item.producer_unit_price + self.offer_item.unit_deposit) * qty
                    ).quantize(TWO_DECIMALS) - previous_total_price_with_tax
            else:
                self.offer_item.quantity_invoiced += delta_quantity_invoiced
                self.offer_item.total_purchase_with_tax += delta_purchase_price
                self.offer_item.total_selling_with_tax += delta_selling_price

                if self.offer_item.customer_unit_price < self.offer_item.producer_unit_price:
                    delta_total_price_with_tax = delta_selling_price
                else:
                    delta_total_price_with_tax = delta_purchase_price

            ProducerInvoice.objects.filter(id=self.producer_invoice_id).update(
                total_price_with_tax=F('total_price_with_tax') +
                delta_total_price_with_tax
            )

            OfferItem.objects.filter(id=self.offer_item_id).update(
                quantity_invoiced=F('quantity_invoiced') +
                delta_quantity_invoiced,
                total_purchase_with_tax=F('total_purchase_with_tax') +
                delta_purchase_price,
                total_selling_with_tax=F('total_selling_with_tax') +
                delta_selling_price
            )
            # Do not do it twice
            self.previous_quantity_invoiced = self.quantity_invoiced
            self.previous_purchase_price = self.purchase_price
            self.previous_selling_price = self.selling_price
            super(PurchaseSendForUpdate, self).save(*args, **kwargs)
        elif self.previous_comment != self.comment:
            super(PurchaseSendForUpdate, self).save(*args, **kwargs)

    @property
    def is_quantity_invoiced(self):
        return True

    def get_long_name(self):
        if self.offer_item is not None:
            return self.offer_item.get_long_name(is_quantity_invoiced=True)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'offer_item__translations__long_name'

    class Meta:
        proxy = True
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")


class PurchaseInvoiced(Purchase):

    def get_quantity(self):
        return self.quantity_invoiced

    get_quantity.short_description = (_("quantity invoiced"))
    get_quantity.allow_tags = False

    def get_long_name(self):
        if self.offer_item is not None:
            return self.offer_item.get_long_name(is_quantity_invoiced=True)
        else:
            raise AttributeError

    get_long_name.short_description = (_("long_name"))
    get_long_name.allow_tags = False
    get_long_name.admin_order_field = 'offer_item__translations__long_name'

    class Meta:
        proxy = True
        verbose_name = _("purchase")
        verbose_name_plural = _("purchases")


class BankAccount(models.Model):
    permanence = models.ForeignKey(
        Permanence, verbose_name=apps.REPANIER_SETTINGS_PERMANENCE_NAME,
        on_delete=models.PROTECT, blank=True, null=True)
    producer = models.ForeignKey(
        Producer, verbose_name=_("producer"),
        on_delete=models.PROTECT, blank=True, null=True)
    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"),
        on_delete=models.PROTECT, blank=True, null=True)
    operation_date = models.DateField(_("operation_date"),
                                      db_index=True)
    operation_comment = models.CharField(
        _("operation_comment"), max_length=100, null=True, blank=True)
    operation_status = models.CharField(
        max_length=3,
        choices=LUT_BANK_TOTAL,
        default=BANK_NOT_LATEST_TOTAL,
        verbose_name=_("Bank balance status"),
    )
    bank_amount_in = models.DecimalField(
        _("bank_amount_in"), help_text=_('payment_on_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    bank_amount_out = models.DecimalField(
        _("bank_amount_out"), help_text=_('payment_from_the_account'),
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO)
    producer_invoice = models.ForeignKey(
        ProducerInvoice, verbose_name=_("producer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    customer_invoice = models.ForeignKey(
        CustomerInvoice, verbose_name=_("customer_invoice"),
        blank=True, null=True, on_delete=models.PROTECT, db_index=True)
    is_created_on = models.DateTimeField(
        _("is_created_on"), auto_now_add=True)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)

    def get_bank_amount_in(self):
        return self.bank_amount_in if self.bank_amount_in != DECIMAL_ZERO else ""

    get_bank_amount_in.short_description = (_("bank_amount_in"))
    get_bank_amount_in.allow_tags = False
    get_bank_amount_in.admin_order_field = 'bank_amount_in'

    def get_bank_amount_out(self):
        return self.bank_amount_out if self.bank_amount_out != DECIMAL_ZERO else ""

    get_bank_amount_out.short_description = (_("bank_amount_out"))
    get_bank_amount_out.allow_tags = False
    get_bank_amount_out.admin_order_field = 'bank_amount_out'

    def get_producer(self):
        if self.producer:
            return self.producer
        else:
            if self.customer is None:
                # This is a total, show it
                if self.operation_status == BANK_LATEST_TOTAL:
                    return "=============="
                else:
                    return "--------------"
            return ""

    get_producer.short_description = (_("producer"))
    get_producer.allow_tags = False
    get_producer.admin_order_field = 'producer'

    def get_customer(self):
        if self.customer:
            return self.customer
        else:
            if self.producer is None:
                # This is a total, show it
                if self.operation_status == BANK_LATEST_TOTAL:
                    return "=============="
                else:
                    return "--------------"
            return ""

    get_customer.short_description = (_("customers"))
    get_customer.allow_tags = False
    get_customer.admin_order_field = 'customer'

    class Meta:
        verbose_name = _("bank account movement")
        verbose_name_plural = _("bank account movements")
        ordering = ('-operation_date', '-id')
        index_together = [
            ['operation_date', 'id'],
            ['customer_invoice', 'operation_date'],
            ['producer_invoice', 'operation_date'],
        ]


@receiver(pre_save, sender=BankAccount)
def bank_account_pre_save(sender, **kwargs):
    bank_account = kwargs['instance']
    if bank_account.producer is None and bank_account.customer is None:
        initial_balance = BankAccount.objects.filter(
            producer__isnull=True, customer__isnull=True).order_by().first()
        if initial_balance is None:
            bank_account.operation_status = BANK_LATEST_TOTAL
            bank_account.permanence = None
            bank_account.operation_comment = _("Initial balance")
            bank_account.producer_invoice = None
            bank_account.customer_invoice = None