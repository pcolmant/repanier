# -*- coding: utf-8

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.managers import TreeManager
from mptt.models import MPTTModel, TreeForeignKey
from parler.managers import TranslatableManager, TranslatableQuerySet
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.picture.const import SIZE_XS
from repanier.picture.fields import RepanierPictureField


class LUT_ProductionModeQuerySet(TranslatableQuerySet):
    pass


class LUT_ProductionModeManager(TreeManager, TranslatableManager):
    queryset_class = LUT_ProductionModeQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


class LUT_ProductionMode(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        'self', null=True, blank=True, related_name='children',
        on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"),
            max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration='CKEDITOR_SETTINGS_MODEL2', blank=True, default=EMPTY_STRING
        ),
    )
    picture2 = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="label", size=SIZE_XS)

    is_active = models.BooleanField(_("Active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        # return self.short_name
        return self.safe_translation_getter('short_name', any_language=True, default=EMPTY_STRING)

    class Meta:
        verbose_name = _("Production mode")
        verbose_name_plural = _("Production modes")


class LUT_DeliveryPointQuerySet(TranslatableQuerySet):
    pass


class LUT_DeliveryPointManager(TreeManager, TranslatableManager):
    queryset_class = LUT_DeliveryPointQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


class LUT_DeliveryPoint(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        'self', null=True, blank=True, related_name='children',
        on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"),
            max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration='CKEDITOR_SETTINGS_MODEL2', blank=True, default=EMPTY_STRING
        ),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    customer_responsible = models.ForeignKey(
        'Customer', verbose_name=_("Customer responsible"),
        help_text=_("Invoices are sent to this customer who is responsible for collecting the payments."),
        blank=True, null=True, default=None,
        on_delete=models.CASCADE
    )
    inform_customer_responsible = models.BooleanField(_("Inform the group of orders placed by its members"),
                                                      default=False)
    transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        # help_text=_("This amount is added once for groups with entitled customer or at each customer for open groups."),
        default=DECIMAL_ZERO, blank=True, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])
    min_transport = ModelMoneyField(
        _("Minium order amount for free shipping cost"),
        # help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO, blank=True, max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)])

    objects = LUT_DeliveryPointManager()

    def __str__(self):
        if self.customer_responsible is not None:
            return "[{}]".format(self.customer_responsible.short_basket_name)
        else:
            return self.safe_translation_getter('short_name', any_language=True, default=EMPTY_STRING)

    class Meta:
        verbose_name = _("Delivery point")
        verbose_name_plural = _("Deliveries points")


class LUT_DepartmentForCustomerQuerySet(TranslatableQuerySet):
    pass


class LUT_DepartmentForCustomerManager(TreeManager, TranslatableManager):
    queryset_class = LUT_DepartmentForCustomerQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


class LUT_DepartmentForCustomer(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        'self', null=True, blank=True, related_name='children',
        on_delete=models.CASCADE
    )
    is_active = models.BooleanField(_("Active"), default=True)
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"),
            max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration='CKEDITOR_SETTINGS_MODEL2', blank=True, default=EMPTY_STRING
        ),
    )
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.safe_translation_getter('short_name', any_language=True, default=EMPTY_STRING)

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")


class LUT_PermanenceRoleQuerySet(TranslatableQuerySet):
    pass


class LUT_PermanenceRoleManager(TreeManager, TranslatableManager):
    queryset_class = LUT_PermanenceRoleQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(self.tree_id_attr, self.left_attr)


class LUT_PermanenceRole(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        'self', null=True, blank=True, related_name='children',
        on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"),
            max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration='CKEDITOR_SETTINGS_MODEL2', blank=True, default=EMPTY_STRING
        ),
    )

    is_counted_as_participation = models.BooleanField(
        _("This task constitutes a participation in the activities of the group"), default=True)
    customers_may_register = models.BooleanField(_("Customers can register for this task"), default=True)
    is_active = models.BooleanField(_("Active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.safe_translation_getter('short_name', any_language=True, default=EMPTY_STRING)

    class Meta:
        verbose_name = _("Permanence role")
        verbose_name_plural = _("Permanences roles")


@receiver(pre_save, sender=LUT_PermanenceRole)
def lut_permanence_role_pre_save(sender, **kwargs):
    permanence_role = kwargs["instance"]
    if not permanence_role.is_active:
        permanence_role.automatically_added = False
