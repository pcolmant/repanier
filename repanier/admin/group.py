from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from repanier.const import EMPTY_STRING, DECIMAL_ONE
from repanier.const import REPANIER_MONEY_ZERO
from repanier.fields.RepanierMoneyField import FormMoneyField
from repanier.models import Customer
from repanier.models import LUT_DeliveryPoint
from repanier.models.group import Group
from repanier.xlsx.xlsx_invoice import export_invoice


class UserDataForm(forms.ModelForm):
    email = forms.EmailField(label=_("Email"), required=True)
    user = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        short_basket_name_field = "short_basket_name"
        username = self.cleaned_data.get(short_basket_name_field)
        user_error1 = _("The given short_basket_name must be set")
        user_error2 = _("The given short_basket_name is used by another user.")
        if not username:
            self.add_error(short_basket_name_field, user_error1)
        # Check that the email is set
        # if not "email" in self.cleaned_data:
        #     self.add_error('email', _('The given email must be set'))
        # else:
        email = self.cleaned_data["email"].lower()
        user_model = get_user_model()
        qs = user_model.objects.filter(email=email, is_staff=False).order_by("?")
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
            self.add_error(short_basket_name_field, user_error2)
        bank_account1 = self.cleaned_data["bank_account1"]
        if bank_account1:
            qs = Group.objects.filter(
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
            qs = Group.objects.filter(
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
            delivery_point__isnull=True,
            represent_this_buyinggroup=False,
        ),
        label=_("Members"),
        widget=FilteredSelectMultiple(_("Members"), False),
        required=False,
    )
    inform_customer_responsible = forms.BooleanField(
        label=_("Inform the group of orders placed by its members"), required=False
    )
    transport = FormMoneyField(
        label=_("Delivery point shipping cost"),
        # help_text=_("This amount is added once for groups with entitled customer or at each customer for open groups."),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        initial=REPANIER_MONEY_ZERO,
        required=False,
    )
    min_transport = FormMoneyField(
        label=_("Minimum order amount for free shipping cost"),
        # help_text=_("This is the minimum order amount to avoid shipping cost."),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        initial=REPANIER_MONEY_ZERO,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            delivery_point = (
                LUT_DeliveryPoint.objects.filter(
                    customer_responsible_id=self.instance.id
                )
                .order_by("?")
                .first()
            )
            if delivery_point is not None:
                self.fields["customers"].initial = Customer.objects.filter(
                    delivery_point_id=delivery_point.id
                )
                self.fields["customers"].queryset = Customer.objects.filter(
                    Q(may_order=True, delivery_point__isnull=True)
                    | Q(delivery_point_id=delivery_point.id)
                ).distinct()
                self.fields[
                    "inform_customer_responsible"
                ].initial = delivery_point.inform_customer_responsible
                self.fields["transport"].initial = delivery_point.transport
                self.fields["min_transport"].initial = delivery_point.min_transport
            else:
                self.fields["customers"].initial = Customer.objects.none()
                self.fields["customers"].queryset = Customer.objects.filter(
                    Q(may_order=True, delivery_point__isnull=True)
                )

    # def save(self, *args, **kwargs):
    #     super(GroupWithUserDataForm, self).save(*args, **kwargs)
    #     self.selected_customers = self.cleaned_data['customers']
    #     self.selected_inform = self.cleaned_data['inform_customer_responsible']
    #     self.selected_transport = self.cleaned_data['transport']
    #     self.selected_min_transport = self.cleaned_data['min_transport']
    #     return self.instance

    class Meta:
        widgets = {
            "address": Textarea(
                attrs={"rows": 4, "cols": 80, "style": "height: 5em; width: 30em;"}
            ),
            "memo": Textarea(
                attrs={"rows": 4, "cols": 160, "style": "height: 5em; width: 60em;"}
            ),
        }
        model = Group
        fields = "__all__"


class GroupWithUserDataAdmin(admin.ModelAdmin):
    form = GroupWithUserDataForm
    list_display = ("short_basket_name",)
    search_fields = ("short_basket_name", "long_basket_name", "user__email", "email2")
    list_filter = ("is_active", "valid_email")
    list_per_page = 16
    list_max_show_all = 16

    def has_delete_permission(self, request, customer=None):
        return request.user.is_repanier_admin

    def has_add_permission(self, request):
        user = request.user
        return user.is_order_manager or user.is_invoice_manager

    def has_change_permission(self, request, staff=None):
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

    get_last_login.short_description = _("Last login")
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

    def get_list_display(self, request):
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return (
                "__str__",
                "get_balance",
                "long_basket_name",
                "phone1",
                "get_email",
                "valid_email",
            )
        else:
            return ("__str__", "long_basket_name", "phone1", "get_email", "valid_email")

    def get_fieldsets(self, request, customer=None):
        fields_basic = [
            ("short_basket_name", "long_basket_name", "language"),
            ("email", "email2"),
            ("phone1", "phone2"),
            "memo",
            "price_list_multiplier",
            ("transport", "min_transport"),
            "inform_customer_responsible",
            "customers",
            "is_active",
        ]
        if customer is not None:
            fields_basic += ["get_admin_balance", "get_admin_date_balance"]
            fields_advanced = ["bank_account1", "bank_account2", "get_purchase_counter"]
        else:
            fields_advanced = ["bank_account1", "bank_account2"]
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

    def save_model(self, request, group, form, change):
        group.user = form.user
        form.user.is_staff = False
        form.user.is_active = group.is_active
        form.user.save()
        super().save_model(request, group, form, change)
        delivery_point = (
            LUT_DeliveryPoint.objects.filter(customer_responsible_id=group.id)
            .order_by("?")
            .first()
        )
        if delivery_point is None:
            delivery_point = LUT_DeliveryPoint.objects.create(
                customer_responsible=group
            )
        delivery_point.inform_customer_responsible = form.cleaned_data[
            "inform_customer_responsible"
        ]
        delivery_point.is_active = True
        delivery_point.transport = form.cleaned_data["transport"]
        delivery_point.min_transport = form.cleaned_data["min_transport"]
        delivery_point.short_name = form.cleaned_data["short_basket_name"]
        delivery_point.save()
        Customer.objects.filter(delivery_point_id=delivery_point.id).update(
            delivery_point=None
        )
        Customer.objects.filter(id__in=form.cleaned_data["customers"]).update(
            delivery_point_id=delivery_point.id, price_list_multiplier=DECIMAL_ONE
        )
