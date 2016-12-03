# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *


@python_2_unicode_compatible
class Staff(TranslatableModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("login"))
    customer_responsible = models.ForeignKey(
        'Customer', verbose_name=_("customer_responsible"),
        on_delete=models.PROTECT, blank=True, null=True, default=None)
    login_attempt_counter = models.DecimalField(
        _("login attempt counter"),
        default=DECIMAL_ZERO, max_digits=2, decimal_places=0)
    translations = TranslatedFields(
        long_name=models.CharField(_("long_name"), max_length=100, db_index=True, null=True, default=EMPTY_STRING),
        function_description=HTMLField(_("function_description"), blank=True, default=EMPTY_STRING),
    )
    is_reply_to_order_email = models.BooleanField(_("is_reply_to_order_email"),
                                                  default=False)
    is_reply_to_invoice_email = models.BooleanField(_("is_reply_to_invoice_email"),
                                                    default=False)
    is_contributor = models.BooleanField(_("is_contributor"),
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
        # ordering = ("long_name",)


@receiver(pre_save, sender=Staff)
def staff_pre_save(sender, **kwargs):
    staff = kwargs["instance"]
    staff.login_attempt_counter = DECIMAL_ZERO
    # if staff.is_contributor:
    #     staff.is_reply_to_order_email = False
    #     staff.is_reply_to_invoice_email = False
    #     staff.is_webmaster = False
    #     # Do not kill yourself
    #     if not staff.user.groups.filter(name=COORDINATION_GROUP).exists():
    #         staff.is_coordinator = False
    # if staff.is_webmaster:
    #     staff.is_reply_to_order_email = False
    #     staff.is_reply_to_invoice_email = False
    #     staff.is_contributor = False
    #     # Do not kill yourself
    #     if not staff.user.groups.filter(name=COORDINATION_GROUP).exists():
    #         staff.is_coordinator = False


@receiver(post_save, sender=Staff)
def staff_post_save(sender, **kwargs):
    staff = kwargs["instance"]
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
        if staff.is_contributor:
            group_id = Group.objects.filter(name=CONTRIBUTOR_GROUP).first()
            user.groups.add(group_id)
        if staff.is_coordinator:
            group_id = Group.objects.filter(name=COORDINATION_GROUP).first()
            user.groups.add(group_id)


@receiver(post_delete, sender=Staff)
def staff_post_delete(sender, **kwargs):
    staff = kwargs["instance"]
    user = staff.user
    user.delete()
