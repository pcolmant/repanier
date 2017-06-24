# -*- coding: utf-8
from __future__ import unicode_literals

import uuid
from collections import OrderedDict
from decimal import Decimal
from os import sep as os_sep

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db.models import Q
from django.forms import Textarea
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import XLS
from import_export.widgets import CharWidget

import repanier.apps
from repanier.const import EMPTY_STRING, ORDER_GROUP, INVOICE_GROUP, \
    COORDINATION_GROUP, DECIMAL_ONE, TWO_DECIMALS
from repanier.models.customer import Customer
from repanier.models.lut import LUT_DeliveryPoint
from repanier.xlsx.extended_formats import XLSX_OPENPYXL_1_8_6
from repanier.xlsx.widget import IdWidget, OneToOneWidget, \
    DecimalBooleanWidget, ZeroDecimalsWidget, TwoMoneysWidget, TranslatedForeignKeyWidget, DateWidgetExcel
from repanier.xlsx.xlsx_invoice import export_invoice


class UserDataForm(forms.ModelForm):
    email = forms.EmailField(label=_('Email'))
    user = None

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        # cleaned_data = super(UserDataForm, self).clean()
        username_field_name = 'short_basket_name'
        username = self.cleaned_data.get(username_field_name)
        user_error1 = _('The given short_basket_name must be set')
        user_error2 = _('The given short_basket_name is used by another user')
        if not username:
            self.add_error(username_field_name, user_error1)
        # Check that the email is set
        if not "email" in self.cleaned_data:
            self.add_error('email', _('The given email must be set'))
        else:
            email = self.cleaned_data["email"]
            user_model = get_user_model()
            qs = user_model.objects.filter(email=email, is_staff=False).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.user_id)
            if qs.exists():
                self.add_error('email', _('The given email is used by another user'))
            qs = user_model.objects.filter(username=username).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.user_id)
            if qs.exists():
                self.add_error(username_field_name, user_error2)
        if self.instance.id is not None and "price_list_multiplier" in self.cleaned_data:
            if self.instance.delivery_point is not None \
                    and self.instance.delivery_point.customer_responsible is not None \
                    and self.cleaned_data["price_list_multiplier"] != DECIMAL_ONE:
                self.add_error('price_list_multiplier', _('If the customer is member of a closed group with a customer_responsible, the customer.price_list_multiplier must be set to ONE'))
            may_order = self.cleaned_data["may_order"]
            if may_order:
                delivery_point = LUT_DeliveryPoint.objects.filter(
                        customer_responsible_id=self.instance.id
                ).order_by('?').first()
                if delivery_point is not None:
                    self.add_error(
                        "may_order",
                        _(
                            'This customer is responsible of the delivery point (%(delivery_point)s). A customer responsible of a delivery point may not pass order.') % {
                            'delivery_point': delivery_point,})
            is_active = self.cleaned_data.get("is_active")
            if is_active is not None and not is_active:
                delivery_point = LUT_DeliveryPoint.objects.filter(
                    customer_responsible_id=self.instance.id
                ).order_by('?').first()
                if delivery_point is not None:
                    self.add_error(
                        "is_active",
                        _(
                            'This customer is responsible of the delivery point (%(delivery_point)s). A customer responsible of a delivery point must be active.') % {
                            'delivery_point': delivery_point,})
        bank_account1 = self.cleaned_data["bank_account1"]
        if bank_account1:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account1) | Q(bank_account2=bank_account1)
            ).order_by("?")
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error('bank_account1', _('This bank account already belongs to another customer.'))
        bank_account2 = self.cleaned_data["bank_account2"]
        if bank_account2:
            qs = Customer.objects.filter(
                Q(bank_account1=bank_account2) | Q(bank_account2=bank_account2)
            ).order_by("?")
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error('bank_account2', _('This bank account already belongs to another customer.'))
        # return cleaned_data

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        username = self.data['short_basket_name']
        email = self.data['email'].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.username = username
            user.first_name = EMPTY_STRING
            user.last_name = username
            user.email = email
            user.save()
        else:
            user = user_model.objects.create_user(
                username=username, email=email, password=None,
                first_name=EMPTY_STRING, last_name=username)
        self.user = user
        return self.instance


# Customer
class CustomerResource(resources.ModelResource):
    id = fields.Field(attribute='id', widget=IdWidget(), readonly=True)
    email = fields.Field(attribute='user', default="ask.it@to.me", widget=OneToOneWidget(User, 'email'), readonly=False)
    phone1 = fields.Field(attribute='phone1', default="1234", widget=CharWidget(), readonly=False)
    phone2 = fields.Field(attribute='phone2', widget=CharWidget(), readonly=False)
    date_balance = fields.Field(attribute='get_admin_date_balance', widget=CharWidget(), readonly=True)
    balance = fields.Field(attribute='get_admin_balance', widget=TwoMoneysWidget(), readonly=True)
    may_order = fields.Field(attribute='may_order', default=False, widget=DecimalBooleanWidget(), readonly=False)
    is_group = fields.Field(attribute='is_group', default=False, widget=DecimalBooleanWidget(), readonly=False)
    represent_this_buyinggroup = fields.Field(attribute='represent_this_buyinggroup', widget=DecimalBooleanWidget(),
                                              readonly=True)
    is_active = fields.Field(attribute='is_active', widget=DecimalBooleanWidget(), readonly=True)
    membership_fee_valid_until = fields.Field(
        attribute='membership_fee_valid_until', default=timezone.now().date(),
        widget=DateWidgetExcel(),
        readonly=False)
    last_membership_fee = fields.Field(attribute='get_last_membership_fee', widget=TwoMoneysWidget(), readonly=True)
    last_membership_fee_date = fields.Field(
        attribute='last_membership_fee_date',
        widget=DateWidgetExcel(),
        readonly=True)
    purchase = fields.Field(attribute='get_purchase', widget=ZeroDecimalsWidget(), readonly=True)
    participation = fields.Field(attribute='get_participation', widget=ZeroDecimalsWidget(), readonly=True)
    delivery_point = fields.Field(attribute='delivery_point',
                                  widget=TranslatedForeignKeyWidget(LUT_DeliveryPoint, field='short_name'))
    valid_email = fields.Field(attribute='valid_email', widget=DecimalBooleanWidget(), readonly=True)
    date_joined = fields.Field(attribute='get_admin_date_joined', widget=CharWidget(), readonly=True)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        user_model = get_user_model()
        user_email_qs = user_model.objects.filter(email=instance.user.email, is_staff=False).order_by('?')
        user_username_qs = user_model.objects.filter(username=instance.short_basket_name).order_by('?')
        if instance.id is not None:
            customer = Customer.objects.filter(id=instance.id).order_by('?').only('id', 'user_id').first()
            user_email_qs = user_email_qs.exclude(id=customer.user_id)
            user_username_qs = user_username_qs.exclude(id=customer.user_id)
        else:
            customer = None
        if user_email_qs.exists():
            raise ValueError(_("The email %s is already used by another user.") % instance.user.email)
        if user_username_qs.exists():
            raise ValueError(
                _("The short_basket_name %s is already used by another user.") % instance.short_basket_name)
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
                    username=instance.short_basket_name, email=instance.user.email, password=uuid.uuid1().hex,
                    first_name=EMPTY_STRING, last_name=instance.short_basket_name)
                instance.user_id = instance.user.id

    class Meta:
        model = Customer
        fields = (
            'id', 'may_order', 'short_basket_name', 'long_basket_name', 'email',
            'email2', 'language',
            'phone1', 'phone2', 'address', 'city',
            'bank_account1', 'bank_account2',
            'date_balance', 'balance', 'price_list_multiplier',
            'membership_fee_valid_until', 'last_membership_fee', 'last_membership_fee_date',
            'participation', 'purchase', 'represent_this_buyinggroup', 'is_group', 'is_active', 'delivery_point',
            'valid_email'
        )
        export_order = fields
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


def create__customer_action(year):
    def action(modeladmin, request, customer_qs):
        # To the customer we speak of "invoice".
        # This is the detail of the invoice, i.e. sold products
        wb = None
        for customer in customer_qs:
            wb = export_invoice(year=year, customer=customer, wb=wb, sheet_name=slugify(customer))
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                "%s %s" % (_('Invoice'), year),
                repanier.apps.REPANIER_SETTINGS_GROUP_NAME
            )
            wb.save(response)
            return response
        return

    name = "export_producer_%d" % (year,)
    return (name, (action, name, _("Export purchases of %s") % (year,)))


class CustomerWithUserDataForm(UserDataForm):
    class Meta:
        widgets = {
            'address': Textarea(attrs={'rows': 4, 'cols': 80, 'style': 'height: 5em; width: 30em;'}),
            'memo'   : Textarea(attrs={'rows': 4, 'cols': 160, 'style': 'height: 5em; width: 60em;'}),
        }
        model = Customer
        fields = "__all__"


class CustomerWithUserDataAdmin(ImportExportMixin, admin.ModelAdmin):
    form = CustomerWithUserDataForm
    resource_class = CustomerResource
    list_display = (
        'short_basket_name', 'get_balance', 'may_order', 'long_basket_name', 'phone1', 'get_email',
        'get_last_login', 'valid_email')
    search_fields = ('short_basket_name', 'long_basket_name', 'user__email', 'email2')
    list_per_page = 16
    list_max_show_all = 16
    list_filter = ('is_active', 'may_order', 'is_group', 'valid_email')

    def has_delete_permission(self, request, customer=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            if customer is not None:
                if customer.represent_this_buyinggroup:
                    # I can't delete the customer representing the buying group
                    return False
            return True
        return False

    def has_add_permission(self, request):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request)

    def get_email(self, customer):
        if customer.user is not None:
            return customer.user.email
        else:
            return EMPTY_STRING

    get_email.short_description = _("email")
    get_email.admin_order_field = 'user__email'

    def get_last_login(self, customer):
        if customer.user is not None and customer.user.last_login is not None:
            return customer.user.last_login.strftime(settings.DJANGO_SETTINGS_DATE)
        else:
            return EMPTY_STRING

    get_last_login.short_description = _("last login")
    get_last_login.admin_order_field = 'user__last_login'

    def get_actions(self, request):
        actions = super(CustomerWithUserDataAdmin, self).get_actions(request)
        this_year = timezone.now().year
        actions.update(OrderedDict(create__customer_action(y) for y in [this_year, this_year - 1, this_year - 2]))
        return actions

    def get_list_display(self, request):
        if repanier.apps.REPANIER_SETTINGS_INVOICE:
            return ('short_basket_name', 'get_balance', 'may_order', 'long_basket_name', 'phone1', 'get_email',
                    'get_last_login', 'valid_email')
        else:
            return ('short_basket_name', 'may_order', 'long_basket_name', 'phone1', 'get_email',
                    'get_last_login', 'valid_email')

    def get_fieldsets(self, request, customer=None):
        fields_basic = [
            ('short_basket_name', 'long_basket_name', 'language'),
            ('email', 'email2', 'accept_mails_from_members'),
            ('phone1', 'phone2', 'accept_phone_call_from_members'),
            ('membership_fee_valid_until', 'vat_id',),
        ]
        if customer is not None:
            fields_basic += [
                ('address', 'city', 'picture'),
                'memo',
            ]
        else:
            # Do not accept the picture because there is no customer.id for the "upload_to"
            fields_basic += [
                ('address', 'city'),
                'memo',
            ]

        if customer is not None:
            if customer.represent_this_buyinggroup:
                fields_basic += [
                    ('get_admin_balance', 'get_admin_date_balance'),
                    ('may_order', 'represent_this_buyinggroup')
                ]
            else:
                fields_basic += [
                    ('get_admin_balance', 'price_list_multiplier', 'get_admin_date_balance'),
                    ('may_order', 'is_group', 'is_active', 'subscribe_to_email'),
                ]
        else:
            fields_basic += [
                'price_list_multiplier',
                ('may_order', 'is_active'),
            ]
        fields_advanced = [
            'bank_account1',
            'bank_account2',
            'get_last_login',
            'get_admin_date_joined',
            'get_last_membership_fee',
            'get_last_membership_fee_date',
            'get_participation',
            'get_purchase'
        ]
        fieldsets = (
            (None, {'fields': fields_basic}),
            (_('Advanced options'), {'classes': ('collapse',), 'fields': fields_advanced})
        )
        return fieldsets

    def get_readonly_fields(self, request, customer=None):
        if customer is not None:
            if customer.represent_this_buyinggroup:
                return [
                    'get_admin_date_balance', 'get_admin_balance',
                    'represent_this_buyinggroup', 'get_last_login',
                    'get_admin_date_joined', 'get_participation', 'get_purchase',
                    'get_last_membership_fee', 'get_last_membership_fee_date'
                ]
            else:
                return [
                    'get_admin_date_balance', 'get_admin_balance',
                    'get_last_login',
                    'get_admin_date_joined', 'get_participation', 'get_purchase',
                    'get_last_membership_fee', 'get_last_membership_fee_date'
                ]
        else:
            return [
                'represent_this_buyinggroup', 'get_last_login',
                'get_admin_date_joined', 'get_participation', 'get_purchase',
                'get_last_membership_fee', 'get_last_membership_fee_date'
            ]

    def get_form(self, request, customer=None, **kwargs):
        form = super(CustomerWithUserDataAdmin, self).get_form(request, customer, **kwargs)
        username_field = form.base_fields['short_basket_name']
        email_field = form.base_fields['email']

        if customer is not None:
            user_model = get_user_model()
            user = user_model.objects.get(id=customer.user_id)
            # username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            username_field.initial = user.username
            email_field.initial = user.email
            # One folder by customer to avoid picture names conflicts
            picture_field = form.base_fields["picture"]
            if hasattr(picture_field.widget, 'upload_to'):
                picture_field.widget.upload_to = "%s%s%d" % ("customer", os_sep, customer.id)
        else:
            # Clean data displayed
            username_field.initial = EMPTY_STRING
            email_field.initial = EMPTY_STRING
        return form

    def save_model(self, request, customer, form, change):
        customer.user = form.user
        form.user.is_staff = False
        form.user.is_active = customer.is_active
        form.user.save()
        super(CustomerWithUserDataAdmin, self).save_model(
            request, customer, form, change)
        if customer.delivery_point is not None:
            customer_price = EMPTY_STRING
            if customer.price_list_multiplier < DECIMAL_ONE:
                customer_price = \
                    _(' in addition to the %(discount)s%% personal discount rate on to the pricelist') % {
                        'discount': Decimal((DECIMAL_ONE - customer.price_list_multiplier) * 100).quantize(TWO_DECIMALS)
                    }
            elif customer.price_list_multiplier > DECIMAL_ONE:
                customer_price = \
                    _(' in addition to the %(surcharge)s%% personal surcharge on to the pricelist') % {
                        'surcharge': Decimal((customer.price_list_multiplier - DECIMAL_ONE) * 100).quantize(TWO_DECIMALS)
                    }
            if customer.delivery_point.price_list_multiplier < DECIMAL_ONE:
                messages.add_message(request, messages.WARNING,
                        _('%(discount)s%% discount is granted to consumer invoices when delivered to %(delivery_point)s%(customer_price)s.') % {
                            'discount': Decimal((DECIMAL_ONE - customer.delivery_point.price_list_multiplier) * 100).quantize(TWO_DECIMALS),
                            'delivery_point': customer.delivery_point,
                            'customer_price': customer_price
                        }
                )
            elif customer.delivery_point.price_list_multiplier > DECIMAL_ONE:
                messages.add_message(request, messages.WARNING,
                        _('%(surcharge)s%% surcharge is applied to consumer invoices when delivered to %(delivery_point)s%(customer_price)s.') % {
                            'surcharge': Decimal((customer.delivery_point.price_list_multiplier - DECIMAL_ONE) * 100).quantize(TWO_DECIMALS),
                            'delivery_point': customer.delivery_point,
                            'customer_price': customer_price
                        }
                )

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLS, XLSX_OPENPYXL_1_8_6) if f().can_import()]