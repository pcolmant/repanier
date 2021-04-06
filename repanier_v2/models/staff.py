from django.db import models
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from parler.managers import TranslatableQuerySet, TranslatableManager
from parler.models import TranslatableModel, TranslatedFields

from repanier_v2.const import *


class StaffQuerySet(TranslatableQuerySet):
    pass


class StaffManager(TreeManager, TranslatableManager):
    queryset_class = StaffQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class Staff(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    customer_responsible = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer responsible"),
        on_delete=models.PROTECT,
        null=True,
        default=None,
        blank=False,
    )
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"), default=DECIMAL_ZERO, max_digits=2, decimal_places=0
    )
    translations = TranslatedFields(
        long_name=models.CharField(
            _("Long name"),
            max_length=100,
            db_index=True,
            blank=True,
            default=EMPTY_STRING,
        ),
        function_description=HTMLField(
            _("Function description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            blank=True,
            default=EMPTY_STRING,
        ),
    )

    is_repanier_admin = models.BooleanField(_("Repanier administrator"), default=False)
    is_order_manager = models.BooleanField(
        _("Offers in preparation manager"), default=False
    )
    is_invoice_manager = models.BooleanField(_("Billing offers manager"), default=False)
    is_webmaster = models.BooleanField(_("Webmaster"), default=False)
    is_other_manager = models.BooleanField(_("Other responsibility"), default=False)
    can_be_contacted = models.BooleanField(_("Can be contacted"), default=True)

    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None
    )
    is_active = models.BooleanField(_("Active"), default=True)

    @classmethod
    def get_or_create_any_coordinator(cls):
        coordinator = (
            Staff.objects.filter(
                is_active=True, is_repanier_admin=True, can_be_contacted=True
            )
            .order_by("id")
            .first()
        ) or (
            Staff.objects.filter(is_active=True, is_repanier_admin=True)
            .order_by("id")
            .first()
        )
        if coordinator is None:
            # Create the very first staff member
            from repanier_v2.models.customer import Customer

            customer_buyinggroup = Customer.get_or_create_default()
            coordinator = Staff.objects.create(
                is_active=True,
                is_repanier_admin=True,
                is_order_manager=True,  # The first coordinator is also order manager (by default)
                is_invoice_manager=True,  # The first coordinator is also invoice manager (by default)
                is_webmaster=True,
                customer_responsible=customer_buyinggroup,
                can_be_contacted=True,
                long_name=_("Coordinator"),
            )
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)
                coordinator.set_current_language(language_code, initialize=True)
                coordinator.long_name = _("Coordinator")
                coordinator.save()
            translation.activate(cur_language)
        return coordinator

    @classmethod
    def get_or_create_order_responsible(cls):
        signature = []
        html_signature = []
        to_email = []
        order_responsible_qs = Staff.objects.filter(
            is_active=True, is_order_manager=True
        ).order_by("?")
        for order_responsible in order_responsible_qs:
            if order_responsible.customer_responsible is not None:
                if order_responsible.can_be_contacted:
                    signature.append(order_responsible.get_str_member)
                    html_signature.append(order_responsible.get_html_signature)
                to_email.extend(order_responsible.get_to_email)
        separator = chr(10) + " "
        return {
            "signature": separator.join(signature),
            "html_signature": mark_safe("<br>".join(html_signature)),
            "to_email": to_email,
        }

    @classmethod
    def get_or_create_invoice_responsible(cls):
        signature = []
        html_signature = []
        to_email = []
        invoice_responsible_qs = Staff.objects.filter(
            is_active=True, is_invoice_manager=True
        ).order_by("?")
        for invoice_responsible in invoice_responsible_qs:
            if invoice_responsible.customer_responsible is not None:
                if invoice_responsible.can_be_contacted:
                    signature.append(invoice_responsible.get_str_member)
                    html_signature.append(invoice_responsible.get_html_signature)
                to_email.extend(invoice_responsible.get_to_email)
        separator = chr(10) + " "
        return {
            "signature": separator.join(signature),
            "html_signature": mark_safe("<br>".join(html_signature)),
            "to_email": to_email,
        }

    @cached_property
    def get_html_signature(self):
        function_name = self.safe_translation_getter(
            "long_name", any_language=True, default=EMPTY_STRING
        )
        if self.customer_responsible is not None:
            customer = self.customer_responsible
            customer_name = customer.long_name or customer.short_name
            customer_contact_info = "{}{}".format(
                customer_name, customer.get_phone1(prefix=" - ")
            )
            html_signature = mark_safe(
                "{}<br>{}<br>{}".format(
                    customer_contact_info,
                    function_name,
                    settings.REPANIER_SETTINGS_GROUP_NAME,
                )
            )
        else:
            html_signature = mark_safe(
                "{}<br>{}".format(function_name, settings.REPANIER_SETTINGS_GROUP_NAME)
            )
        return html_signature

    @cached_property
    def get_to_email(self):
        if self.customer_responsible is not None:
            to_email = [self.customer_responsible.user.email]
        else:
            to_email = [settings.DEFAULT_FROM_EMAIL]
        return to_email

    @cached_property
    def get_str_member(self):
        if self.customer_responsible is not None:
            return "{} : {}{}".format(
                # --
                # Django 3.0, python 3.7
                # if use "self" : TypeError: __str__ returned non-string (type __proxy__)
                self.safe_translation_getter(
                    "long_name", any_language=True, default=EMPTY_STRING
                ),
                # --
                self.customer_responsible.long_name or self.customer_responsible,
                self.customer_responsible.get_phone1(prefix=" (", postfix=")"),
            )
        else:
            return "{}".format(self)

    objects = StaffManager()

    def __str__(self):
        return self.safe_translation_getter(
            "long_name", any_language=True, default=EMPTY_STRING
        )

    class Meta:
        verbose_name = _("Staff member")
        verbose_name_plural = _("Staff members")
