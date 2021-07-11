from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from mptt.managers import TreeManager
from mptt.models import MPTTModel, TreeForeignKey
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelRepanierMoneyField
from repanier.picture.const import SIZE_XS
from repanier.picture.fields import RepanierPictureField


class LUT_ProductionModeQuerySet(QuerySet):
    pass


class LUT_ProductionModeManager(TreeManager):
    queryset_class = LUT_ProductionModeQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class LUT_ProductionMode(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name_v2 = models.CharField(
        _("Short name"), max_length=50, default=EMPTY_STRING
    )
    description_v2 = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )
    picture2 = RepanierPictureField(
        verbose_name=_("Picture"),
        null=True,
        blank=True,
        upload_to="label",
        size=SIZE_XS,
    )

    is_active = models.BooleanField(_("Active"), default=True)
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name_v2

    class Meta:
        verbose_name = _("Production mode")
        verbose_name_plural = _("Production modes")


class LUT_DeliveryPointQuerySet(QuerySet):
    pass


class LUT_DeliveryPointManager(TreeManager):
    queryset_class = LUT_DeliveryPointQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class LUT_DeliveryPoint(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name_v2 = models.CharField(
        _("Short name"), max_length=50, default=EMPTY_STRING
    )
    description_v2 = HTMLField(
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
        "Customer",
        related_name="+",
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
    inform_customer_responsible = models.BooleanField(
        _("Inform the group of orders placed by its members"), default=False
    )
    transport = ModelRepanierMoneyField(
        _("Delivery point shipping cost"),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    min_transport = ModelRepanierMoneyField(
        _("Minimum order amount for free shipping cost"),
        default=DECIMAL_ZERO,
        blank=True,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    objects = LUT_DeliveryPointManager()

    def __str__(self):
        if self.group is not None:
            return "[{}]".format(self.group.short_basket_name)
        else:
            return self.short_name_v2

    class Meta:
        verbose_name = _("Delivery point")
        verbose_name_plural = _("Deliveries points")


class LUT_DepartmentForCustomerQuerySet(QuerySet):
    pass


class LUT_DepartmentForCustomerManager(TreeManager):
    queryset_class = LUT_DepartmentForCustomerQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class LUT_DepartmentForCustomer(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    is_active = models.BooleanField(_("Active"), default=True)
    short_name_v2 = models.CharField(
        _("Short name"), max_length=50, default=EMPTY_STRING
    )
    description_v2 = HTMLField(
        _("Description"),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        blank=True,
        default=EMPTY_STRING,
    )
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name_v2

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")


class LUT_PermanenceRoleQuerySet(QuerySet):
    pass


class LUT_PermanenceRoleManager(TreeManager):
    queryset_class = LUT_PermanenceRoleQuerySet

    def get_queryset(self):
        # This is the safest way to combine both get_queryset() calls
        # supporting all Django versions and MPTT 0.7.x versions
        return self.queryset_class(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class LUT_PermanenceRole(MPTTModel):
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    short_name_v2 = models.CharField(
        _("Short name"), max_length=50, default=EMPTY_STRING
    )
    description_v2 = HTMLField(
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
    objects = LUT_ProductionModeManager()

    def __str__(self):
        return self.short_name_v2

    class Meta:
        verbose_name = _("Permanence role")
        verbose_name_plural = _("Permanences roles")
