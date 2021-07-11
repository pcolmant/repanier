import uuid
from collections import OrderedDict
from decimal import Decimal
from os import sep as os_sep

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import Textarea, EmailInput, TextInput
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX
from import_export.widgets import CharWidget, ForeignKeyWidget
from repanier.const import EMPTY_STRING, DECIMAL_ONE, TWO_DECIMALS
from repanier.models.customer import Customer
from repanier.models.lut import LUT_DeliveryPoint
from repanier.xlsx.widget import (
    IdWidget,
    OneToOneWidget,
    DecimalBooleanWidget,
    ZeroDecimalsWidget,
    TwoMoneysWidget,
    DateWidgetExcel,
)
from repanier.xlsx.xlsx_invoice import export_invoice

User = get_user_model()


class UserDataForm(forms.ModelForm):
    email = forms.EmailField(
        label=_("Email"),
        required=True,
        widget=forms.TextInput(
            attrs={"placeholder": _("Email"), "style": "width: 70%;"}
        ),
    )
    user = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        # cleaned_data = super().clean()
        short_basket_name_field = "short_basket_name"
        short_basket_name = self.cleaned_data.get(short_basket_name_field)
        if not short_basket_name:
            self.add_error(
                short_basket_name_field,
                _("The given short_basket_name must be set"),
            )
        # Check that the short_basket_name is set
        qs = Customer.objects.filter(short_basket_name=short_basket_name)
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            self.add_error(
                short_basket_name_field,
                _("The given short_basket_name is used by another user."),
            )
        # Check that the email is set
        email = self.cleaned_data["email"].lower()
        user_model = get_user_model()
        qs = user_model.objects.filter(Q(username=email) | Q(email=email))
        if self.instance.id is not None:
            qs = qs.exclude(id=self.instance.user_id)
        if qs.exists():
            self.add_error(
                "email",
                _("The email address {} is already used by another user.").format(
                    email
                ),
            )
        if self.instance.id is not None:
            if (
                self.instance.group is not None
                and self.cleaned_data.get("price_list_multiplier") != DECIMAL_ONE
            ):
                self.add_error(
                    "price_list_multiplier",
                    _(
                        "If the customer is member of a group, the customer.price_list_multiplier must be set to ONE."
                    ),
                )
        bank_account1 = self.cleaned_data.get("bank_account1", EMPTY_STRING)
        if bank_account1:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account1) | Q(bank_account2=bank_account1)
            )
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    "bank_account1",
                    _("This bank account already belongs to another customer."),
                )
        bank_account2 = self.cleaned_data.get("bank_account2", EMPTY_STRING)
        if bank_account2:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account2) | Q(bank_account2=bank_account2)
            )
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
        short_basket_name = self.data["short_basket_name"]
        email = self.data["email"].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.username = email
            user.email = email
            user.first_name = EMPTY_STRING
            user.last_name = short_basket_name
            user.save()
        else:
            user = user_model.objects.create_user(
                username=email,
                email=email,
                password=None,
                first_name=EMPTY_STRING,
                last_name=short_basket_name,
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
    balance = fields.Field(
        attribute="get_admin_balance", widget=TwoMoneysWidget(), readonly=True
    )
    may_order = fields.Field(
        attribute="may_order",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    membership_fee_valid_until = fields.Field(
        attribute="membership_fee_valid_until",
        default=timezone.now().date(),
        widget=DateWidgetExcel(),
        readonly=False,
    )
    purchase = fields.Field(
        attribute="get_purchase_counter", widget=ZeroDecimalsWidget(), readonly=True
    )
    participation = fields.Field(
        attribute="get_participation_counter",
        widget=ZeroDecimalsWidget(),
        readonly=True,
    )
    group = fields.Field(
        attribute="group",
        widget=ForeignKeyWidget(LUT_DeliveryPoint, field="short_basket_name"),
    )
    zero_waste = fields.Field(
        attribute="zero_waste", widget=DecimalBooleanWidget(), readonly=True
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        user_model = get_user_model()
        user_email_qs = user_model.objects.filter(
            email=instance.user.email, is_staff=False
        )
        user_username_qs = user_model.objects.filter(
            username=instance.short_basket_name
        )
        if instance.id is not None:
            customer = (
                Customer.objects.filter(id=instance.id).only("id", "user_id").first()
            )
            user_email_qs = user_email_qs.exclude(id=customer.user_id)
            user_username_qs = user_username_qs.exclude(id=customer.user_id)
        else:
            customer = None
        if user_email_qs.exists():
            raise ValueError(
                _("The email address {} is already used by another user.").format(
                    instance.user.email
                )
            )
        if user_username_qs.exists():
            raise ValueError(
                _("The short_basket_name {} is already used by another user.").format(
                    instance.short_basket_name
                )
            )
        if using_transactions or not dry_run:
            if instance.id is not None:
                email = instance.user.email
                instance.user = user_model.objects.get(id=customer.user_id)
                instance.user.username = instance.short_basket_name
                instance.user.first_name = EMPTY_STRING
                instance.user.last_name = instance.short_basket_name
                instance.user.email = email
                instance.user.save()
            else:
                instance.user = user_model.objects.create_user(
                    username=instance.short_basket_name,
                    email=instance.user.email,
                    password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING,
                    last_name=instance.short_basket_name,
                )
                instance.user_id = instance.user.id

    class Meta:
        model = Customer
        fields = (
            "id",
            "may_order",
            "short_basket_name",
            "long_basket_name",
            "email",
            "email2",
            "phone1",
            "phone2",
            "address",
            "city",
            "bank_account1",
            "bank_account2",
            "balance",
            "price_list_multiplier",
            "membership_fee_valid_until",
            "participation",
            "purchase",
            "group",
            "zero_waste",
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
    class Meta:
        widgets = {
            "long_basket_name": TextInput(attrs={"style": "width: 70%;"}),
            "email2": EmailInput(attrs={"style": "width: 70%;"}),
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 95%;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 95%;"}
            ),
        }
        model = Customer
        fields = "__all__"


class CustomerWithUserDataAdmin(ImportExportMixin, admin.ModelAdmin):
    form = CustomerWithUserDataForm
    resource_class = CustomerResource
    list_display = ("short_basket_name",)
    search_fields = (
        "short_basket_name",
        "long_basket_name",
        "user__email",
        "email2",
    )
    list_filter = (
        "may_order",
        "subscribe_to_email",
        "valid_email",
        "is_active",
    )
    list_per_page = 16
    list_max_show_all = 16
    autocomplete_fields = ["group"]

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

    get_last_login.short_description = _("Last sign in")
    get_last_login.admin_order_field = "user__last_login"

    def get_list_display(self, request):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return (
                "__str__",
                "get_balance",
                "may_order",
                "long_basket_name",
                "phone1",
                "get_email",
                "get_last_login",
                "valid_email",
            )
        else:
            return (
                "__str__",
                "may_order",
                "long_basket_name",
                "phone1",
                "get_email",
                "get_last_login",
                "valid_email",
            )

    def get_fieldsets(self, request, customer=None):
        fields_advanced = None
        if customer is not None and customer.represent_this_buyinggroup:
            fields_basic = [
                "short_basket_name",
                "long_basket_name",
                "represent_this_buyinggroup",
                "email",
                "email2",
                "phone1",
                "phone2",
                "get_admin_balance",
                "get_admin_date_balance",
            ]
        else:
            fields_basic = [
                "short_basket_name",
                "long_basket_name",
                "email",
                "email2",
                "subscribe_to_email",
                "may_order",
                "zero_waste",
                "phone1",
                "phone2",
                "membership_fee_valid_until",
                "price_list_multiplier",
            ]
            if settings.REPANIER_SETTINGS_DELIVERY_POINT:
                fields_basic += ["group"]
            if customer is not None:
                fields_basic += [
                    "get_admin_balance",
                    "get_admin_date_balance",
                ]
            fields_basic += [
                "address",
                "city",
                "picture",
                "memo",
                "bank_account1",
                "bank_account2",
            ]
            if customer is not None:
                fields_advanced = [
                    "get_last_login",
                    "get_admin_date_joined",
                    "get_last_membership_fee",
                    "get_last_membership_fee_date",
                    "get_participation_counter",
                    "get_purchase_counter",
                ]

        if fields_advanced is None:
            fieldsets = ((None, {"fields": fields_basic}),)
        else:
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
            if customer.represent_this_buyinggroup:
                readonly_fields += ["represent_this_buyinggroup"]
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
            picture_field = form.base_fields.get("picture", None)
            if picture_field is not None and hasattr(picture_field.widget, "upload_to"):
                picture_field.widget.upload_to = "{}{}{}".format(
                    "customer", os_sep, customer.id
                )
        else:
            # Clean data displayed
            email_field.initial = EMPTY_STRING
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_group=False, is_active=True)
        return qs

    def get_actions(self, request):
        actions = super().get_actions(request)
        this_year = timezone.now().year
        actions.update(
            OrderedDict(
                create__customer_action(y)
                for y in [this_year, this_year - 1, this_year - 2]
            )
        )
        if "delete_selected" in actions:
            del actions["delete_selected"]
        if not actions:
            try:
                self.list_display.remove("action_checkbox")
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def save_model(self, request, customer, form, change):
        customer.user = form.user
        form.user.is_staff = False
        form.user.is_active = True
        form.user.save()
        super().save_model(request, customer, form, change)
        if customer.group is not None:
            customer_price = EMPTY_STRING
            if settings.REPANIER_SETTINGS_CUSTOM_CUSTOMER_PRICE:
                if customer.price_list_multiplier < DECIMAL_ONE:
                    customer_price = _(
                        " in addition to the %(discount)s%% personal discount rate on to the pricelist"
                    ) % {
                        "discount": Decimal(
                            (DECIMAL_ONE - customer.price_list_multiplier) * 100
                        ).quantize(TWO_DECIMALS)
                    }
                elif customer.price_list_multiplier > DECIMAL_ONE:
                    customer_price = _(
                        " in addition to the %(surcharge)s%% personal surcharge on to the pricelist"
                    ) % {
                        "surcharge": Decimal(
                            (customer.price_list_multiplier - DECIMAL_ONE) * 100
                        ).quantize(TWO_DECIMALS)
                    }
            if customer.group.price_list_multiplier < DECIMAL_ONE:
                messages.add_message(
                    request,
                    messages.WARNING,
                    _(
                        "%(discount)s%% discount is granted to customer invoices when delivered to %(group)s%(customer_price)s."
                    )
                    % {
                        "discount": Decimal(
                            (DECIMAL_ONE - customer.group.price_list_multiplier) * 100
                        ).quantize(TWO_DECIMALS),
                        "group": customer.group,
                        "customer_price": customer_price,
                    },
                )
            elif customer.group.price_list_multiplier > DECIMAL_ONE:
                messages.add_message(
                    request,
                    messages.WARNING,
                    _(
                        "%(surcharge)s%% surcharge is applied to customer invoices when delivered to %(group)s%(customer_price)s."
                    )
                    % {
                        "surcharge": Decimal(
                            (customer.group.price_list_multiplier - DECIMAL_ONE) * 100
                        ).quantize(TWO_DECIMALS),
                        "group": customer.group,
                        "customer_price": customer_price,
                    },
                )

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, CSV) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, CSV) if f().can_export()]
