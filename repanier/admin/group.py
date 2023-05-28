from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.forms import Textarea, TextInput
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from repanier.const import EMPTY_STRING, DECIMAL_ONE
from repanier.const import REPANIER_MONEY_ZERO
from repanier.fields.RepanierMoneyField import FormRepanierMoneyField
from repanier.models import Customer
from repanier.models import LUT_DeliveryPoint
from repanier.models.group import Group
from repanier.xlsx.xlsx_invoice import export_invoice


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
                short_basket_name_field, _("The given short_basket_name must be set")
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
        bank_account1 = self.cleaned_data["bank_account1"]
        if bank_account1:
            qs = Group.objects.filter(
                Q(bank_account1=bank_account1) | Q(bank_account2=bank_account1)
            )
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    "bank_account1",
                    _("This bank account already belongs to another customer."),
                )
        bank_account2 = self.cleaned_data["bank_account2"]
        if bank_account2:
            qs = Group.objects.filter(
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


def create__group_action(year):
    def action(modeladmin, request, group_qs):
        # To the customer we speak of "invoice".
        # This is the detail of the invoice, i.e. sold products
        wb = None
        for group in group_qs:
            wb = export_invoice(year=year, customer=group, wb=wb, sheet_name=str(group))
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


class GroupWithUserDataForm(UserDataForm):
    customers = forms.ModelMultipleChoiceField(
        Customer.objects.filter(
            may_order=True,
            group__isnull=True,
            represent_this_buyinggroup=False,
        ),
        label=_("Members"),
        widget=FilteredSelectMultiple(_("Members"), False),
        required=False,
    )
    inform_customer_responsible = forms.BooleanField(
        label=_("Inform the group of orders placed by its members"), required=False
    )
    transport = FormRepanierMoneyField(
        label=_("Shipping cost"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        initial=REPANIER_MONEY_ZERO,
        required=False,
    )
    min_transport = FormRepanierMoneyField(
        label=_("Minimum order amount for free shipping cost"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        initial=REPANIER_MONEY_ZERO,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            delivery_point = LUT_DeliveryPoint.objects.filter(
                group_id=self.instance.id
            ).first()
            if delivery_point is not None:
                self.fields["customers"].initial = Customer.objects.filter(
                    group_id=delivery_point.group_id
                )
                self.fields["customers"].queryset = Customer.objects.filter(
                    Q(may_order=True, group__isnull=True)
                    | Q(group_id=delivery_point.group_id)
                ).distinct()
                self.fields[
                    "inform_customer_responsible"
                ].initial = delivery_point.inform_customer_responsible
                self.fields["transport"].initial = delivery_point.transport
                self.fields["min_transport"].initial = delivery_point.min_transport
            else:
                self.fields["customers"].initial = Customer.objects.none()
                self.fields["customers"].queryset = Customer.objects.filter(
                    Q(may_order=True, group_id__isnull=True)
                )

    class Meta:
        widgets = {
            "long_basket_name": TextInput(attrs={"style": "width: 70%;"}),
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 95%;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 95%;"}
            ),
        }
        model = Group
        fields = "__all__"


class GroupWithUserDataAdmin(admin.ModelAdmin):
    form = GroupWithUserDataForm
    list_display = (
        "__str__",
        "get_balance",
        "long_basket_name",
        "phone1",
        "get_email",
        "is_active",
    )
    search_fields = (
        "short_basket_name",
        "long_basket_name",
        "user__email",
    )
    list_filter = ("is_active",)
    list_per_page = 16
    list_max_show_all = 16

    def has_delete_permission(self, request, customer=None):
        return request.user.is_repanier_admin

    def has_add_permission(self, request):
        user = request.user
        return user.is_order_manager or user.is_invoice_manager

    def has_change_permission(self, request, group=None):
        return self.has_delete_permission(request)

    def get_email(self, group):
        if group.user is not None:
            return group.user.email
        else:
            return EMPTY_STRING

    get_email.short_description = _("Email")
    get_email.admin_order_field = "user__email"

    def get_last_login(self, group):
        if group.user is not None and group.user.last_login is not None:
            return group.user.last_login.strftime(settings.DJANGO_SETTINGS_DATE)
        else:
            return EMPTY_STRING

    get_last_login.short_description = _("Last sign in")
    get_last_login.admin_order_field = "user__last_login"

    def get_actions(self, request):
        actions = super().get_actions(request)
        this_year = timezone.now().year
        actions.update(
            OrderedDict(
                create__group_action(y)
                for y in [this_year, this_year - 1, this_year - 2]
            )
        )
        return actions

    def get_fieldsets(self, request, group=None):
        fields_advanced = None
        fields_basic = [
            "short_basket_name",
            "long_basket_name",
            "email",
            "phone1",
            "phone2",
            "memo",
            "price_list_multiplier",
            ("transport", "min_transport"),
            "inform_customer_responsible",
            "customers",
            "is_active",
            "bank_account1",
            "bank_account2",
        ]
        if group is not None:
            fields_advanced = ["get_admin_balance", "get_admin_date_balance"]

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

    def get_readonly_fields(self, request, group=None):
        if group is not None:
            readonly_fields = [
                "get_admin_date_balance",
                "get_admin_balance",
                "get_purchase_counter",
            ]
            return readonly_fields
        return []

    def get_form(self, request, group=None, **kwargs):

        form = super().get_form(request, group, **kwargs)

        email_field = form.base_fields["email"]
        if group is not None:
            user_model = get_user_model()
            user = user_model.objects.get(id=group.user_id)
            # username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            email_field.initial = user.email
        else:
            # Clean data displayed
            email_field.initial = EMPTY_STRING
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_group=True)
        return qs

    def get_actions(self, request):
        actions = super().get_actions(request)
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

    def save_model(self, request, group, form, change):
        group.user = form.user
        form.user.is_staff = False
        form.user.is_active = group.is_active
        form.user.save()
        super().save_model(request, group, form, change)
        delivery_point = LUT_DeliveryPoint.objects.filter(group_id=group.id).first()
        if delivery_point is None:
            delivery_point = LUT_DeliveryPoint.objects.create(group=group)
        delivery_point.inform_customer_responsible = form.cleaned_data[
            "inform_customer_responsible"
        ]
        delivery_point.is_active = form.cleaned_data["is_active"]
        delivery_point.transport = form.cleaned_data["transport"]
        delivery_point.min_transport = form.cleaned_data["min_transport"]
        delivery_point.short_name_v2 = form.cleaned_data["short_basket_name"]
        delivery_point.save()
        Customer.objects.filter(group_id=group.id).update(group_id=None)
        Customer.objects.filter(id__in=form.cleaned_data["customers"]).update(
            group_id=group.id, price_list_multiplier=DECIMAL_ONE
        )
