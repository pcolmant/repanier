# -*- coding: utf-8 -*-
import uuid

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl

from re import compile
from tools import *
from admin_filter import *
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
import datetime
from django.utils.translation import ugettext_lazy as _
from django.core import validators
from django.db.models import Q
from django import forms
from django.shortcuts import get_object_or_404
from django.db import transaction

from models import LUT_ProductionMode
from models import LUT_DepartmentForCustomer
from models import LUT_PermanenceRole

from models import Producer
from models import Permanence
from models import Customer
from models import Staff
from models import Product
from models import PermanenceBoard
from models import OfferItem
from models import PermanenceInPreparation
from models import PermanenceDone
from models import Purchase
from models import BankAccount
from views import render_response

from xslx import xslx_offer
from xslx import xslx_order
from xslx import xslx_product
from xslx import xslx_invoice
from xslx import xslx_purchase

from menus.menu_pool import menu_pool

from task import task_invoice
from task import task_order
from task import task_product
from task import task_purchase


# Filters in the right sidebar of the change list page of the admin
class ReadOnlyAdmin(admin.ModelAdmin):
    # ModelAdmin with ReadOnly

    def save_model(self, request, obj, form, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            obj.save()
            return super(ReadOnlyAdmin, self).save_model(request, obj, form, change)

    def has_add_permission(self, request):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() != 0:
            return False
        return super(ReadOnlyAdmin, self).has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() != 0:
            return False
        return super(ReadOnlyAdmin, self).has_delete_permission(request, obj=obj)

    def get_actions(self, request):
        actions = super(ReadOnlyAdmin, self).get_actions(request)
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() != 0:
            actions_copied = actions.copy()
            for key in actions_copied:
                if key not in ['export_xlsx', 'export_xlsx_offer', 'export_xlsx_order']:
                    del actions[key]
        return actions


# LUT
class LUTProductionModeAdmin(ReadOnlyAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_ProductionMode, LUTProductionModeAdmin)


class LUTDepartmentForCustomerAdmin(ReadOnlyAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)


class LUTPermanenceRoleAdmin(ReadOnlyAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_PermanenceRole, LUTPermanenceRoleAdmin)


class ProducerAdmin(ReadOnlyAdmin):
    fields = [
        ('short_profile_name', 'long_profile_name'),
        ('email', 'fax'),
        ('phone1', 'phone2',),
        ('price_list_multiplier', 'vat_level'),
        ('initial_balance', 'date_balance', 'balance'),
        ('invoice_by_basket', 'represent_this_buyinggroup', 'limit_to_alert_order_quantity'),
        'address',
        'is_active']
    readonly_fields = (
        'date_balance',
        'balance',
    )
    search_fields = ('short_profile_name', 'email')
    list_display = (
        'short_profile_name', 'get_products', 'get_balance', 'phone1', 'email', 'represent_this_buyinggroup',
        'is_active')
    list_per_page = 17
    list_max_show_all = 17
    actions = [
        'export_xlsx',
        'import_xlsx'
    ]

    def export_xlsx(self, request, queryset):
        return xslx_product.admin_export(request, queryset)

    export_xlsx.short_description = _("Export products of selected producer(s) as XSLX file")

    def import_xlsx(self, request, queryset):
        return xslx_product.admin_import(self, admin, request, queryset)

    import_xlsx.short_description = _("Import products of selected producer(s) from a XLSX file")


admin.site.register(Producer, ProducerAdmin)


# Custom User
class UserDataForm(forms.ModelForm):
    username = forms.CharField(label=_('Username'), max_length=30,
                               help_text=_(
                                   'Required. 30 characters or fewer. Letters, numbers and @/./+/-/_ characters'
                               ),
                               validators=[
                                   validators.RegexValidator(compile('^[\w.@+-]+$'), _('Enter a valid username.'),
                                                             'invalid')
                               ])
    email = forms.EmailField(label=_('Email'))
    first_name = forms.CharField(label=_('First_name'), max_length=30)
    last_name = forms.CharField(label=_('Last_name'), max_length=30)
    user = None
    read_only = True

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    # self.user = None
    # self.read_only = True

    def error(self, field, msg):
        if field not in self._errors:
            self._errors[field] = self.error_class([msg])

    def clean(self, *args, **kwargs):
        cleaned_data = super(UserDataForm, self).clean(*args, **kwargs)
        # The Staff has no first_name or last_name because it's a function with login/pwd.
        # A Customer with a first_name and last_name is responsible of this function.
        customer_form = 'short_basket_name' in self.fields
        if any(self.errors):
            if 'first_name' in self._errors:
                del self._errors['first_name']
            self.data['first_name'] = self.fields['first_name'].initial
            if 'last_name' in self._errors:
                del self._errors['last_name']
            self.data['last_name'] = self.fields['last_name'].initial
        username_field_name = 'username'
        initial_username = None
        try:
            initial_username = self.instance.user.username
        except:
            pass
        if customer_form:
            # Customer
            username_field_name = 'short_basket_name'
        # initial_username = self.fields[username_field_name].initial
        username = self.cleaned_data.get(username_field_name)
        user_error1 = _('The given username must be set')
        user_error2 = _('The given username is used by another user')
        if customer_form:
            user_error1 = _('The given short_basket_name must be set')
            user_error2 = _('The given short_basket_name is used by another user')
            if 'username' in self._errors:
                del self._errors['username']
            self.data['username'] = username
        if not username:
            self.error(username_field_name, user_error1)
        # Check that the email is set
        email = self.cleaned_data.get("email")
        if not email:
            self.error('email', _('The given email must be set'))
        # Check that the email is not already used
        user = None
        email = User.objects.normalize_email(email)
        if email:
            # Only if a email is given
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
        # Check that the username is not already used
        if user is not None:
            if initial_username != user.username:
                self.error('email', _('The given email is used by another user'))
        user = None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass
        if user is not None:
            if initial_username != user.username:
                self.error(username_field_name, user_error2)
        return cleaned_data

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        username = self.data['username']
        email = self.data['email']
        # password = self.data['password1']
        first_name = self.data['first_name']
        last_name = self.data['last_name']
        user = None
        if not self.read_only:
            # Update allowed, this is not a read only user
            if change:
                user = User.objects.get(id=self.instance.user_id)
                user.username = username
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                # if password:
                # user.set_password(password)
                user.save()
            else:
                user = User.objects.create_user(
                    username=username, email=email, password=uuid.uuid1().hex,
                    first_name=first_name, last_name=last_name)
        self.user = user
        read_only = self.read_only
        return self.instance


# Customer
class CustomerWithUserDataForm(UserDataForm):
    class Meta:
        model = Customer


class CustomerWithUserDataAdmin(ReadOnlyAdmin):
    form = CustomerWithUserDataForm
    fields = [
        ('short_basket_name', 'long_basket_name'),
        ('email', 'email2'),
        ('phone1', 'phone2'),
        'address', 'vat_id',
        ('initial_balance', 'date_balance', 'balance'),
        ('represent_this_buyinggroup', 'may_order', 'is_active')
    ]
    readonly_fields = (
        'date_balance',
        'balance',
    )
    search_fields = ('short_basket_name', 'user__email', 'email2')
    list_display = (
        '__unicode__', 'get_balance', 'may_order', 'phone1', 'phone2', 'get_email', 'email2',
        'represent_this_buyinggroup')
    list_per_page = 17
    list_max_show_all = 17

    def get_email(self, obj):
        if obj.user:
            return '%s' % (obj.user.email)
        else:
            return ''

    get_email.short_description = _("email")

    def get_form(self, request, obj=None, **kwargs):
        form = super(CustomerWithUserDataAdmin, self).get_form(request, obj, **kwargs)
        username = form.base_fields['username']
        email = form.base_fields['email']
        first_name = form.base_fields['first_name']
        last_name = form.base_fields['last_name']
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            form.read_only = False

        if obj:
            user_model = get_user_model()
            user = user_model.objects.get(id=obj.user_id)
            username.initial = getattr(user, user_model.USERNAME_FIELD)
            # username.widget.attrs['readonly'] = True
            email.initial = user.email
            first_name.initial = user.first_name
            last_name.initial = user.last_name
        else:
            # Clean data displayed
            username.initial = ''
            # username.widget.attrs['readonly'] = False
            email.initial = ''
            first_name.initial = 'N/A'
            last_name.initial = 'N/A'
        return form

    def save_model(self, request, customer, form, change):
        if not form.read_only:
            # Update allowed, this is not a read only user
            customer.user = form.user
            form.user.is_staff = False
            form.user.is_active = customer.is_active
            form.user.save()
            super(CustomerWithUserDataAdmin, self).save_model(
                request, customer, form, change)


admin.site.register(Customer, CustomerWithUserDataAdmin)


# Staff
class StaffWithUserDataForm(UserDataForm):
    class Meta:
        model = Staff


class StaffWithUserDataAdmin(ReadOnlyAdmin):
    form = StaffWithUserDataForm
    fields = ['username', 'is_external_group',
              'email', 'is_reply_to_order_email', 'is_reply_to_invoice_email',
              'customer_responsible', 'long_name', 'function_description', 'is_active']
    list_display = ('user', '__unicode__', 'customer_responsible', 'get_customer_phone1', 'is_active')
    list_select_related = ('customer_responsible',)
    list_per_page = 17
    list_max_show_all = 17

    def get_form(self, request, obj=None, **kwargs):
        form = super(StaffWithUserDataAdmin, self).get_form(request, obj, **kwargs)
        username = form.base_fields['username']
        email = form.base_fields['email']
        first_name = form.base_fields['first_name']
        last_name = form.base_fields['last_name']
        if "customer_responsible" in form.base_fields:
            # This is not the case if the user has "read_only" right
            customer_responsible = form.base_fields["customer_responsible"]
            customer_responsible.widget.can_add_related = False
            if obj:
                customer_responsible.empty_label = None
                customer_responsible.initial = obj.customer_responsible
            else:
                customer_responsible.queryset = Customer.objects.filter(is_active=True).order_by(
                    "short_basket_name")
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            form.read_only = False

        if obj:
            user_model = get_user_model()
            user = user_model.objects.get(id=obj.user_id)
            username.initial = getattr(user, user_model.USERNAME_FIELD)
            # username.widget.attrs['readonly'] = True
            email.initial = user.email
            first_name.initial = user.first_name
            last_name.initial = user.last_name
        else:
            # Clean data displayed
            username.initial = ''
            # username.widget.attrs['readonly'] = False
            email.initial = ''
            first_name.initial = 'N/A'
            last_name.initial = 'N/A'
        return form

    def save_model(self, request, staff, form, change):
        # TODO Check there is not more that one is_reply_to_order_email set to True
        # TODO Check there is not more that one is_reply_to_invoice_email set to True
        if not form.read_only:
            # Update allowed, this is not a read only user
            staff.user = form.user
            form.user.is_staff = True
            form.user.is_active = staff.is_active
            form.user.save()
            super(StaffWithUserDataAdmin, self).save_model(
                request, staff, form, change)


admin.site.register(Staff, StaffWithUserDataAdmin)


class ProductAdmin(ReadOnlyAdmin):
    list_display = (
        'is_into_offer',
        'producer',
        'department_for_customer',
        'long_name',
        'original_unit_price',
        'unit_deposit',
        'customer_alert_order_quantity',
        'get_order_unit',
        'is_active')
    list_display_links = ('long_name',)
    list_editable = ('original_unit_price', 'customer_alert_order_quantity')
    readonly_fields = ('is_created_on',
                       'is_updated_on')
    fields = (
        ('producer', 'long_name', 'picture'),
        ('original_unit_price', 'unit_deposit', 'vat_level'),
        ('order_unit', 'order_average_weight'),
        ('customer_minimum_order_quantity', 'customer_increment_order_quantity', 'customer_alert_order_quantity'),
        ('production_mode', 'department_for_customer', 'placement'),
        'offer_description',
        ('is_into_offer', 'is_active', 'is_created_on', 'is_updated_on')
    )
    list_select_related = ('producer', 'department_for_customer')
    list_per_page = 100
    list_max_show_all = 100
    ordering = ('producer',
                'department_for_customer',
                'long_name',)
    search_fields = ('long_name',)
    list_filter = ('is_active',
                   'is_into_offer',
                   ProductFilterByDepartmentForThisProducer,
                   ProductFilterByProducer,)
    actions = ['flip_flop_select_for_offer_status', 'duplicate_product']

    def get_order_unit(self, obj):
        return obj.get_order_unit_display()

    get_order_unit.short_description = _("order unit")

    def flip_flop_select_for_offer_status(self, request, queryset):
        task_product.flip_flop_is_into_offer(queryset)

    flip_flop_select_for_offer_status.short_description = _(
        'flip_flop_select_for_offer_status for offer')

    def duplicate_product(self, request, queryset):
        user_message, user_message_level = task_product.admin_duplicate(queryset)
        self.message_user(request, user_message, user_message_level)

    duplicate_product.short_description = _('duplicate product')

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProductAdmin, self).get_form(request, obj, **kwargs)
        # If we are coming from a list screen, use the filter to pre-fill the form

        # print form.base_fields
        if "producer" in form.base_fields:
            # This is not the case if the user has "read_only" right
            producer = form.base_fields["producer"]
            department_for_customer = form.base_fields["department_for_customer"]
            production_mode = form.base_fields["production_mode"]

            producer.widget.can_add_related = False
            department_for_customer.widget.can_add_related = False
            production_mode.widget.can_add_related = False

            if obj:
                producer.empty_label = None
                producer.queryset = Producer.objects.filter(is_active=True)
                department_for_customer.empty_label = None
                department_for_customer.queryset = LUT_DepartmentForCustomer.objects.filter(is_active=True)
                production_mode.empty_label = None
            else:
                producer_id = None
                department_for_customer_id = None
                is_actif_value = None
                is_into_offer_value = None
                preserved_filters = request.GET.get('_changelist_filters', None)
                if preserved_filters:
                    param = dict(parse_qsl(preserved_filters))
                    if 'producer' in param:
                        producer_id = param['producer']
                    if 'department_for_customer' in param:
                        department_for_customer_id = param['department_for_customer']
                    if 'is_active__exact' in param:
                        is_actif_value = param['is_active__exact']
                    if 'is_into_offer__exact' in param:
                        is_into_offer_value = param['is_into_offer__exact']
                is_active = form.base_fields["is_active"]
                is_into_offer = form.base_fields["is_into_offer"]
                vat_level = form.base_fields["vat_level"]
                if producer_id:
                    vat_level.initial = get_object_or_404(Producer, id=producer_id).vat_level
                    producer.empty_label = None
                    producer.queryset = Producer.objects.filter(id=producer_id)
                else:
                    producer.queryset = Producer.objects.filter(is_active=True)
                if department_for_customer_id:
                    department_for_customer.empty_label = None
                    department_for_customer.queryset = LUT_DepartmentForCustomer.objects.filter(
                        id=department_for_customer_id
                    )
                else:
                    department_for_customer.queryset = LUT_DepartmentForCustomer.objects.filter(is_active=True)
                if is_actif_value:
                    if is_actif_value == '0':
                        is_active.initial = False
                    else:
                        is_active.initial = True
                if is_into_offer_value:
                    if is_into_offer_value == '0':
                        is_into_offer.initial = False
                    else:
                        is_into_offer.initial = True
            production_mode.queryset = LUT_ProductionMode.objects.filter(is_active=True)
        return form


admin.site.register(Product, ProductAdmin)


# Permanence
class PermanenceBoardInline(admin.TabularInline):
    model = PermanenceBoard
    fields = ['permanence_role', 'customer']
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(is_active=True)  # .not_the_buyinggroup()
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True)
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

        # def save_formset(self, request, form, formset, change):
        # -> replaced by pre_save signal in model


class PermanenceDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PermanenceDataForm, self).__init__(*args, **kwargs)
        self.user = None

    def error(self, field, msg):
        if field not in self._errors:
            self._errors[field] = self.error_class([msg])

    def clean(self, *args, **kwargs):
        cleaned_data = super(PermanenceDataForm, self).clean(*args, **kwargs)
        initial_distribution_date = self.instance.distribution_date
        distribution_date = self.cleaned_data.get("distribution_date")
        initial_short_name = self.instance.short_name
        short_name = self.cleaned_data.get("short_name")
        if initial_distribution_date != distribution_date or initial_short_name != short_name:
            permanence_already_exist = False
            try:
                Permanence.objects.get(distribution_date=distribution_date, short_name=short_name)
                permanence_already_exist = True
            except Permanence.DoesNotExist:
                pass
            if permanence_already_exist:
                self.error('short_name', _(
                    'A permanence with the same distribution date and the same short_name already exist. You must either change te distribution_date or the name.'))
            else:
                # Empty menu cache to eventually display the modified Permanence Label
                menu_pool.clear()
        return cleaned_data

    class Meta:
        model = Permanence


class PermanenceInPreparationAdmin(ReadOnlyAdmin):
    form = PermanenceDataForm
    fields = (
        'distribution_date',
        'short_name',  # ('status', 'automatically_closed'),
        'automatically_closed',
        'offer_description',  # 'order_description',
        'producers'
    )
    # readonly_fields = ('status', 'is_created_on', 'is_updated_on')
    exclude = ['invoice_description']
    list_per_page = 10
    list_max_show_all = 10
    filter_horizontal = ('producers',)
    # inlines = [PermanenceBoardInline, OfferItemInline]
    inlines = [PermanenceBoardInline]
    date_hierarchy = 'distribution_date'
    list_display = ('__unicode__', 'get_producers', 'get_customers', 'get_board', 'status')
    ordering = ('distribution_date',)
    actions = [
        'export_xlsx_offer',
        'open_and_send_offer',
        'export_xlsx_order',
        'close_and_send_order',
        'delete_purchases',
        'back_to_planned',
        'generate_calendar'
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            status = obj.status
            if status > PERMANENCE_PLANNED:
                return ['status', 'is_created_on', 'is_updated_on', 'producers']
        return ['status', 'is_created_on', 'is_updated_on']

    def export_xlsx_offer(self, request, queryset):
        return xslx_offer.admin_export(request, queryset)

    export_xlsx_offer.short_description = _("Export planned XLSX")


    def export_xlsx_order(self, request, queryset):
        return xslx_order.admin_export(request, queryset)

    export_xlsx_order.short_description = _("Export orders XLSX")

    def open_and_send_offer(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_open_and_send(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : open and send offers"),
                'action': 'open_and_send_offer',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    open_and_send_offer.short_description = _('open and send offers')

    def close_and_send_order(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_close_and_send(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : close and send orders"),
                'action': 'close_and_send_order',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    close_and_send_order.short_description = _('close and send orders')

    def back_to_planned(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_back_to_planned(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : back to planned"),
                'action': 'back_to_planned',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    back_to_planned.short_description = _('back to planned')

    def delete_purchases(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_purchase.admin_delete(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _(
                    "Please, confirm the action : delete purchases. Be carefull : !!! THERE IS NO WAY TO RESTORE THEM AUTOMATICALY !!!!"),
                'action': 'delete_purchases',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    delete_purchases.short_description = _('delete purchases')

    def generate_calendar(self, request, queryset):
        for permanence in queryset[:1]:
            starting_date = permanence.distribution_date
            for i in xrange(1, 13):
                # PermanenceInPreparation used to generate PermanenceBoard when post_save
                try:
                    PermanenceInPreparation.objects.create(
                        distribution_date=starting_date + datetime.timedelta(days=7 * i))
                except:
                    pass

    generate_calendar.short_description = _("Generate 12 weekly permanences starting from this")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "producers":
            kwargs["queryset"] = Producer.objects.filter(is_active=True)
        return super(PermanenceInPreparationAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)

    def queryset(self, request):
        qs = super(PermanenceInPreparationAdmin, self).queryset(request)
        return qs.filter(status__lte=PERMANENCE_SEND)

    # save_model() is called before the inlines are saved
    def save_model(self, request, permanence, form, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            if change and ('distribution_date' in form.changed_data):
                PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                    distribution_date=permanence.distribution_date)
                Purchase.objects.filter(permanence_id=permanence.id).update(
                    distribution_date=permanence.distribution_date)
            super(PermanenceInPreparationAdmin, self).save_model(
                request, permanence, form, change)

    def save_related(self, request, form, formsets, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            super(PermanenceInPreparationAdmin, self).save_related(request, form, formsets, change)
        else:
            for formset in formsets:
                # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
                formset.new_objects = []
                formset.changed_objects = []
                formset.deleted_objects = []


admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)


class PermanenceDoneAdmin(ReadOnlyAdmin):
    fields = (
        'distribution_date',
        'short_name',
        'invoice_description',  # 'status'
    )
    readonly_fields = ('status', 'is_created_on', 'is_updated_on', 'automatically_closed')
    exclude = ['offer_description', ]
    list_per_page = 10
    list_max_show_all = 10
    # inlines = [PermanenceBoardInline, OfferItemInline]
    inlines = [PermanenceBoardInline]
    date_hierarchy = 'distribution_date'
    list_display = ('__unicode__', 'get_producers', 'get_customers', 'get_board', 'status')
    ordering = ('-distribution_date',)
    actions = [
        'export_xlsx',
        'import_xlsx',
        'generate_invoices',
        'preview_invoices',
        'send_invoices',
        'cancel_invoices',
    ]

    def export_xlsx(self, request, queryset):
        return xslx_purchase.admin_export(request, queryset)

    export_xlsx.short_description = _("Export orders prepared as XSLX file")

    def import_xlsx(self, request, queryset):
        return xslx_purchase.admin_import(self, admin, request, queryset)

    import_xlsx.short_description = _("Import orders prepared from a XLSX file")

    def preview_invoices(self, request, queryset):
        return xslx_invoice.admin_export(request, queryset)

    preview_invoices.short_description = _("Preview invoices before sending them by email")

    def generate_invoices(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            permanence_id = request.POST.get('permanence', None)
            if permanence_id is not None:
                producers_to_be_paid = []
                if admin.ACTION_CHECKBOX_NAME in request.POST:
                    # List of PK's of the selected models
                    producers_to_be_paid = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
                    queryset = Producer.objects.filter(pk__in=producers_to_be_paid)
                user_message, user_message_level = task_invoice.admin_generate(request,
                                                                               producers_to_be_paid_set=queryset,
                                                                               permanence_id=permanence_id)
                if user_message_level == messages.INFO:
                    opts = self.model._meta
                    app_label = opts.app_label
                    permanence = Permanence.objects.filter(id=permanence_id).order_by().first()
                    previous_latest_total = BankAccount.objects.filter(operation_status=BANK_NOT_LATEST_TOTAL,
                                                                       producer__isnull=True,
                                                                       customer__isnull=True).order_by('-id').first()
                    previous_latest_total_id = previous_latest_total.id if previous_latest_total else 0
                    return render_response(request, 'repanier/confirm_admin_bank_movement.html', {
                        'title': _("Please make the following payments, whose bank movements have been generated"),
                        'action': 'generate_invoices',
                        'permanence': permanence,
                        'queryset': BankAccount.objects.filter(id__gt=previous_latest_total_id, producer__isnull=False,
                                                               customer__isnull=True).order_by('producer',
                                                                                               '-operation_date',
                                                                                               '-id'),
                        "app_label": app_label,
                        'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                    })
        elif 'cancel' not in request.POST and 'done' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            permanence = queryset[:1][0]
            return render_response(request, 'repanier/confirm_admin_invoice.html', {
                'title': _("Please, confirm the action : generate the invoices"),
                'action': 'generate_invoices',
                'permanence': permanence,
                'queryset': Producer.objects.filter(
                    Q(purchase__permanence=permanence.id) | Q(is_active=True, balance__gt=0) | Q(is_active=True,
                                                                                                 balance__lt=0)).values(
                    'id', 'short_profile_name').distinct(),
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        elif 'done' in request.POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
        self.message_user(request, user_message, user_message_level)
        return None

    generate_invoices.short_description = _('generate invoices')

    def send_invoices(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_invoice.admin_send(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : send the invoices"),
                'action': 'send_invoices',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    send_invoices.short_description = _('send invoices')

    def cancel_invoices(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_invoice.admin_cancel(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : cancel the invoices"),
                'action': 'cancel_invoices',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    cancel_invoices.short_description = _('cancel latest invoices')


    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super(PermanenceDoneAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def queryset(self, request):
        qs = super(PermanenceDoneAdmin, self).queryset(request)
        return qs.filter(status__gte=PERMANENCE_SEND)

    def save_model(self, request, permanence, form, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            if change and ('distribution_date' in form.changed_data):
                PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                    distribution_date=permanence.distribution_date)
                Purchase.objects.filter(permanence_id=permanence.id).update(
                    distribution_date=permanence.distribution_date)
            super(PermanenceDoneAdmin, self).save_model(
                request, permanence, form, change)

    def save_related(self, request, form, formsets, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            super(PermanenceDoneAdmin, self).save_related(request, form, formsets, change)
        else:
            for formset in formsets:
                # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
                formset.new_objects = []
                formset.changed_objects = []
                formset.deleted_objects = []


admin.site.register(PermanenceDone, PermanenceDoneAdmin)


class PurchaseAdmin(ReadOnlyAdmin):
    fields = (
        'permanence',
        'customer',
        'product',
        'long_name',
        'quantity',
        'original_unit_price',
        'unit_deposit',  # 'original_price',
        'comment'
    )
    readonly_fields = ('long_name',)
    exclude = ['offer_item']
    list_display = [
        'permanence',
        'producer',
        'long_name',
        'customer',
        'quantity',
        'original_unit_price',
        'unit_deposit',
        'original_price',
        'comment',
    ]
    list_select_related = ('producer', 'permanence', 'customer')
    list_per_page = 17
    list_max_show_all = 17
    ordering = ('-distribution_date', 'customer', 'product')
    date_hierarchy = 'distribution_date'
    list_filter = (
        PurchaseFilterByPermanence, PurchaseFilterByCustomerForThisPermanence,
        PurchaseFilterByProducerForThisPermanence)
    list_display_links = ('long_name',)
    search_fields = ('customer__short_basket_name', 'long_name')
    actions = []

    def __init__(self, model, admin_site):
        super(PurchaseAdmin, self).__init__(model, admin_site)
        self.q_previous_order = 0

    def get_readonly_fields(self, request, obj=None):
        if obj:
            status = obj.permanence.status
            if status == PERMANENCE_SEND:
                return ['long_name']
        else:
            preserved_filters = request.GET.get('_changelist_filters', None)
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if 'permanence' in param:
                    permanence_id = param['permanence']
                    permanence = Permanence.objects.filter(
                        id=permanence_id).order_by().first()
                    if permanence and permanence.status == PERMANENCE_SEND:
                        return ['long_name']
        return ['long_name', 'original_unit_price', 'unit_deposit']

    def queryset(self, request):
        queryset = super(PurchaseAdmin, self).queryset(request)
        return queryset.exclude(producer__isnull=True)

    def get_form(self, request, obj=None, **kwargs):
        form = super(PurchaseAdmin, self).get_form(request, obj, **kwargs)
        # /purchase/add/?_changelist_filters=permanence%3D6%26customer%3D3
        # If we are coming from a list screen, use the filter to pre-fill the form
        permanence_id = None
        customer_id = None
        producer_id = None
        preserved_filters = request.GET.get('_changelist_filters', None)
        if preserved_filters:
            param = dict(parse_qsl(preserved_filters))
            if 'permanence' in param:
                permanence_id = param['permanence']
            if 'customer' in param:
                customer_id = param['customer']
            if 'producer' in param:
                producer_id = param['producer']
        if "permanence" in form.base_fields:
            # This is not the case if the user has "read_only" right
            permanence = form.base_fields["permanence"]
            customer = form.base_fields["customer"]
            product = form.base_fields["product"]
            permanence.widget.can_add_related = False
            customer.widget.can_add_related = False
            product.widget.can_add_related = False

            if obj:
                self.q_previous_order = obj.quantity
                permanence.empty_label = None
                permanence.queryset = Permanence.objects.filter(
                    id=obj.permanence_id)
                customer.empty_label = None
                customer.queryset = Customer.objects.filter(
                    id=obj.customer_id)
                product.empty_label = None
                product.queryset = Product.objects.filter(
                    id=obj.product_id)
            else:
                self.q_previous_order = 0
                if permanence_id:
                    permanence.empty_label = None
                    permanence.queryset = Permanence.objects.filter(
                        id=permanence_id,
                        status__in=[PERMANENCE_OPENED, PERMANENCE_SEND]
                    )
                    if producer_id:
                        product.queryset = Product.objects.filter(offeritem__permanence_id=permanence_id,
                                                                  producer_id=producer_id, is_active=True)
                    else:
                        product.queryset = Product.objects.filter(offeritem__permanence_id=permanence_id,
                                                                  is_active=True)
                else:
                    permanence.queryset = Permanence.objects.filter(
                        status__in=[PERMANENCE_OPENED, PERMANENCE_SEND]
                    )
                    if producer_id:
                        product.queryset = Product.objects.filter(producer_id=producer_id, is_active=True,
                                                                  is_into_offer=True)
                    else:
                        product.queryset = Product.objects.filter(is_active=True, is_into_offer=True)
                if customer_id:
                    customer.empty_label = None
                    customer.queryset = Customer.objects.filter(id=customer_id, is_active=True, may_order=True)
                else:
                    customer.queryset = Customer.objects.filter(is_active=True, may_order=True)
        return form

    @transaction.atomic
    def save_model(self, request, purchase, form, change):
        # obj.preformed_by = request.user
        # obj.ip_address = utils.get_client_ip(request)
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            offer_item = purchase.offer_item
            if purchase.offer_item is None:
                offer_item = OfferItem.objects.filter(permanence_id=purchase.permanence_id,
                                                      product_id=purchase.product_id).order_by().first()
                purchase.offer_item = offer_item
                purchase.producer = purchase.product.producer
                purchase.distribution_date = purchase.permanence.distribution_date
            if purchase.offer_item is not None:
                if offer_item.limit_to_alert_order_quantity:
                    offer_item = OfferItem.objects.select_for_update(nowait=True).get(id=purchase.offer_item_id)
                    offer_item.customer_alert_order_quantity += self.q_previous_order
                    if purchase.quantity > offer_item.customer_alert_order_quantity:
                        # Limit to available qty
                        purchase.quantity = offer_item.customer_alert_order_quantity
                    offer_item.customer_alert_order_quantity -= purchase.quantity
                    offer_item.save(update_fields=['customer_alert_order_quantity'])
            purchase.permanence.producers.add(purchase.producer)
            purchase.save()
            recalculate_order_amount(purchase.permanence.id, purchase.customer.id)

    def get_actions(self, request):
        actions = super(PurchaseAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions


admin.site.register(Purchase, PurchaseAdmin)


# Accounting
class BankAccountDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(BankAccountDataForm, self).__init__(*args, **kwargs)

    def error(self, field, msg):
        if field not in self._errors:
            self._errors[field] = self.error_class([msg])

    def clean(self, *args, **kwargs):
        cleaned_data = super(BankAccountDataForm, self).clean(*args, **kwargs)
        customer = self.cleaned_data.get("customer")
        producer = self.cleaned_data.get("producer")
        initial_id = self.instance.id
        initial_customer = self.instance.customer
        initial_producer = self.instance.producer
        if not customer and not producer:
            if initial_id is not None:
                if initial_customer is None and initial_producer is None:
                    pass
                else:
                    self.error('customer', _('Either a customer or a producer must be given.'))
                    self.error('producer', _('Either a customer or a producer must be given.'))
            else:
                bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
                if bank_account:
                    # You may only insert the first latest bank total at initialisation of the website
                    self.error('customer', _('Either a customer or a producer must be given.'))
                    self.error('producer', _('Either a customer or a producer must be given.'))
        if customer and producer:
            self.error('customer', _('Only one customer or one producer must be given.'))
            self.error('producer', _('Only one customer or one producer must be given.'))
        return cleaned_data

    class Meta:
        model = BankAccount


class BankAccountAdmin(ReadOnlyAdmin):
    form = BankAccountDataForm
    fields = ('operation_date',
              ('producer', 'customer'), 'operation_comment', 'bank_amount_in',
              'bank_amount_out',
              ('is_recorded_on_customer_invoice', 'is_recorded_on_producer_invoice'),
              ('is_created_on', 'is_updated_on') )
    list_per_page = 17
    list_max_show_all = 17
    list_display = ['operation_date', 'get_producer', 'get_customer',
                    'get_bank_amount_in', 'get_bank_amount_out', 'operation_comment']
    date_hierarchy = 'operation_date'
    ordering = ('-operation_date', '-id')
    search_fields = ('producer__short_profile_name', 'customer__short_basket_name', 'operation_comment')
    actions = []

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = [
            'is_created_on', 'is_updated_on',
            'is_recorded_on_customer_invoice', 'is_recorded_on_producer_invoice'
        ]
        if obj:
            if (obj.is_recorded_on_customer_invoice is not None or obj.is_recorded_on_producer_invoice is not None) or (
                            obj.customer is None and obj.producer is None):
                readonly_fields.append('operation_date')
                readonly_fields.append('bank_amount_in')
                readonly_fields.append('bank_amount_out')
                if obj.customer is None:
                    readonly_fields.append('customer')
                if obj.producer is None:
                    readonly_fields.append('producer')
                if obj.customer is None and obj.producer is None:
                    readonly_fields.append('operation_comment')
                return readonly_fields
        return readonly_fields

    def get_form(self, request, obj=None, **kwargs):
        form = super(BankAccountAdmin, self).get_form(request, obj, **kwargs)
        if obj:
            if obj.customer:
                customer = form.base_fields["customer"]
                customer.widget.can_add_related = False
                customer.empty_label = None
                customer.queryset = Customer.objects.filter(id=obj.customer_id)
            if obj.producer:
                producer = form.base_fields["producer"]
                producer.widget.can_add_related = False
                producer.empty_label = None
                producer.queryset = Producer.objects.filter(id=obj.producer_id)
        else:
            producer = form.base_fields["producer"]
            customer = form.base_fields["customer"]
            producer.widget.can_add_related = False
            customer.widget.can_add_related = False
            producer.queryset = Producer.objects.filter(represent_this_buyinggroup=False, is_active=True).order_by(
                "short_profile_name")
            customer.queryset = Customer.objects.filter(represent_this_buyinggroup=False, is_active=True).order_by(
                "short_basket_name")
        return form

    def get_actions(self, request):
        actions = super(BankAccountAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, bank_account, form, change):
        if request.user.groups.filter(name=READ_ONLY_GROUP).count() == 0:
            if not change:
                # create
                if bank_account.producer is None and bank_account.customer is None:
                    # You may only insert the first latest bank total at initialisation of the website
                    bank_account.operation_status = BANK_LATEST_TOTAL
            super(BankAccountAdmin, self).save_model(request, bank_account, form, change)


admin.site.register(BankAccount, BankAccountAdmin)