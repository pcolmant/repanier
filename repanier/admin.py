# -*- coding: utf-8
from __future__ import unicode_literals
from collections import OrderedDict
from os import sep as os_sep
import uuid
from django.forms import Textarea
from django.utils.timezone import utc
import parler
from apps import RepanierSettings
from fkey_choice_cache_mixin import ForeignKeyCacheMixin
from widget import SelectAdminOrderUnitWidget, PreviewProductOrderWidget

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
import datetime
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.core import validators
from django.db.models import Q, F
from django import forms
from django.db import transaction
from django_mptt_admin.admin import DjangoMpttAdmin

from parler.admin import TranslatableAdmin, TranslatableModelForm

from models import LUT_ProductionMode, OfferItemSend, PurchaseSendForUpdate, \
    PurchaseOpenedOrClosedForUpdate, CustomerSend, OfferItemClosed, CustomerInvoice, ProducerInvoice
from models import Configuration
from models import LUT_DepartmentForCustomer
from models import LUT_PermanenceRole
from models import LUT_DeliveryPoint

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
from xslx import xslx_stock

from menus.menu_pool import menu_pool

from task import task_invoice
from task import task_order
from task import task_product
from task import task_purchase


# LUT
class LUTProductionModeAdmin(TranslatableAdmin, DjangoMpttAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17
    exclude = ('picture',)


admin.site.register(LUT_ProductionMode, LUTProductionModeAdmin)


class LUTDeliveryPointAdmin(TranslatableAdmin, DjangoMpttAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_DeliveryPoint, LUTDeliveryPointAdmin)


class LUTDepartmentForCustomerAdmin(TranslatableAdmin, DjangoMpttAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)


class LUTPermanenceRoleAdmin(TranslatableAdmin, DjangoMpttAdmin):
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    list_per_page = 17
    list_max_show_all = 17


admin.site.register(LUT_PermanenceRole, LUTPermanenceRoleAdmin)


def create__producer_action(year):
    def action(modeladmin, request, queryset):
        queryset = queryset.order_by()
        return xslx_purchase.admin_export_in(year, queryset)

    name = "export_producer_%d" % (year,)
    return (name, (action, name, _("Export purchases of %s") % (year,)))


class ConfigurationAdmin(TranslatableAdmin):
    fieldsets = [
        (None, {
            'fields':
                (('test_mode', 'group_name', 'name'),
                'display_anonymous_order_form',
                ('display_producer_on_order_form', 'max_week_wo_participation'),
                ('display_vat', 'invoice', 'bank_account', 'vat_id')),
        }),
        (_('Opening mails'), {
            'classes': ('collapse',),
            'fields':
                (
                    'send_opening_mail_to_customer', 'offer_customer_mail',
                ),
        }),
        (_('Ordering mails'), {
            'classes': ('collapse',),
            'fields':
                (
                    'send_order_mail_to_customer', 'order_customer_mail',
                    'send_order_mail_to_producer', 'order_producer_mail',
                    'send_order_mail_to_board', 'order_staff_mail',
                ),
        }),
        (_('Invoicing mails'), {
            'classes': ('collapse',),
            'fields':
                (
                    'send_invoice_mail_to_customer', 'invoice_customer_mail',
                    'send_invoice_mail_to_producer', 'invoice_producer_mail',
                    # 'invoice_staff_mail',
                ),
        }),
        (_('Advanced options'), {
            'classes': ('collapse',),
            'fields':
                (('accept_child_group', 'delivery_point'),
                'page_break_on_customer_check',
                ('stock', 'producer_order_rounded',),
                'producer_pre_opening', 'offer_producer_mail'),
        }),
        ]

    def get_readonly_fields(self, request, configuration=None):
        permanence = Permanence.objects.all().order_by().first()
        if permanence is None:
            return []
        else:
            return ['bank_account']


admin.site.register(Configuration, ConfigurationAdmin)


class ProducerAdmin(admin.ModelAdmin):

    search_fields = ('short_profile_name', 'email')
    list_per_page = 17
    list_max_show_all = 17
    list_filter = ('is_active', 'invoice_by_basket', 'manage_stock', 'is_resale_price_fixed')
    actions = ['export_xlsx_producer_prices', 'export_xlsx_customer_prices', 'import_xlsx', 'recalculate_prices']

    def export_xlsx_producer_prices(self, request, queryset):
        return xslx_product.admin_export(request, queryset, producer_prices=True)

    export_xlsx_producer_prices.short_description = _(
        "Export products of selected producer(s) as XSLX file at procuder's pices")

    def export_xlsx_customer_prices(self, request, queryset):
        return xslx_product.admin_export(request, queryset, producer_prices=False)

    export_xlsx_customer_prices.short_description = _(
        "Export products of selected producer(s) as XSLX file at customer's prices")

    def import_xlsx(self, request, queryset):
        return xslx_product.admin_import(self, admin, request, queryset, action='import_xlsx')

    import_xlsx.short_description = _("Import products of selected producer(s) from a XLSX file")

    def recalculate_prices(self, request, queryset):
        for producer in queryset:
            for product in Product.objects.filter(producer_id=producer.id).order_by():
                product.save()
                for permanence in Permanence.objects.filter(
                        status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND]
                ):
                    offer_item_queryset = OfferItem.objects\
                        .filter(
                            permanence_id=permanence.id,
                            product_id=product.id,
                            is_active=True
                        ).order_by()
                    clean_offer_item(permanence, offer_item_queryset, reorder=False)
                    recalculate_order_amount(permanence_id=permanence.id,
                                             permanence_status=permanence.status,
                                             offer_item_queryset=offer_item_queryset,
                                             send_to_producer=False)

        self.message_user(request, _("The prices have been recalculated."), level=messages.INFO)

    recalculate_prices.short_description = _('recalculate prices')

    def get_actions(self, request):
        actions = super(ProducerAdmin, self).get_actions(request)
        this_year = datetime.datetime.utcnow().replace(tzinfo=utc).year
        actions.update(OrderedDict(create__producer_action(y) for y in [this_year, this_year-1, this_year-2]))
        return actions

    def get_list_display(self, request):
        if RepanierSettings.stock:
            return ('short_profile_name', 'get_products', 'get_balance', 'phone1', 'email', 'manage_stock', 'is_active')
        else:
            return ('short_profile_name', 'get_products', 'get_balance', 'phone1', 'email', 'is_active')

    def get_fields(self, request, producer=None):
        fields = [
            ('short_profile_name', 'long_profile_name', 'language'),
            ('email', 'fax'),
            ('phone1', 'phone2',)
        ]
        if RepanierSettings.display_vat:
            fields += [
                ('price_list_multiplier', 'producer_price_are_wo_vat', 'is_resale_price_fixed', 'vat_level'),
            ]
        else:
            fields += [
                ('price_list_multiplier', 'is_resale_price_fixed'),
            ]
        if RepanierSettings.stock:
            fields += [
                ('invoice_by_basket', 'manage_stock',),
            ]
        else:
            fields += [
                ('invoice_by_basket',),
            ]
        fields += [
            ('address', 'memo'),
        ]
        if RepanierSettings.invoice:
            fields += [
                ('initial_balance', 'date_balance', 'balance', 'represent_this_buyinggroup'),
            ]
        fields += [
            ('is_active', 'uuid')
        ]
        return fields

    def get_readonly_fields(self, request, producer=None):
        if RepanierSettings.invoice:
            if producer is not None:
                producer_invoice = ProducerInvoice.objects.filter(producer_id=producer.id).order_by().first()
                if producer_invoice is not None:
                    # Do not modify the initial balance, an invoice already exist
                    return ['represent_this_buyinggroup', 'date_balance', 'balance', 'uuid', 'initial_balance']
                else:
                    return ['represent_this_buyinggroup', 'date_balance', 'balance', 'uuid']
            else:
                return ['uuid',]
        else:
            return ['represent_this_buyinggroup', 'uuid',]


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
    user = None

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean_phone1(self):
        i = 0
        k = 0
        phone1 = self.cleaned_data['phone1']
        while i < len(phone1):
            if '0' <= phone1[i] <= '9':
                k += 1
            if k == 4:
                break
            i += 1
        if k < 4:
            self.add_error(
                'phone1',
                _('The phone number must ends with 4 digits, eventually separated'))
        return phone1

    def clean(self):
        cleaned_data = super(UserDataForm, self).clean()
        # The Staff has no first_name or last_name because it's a function with login/pwd.
        # A Customer with a first_name and last_name is responsible of this function.
        is_customer_form = 'short_basket_name' in self.fields
        is_staff_form = not is_customer_form
        username_field_name = 'username'
        initial_username = None
        try:
            initial_username = self.instance.user.username
        except:
            pass
        if is_customer_form:
            # Customer
            username_field_name = 'short_basket_name'
        username = self.cleaned_data.get(username_field_name)
        user_error1 = _('The given username must be set')
        user_error2 = _('The given username is used by another user')
        if is_customer_form:
            user_error1 = _('The given short_basket_name must be set')
            user_error2 = _('The given short_basket_name is used by another user')
            if 'username' in self._errors:
                del self._errors['username']
            self.data['username'] = username
        if not username:
            self.add_error(username_field_name, user_error1)
        # Check that the email is set
        if not "email" in self.cleaned_data:
            self.add_error('email', _('The given email must be set'))
        else:
            email = self.cleaned_data["email"]
            if is_staff_form:
                is_reply_to_order_email = self.cleaned_data["is_reply_to_order_email"]
                is_reply_to_invoice_email = self.cleaned_data["is_reply_to_invoice_email"]
                if is_reply_to_order_email or is_reply_to_invoice_email:
                    allowed_mail_extension = get_allowed_mail_extension()
                    if not email.endswith(allowed_mail_extension):
                        self.add_error(
                            'email',
                            _('The given email must end with %(allowed_extension)s') %
                                 {'allowed_extension': allowed_mail_extension}
                        )
            user_model = get_user_model()
            user = user_model.objects.filter(email=email).order_by("id").first()
            # Check that the username is not already used
            if user is not None:
                if initial_username != user.username:
                    self.add_error('email', _('The given email is used by another user'))
            user = user_model.objects.filter(username=username).order_by("id").first()
            if user is not None:
                if initial_username != user.username:
                    self.add_error(username_field_name, user_error2)
        return cleaned_data

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        username = self.data['username']
        email = self.data['email'].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.username = username
            user.email = email
            user.save()
        else:
            user = user_model.objects.create_user(
                username=username, email=email, password=uuid.uuid1().hex,
                first_name="", last_name=username)
        self.user = user
        return self.instance


# Customer
class CustomerWithUserDataForm(UserDataForm):

    class Meta:
        widgets = {
            'address': Textarea(attrs={'rows': 4, 'cols': 80}),
            'memo': Textarea(attrs={'rows': 4, 'cols': 80}),
        }
        model = Customer
        fields = "__all__"


class CustomerWithUserDataAdmin(admin.ModelAdmin):
    form = CustomerWithUserDataForm
    list_display = (
        'short_basket_name', 'get_balance', 'may_order', 'long_basket_name', 'phone1', 'get_email',
        'get_last_login')
    search_fields = ('short_basket_name', 'long_basket_name', 'user__email', 'email2')
    list_per_page = 17
    list_max_show_all = 17
    list_filter = ('is_active',
                   'may_order',
                   'delivery_point')

    def get_email(self, customer):
        if customer.user is not None:
            return customer.user.email
        else:
            return ''

    get_email.short_description = _("email")
    get_email.admin_order_field = 'user__email'

    def get_date_joined(self, customer):
        if customer.user is not None:
            return customer.user.date_joined.strftime('%d-%m-%Y')
        else:
            return ''

    get_date_joined.short_description = _("date joined")

    def get_last_login(self, customer):
        if customer.user is not None:
            return customer.user.last_login.strftime('%d-%m-%Y')
        else:
            return ''

    get_last_login.short_description = _("last login")
    get_last_login.admin_order_field = 'user__last_login'

    def get_fields(self, request, customer=None):
        fields = [
            ('short_basket_name', 'long_basket_name', 'language'),
            ('email', 'email2', 'accept_mails_from_members'),
            ('phone1', 'phone2', 'accept_phone_call_from_members'),
        ]
        if RepanierSettings.invoice:
            if RepanierSettings.delivery_point:
                fields += [
                    ('delivery_point', 'vat_id'),
                ]
            else:
                fields += [
                    ('vat_id',),
                ]
        elif RepanierSettings.delivery_point:
            fields += [
                ('delivery_point',),
            ]
        if customer is not None:
            fields += [
                ('address', 'city', 'picture'),
                'memo',
            ]
        else:
            # Do not accept the picture because there is no customer.id for the "upload_to"
            fields += [
                ('address', 'city'),
                'memo',
            ]

        if RepanierSettings.invoice:
            if customer is not None:
                customer_invoice = CustomerInvoice.objects.filter(customer_id=customer.id).order_by().first()
                if customer_invoice is not None:
                    # Do not modify the initial balance, an invoice already exist
                    fields += [
                        ('date_balance', 'balance', 'represent_this_buyinggroup'),
                    ]
                else:
                    fields += [
                        ('initial_balance', 'represent_this_buyinggroup'),
                    ]
            else:
                fields += [
                    ('initial_balance',),
                ]
        fields += [
            ('may_order', 'is_active'),
            ('get_last_login', 'get_date_joined')
        ]
        return fields

    def get_readonly_fields(self, request, customer=None):
        if RepanierSettings.invoice:
            if customer is not None:
                customer_invoice = CustomerInvoice.objects.filter(customer_id=customer.id).order_by().first()
                if customer_invoice is not None:
                    # Do not modify the initial balance, an invoice already exist
                    return ['represent_this_buyinggroup', 'date_balance', 'balance', 'get_last_login',
                            'get_date_joined']
                else:
                    return ['represent_this_buyinggroup', 'get_last_login', 'get_date_joined']
            else:
                return ['represent_this_buyinggroup', 'get_last_login', 'get_date_joined']
        return ['get_last_login', 'get_date_joined']

    def get_form(self, request, customer=None, **kwargs):
        form = super(CustomerWithUserDataAdmin, self).get_form(request, customer, **kwargs)
        username_field = form.base_fields['username']
        email_field = form.base_fields['email']

        if RepanierSettings.delivery_point:
            delivery_point_field = form.base_fields["delivery_point"]
            delivery_point_field.empty_label = None
            delivery_point_field.queryset = LUT_DeliveryPoint.objects.filter(
                rght=F('lft')+1, is_active=True, translations__language_code=translation.get_language()
            ).order_by('translations__short_name')
            delivery_point_field.widget.can_add_related = False
        if customer is not None:
            user_model = get_user_model()
            user = user_model.objects.get(id=customer.user_id)
            username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            email_field.initial = user.email
            # One folder by customer to avoid picture names conflicts
            picture_field = form.base_fields["picture"]
            if hasattr(picture_field.widget, 'upload_to'):
                picture_field.widget.upload_to = "customer" + os_sep + str(customer.id)
        else:
            # Clean data displayed
            username_field.initial = ''
            email_field.initial = ''
        return form

    def save_model(self, request, customer, form, change):
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
        fields = "__all__"


class StaffWithUserDataAdmin(admin.ModelAdmin):
    form = StaffWithUserDataForm
    fields = ['username',
              'email', 'is_reply_to_order_email', 'is_reply_to_invoice_email',
              'is_coordinator', 'is_webmaster',
              'customer_responsible', 'long_name', 'function_description',
              'is_active']
    list_display = ('user', 'long_name', 'customer_responsible', 'get_customer_phone1', 'is_active')
    list_select_related = ('customer_responsible',)
    list_per_page = 17
    list_max_show_all = 17

    def get_form(self, request, obj=None, **kwargs):
        form = super(StaffWithUserDataAdmin, self).get_form(request, obj, **kwargs)
        username_field = form.base_fields['username']
        email_field = form.base_fields['email']
        if "customer_responsible" in form.base_fields:
            customer_responsible_field = form.base_fields["customer_responsible"]
            customer_responsible_field.widget.can_add_related = False
            if obj:
                customer_responsible_field.empty_label = None
                customer_responsible_field.initial = obj.customer_responsible
            else:
                customer_responsible_field.queryset = Customer.objects.filter(is_active=True).order_by(
                    "short_basket_name")

        if obj:
            user_model = get_user_model()
            user = user_model.objects.get(id=obj.user_id)
            username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            # username.widget.attrs['readonly'] = True
            email_field.initial = user.email
        else:
            # Clean data displayed
            username_field.initial = ''
            # username.widget.attrs['readonly'] = False
            email_field.initial = ''
        return form

    def save_model(self, request, staff, form, change):
        # TODO Check there is not more that one is_reply_to_order_email set to True
        # TODO Check there is not more that one is_reply_to_invoice_email set to True
        staff.user = form.user
        form.user.is_staff = True
        form.user.is_active = staff.is_active
        form.user.save()
        super(StaffWithUserDataAdmin, self).save_model(request, staff, form, change)


admin.site.register(Staff, StaffWithUserDataAdmin)


# Custom Product
class ProductDataForm(TranslatableModelForm):
    # preview_product_order = forms.CharField(label="", widget=PreviewProductOrderWidget)

    def __init__(self, *args, **kwargs):
        super(ProductDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(ProductDataForm, self).clean()
        return cleaned_data

    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
          'order_unit': SelectAdminOrderUnitWidget(),
        }


def create_product_action(permanence):
    def action(modeladmin, request, queryset):
        queryset = queryset.order_by()
        offer_item_queryset = OfferItem.objects\
            .filter(
                permanence_id=permanence.id,
                product__in=queryset,
                is_active=True
            ).order_by()
        clean_offer_item(permanence, offer_item_queryset, reorder=False)
        recalculate_order_amount(permanence_id=permanence.id,
                                 permanence_status=permanence.status,
                                 offer_item_queryset=offer_item_queryset,
                                 send_to_producer=False)
        user_message = _("Action performed.")
        user_message_level = messages.INFO
        modeladmin.message_user(request, user_message, user_message_level)

    name = "apply_to_%d" % (permanence.id,)
    return (name, (action, name, _("Apply to %s") % (permanence,)))


class ProductAdmin(TranslatableAdmin):
    form = ProductDataForm
    # TODO makemigrations
    list_display = ('get_long_name', 'producer_unit_price', 'customer_alert_order_quantity', 'stock')
    list_display_links = ('get_long_name',)
    list_editable = ('producer_unit_price', 'customer_alert_order_quantity', 'stock')
    readonly_fields = ('is_created_on',
                       'is_updated_on')
    list_select_related = ('producer', 'department_for_customer')
    list_per_page = 17
    list_max_show_all = 17
    filter_horizontal = ('production_mode',)
    ordering = ('producer',
                'translations__long_name',)
    search_fields = ('translations__long_name',)
    list_filter = ('is_active',
                   'is_into_offer',
                   ProductFilterByDepartmentForThisProducer,
                   ProductFilterByProducer,)
    actions = ['flip_flop_select_for_offer_status', 'duplicate_product']

    def flip_flop_select_for_offer_status(self, request, queryset):
        task_product.flip_flop_is_into_offer(queryset)

    flip_flop_select_for_offer_status.short_description = _(
        'flip_flop_select_for_offer_status for offer')

    def duplicate_product(self, request, queryset):
        user_message, user_message_level = task_product.admin_duplicate(queryset)
        self.message_user(request, user_message, user_message_level)

    duplicate_product.short_description = _('duplicate product')

    def get_list_display(self, request):
        # list_editable interacts with a couple of other options in particular ways;
        #
        # Any field in list_editable must also be in list_display. You can’t edit a field that’s not displayed!
        # You’ll get a validation error if either of these rules are broken.
        if RepanierSettings.stock:
            return ('is_into_offer', 'producer','department_for_customer', 'get_long_name', 'producer_unit_price',
                'unit_deposit', 'customer_alert_order_quantity', 'stock', 'is_active')
        else:
            #
            return ('is_into_offer', 'producer','department_for_customer', 'get_long_name', 'producer_unit_price',
                'unit_deposit', 'customer_alert_order_quantity', 'stock', 'is_active')

    def get_form(self, request, product=None, **kwargs):
        department_for_customer_id = None
        is_active_value = None
        is_into_offer_value = None
        producer_queryset = Producer.objects.none()
        producer = None
        if product:
            producer_queryset = Producer.objects.filter(id=product.producer_id).order_by()
            producer = product.producer
        else:
            preserved_filters = request.GET.get('_changelist_filters', None)
            if preserved_filters:
                param = dict(parse_qsl(preserved_filters))
                if 'producer' in param:
                    producer_id = param['producer']
                    if producer_id:
                        producer_queryset = Producer.objects.filter(id=producer_id).order_by()
                        producer = producer_queryset.first()
                if 'department_for_customer' in param:
                    department_for_customer_id = param['department_for_customer']
                if 'is_active__exact' in param:
                    is_active_value = param['is_active__exact']
                if 'is_into_offer__exact' in param:
                    is_into_offer_value = param['is_into_offer__exact']
        self.fields = [
            ('producer', 'long_name', 'picture2'),
            # 'preview_product_order',
            ('order_unit', 'wrapped'),
        ]
        if producer is not None and producer.is_resale_price_fixed:
            self.fields += [
                ('producer_unit_price', 'customer_unit_price',),
                ('unit_deposit', 'order_average_weight',),
            ]
        else:
            self.fields += [
                ('producer_unit_price', 'unit_deposit', 'order_average_weight'),
            ]
        self.fields += [
            ('customer_minimum_order_quantity', 'customer_increment_order_quantity', 'customer_alert_order_quantity'),
            ('department_for_customer', 'placement'),
            'production_mode',
            'offer_description',
        ]
        if RepanierSettings.display_vat:
            self.fields += [
            ('reference', 'vat_level'),
            ]
        else:
            self.fields += [
            ('reference',),
            ]
        if producer is not None and producer.manage_stock:
            self.fields += [
                ('stock', 'limit_order_quantity_to_stock'),
            ]
        self.fields += [
            ('is_into_offer', 'is_active', 'is_created_on', 'is_updated_on')
        ]

        form = super(ProductAdmin, self).get_form(request, product, **kwargs)

        producer_field = form.base_fields["producer"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        production_mode_field = form.base_fields["production_mode"]
        picture_field = form.base_fields["picture2"]

        producer_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        production_mode_field.widget.can_add_related = False
        # One folder by producer for clarity
        if hasattr(picture_field.widget, 'upload_to'):
            # picture_field.widget.upload_to += os_sep + str(producer.id)
            picture_field.widget.upload_to = "product" + os_sep + str(producer.id)

        if product:
            producer_field.empty_label = None
            producer_field.queryset = producer_queryset
            # department_for_customer_field.empty_label = None
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                rght=F('lft') + 1, is_active=True, translations__language_code=translation.get_language()).order_by(
                'translations__short_name')
            production_mode_field.empty_label = None
        else:
            if producer is not None:
                if RepanierSettings.display_vat:
                    vat_level_field = form.base_fields["vat_level"]
                    vat_level_field.initial = producer.vat_level
                producer_field.empty_label = None
                producer_field.queryset = producer_queryset
            else:
                producer_field.choices = [('-1', _("Please select first a producer in the filter of previous screen"))]
            if department_for_customer_id is not None:
                # department_for_customer_field.empty_label = None
                department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    id=department_for_customer_id
                )
            else:
                department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.filter(
                    rght=F('lft') + 1, is_active=True, translations__language_code=translation.get_language()).order_by(
                    'translations__short_name')
            if is_active_value:
                is_active_field = form.base_fields["is_active"]
                if is_active_value == '0':
                    is_active_field.initial = False
                else:
                    is_active_field.initial = True
            if is_into_offer_value:
                is_into_offer_field = form.base_fields["is_into_offer"]
                if is_into_offer_value == '0':
                    is_into_offer_field.initial = False
                else:
                    is_into_offer_field.initial = True
        production_mode_field.queryset = LUT_ProductionMode.objects.filter(
            rght=F('lft') + 1, is_active=True, translations__language_code=translation.get_language()).order_by(
            'translations__short_name')
        if RepanierSettings.producer_pre_opening:
            order_unit_field = form.base_fields["order_unit"]
            order_unit_field.choices = LUT_PRODUCER_PRODUCT_ORDER_UNIT
        return form

    def save_model(self, request, product, form, change):
        super(ProductAdmin, self).save_model(
            request, product, form, change)
        for permanence in Permanence.objects.filter(
                status__in=[PERMANENCE_CLOSED, PERMANENCE_SEND]
        ):
            offer_item_queryset = OfferItem.objects\
                .filter(
                    permanence_id=permanence.id,
                    product_id=product.id,
                    is_active=True
                ).order_by()
            clean_offer_item(permanence, offer_item_queryset, reorder=False)
            recalculate_order_amount(permanence_id=permanence.id,
                                     permanence_status=permanence.status,
                                     offer_item_queryset=offer_item_queryset,
                                     send_to_producer=False)

    def get_queryset(self, request):
        queryset = super(ProductAdmin, self).get_queryset(request)
        return queryset.filter(translations__language_code=translation.get_language())

    def get_actions(self, request):
        actions = super(ProductAdmin, self).get_actions(request)
        actions.update(OrderedDict(create_product_action(p) for p in
            Permanence.objects.filter(status__in=[PERMANENCE_PRE_OPEN, PERMANENCE_OPENED])
                .order_by('-permanence_date')))
        return actions

admin.site.register(Product, ProductAdmin)


# Permanence
class PermanenceBoardInline(ForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    fields = ['permanence_role', 'customer']
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(is_active=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True)
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

        # def save_formset(self, request, form, formset, change):
        # -> replaced by pre_save signal in model


class PermanenceInPreparationAdmin(TranslatableAdmin):
    # form = PermanenceDataForm
    fields = (
        'permanence_date',
        'short_name',
        'automatically_closed',
        'offer_description',
        'producers'
    )
    exclude = ['invoice_description']
    list_per_page = 10
    list_max_show_all = 10
    filter_horizontal = ('producers',)
    inlines = [PermanenceBoardInline]
    date_hierarchy = 'permanence_date'
    list_display = ('__str__', 'get_producers', 'get_customers', 'get_board', 'status')
    ordering = ('permanence_date',)
    actions = [
        'export_xlsx_offer',
        'open_and_send_offer',
        'close_order',
        'export_xlsx_customer_order',
        'export_xlsx_producer_order',
        'import_xlsx_stock',
        'send_order',
        'delete_purchases',
        'back_to_planned',
        'undo_back_to_planned',
        'generate_next_week',
        'generate_next_12_week'
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            status = obj.status
            if status > PERMANENCE_PLANNED:
                return ['status', 'producers']
        return ['status',]

    def export_xlsx_offer(self, request, queryset):
        return xslx_offer.admin_export(request, queryset)

    export_xlsx_offer.short_description = _("Export planned xlsx")

    def export_xlsx_customer_order(self, request, queryset):
        return xslx_order.admin_customer_export(request, queryset)

    export_xlsx_customer_order.short_description = _("Export xlsx customers orders")

    def import_xlsx_stock(self, request, queryset):
        return xslx_stock.admin_import(self, admin, request, queryset, action='import_xlsx_stock')

    import_xlsx_stock.short_description = _("Import stock from a xlsx file")

    def export_xlsx_producer_order(self, request, queryset):
        return xslx_order.admin_producer_export(request, queryset)

    export_xlsx_producer_order.short_description = _("Export xlsx producers orders")

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

    def close_order(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_close(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : close orders"),
                'action': 'close_order',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    close_order.short_description = _('close orders')

    def send_order(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_send(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : send orders"),
                'action': 'send_order',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    send_order.short_description = _('send orders1')

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

    def undo_back_to_planned(self, request, queryset):
        user_message = _("Action canceled by the user.")
        user_message_level = messages.WARNING
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_undo_back_to_planned(request, queryset)
        elif 'cancel' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            return render_response(request, 'repanier/confirm_admin_action.html', {
                'title': _("Please, confirm the action : undo back to planned"),
                'action': 'undo_back_to_planned',
                'queryset': queryset[:1],
                "app_label": app_label,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            })
        self.message_user(request, user_message, user_message_level)
        return None

    undo_back_to_planned.short_description = _('undo back to planned')

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

    delete_purchases.short_description = _('delete purchases1')

    def generate_next_week(self, request, queryset):
        permanence = queryset.first()
        starting_date = permanence.permanence_date
        cur_language = translation.get_language()
        for i in xrange(1, 2):
            # PermanenceInPreparation used to generate PermanenceBoard when post_save
            new_date = starting_date + datetime.timedelta(days=7 * i)
            if not PermanenceInPreparation.objects.filter(
                permanence_date=new_date).exists():
                new_permanence = PermanenceInPreparation.objects.create(
                    permanence_date=new_date)
                try:
                    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                        translation.activate(language["code"])
                        new_permanence.short_name = permanence.short_name
                        new_permanence.save()
                except:
                    pass
                translation.activate(cur_language)
                for permanence_board in PermanenceBoard.objects.filter(
                        permanence=permanence,
                        permanence_role__is_active=True
                ):
                    PermanenceBoard.objects.create(
                        permanence=new_permanence,
                        permanence_role=permanence_board.permanence_role
                    )
                for producer in permanence.producers.all():
                    new_permanence.producers.add(producer)

    generate_next_week.short_description = _("Duplicate this permanence next week")

    def generate_next_12_week(self, request, queryset):
        permanence = queryset.first()
        starting_date = permanence.permanence_date
        cur_language = translation.get_language()
        for i in xrange(1, 13):
            # PermanenceInPreparation used to generate PermanenceBoard when post_save
            new_date = starting_date + datetime.timedelta(days=7 * i)
            if not PermanenceInPreparation.objects.filter(
                permanence_date=new_date).exists():
                new_permanence = PermanenceInPreparation.objects.create(
                    permanence_date=new_date)
                try:
                    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                        translation.activate(language["code"])
                        new_permanence.short_name = permanence.short_name
                        new_permanence.save()
                except:
                    pass
                translation.activate(cur_language)
                for permanence_board in PermanenceBoard.objects.filter(
                        permanence=permanence,
                        permanence_role__is_active=True
                ):
                    PermanenceBoard.objects.create(
                        permanence=new_permanence,
                        permanence_role=permanence_board.permanence_role
                    )
                for producer in permanence.producers.all():
                    new_permanence.producers.add(producer)


    generate_next_12_week.short_description = _("Duplicate this permanence during 12 week")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "producers":
            kwargs["queryset"] = Producer.objects.filter(is_active=True)
        return super(PermanenceInPreparationAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)

    def get_actions(self, request):
        actions = super(PermanenceInPreparationAdmin, self).get_actions(request)
        if not RepanierSettings.stock:
            del actions['import_xlsx_stock']

        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def get_queryset(self, request):
        qs = super(PermanenceInPreparationAdmin, self).get_queryset(request)
        return qs.filter(status__lte=PERMANENCE_SEND)

    # save_model() is called before the inlines are saved
    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
            Purchase.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceInPreparationAdmin, self).save_model(
            request, permanence, form, change)

    def save_related(self, request, form, formsets, change):
        super(PermanenceInPreparationAdmin, self).save_related(request, form, formsets, change)


admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)


class PermanenceDoneAdmin(TranslatableAdmin):
    # form = PermanenceDataForm
    fields = (
        'permanence_date',
        'short_name',
        'invoice_description',  # 'status'
    )
    readonly_fields = ('status', 'automatically_closed')
    exclude = ['offer_description', ]
    list_per_page = 10
    list_max_show_all = 10
    inlines = [PermanenceBoardInline]
    date_hierarchy = 'permanence_date'
    list_display = ('__str__', 'get_producers', 'get_customers', 'get_board', 'status')
    ordering = ('-permanence_date',)
    actions = [
        'export_xlsx',
        'import_xlsx',
        'generate_invoices',
        'preview_invoices',
        'send_invoices',
        'cancel_invoices',
        'archive',
        'cancel_archive',
    ]

    def export_xlsx(self, request, queryset):
        return xslx_purchase.admin_export(request, queryset)

    export_xlsx.short_description = _("Export orders prepared as XSLX file")

    def import_xlsx(self, request, queryset):
        return xslx_purchase.admin_import(self, admin, request, queryset, action = 'import_xlsx')

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
                if admin.ACTION_CHECKBOX_NAME in request.POST:
                    # List of PK's of the selected models
                    # producers_to_be_paid = []
                    producers_to_be_paid = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
                    producers_qs = Producer.objects.filter(pk__in=producers_to_be_paid)
                    permanence = Permanence.objects.filter(id=permanence_id).order_by().first()
                    user_message, user_message_level = task_invoice.admin_generate(request,
                        producers_to_be_paid_set=producers_qs,
                        permanence=permanence)
                    if user_message_level == messages.INFO:
                        opts = self.model._meta
                        app_label = opts.app_label
                        previous_latest_total = BankAccount.objects.filter(
                            operation_status=BANK_NOT_LATEST_TOTAL,
                            producer__isnull=True,
                            customer__isnull=True
                        ).order_by('-id').first()
                        previous_latest_total_id = previous_latest_total.id if previous_latest_total is not None else 0
                        return render_response(request, 'repanier/confirm_admin_bank_movement.html', {
                            'title': _("Please make the following payments, whose bank movements have been generated"),
                            'action': 'generate_invoices',
                            'permanence': permanence,
                            'queryset': BankAccount.objects.filter(
                                    id__gt=previous_latest_total_id,
                                    producer__isnull=False,
                                    producer__represent_this_buyinggroup=False,
                                    customer__isnull=True
                                ).order_by(
                                    'producer',
                                    '-operation_date',
                                    '-id'),
                            "app_label": app_label,
                            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                        })
        elif 'cancel' not in request.POST and 'done' not in request.POST:
            opts = self.model._meta
            app_label = opts.app_label
            permanence = queryset[:1][0]
            previous_permanence_not_invoiced = Permanence.objects.filter(
                status=PERMANENCE_SEND,
                permanence_date__lt=permanence.permanence_date).order_by("permanence_date").first()
            if previous_permanence_not_invoiced is not None:
                user_message = _("You must first invoice the %(permanence)s.") % {'permanence': previous_permanence_not_invoiced}
                user_message_level = messages.WARNING
            else:
                return render_response(request, 'repanier/confirm_admin_invoice.html', {
                    'title': _("Please, confirm the action : generate the invoices"),
                    'action': 'generate_invoices',
                    'permanence': permanence,
                    'queryset': Producer.objects.filter(
                        Q(purchase__permanence=permanence.id) | Q(is_active=True, balance__gt=0) | Q(is_active=True,
                             balance__lt=0)).values('id', 'short_profile_name').distinct(),
                    "app_label": app_label,
                    'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                })
        elif 'done' in request.POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
        self.message_user(request, user_message, user_message_level)
        return None

    generate_invoices.short_description = _('generate invoices')

    def archive(self, request, queryset):
        permanence = queryset[:1][0]
        producers_qs = Producer.objects.all()
        permanence = Permanence.objects.filter(id=permanence.id).order_by().first()
        user_message, user_message_level = task_invoice.admin_generate(request,
           producers_to_be_paid_set=producers_qs,
           permanence=permanence)
        self.message_user(request, user_message, user_message_level)
        return None

    archive.short_description = _('archive')

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

    def cancel_archive(self, request, queryset):
        user_message, user_message_level = task_invoice.admin_cancel(request, queryset)
        self.message_user(request, user_message, user_message_level)
        return None

    cancel_archive.short_description = _('cancel archiving')

    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super(PermanenceDoneAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if not RepanierSettings.invoice:
            del actions['export_xlsx']
            del actions['import_xlsx']
            del actions['generate_invoices']
            del actions['preview_invoices']
            del actions['send_invoices']
            del actions['cancel_invoices']
        else:
            del actions['archive']
            del actions['cancel_archive']

        if not actions:
            try:
                self.list_display.remove('action_checkbox')
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def get_queryset(self, request):
        qs = super(PermanenceDoneAdmin, self).get_queryset(request)
        return qs.filter(status__gte=PERMANENCE_SEND)

    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
            Purchase.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceDoneAdmin, self).save_model(
            request, permanence, form, change)

    def save_related(self, request, form, formsets, change):
        super(PermanenceDoneAdmin, self).save_related(request, form, formsets, change)

admin.site.register(PermanenceDone, PermanenceDoneAdmin)


# --------------------------------------------------------------

class OfferItemClosedAdmin(admin.ModelAdmin):
    list_display = ('department_for_customer', 'producer', 'get_long_name', 'stock',
                    'get_HTML_producer_qty_stock_invoiced', 'add_2_stock')
    list_display_links = ('get_long_name',)
    list_editable = ('stock', 'add_2_stock')
    search_fields = ('translations__long_name',)
    list_per_page = 13
    list_max_show_all = 13
    ordering = ('permanence', 'translations__order_sort_order')
    fields = (
        ('permanence', 'department_for_customer', 'product'),
        ('stock', 'get_HTML_producer_qty_stock_invoiced', 'add_2_stock',)
    )
    readonly_fields = ('get_HTML_producer_qty_stock_invoiced',)
    list_filter = (OfferItemSendFilter,)

    def get_queryset(self, request):
        queryset = super(OfferItemClosedAdmin, self).get_queryset(request)\
            .filter(translations__language_code=translation.get_language())\
            .distinct()
            # .distinct("id", "translations__order_sort_order")
        return queryset

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        form = super(OfferItemClosedAdmin, self).get_form(request, obj, **kwargs)
        permanence_field = form.base_fields["permanence"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.empty_label = None
        department_for_customer_field.empty_label = None
        product_field.empty_label = None

        if obj is not None:
            permanence_field.queryset = Permanence.objects \
                .filter(id=obj.permanence_id)
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects \
                .filter(id=obj.department_for_customer_id)
            product_field.queryset = Product.objects \
                .filter(id=obj.product_id)
        else:
            permanence_field.queryset = Permanence.objects.none()
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.none()
            product_field.queryset = Product.objects.none()
        return form

    def get_actions(self, request):
        actions = super(OfferItemClosedAdmin, self).get_actions(request)
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

admin.site.register(OfferItemClosed, OfferItemClosedAdmin)

# --------------------------------------------------------


class OfferItemPurchaseSendForm(forms.ModelForm):

    previous_purchase_price = forms.DecimalField(
        label=_("purchase price"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)
    previous_selling_price = forms.DecimalField(
        label=_("selling price"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)

    def __init__(self, *args, **kwargs):
        super(OfferItemPurchaseSendForm, self).__init__(*args, **kwargs)
        if self.instance.id is not None:
            self.fields["previous_purchase_price"].initial = self.instance.purchase_price
            self.fields["previous_selling_price"].initial = self.instance.selling_price

    class Meta:
        model = PurchaseSendForUpdate
        fields = "__all__"


class OfferItemPurchaseSendInline(ForeignKeyCacheMixin, admin.TabularInline):
    form = OfferItemPurchaseSendForm
    model = PurchaseSendForUpdate
    fields = ['customer', 'quantity_invoiced',
              'purchase_price', 'comment']
    extra = 0
    parent_object = None

    def get_readonly_fields(self, request, obj=None):
        self.parent_object = obj
        if obj.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            return []
        else:
            return ['purchase_price',]

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(is_active=True)
        return super(OfferItemPurchaseSendInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class OfferItemSendDataForm(forms.ModelForm):

    offer_purchase_price = forms.DecimalField(
        label=_("producer amount invoiced"), max_digits=8, decimal_places=2, required=False, initial=0)
    rule_of_3 = forms.BooleanField(
        label=_("apply rule of three"), required=False, initial=False)

    def __init__(self, *args, **kwargs):
        super(OfferItemSendDataForm, self).__init__(*args, **kwargs)
        offer_item = self.instance
        if offer_item.id is not None:
            qty, stock  = offer_item.get_producer_qty_stock_invoiced()
            self.fields["offer_purchase_price"].initial = ((offer_item.producer_unit_price +
                offer_item.unit_deposit) * (qty)).quantize(TWO_DECIMALS)
            # if offer_item.wrapped or offer_item.order_unit not in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            #     self.fields["offer_purchase_price"].widget.attrs['readonly'] = True
            #     self.fields["rule_of_3"].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super(OfferItemSendDataForm, self).clean()
        rule_of_3 = self.cleaned_data["rule_of_3"]
        total_purchase_with_tax = self.cleaned_data["offer_purchase_price"]
        if total_purchase_with_tax < DECIMAL_ZERO:
            if rule_of_3:
                self.add_error('offer_purchase_price', _('The rule of 3 is not applicable when the total_purchase_with_tax is negative'))
        if "stock" in self.cleaned_data:
            stock = self.cleaned_data["stock"]
            if stock < DECIMAL_ZERO:
                self.add_error('stock', _('The stock may not be negative'))
            if stock != DECIMAL_ZERO:
                if rule_of_3:
                    self.add_error('rule_of_3', _('The rule of 3 is not applicable when there is a stock'))
        return cleaned_data


class OfferItemSendAdmin(admin.ModelAdmin):
    form = OfferItemSendDataForm
    list_per_page = 17
    list_max_show_all = 17
    inlines = [OfferItemPurchaseSendInline]
    list_display = ('department_for_customer', 'producer', 'get_long_name', 'get_HTML_producer_qty_stock_invoiced',
                    'get_HTML_producer_price_purchased')
    list_display_links = ('get_long_name',)
    search_fields = ('translations__long_name',)
    ordering = ('translations__order_sort_order',)
    list_filter = (OfferItemSendFilter,)

    def get_queryset(self, request):
        queryset = super(OfferItemSendAdmin, self).get_queryset(request)\
            .filter(translations__language_code=translation.get_language())\
            .distinct()
        return queryset

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.manage_stock:
                return ('producer_unit_price', 'customer_unit_price', 'unit_deposit',
                       'get_HTML_producer_qty_stock_invoiced',
                       'vat_level', 'stock')
        return ('producer_unit_price', 'customer_unit_price', 'unit_deposit',
                       'get_HTML_producer_qty_stock_invoiced',
                       'vat_level')

    def get_form(self, request, obj=None, **kwargs):
        if not obj.wrapped and obj.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            if obj.manage_stock:
                self.fields = (
                    ('permanence', 'department_for_customer', 'product', 'vat_level',),
                    ('producer_unit_price', 'customer_unit_price', 'unit_deposit',),
                    ('stock', 'add_2_stock', 'get_HTML_producer_qty_stock_invoiced', 'offer_purchase_price', 'rule_of_3',)
                )
            else:
                self.fields = (
                    ('permanence', 'department_for_customer', 'product', 'vat_level',),
                    ('producer_unit_price', 'customer_unit_price', 'unit_deposit',),
                    ('offer_purchase_price', 'rule_of_3',)
                )
        else:
            if obj.manage_stock:
                self.fields = (
                    ('permanence', 'department_for_customer', 'product', 'vat_level',),
                    ('producer_unit_price', 'customer_unit_price', 'unit_deposit',),
                    ('stock', 'add_2_stock', 'get_HTML_producer_qty_stock_invoiced', 'offer_purchase_price',)
                )
            else:
                self.fields = (
                    ('permanence', 'department_for_customer', 'product', 'vat_level',),
                    ('producer_unit_price', 'customer_unit_price', 'unit_deposit',),
                    ('offer_purchase_price',)
                )

        form = super(OfferItemSendAdmin, self).get_form(request, obj, **kwargs)

        permanence_field = form.base_fields["permanence"]
        department_for_customer_field = form.base_fields["department_for_customer"]
        product_field = form.base_fields["product"]

        permanence_field.widget.can_add_related = False
        department_for_customer_field.widget.can_add_related = False
        product_field.widget.can_add_related = False
        permanence_field.empty_label = None
        department_for_customer_field.empty_label = None
        product_field.empty_label = None

        if obj is not None:
            permanence_field.queryset = Permanence.objects \
                .filter(id=obj.permanence_id)
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects \
                .filter(id=obj.department_for_customer_id)
            product_field.queryset = Product.objects \
                .filter(id=obj.product_id)
        else:
            permanence_field.queryset = Permanence.objects.none()
            department_for_customer_field.queryset = LUT_DepartmentForCustomer.objects.none()
            product_field.queryset = Product.objects.none()
        return form

    def get_actions(self, request):
        actions = super(OfferItemSendAdmin, self).get_actions(request)
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

    def save_model(self, request, offer_item, form, change):
        super(OfferItemSendAdmin, self).save_model(
            request, offer_item, form, change)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, 'new_objects'): formset.new_objects = []
            if not hasattr(formset, 'changed_objects'): formset.changed_objects = []
            if not hasattr(formset, 'deleted_objects'): formset.deleted_objects = []
        offer_item = form.instance
        save_purchase = True
        formset = formsets[0]
        for purchase_form in formset:
            customer = purchase_form.cleaned_data["customer"]
            purchase=purchase_form.instance
            if purchase.id is None:
                if offer_item.product.vat_level in [VAT_200, VAT_300] \
                    and customer.vat_id is not None \
                    and len(customer.vat_id) > 0:
                    is_compensation = True
                else:
                    is_compensation = False
                purchase = purchase_form.instance = PurchaseSendForUpdate.objects.create(
                    permanence_id=offer_item.permanence_id,
                    permanence_date=offer_item.permanence.permanence_date,
                    offer_item_id=offer_item.id,
                    producer_id=offer_item.producer_id,
                    customer_id=customer.id,
                    quantity_invoiced=DECIMAL_ZERO,
                    invoiced_price_with_compensation=is_compensation,
                    comment=purchase_form.cleaned_data['comment']
                )
            purchase.quantity_invoiced = purchase_form.cleaned_data['quantity_invoiced'].quantize(FOUR_DECIMALS) or DECIMAL_ZERO
            if offer_item.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
                purchase_price = purchase.purchase_price.quantize(TWO_DECIMALS) or DECIMAL_ZERO
                previous_purchase_price = purchase_form.fields['previous_purchase_price'].initial.quantize(TWO_DECIMALS) or DECIMAL_ZERO
            else:
                purchase_price = previous_purchase_price = DECIMAL_ZERO
            if purchase_price != previous_purchase_price:
                purchase.purchase_price = purchase_price
                if offer_item.producer_unit_price != DECIMAL_ZERO:
                    purchase.quantity_invoiced = (purchase_price / offer_item.producer_unit_price)\
                        .quantize(FOUR_DECIMALS)
                else:
                    purchase.quantity_invoiced = DECIMAL_ZERO
            else:
                purchase.purchase_price = (purchase.quantity_invoiced * offer_item.producer_unit_price)\
                    .quantize(TWO_DECIMALS)

        if not offer_item.wrapped and offer_item.order_unit in [PRODUCT_ORDER_UNIT_KG, PRODUCT_ORDER_UNIT_PC_KG]:
            rule_of_3 = form.cleaned_data['rule_of_3']
            if rule_of_3:
                rule_of_3_target = form.cleaned_data['offer_purchase_price'].quantize(TWO_DECIMALS)
                rule_of_3_source = DECIMAL_ZERO
                max_purchase_counter = 0
                for purchase_form in formset:
                    rule_of_3_source += purchase_form.instance.purchase_price
                    max_purchase_counter += 1
                if rule_of_3_target is not None and rule_of_3_target != rule_of_3_source:
                    if rule_of_3_source != DECIMAL_ZERO:
                        ratio = rule_of_3_target / rule_of_3_source
                    else:
                        if rule_of_3_target == DECIMAL_ZERO:
                            ratio = DECIMAL_ZERO
                        else:
                            ratio = DECIMAL_ONE
                    if ratio != DECIMAL_ONE:
                        adjusted_invoice = DECIMAL_ZERO
                        save_purchase = False
                        for i, purchase_form in enumerate(formsets[0], start=1):
                            purchase = purchase_form.instance
                            if i == max_purchase_counter:
                                delta = (rule_of_3_target - adjusted_invoice).quantize(TWO_DECIMALS)
                                if offer_item.producer_unit_price != DECIMAL_ZERO:
                                    purchase.quantity_invoiced = (delta / offer_item.producer_unit_price).quantize(FOUR_DECIMALS)
                                else:
                                    purchase.quantity_invoiced = DECIMAL_ZERO
                            else:
                                purchase.quantity_invoiced = (purchase.quantity_invoiced * ratio).quantize(FOUR_DECIMALS)
                                adjusted_invoice += (purchase.quantity_invoiced * offer_item.producer_unit_price).quantize(TWO_DECIMALS)
                            purchase.save()
        if save_purchase:
            for purchase_form in formset:
                if purchase_form.has_changed():
                    purchase_form.instance.save()

admin.site.register(OfferItemSend, OfferItemSendAdmin)

# --------------------------------------------------------

class CustomerPurchaseSendForm(forms.ModelForm):

    previous_purchase_price = forms.DecimalField(
        label=_("purchase price"), max_digits=8, decimal_places=2, required=False, initial=DECIMAL_ZERO)

    def __init__(self, *args, **kwargs):
        super(CustomerPurchaseSendForm, self).__init__(*args, **kwargs)
        if self.instance.id is not None:
            self.fields["previous_purchase_price"].initial = self.instance.purchase_price


class CustomerPurchaseSendInline(ForeignKeyCacheMixin, admin.TabularInline):
    form = CustomerPurchaseSendForm
    model = PurchaseSendForUpdate
    fields = ['offer_item', 'quantity_invoiced',
              'get_HTML_producer_unit_price',
              'get_HTML_unit_deposit',
              'purchase_price', 'comment']
    readonly_fields = ['get_HTML_producer_unit_price', 'get_HTML_unit_deposit',]
    extra = 0
    parent_object = None

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super(CustomerPurchaseSendInline, self).get_queryset(request)\
            .filter(offer_item__translations__language_code=translation.get_language())\
            .order_by("offer_item__translations__order_sort_order")\
            .distinct()
        return queryset


    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super(CustomerPurchaseSendInline, self).get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "offer_item":
            kwargs["queryset"] = OfferItemClosed.objects.filter(
                producer_id=self.parent_object.producer_id,
                permanence_id=self.parent_object.permanence_id,
                is_active=True,
                translations__language_code=translation.get_language()
                ).order_by("translations__order_sort_order",).distinct()
        return super(CustomerPurchaseSendInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class CustomerSendDataForm(forms.ModelForm):

    offer_purchase_price = forms.DecimalField(
        label=_("producer amount invoiced"), max_digits=8, decimal_places=2, required=False, initial=0)
    rule_of_3 = forms.BooleanField(
        label=_("apply rule of three"), required=False, initial=False)

    def __init__(self, *args, **kwargs):
        super(CustomerSendDataForm, self).__init__(*args, **kwargs)
        customer_producer_invoice = self.instance
        self.fields["offer_purchase_price"].initial = customer_producer_invoice.total_purchase_with_tax


class CustomerSendAdmin(admin.ModelAdmin):
    form = CustomerSendDataForm
    fields = (
        ('permanence', 'customer', 'producer',),
        ('offer_purchase_price', 'rule_of_3',)
    )
    list_per_page = 17
    list_max_show_all = 17
    inlines = [CustomerPurchaseSendInline]
    list_display = ('producer', 'customer', 'get_HTML_producer_price_purchased')
    list_display_links = ('customer',)
    search_fields = ('customer__short_basket_name',)
    ordering = ('customer',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(CustomerSendAdmin, self).get_form(request, obj, **kwargs)

        permanence_field = form.base_fields["permanence"]
        customer_field = form.base_fields["customer"]
        producer_field = form.base_fields["producer"]

        permanence_field.widget.can_add_related = False
        customer_field.widget.can_add_related = False
        producer_field.widget.can_add_related = False
        permanence_field.empty_label = None
        customer_field.empty_label = None
        producer_field.empty_label = None

        if obj is not None:
            permanence_field.queryset = Permanence.objects \
                .filter(id=obj.permanence_id)
            customer_field.queryset = Customer.objects \
                .filter(id=obj.customer_id)
            producer_field.queryset = Producer.objects \
                .filter(id=obj.producer_id)
        else:
            permanence_field.queryset = Permanence.objects.none()
            customer_field.queryset = Customer.objects.none()
            producer_field.queryset = Producer.objects.none()
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(CustomerSendAdmin, self).get_actions(request)
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

    def save_model(self, request, customer_producer_invoice, form, change):
        super(CustomerSendAdmin, self).save_model(
            request, customer_producer_invoice, form, change)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            # option.py -> construct_change_message doesn't test the presence of those array not created at form initialisation...
            if not hasattr(formset, 'new_objects'): formset.new_objects = []
            if not hasattr(formset, 'changed_objects'): formset.changed_objects = []
            if not hasattr(formset, 'deleted_objects'): formset.deleted_objects = []
        customer_producer_invoice = form.instance
        customer = customer_producer_invoice.customer
        save_purchase = True
        formset = formsets[0]
        for purchase_form in formset:
            purchase=purchase_form.instance
            if purchase.id is None:
                offer_item = purchase.offer_item
                if offer_item.product.vat_level in [VAT_200, VAT_300] \
                    and customer.vat_id is not None \
                    and len(customer.vat_id) > 0:
                    is_compensation = True
                else:
                    is_compensation = False
                purchase = purchase_form.instance = PurchaseSendForUpdate.objects.create(
                    permanence_id=offer_item.permanence_id,
                    permanence_date=offer_item.permanence.permanence_date,
                    offer_item_id=offer_item.id,
                    producer_id=offer_item.producer_id,
                    customer_id=customer.id,
                    quantity_invoiced=DECIMAL_ZERO,
                    invoiced_price_with_compensation=is_compensation,
                    comment=purchase_form.cleaned_data['comment']
                )
            purchase_price = purchase_form.cleaned_data['purchase_price'].quantize(TWO_DECIMALS) or DECIMAL_ZERO
            previous_purchase_price = purchase_form.fields['previous_purchase_price'].initial.quantize(TWO_DECIMALS) or DECIMAL_ZERO
            if purchase_price != previous_purchase_price:
                purchase.purchase_price = purchase_price
                if purchase.get_producer_unit_price() != DECIMAL_ZERO:
                    purchase.quantity_invoiced = (purchase_price / purchase.get_producer_unit_price())\
                        .quantize(FOUR_DECIMALS)
                else:
                    purchase.quantity_invoiced = DECIMAL_ZERO
        rule_of_3 = form.cleaned_data['rule_of_3']
        if rule_of_3:
            rule_of_3_target = form.cleaned_data['offer_purchase_price'].quantize(TWO_DECIMALS)
            rule_of_3_source = DECIMAL_ZERO
            max_purchase_counter = 0
            for purchase_form in formset:
                rule_of_3_source += purchase_form.instance.purchase_price
                max_purchase_counter += 1
            if rule_of_3_target is not None and rule_of_3_target != rule_of_3_source:
                if rule_of_3_source != DECIMAL_ZERO:
                    ratio = rule_of_3_target / rule_of_3_source
                else:
                    if rule_of_3_target == DECIMAL_ZERO:
                        ratio = DECIMAL_ZERO
                    else:
                        ratio = DECIMAL_ONE
                if ratio != DECIMAL_ONE:
                    adjusted_invoice = DECIMAL_ZERO
                    save_purchase = False
                    for i, purchase_form in enumerate(formsets[0], start=1):
                        purchase = purchase_form.instance
                        if i == max_purchase_counter:
                            delta = (rule_of_3_target - adjusted_invoice).quantize(TWO_DECIMALS)
                            if purchase.get_producer_unit_price() != DECIMAL_ZERO:
                                purchase.quantity_invoiced = (delta / purchase.get_producer_unit_price()).quantize(FOUR_DECIMALS)
                            else:
                                purchase.quantity_invoiced = DECIMAL_ZERO
                        else:
                            purchase.quantity_invoiced = (purchase.quantity_invoiced * ratio).quantize(FOUR_DECIMALS)
                            adjusted_invoice += (purchase.quantity_invoiced * purchase.get_producer_unit_price()).quantize(TWO_DECIMALS)
                        purchase.save()
        if save_purchase:
            for purchase_form in formset:
                if purchase_form.has_changed():
                    purchase_form.instance.save()

admin.site.register(CustomerSend, CustomerSendAdmin)


# Custom Purchase
class PurchaseWithProductForm(forms.ModelForm):
    product = forms.ChoiceField(label=_("product"))

    def __init__(self, *args, **kwargs):
        super(PurchaseWithProductForm, self).__init__(*args, **kwargs)
        if "quantity_invoiced" in self.fields:
            purchase = self.instance
            self.fields["quantity_invoiced"].initial = purchase.quantity_invoiced

    def clean_product(self):
        product_id = sint(self.cleaned_data.get("product"))
        if product_id < 0:
            self.add_error(
                'product',
                _("Please select first a producer in the filter of previous screen")
            )
        else:
            permanence = self.cleaned_data.get("permanence")
            customer = self.cleaned_data.get("customer")
            purchase = Purchase.objects.filter(
                permanence_id=permanence.id, customer_id=customer.id,
                offer_item__product_id=product_id, offer_item__permanence_id=permanence.id
            ).order_by().only("id").first()
            if purchase is not None and self.instance is not None:
                self.instance.id = purchase.id
        return product_id

    def clean(self):
        cleaned_data = super(PurchaseWithProductForm, self).clean()
        # self._validate_unique = False is required to avoid
        # django.db.models.fields.FieldDoesNotExist:
        # PurchaseOpenedOrClosed has no field named 'product'
        self._validate_unique = False
        return cleaned_data

    class Meta:
        model = Purchase
        fields = "__all__"


class PurchaseWithProductAdmin(admin.ModelAdmin):
    form = PurchaseWithProductForm
    list_display = [
        'permanence',
        'customer',
        'get_department_for_customer',
        'offer_item',
        'get_quantity',
        'get_customer_unit_price',
        'get_unit_deposit',
        'selling_price',
        'comment',
    ]
    list_select_related = ('permanence', 'customer')
    list_per_page = 17
    list_max_show_all = 17
    ordering = ('-permanence_date', 'customer', 'producer', 'offer_item')
    date_hierarchy = 'permanence_date'
    list_filter = (
        PurchaseFilterByPermanence,
        PurchaseFilterByCustomerForThisPermanence,
        PurchaseFilterByProducerForThisPermanence)
    list_display_links = ('offer_item',)
    search_fields = ('offer_item__translations__long_name',)
    actions = []

    def __init__(self, model, admin_site):
        super(PurchaseWithProductAdmin, self).__init__(model, admin_site)
        self.q_previous_order = DECIMAL_ZERO

    def get_department_for_customer(self, obj):
        return obj.offer_item.department_for_customer

    get_department_for_customer.short_description = _("department_for_customer")

    def get_queryset(self, request):
        queryset = super(PurchaseWithProductAdmin, self).get_queryset(request)\
            .filter(
                permanence__status__in=self.permanence_status_list,
                offer_item__translations__language_code=translation.get_language()
            ).distinct()
        return queryset

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        form = super(PurchaseWithProductAdmin, self).get_form(request, obj, **kwargs)
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
            permanence_field = form.base_fields["permanence"]
            customer_field = form.base_fields["customer"]
            product_field = form.base_fields["product"]
            permanence_field.widget.can_add_related = False
            customer_field.widget.can_add_related = False
            product_field.widget.can_add_related = False

            if obj is not None:
                self.q_previous_order = obj.get_quantity()
                permanence_field.empty_label = None
                permanence_field.queryset = Permanence.objects \
                    .filter(id=obj.permanence_id)
                customer_field.empty_label = None
                customer_field.queryset = Customer.objects \
                    .filter(id=obj.customer_id)
                product_field.empty_label = None
                product_field.choices = [(o.id, str(o)) for o in Product.objects.filter(offeritem=obj.offer_item_id,
                                translations__language_code=translation.get_language()
                                ).order_by('translations__long_name')]
            else:
                self.q_previous_order = 0
                if permanence_id is not None:
                    permanence_field.empty_label = None
                    permanence_field.queryset = Permanence.objects \
                        .filter(id=permanence_id)
                else:
                    permanence_field.queryset = Permanence.objects \
                        .filter(status__in=self.permanence_status_list)
                if producer_id is not None:
                    product_field.choices = [(o.id, str(o)) for o in Product.objects
                        .filter(is_active=True,producer_id=producer_id,
                                translations__language_code=translation.get_language()
                                ).order_by('translations__long_name')]
                else:
                    product_field.choices = [
                        ('-1', _("Please select first a producer in the filter of previous screen"))]
                if customer_id is not None:
                    customer_field.empty_label = None
                    customer_field.queryset = Customer.objects.filter(id=customer_id, is_active=True, may_order=True)
                else:
                    customer_field.queryset = Customer.objects.filter(is_active=True, may_order=True)
        return form

    @transaction.atomic
    def save_model(self, request, purchase, form, change):
        offer_item = purchase.offer_item
        if offer_item is None:
            product_id = form.cleaned_data.get("product")
            queryset = OfferItem.objects.filter(permanence_id=purchase.permanence_id,
                                                  product_id=product_id).order_by()
            offer_item = queryset.first()
            if offer_item is None:
                OfferItem.objects.create(
                    permanence_id=purchase.permanence_id,
                    product_id=product_id,
                    is_active=True
                )
                clean_offer_item(purchase.permanence, queryset, reorder=False)
                offer_item = queryset.first()
            purchase.offer_item = offer_item
        if offer_item.limit_order_quantity_to_stock:
            offer_item = OfferItem.objects.select_for_update(nowait=True).get(id=purchase.offer_item_id)
            offer_item.stock += self.q_previous_order
            if purchase.quantity_ordered > offer_item.stock:
                # Limit to available qty
                purchase.quantity_ordered = offer_item.stock
            offer_item.stock -= purchase.quantity_ordered
            offer_item.save(update_fields=['stock'])
        if offer_item.vat_level in [VAT_200, VAT_300] and purchase.customer.vat_id is not None and len(
            purchase.customer.vat_id) > 0:
            purchase.invoiced_price_with_compensation = True
        else:
            purchase.invoiced_price_with_compensation = False
        purchase.producer = offer_item.producer
        purchase.permanence_date = purchase.permanence.permanence_date
        purchase.permanence.producers.add(offer_item.producer)
        purchase.save()

    def get_actions(self, request):
        actions = super(PurchaseWithProductAdmin, self).get_actions(request)
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


class PurchaseOpenedOrClosedAdmin(PurchaseWithProductAdmin):
    fields = (
        'permanence',
        'customer',
        'product',
        'quantity_ordered',
        'comment'
    )

    @property
    def permanence_status_list(self):
        return [PERMANENCE_OPENED, PERMANENCE_CLOSED]


admin.site.register(PurchaseOpenedOrClosedForUpdate, PurchaseOpenedOrClosedAdmin)


class PurchaseSendAdmin(PurchaseWithProductAdmin):
    fields = (
        'permanence',
        'customer',
        'product',
        'quantity_ordered',
        'quantity_invoiced',
        'comment'
    )
    readonly_fields = ('quantity_ordered',)

    @property
    def permanence_status_list(self):
        return [PERMANENCE_SEND]


admin.site.register(PurchaseSendForUpdate, PurchaseSendAdmin)


# Accounting
class BankAccountDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(BankAccountDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(BankAccountDataForm, self).clean()
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
                    self.add_error('customer', _('Either a customer or a producer must be given.'))
                    self.add_error('producer', _('Either a customer or a producer must be given.'))
            else:
                bank_account = BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL).order_by().first()
                if bank_account:
                    # You may only insert the first latest bank total at initialisation of the website
                    self.add_error('customer', _('Either a customer or a producer must be given.'))
                    self.add_error('producer', _('Either a customer or a producer must be given.'))
        if customer and producer:
            self.add_error('customer', _('Only one customer or one producer must be given.'))
            self.add_error('producer', _('Only one customer or one producer must be given.'))
        return cleaned_data

    class Meta:
        model = BankAccount
        fields = "__all__"


class BankAccountAdmin(admin.ModelAdmin):
    form = BankAccountDataForm
    fields = ('operation_date',
              ('producer', 'customer'), 'operation_comment', 'bank_amount_in',
              'bank_amount_out',
              ('customer_invoice', 'producer_invoice'),
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
            'customer_invoice', 'producer_invoice'
        ]
        if obj:
            if (obj.customer_invoice is not None or obj.producer_invoice is not None) or (
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
                customer_field = form.base_fields["customer"]
                customer_field.widget.can_add_related = False
                customer_field.empty_label = None
                customer_field.queryset = Customer.objects.filter(id=obj.customer_id)
            if obj.producer:
                producer_field = form.base_fields["producer"]
                producer_field.widget.can_add_related = False
                producer_field.empty_label = None
                producer_field.queryset = Producer.objects.filter(id=obj.producer_id)
        else:
            producer_field = form.base_fields["producer"]
            customer_field = form.base_fields["customer"]
            producer_field.widget.can_add_related = False
            customer_field.widget.can_add_related = False
            producer_field.queryset = Producer.objects.filter(represent_this_buyinggroup=False,
                                                              is_active=True).order_by(
                "short_profile_name")
            # customer.queryset = Customer.objects.filter(represent_this_buyinggroup=False, is_active=True).order_by(
            #     "short_basket_name")
            customer_field.queryset = Customer.objects.filter(is_active=True).order_by(
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
        if not change:
            # create
            if bank_account.producer is None and bank_account.customer is None:
                # You may only insert the first latest bank total at initialisation of the website
                bank_account.operation_status = BANK_LATEST_TOTAL
        super(BankAccountAdmin, self).save_model(request, bank_account, form, change)


admin.site.register(BankAccount, BankAccountAdmin)