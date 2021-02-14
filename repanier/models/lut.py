from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.managers import TreeManager
from mptt.models import MPTTModel, TreeForeignKey
from parler.models import TranslatableModel, TranslatedFields

from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.picture.const import SIZE_XS
from repanier.picture.fields import RepanierPictureField


class LUT_ProductionMode(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"), max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            blank=True,
            default=EMPTY_STRING,
        ),
    )
    picture2 = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="label",
        size=SIZE_XS,
    )

    is_active = models.BooleanField(_("Active"), default=True)

    def __str__(self):
        # return self.short_name
        return self.safe_translation_getter(
            "short_name", any_language=True, default=EMPTY_STRING
        )

    class Meta:
        verbose_name = _("Production mode")
        verbose_name_plural = _("Production modes")


class LUT_DeliveryPoint(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"), max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            blank=True,
            default=EMPTY_STRING,
        ),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    # A delivery point may have a customer who is responsible to pay
    # for all the customers who have selected this delivery point
    # Such delivery point represent a closed group of customers.
    customer_responsible = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer responsible"),
        help_text=_(
            "Invoices are sent to this customer who is responsible for collecting the payments."
        ),
        blank=True,
        null=True,
        default=None,
        on_delete=models.CASCADE,
    )
    # Does the customer responsible of this delivery point be informed of
    # each individual order for this delivery point ?
    inform_customer_responsible = models.BooleanField(
        _("Inform the group of orders placed by its members"), default=False
    )
    transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    min_transport = ModelMoneyField(
        _("Minimum order amount for free shipping cost"),
        # help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        # IMPORTANT : if self.customer_responsible is not None:
        #     self.customer_responsible.short_name == self.short_name
        return self.safe_translation_getter(
            "short_name", any_language=True, default=EMPTY_STRING
        )

    class Meta:
        verbose_name = _("Delivery point")
        verbose_name_plural = _("Deliveries points")


class LUT_DepartmentForCustomer(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    is_active = models.BooleanField(_("Active"), default=True)
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"), max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            blank=True,
            default=EMPTY_STRING,
        ),
    )

    def __str__(self):
        return self.safe_translation_getter(
            "short_name", any_language=True, default=EMPTY_STRING
        )

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")


class LUT_PermanenceRole(MPTTModel, TranslatableModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Short name"), max_length=50, default=EMPTY_STRING
        ),
        description=HTMLField(
            _("Description"),
            configuration="CKEDITOR_SETTINGS_MODEL2",
            blank=True,
            default=EMPTY_STRING,
        ),
    )

    is_counted_as_participation = models.BooleanField(
        _("This task constitutes a participation in the activities of the group"),
        default=True,
    )
    customers_may_register = models.BooleanField(
        _("Customers can register for this task"), default=True
    )
    is_active = models.BooleanField(_("Active"), default=True)

    def __str__(self):
        return self.safe_translation_getter(
            "short_name", any_language=True, default=EMPTY_STRING
        )

    class Meta:
        verbose_name = _("Permanence role")
        verbose_name_plural = _("Permanences roles")


# xxxxxxxxxxxxxxxxxxxxx


class Label(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name = models.CharField(_("Short name"), max_length=50, default=EMPTY_STRING)
    description = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )
    picture = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="label",
        size=SIZE_XS,
    )

    is_active = models.BooleanField(_("Active"), default=True)

    def __str__(self):
        # return self.short_name
        return self.short_name

    class Meta:
        verbose_name = _("Label")
        verbose_name_plural = _("Labels")


class DeliveryPoint(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name = models.CharField(_("Short name"), max_length=50, default=EMPTY_STRING)
    description = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )
    is_active = models.BooleanField(_("Active"), default=True)
    # A delivery point may have a customer who is responsible to pay
    # for all the customers who have selected this delivery point
    # Such delivery point represent a closed group of customers.
    group = models.ForeignKey(
        "Group",
        verbose_name=_("Group"),
        help_text=_(
            "Invoices are sent to this group who is responsible for collecting the payments."
        ),
        blank=True,
        null=True,
        default=None,
        on_delete=models.CASCADE,
    )
    # Does the customer responsible of this delivery point be informed of
    # each individual order for this delivery point ?
    inform_group = models.BooleanField(
        _("Inform the group of orders placed by its members"), default=False
    )
    transport = ModelMoneyField(
        _("Delivery point shipping cost"),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    min_transport = ModelMoneyField(
        _("Minimum order amount for free shipping cost"),
        # help_text=_("This is the minimum order amount to avoid shipping cost."),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        # IMPORTANT : if self.customer_responsible is not None:
        #     self.customer_responsible.short_name == self.short_name
        return self.short_name

    class Meta:
        verbose_name = _("Delivery point")
        verbose_name_plural = _("Deliveries points")


class DepartmentQuerySet(QuerySet):
    pass


class DepartmentManager(TreeManager):
    queryset_class = DepartmentQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class Department(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    is_active = models.BooleanField(_("Active"), default=True)
    short_name = models.CharField(_("Short name"), max_length=50, default=EMPTY_STRING)
    description = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )
    objects = DepartmentManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")


class ActivityQuerySet(QuerySet):
    pass


class ActivityManager(TreeManager):
    queryset_class = ActivityQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class Activity(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name = models.CharField(_("Short name"), max_length=50, default=EMPTY_STRING)
    description = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )

    is_counted_as_participation = models.BooleanField(
        _("This task constitutes a participation in the activities of the group"),
        default=True,
    )
    customers_may_register = models.BooleanField(
        _("Customers can register for this task"), default=True
    )
    is_active = models.BooleanField(_("Active"), default=True)
    objects = ActivityManager()

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")
