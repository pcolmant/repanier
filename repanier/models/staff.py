# -*- coding: utf-8

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from parler.managers import TranslatableQuerySet, TranslatableManager
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *


class StaffQuerySet(TranslatableQuerySet):
    pass


class StaffManager(TreeManager, TranslatableManager):
    queryset_class = StaffQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


class Staff(MPTTModel, TranslatableModel):
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("Login"))
    customer_responsible = models.ForeignKey(
        'Customer', verbose_name=_("Customer responsible"),
        on_delete=models.PROTECT)
    login_attempt_counter = models.DecimalField(
        _("Login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    translations = TranslatedFields(
        long_name=models.CharField(_("Long name"), max_length=100, db_index=True, null=True, default=EMPTY_STRING),
        function_description=HTMLField(_("Function description"), configuration='CKEDITOR_SETTINGS_MODEL2',
                                       blank=True, default=EMPTY_STRING),
    )
    is_reply_to_order_email = models.BooleanField(
        _("Responsible for orders; this contact is used to transmit offers and orders"),
        default=False)
    is_reply_to_invoice_email = models.BooleanField(
        _("Responsible for invoices; this contact is used to transmit invoices"),
        default=False)
    is_contributor = models.BooleanField(_("Producer referent"),
                                         default=False)
    is_webmaster = models.BooleanField(_("Webmaster"),
                                       default=False)
    is_coordinator = models.BooleanField(_("Coordonnateur"),
                                         default=False)
    is_tester = models.BooleanField(_("Tester"),
                                    default=False)
    password_reset_on = models.DateTimeField(
        _("Password reset on"), null=True, blank=True, default=None)
    is_active = models.BooleanField(_("Active"), default=True)

    @classmethod
    def get_order_responsible(cls):
        return cls.objects.filter(is_active=True, is_reply_to_order_email=True).order_by('?').first()

    @classmethod
    def get_invoice_responsible(cls):
        return cls.objects.filter(is_active=True, is_reply_to_invoice_email=True).order_by('?').first()

    def get_customer_phone1(self):
        try:
            return self.customer_responsible.phone1
        except:
            return "----"
    get_customer_phone1.short_description = (_("Phone1"))

    @cached_property
    def get_html_signature(self):
        from repanier.apps import REPANIER_SETTINGS_GROUP_NAME

        function_name = self.safe_translation_getter(
            'long_name', any_language=True, default=EMPTY_STRING
        )
        customer = self.customer_responsible
        customer_name = customer.long_basket_name or customer.short_basket_name
        customer_phone = []
        if customer.phone1:
            customer_phone.append(customer.phone1)
        if customer.phone2:
            customer_phone.append(customer.phone2)
        customer_phone_str = " / ".join(customer_phone)
        if customer_phone_str:
            customer_contact_info = "{} - {}".format(customer_name, customer_phone_str)
        else:
            customer_contact_info = customer_name
        html_signature = mark_safe(
            "{}<br>{}<br>{}".format(
                customer_contact_info, function_name, REPANIER_SETTINGS_GROUP_NAME
            )
        )
        return html_signature

    @cached_property
    def get_from_email(self):
        if settings.DJANGO_SETTINGS_DEMO:
            from_email = "no-reply@repanier.be"
        else:
            from repanier.apps import REPANIER_SETTINGS_CONFIG
            config = REPANIER_SETTINGS_CONFIG
            if config.email_is_custom:
                from_email = config.email_host_user
            else:
                staff_email = self.user.email
                if staff_email:
                    if staff_email.endswith(settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION):
                        from_email = staff_email
                    else:
                        # The mail address of the staff member doesn't end with an allowed mail extension,
                        # set a generic one
                        from_email = "no-reply@repanier.be"
                else:
                    # No specific mail address for the staff member,
                    # set a generic one
                    from_email = "no-reply@repanier.be"
        return from_email

    @cached_property
    def get_reply_to_email(self):
        if settings.DJANGO_SETTINGS_DEMO:
            reply_to_email = "no-reply@repanier.be"
        else:
            from repanier.apps import REPANIER_SETTINGS_CONFIG
            config = REPANIER_SETTINGS_CONFIG
            if config.email_is_custom:
                reply_to_email = config.email_host_user
            else:
                staff_email = self.user.email
                if staff_email:
                    reply_to_email = staff_email
                else:
                    # No specific mail address for the staff member,
                    # use the customer responsible email
                    reply_to_email = self.customer_responsible.user.email
        return reply_to_email

    @cached_property
    def get_to_email(self):
        if self.user.email:
            return [self.user.email, self.customer_responsible.user.email]
        else:
            # No specific mail address for the staff member,
            # use only the customer responsible email
            return [self.customer_responsible.user.email]

    @property
    def title_for_admin(self):
        if self.customer_responsible is not None:
            tester = _(" who is also tester ") if self.is_tester else EMPTY_STRING
            return "{} : {}{} ({})".format(
                self.safe_translation_getter('long_name', any_language=True),
                self.customer_responsible.long_basket_name,
                tester,
                self.customer_responsible.phone1
            )
        else:
            return "{}".format(self.safe_translation_getter('long_name', any_language=True))

    objects = StaffManager()

    def anonymize(self):
        self.user.username = self.user.email = "{}-{}@repanier.be".format(_("STAFF"), self.id).lower()
        self.user.first_name = EMPTY_STRING
        self.user.last_name = self.safe_translation_getter('long_name', any_language=True)
        self.user.set_password(None)
        self.user.save()

    def __str__(self):
        return self.safe_translation_getter('long_name', any_language=True)

    class Meta:
        verbose_name = _("Staff member")
        verbose_name_plural = _("Staff members")


@receiver(pre_save, sender=Staff)
def staff_pre_save(sender, **kwargs):
    staff = kwargs["instance"]
    staff.login_attempt_counter = DECIMAL_ZERO


@receiver(post_save, sender=Staff)
def staff_post_save(sender, **kwargs):
    staff = kwargs["instance"]
    if staff.id is not None:
        user = staff.user
        user.groups.clear()
        if staff.is_webmaster:
            group_id = Group.objects.filter(name=WEBMASTER_GROUP).first()
            user.groups.add(group_id)


@receiver(post_delete, sender=Staff)
def staff_post_delete(sender, **kwargs):
    staff = kwargs["instance"]
    user = staff.user
    user.delete()
