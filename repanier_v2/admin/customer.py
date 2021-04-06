import uuid
from collections import OrderedDict
from decimal import Decimal
from os import sep as os_sep

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from easy_select2 import apply_select2
from import_export import resources, fields
from import_export.widgets import CharWidget

from repanier_v2.admin.admin_filter import CustomerFilterByGroup
from repanier_v2.admin.admin_model import RepanierAdminImportExport
from repanier_v2.const import EMPTY_STRING, DECIMAL_ONE, TWO_DECIMALS
from repanier_v2.models.customer import Customer
from repanier_v2.models.lut import LUT_DeliveryPoint
from repanier_v2.xlsx.widget import (
    IdWidget,
    OneToOneWidget,
    DecimalBooleanWidget,
    ZeroDecimalsWidget,
    TwoMoneysWidget,
    TranslatedForeignKeyWidget,
    DateWidgetExcel,
)
from repanier_v2.xlsx.xlsx_invoice import export_invoice

User = get_user_model()


class UserDataForm(forms.ModelForm):
    email = forms.EmailField(label=_("Email"), required=True)
    user = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        username_field_name = "short_name"
        username = self.cleaned_data.get(username_field_name)
        user_error1 = _("The given short_name must be set")
        user_error2 = _("The given short_name is used by another user.")
        if not username:
            self.add_error(username_field_name, user_error1)
        # Check that the email is set
        email = self.cleaned_data["email"].lower()
        user_model = get_user_model()
        qs = user_model.objects.filter(email=email).order_by("?")
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.user_id)
        if qs.exists():
            self.add_error(
                "email",
                _("The email {} is already used by another user.").format(email),
            )
        qs = user_model.objects.filter(username=username).order_by("?")
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.user_id)
        if qs.exists():
            self.add_error(username_field_name, user_error2)
        if self.instance.id is not None:
            if (
                self.instance.delivery_point is not None
                and self.instance.delivery_point.customer_responsible is not None
                and self.cleaned_data.get("custom_tariff_margin") != DECIMAL_ONE
            ):
                self.add_error(
                    "custom_tariff_margin",
                    _(
                        "If the customer is member of a group, the customer.custom_tariff_margin must be set to ONE."
                    ),
                )
            is_active = self.cleaned_data.get("is_active")
            if is_active is not None and not is_active:
                delivery_point = (
                    LUT_DeliveryPoint.objects.filter(
                        customer_responsible_id=self.instance.id
                    )
                    .order_by("?")
                    .first()
                )
                if delivery_point is not None:
                    self.add_error(
                        "is_active",
                        _(
                            "This customer is responsible of the delivery point (%(delivery_point)s). A customer responsible of a delivery point must be active."
                        )
                        % {"delivery_point": delivery_point},
                    )
        bank_account1 = self.cleaned_data["bank_account1"]
        if bank_account1:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account1) | Q(bank_account2=bank_account1)
            ).order_by("?")
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    "bank_account1",
                    _("This bank account already belongs to another customer."),
                )
        bank_account2 = self.cleaned_data["bank_account2"]
        if bank_account2:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account2) | Q(bank_account2=bank_account2)
            ).order_by("?")
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    "bank_account2",
                    _("This bank account already belongs to another customer."),
                )
                # return cleaned_data

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        change = self.instance.id is not None
        short_name = self.data["short_name"]
        email = self.data["email"].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.username = email
            user.email = email
            user.first_name = EMPTY_STRING
            user.last_name = short_name
            user.save()
        else:
            user = user_model.objects.create_user(
                username=email,
                email=email,
                password=None,
                first_name=EMPTY_STRING,
                last_name=short_name,
            )
        self.user = user
        return self.instance


# Customer
class CustomerResource(resources.ModelResource):
    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    email = fields.Field(
        attribute="user",
        default="ask.it@to.me",
        widget=OneToOneWidget(User, "email"),
        readonly=False,
    )
    phone1 = fields.Field(
        attribute="phone1", default="1234", widget=CharWidget(), readonly=False
    )
    phone2 = fields.Field(attribute="phone2", widget=CharWidget(), readonly=False)
    date_balance = fields.Field(
        attribute="get_admin_date_balance", widget=CharWidget(), readonly=True
    )
    balance = fields.Field(
        attribute="get_admin_balance", widget=TwoMoneysWidget(), readonly=True
    )
    may_order = fields.Field(
        attribute="may_order",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    is_group = fields.Field(
        attribute="is_group",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    is_default = fields.Field(
        attribute="is_default",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=True,
    )
    is_active = fields.Field(
        attribute="is_active", widget=DecimalBooleanWidget(), readonly=True
    )
    membership_fee_valid_until = fields.Field(
        attribute="membership_fee_valid_until",
        default=timezone.now().date(),
        widget=DateWidgetExcel(),
        readonly=False,
    )
    last_membership_fee = fields.Field(
        attribute="get_last_membership_fee", widget=TwoMoneysWidget(), readonly=True
    )
    last_membership_fee_date = fields.Field(
        attribute="last_membership_fee_date", widget=DateWidgetExcel(), readonly=True
    )
    purchase = fields.Field(
        attribute="get_purchase_counter", widget=ZeroDecimalsWidget(), readonly=True
    )
    participation = fields.Field(
        attribute="get_participation_counter",
        widget=ZeroDecimalsWidget(),
        readonly=True,
    )
    delivery_point = fields.Field(
        attribute="delivery_point",
        widget=TranslatedForeignKeyWidget(LUT_DeliveryPoint, field="short_name"),
    )
    valid_email = fields.Field(
        attribute="valid_email", widget=DecimalBooleanWidget(), readonly=True
    )
    zero_waste = fields.Field(
        attribute="zero_waste", widget=DecimalBooleanWidget(), readonly=True
    )
    date_joined = fields.Field(
        attribute="get_admin_date_joined", widget=CharWidget(), readonly=True
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        user_model = get_user_model()
        user_email_qs = user_model.objects.filter(
            email=instance.user.email, is_staff=False
        ).order_by("?")
        user_username_qs = user_model.objects.filter(
            username=instance.short_name
        ).order_by("?")
        if instance.id is not None:
            customer = (
                Customer.objects.filter(id=instance.id)
                .order_by("?")
                .only("id", "user_id")
                .first()
            )
            user_email_qs = user_email_qs.exclude(id=customer.user_id)
            user_username_qs = user_username_qs.exclude(id=customer.user_id)
        else:
            customer = None
        if user_email_qs.exists():
            raise ValueError(
                _("The email {} is already used by another user.").format(
                    instance.user.email
                )
            )
        if user_username_qs.exists():
            raise ValueError(
                _("The short_name {} is already used by another user.").format(
                    instance.short_name
                )
            )
        if using_transactions or not dry_run:
            if instance.id is not None:
                email = instance.user.email
                instance.user = user_model.objects.get(id=customer.user_id)
                instance.user.username = instance.short_name
                instance.user.first_name = EMPTY_STRING
                instance.user.last_name = instance.short_name
                instance.user.email = email
                instance.user.save()
            else:
                instance.user = user_model.objects.create_user(
                    username=instance.short_name,
                    email=instance.user.email,
                    password=uuid.uuid4().hex,
                    first_name=EMPTY_STRING,
                    last_name=instance.short_name,
                )
                instance.user_id = instance.user.id

    class Meta:
        model = Customer
        fields = (
            "id",
            "may_order",
            "short_name",
            "long_name",
            "email",
            "email2",
            "language",
            "phone1",
            "phone2",
            "address",
            "city",
            "bank_account1",
            "bank_account2",
            "date_balance",
            "balance",
            "custom_tariff_margin",
            "membership_fee_valid_until",
            "last_membership_fee",
            "last_membership_fee_date",
            "participation",
            "purchase",
            "is_default",
            "is_group",
            "is_active",
            "delivery_point",
            "zero_waste",
            "valid_email",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


def create__customer_action(year):
    def action(modeladmin, request, customer_qs):
        # To the customer we speak of "invoice".
        # This is the detail of the invoice, i.e. sold products
        wb = None
        for customer in customer_qs:
            wb = export_invoice(
                year=year, customer=customer, wb=wb, sheet_name=customer
            )
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(
                "{} {}".format(_("Invoice"), year),
                settings.REPANIER_SETTINGS_GROUP_NAME,
            )
            wb.save(response)
            return response
        return

    name = "export_producer_{}".format(year)
    return (
        name,
        (action, name, _("Export the list of products purchased in {}").format(year)),
    )


class CustomerWithUserDataForm(UserDataForm):
    delivery_point = forms.ModelChoiceField(
        LUT_DeliveryPoint.objects.filter(customer_responsible__isnull=False),
        label=_("Group"),
        widget=apply_select2(forms.Select),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_point"].widget.can_add_related = False
        self.fields["delivery_point"].widget.can_delete_related = False

    class Meta:
        widgets = {
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 30em;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 60em;"}
            ),
        }
        model = Customer
        fields = "__all__"


class CustomerWithUserDataAdmin(RepanierAdminImportExport):
    form = CustomerWithUserDataForm
    resource_class = CustomerResource
    list_display = (
        "__str__",
        "delivery_point",
        "get_balance",
        "may_order",
        "long_name",
        "phone1",
        "get_email",
        "get_last_login",
        "valid_email",
    )
    search_fields = ("short_name", "long_name", "user__email", "email2")
    list_filter = ("may_order", CustomerFilterByGroup, "is_active", "valid_email")
    ordering = ["-is_default", "short_name"]
    list_per_page = 16
    list_max_show_all = 16

    def has_delete_permission(self, request, customer=None):
        user = request.user
        if user.is_order_manager or user.is_invoice_manager:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def get_email(self, customer):
        if customer.user is not None:
            return customer.user.email
        else:
            return EMPTY_STRING

    get_email.short_description = _("Email")
    get_email.admin_order_field = "user__email"

    def get_last_login(self, customer):
        if customer.user is not None and customer.user.last_login is not None:
            return customer.user.last_login.strftime(settings.DJANGO_SETTINGS_DATE)
        else:
            return EMPTY_STRING

    get_last_login.short_description = _("Last login")
    get_last_login.admin_order_field = "user__last_login"

    def get_actions(self, request):
        actions = super().get_actions(request)
        this_year = timezone.now().year
        actions.update(
            OrderedDict(
                create__customer_action(y)
                for y in [this_year, this_year - 1, this_year - 2]
            )
        )
        return actions

    def get_fieldsets(self, request, customer=None):
        fields_basic = [
            ("short_name", "long_name", "language"),
            ("email", "email2"),
            ("phone1", "phone2"),
            "membership_fee_valid_until",
        ]
        if customer is not None:
            if customer.is_default:
                fields_basic += [
                    "get_admin_balance",
                    "get_admin_date_balance",
                    "may_order",
                ]
            else:
                fields_basic += ["subscribe_to_email"]
                fields_basic += ["custom_tariff_margin"]
                if settings.REPANIER_SETTINGS_GROUP:
                    fields_basic += ["delivery_point"]
                fields_basic += [
                    "get_admin_balance",
                    "get_admin_date_balance",
                    ("may_order", "is_active", "zero_waste"),
                ]
            fields_basic += [("address", "city", "picture"), "memo"]
            fields_advanced = [
                "bank_account1",
                "bank_account2",
                "get_last_login",
                "get_admin_date_joined",
                "get_last_membership_fee",
                "get_last_membership_fee_date",
                "get_participation_counter",
                "get_purchase_counter",
            ]
        else:
            fields_basic += [("may_order", "is_active", "zero_waste")]
            fields_basic += ["custom_tariff_margin"]
            # Do not accept the picture because there is no customer.id for the "upload_to"
            fields_basic += [("address", "city"), "memo"]
            fields_advanced = ["bank_account1", "bank_account2", "zero_waste"]

        fieldsets = (
            (None, {"fields": fields_basic}),
            (
                _("Advanced options"),
                {"classes": ("collapse",), "fields": fields_advanced},
            ),
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        if customer is not None:
            readonly_fields = [
                "get_admin_date_balance",
                "get_admin_balance",
                "get_last_login",
                "get_admin_date_joined",
                "get_purchase_counter",
                "get_participation_counter",
                "get_last_membership_fee",
                "get_last_membership_fee_date",
            ]
            if customer.is_default:
                readonly_fields += ["is_default"]
            return readonly_fields
        return []

    def get_form(self, request, customer=None, **kwargs):
        form = super().get_form(request, customer, **kwargs)
        email_field = form.base_fields["email"]

        if customer is not None:
            user_model = get_user_model()
            user = user_model.objects.get(id=customer.user_id)
            # username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            email_field.initial = user.email
            # One folder by customer to avoid picture names conflicts
            picture_field = form.base_fields["picture"]
            if hasattr(picture_field.widget, "upload_to"):
                picture_field.widget.upload_to = "{}{}{}".format(
                    "customer", os_sep, customer.id
                )
        else:
            # Clean data displayed
            email_field.initial = EMPTY_STRING
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_group=False)
        return qs

    def save_model(self, request, customer, form, change):
        customer.user = form.user
        form.user.is_staff = False
        form.user.is_active = customer.is_active
        form.user.save()
        super().save_model(request, customer, form, change)
        if customer.delivery_point is not None:
            customer_price = EMPTY_STRING
            if customer.custom_tariff_margin < DECIMAL_ONE:
                customer_price = _(
                    " in addition to the %(discount)s%% personal discount rate on to the pricelist"
                ) % {
                    "discount": Decimal(
                        (DECIMAL_ONE - customer.custom_tariff_margin) * 100
                    ).quantize(TWO_DECIMALS)
                }
            elif customer.custom_tariff_margin > DECIMAL_ONE:
                customer_price = _(
                    " in addition to the %(surcharge)s%% personal surcharge on to the pricelist"
                ) % {
                    "surcharge": Decimal(
                        (customer.custom_tariff_margin - DECIMAL_ONE) * 100
                    ).quantize(TWO_DECIMALS)
                }
            if (
                customer.delivery_point.customer_responsible.custom_tariff_margin
                < DECIMAL_ONE
            ):
                messages.add_message(
                    request,
                    messages.WARNING,
                    _(
                        "%(discount)s%% discount is granted to customer invoices when delivered to %(delivery_point)s%(customer_price)s."
                    )
                    % {
                        "discount": Decimal(
                            (
                                DECIMAL_ONE
                                - customer.delivery_point.customer_responsible.custom_tariff_margin
                            )
                            * 100
                        ).quantize(TWO_DECIMALS),
                        "delivery_point": customer.delivery_point,
                        "customer_price": customer_price,
                    },
                )
            elif (
                customer.delivery_point.customer_responsible.custom_tariff_margin
                > DECIMAL_ONE
            ):
                messages.add_message(
                    request,
                    messages.WARNING,
                    _(
                        "%(surcharge)s%% surcharge is applied to customer invoices when delivered to %(delivery_point)s%(customer_price)s."
                    )
                    % {
                        "surcharge": Decimal(
                            (
                                customer.delivery_point.customer_responsible.custom_tariff_margin
                                - DECIMAL_ONE
                            )
                            * 100
                        ).quantize(TWO_DECIMALS),
                        "delivery_point": customer.delivery_point,
                        "customer_price": customer_price,
                    },
                )
