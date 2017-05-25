# -*- coding: utf-8
from __future__ import unicode_literals

from collections import OrderedDict

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import XLS
from import_export.widgets import CharWidget

import repanier.apps
from repanier.admin.forms import ImportXlsxForm
from repanier.models import BoxContent
from repanier.const import *
from repanier.models import Permanence, Product, \
    Producer
from repanier.tools import producer_web_services_activated, \
    update_offer_item
from repanier.xlsx.widget import IdWidget, TwoDecimalsWidget, \
    DecimalBooleanWidget, TwoMoneysWidget, DateWidgetExcel
from repanier.xlsx.extended_formats import XLSX_OPENPYXL_1_8_6
from repanier.xlsx.views import import_xslx_view
from repanier.xlsx.xlsx_invoice import export_invoice
from repanier.xlsx.xlsx_product import export_customer_prices
from repanier.xlsx.xlsx_stock import handle_uploaded_stock, export_producer_stock

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl


class ProducerResource(resources.ModelResource):
    id = fields.Field(attribute='id', widget=IdWidget(), readonly=True)
    phone1 = fields.Field(attribute='phone1', default='1234', widget=CharWidget(), readonly=False)
    phone2 = fields.Field(attribute='phone2', widget=CharWidget(), readonly=False)
    price_list_multiplier = fields.Field(attribute='price_list_multiplier', default=DECIMAL_ONE,
                                         widget=TwoDecimalsWidget(), readonly=False)
    date_balance = fields.Field(attribute='get_admin_date_balance', widget=DateWidgetExcel(), readonly=True)
    balance = fields.Field(attribute='get_admin_balance', widget=TwoMoneysWidget(), readonly=True)
    invoice_by_basket = fields.Field(attribute='invoice_by_basket', default=False, widget=DecimalBooleanWidget(),
                                     readonly=False)
    manage_replenishment = fields.Field(attribute='manage_replenishment', default=False, widget=DecimalBooleanWidget(),
                                        readonly=False)
    manage_production = fields.Field(attribute='manage_production', default=False, widget=DecimalBooleanWidget(),
                                     readonly=False)
    sort_products_by_reference = fields.Field(attribute='sort_products_by_reference', default=False,
                                              widget=DecimalBooleanWidget(),
                                              readonly=False)
    is_resale_price_fixed = fields.Field(attribute='is_resale_price_fixed', default=False,
                                         widget=DecimalBooleanWidget(), readonly=False)
    represent_this_buyinggroup = fields.Field(attribute='represent_this_buyinggroup', widget=DecimalBooleanWidget(),
                                              readonly=True)
    is_active = fields.Field(attribute='is_active', widget=DecimalBooleanWidget(), readonly=True)
    reference_site = fields.Field(attribute='reference_site', readonly=True)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        producer_qs = Producer.objects.filter(short_profile_name=instance.short_profile_name).order_by('?')
        if instance.id is not None:
            producer_qs = producer_qs.exclude(id=instance.id)
        if producer_qs.exists():
            raise ValueError(
                _("The short_basket_name %s is already used by another producer.") % instance.short_profile_name)

    class Meta:
        model = Producer
        fields = (
            'id', 'short_profile_name', 'long_profile_name',
            'email', 'email2', 'email3', 'language', 'phone1', 'phone2',
            'fax', 'address', 'invoice_by_basket', 'manage_replenishment', 'manage_production',
            'sort_products_by_reference',
            'producer_pre_opening', 'producer_price_are_wo_vat',
            'price_list_multiplier', 'is_resale_price_fixed',
            'reference_site',
            'bank_account',
            'date_balance', 'balance', 'represent_this_buyinggroup', 'is_active'
        )
        export_order = fields
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


def create__producer_action(year):
    def action(modeladmin, request, producer_qs):
        # To the producer we speak of "payment".
        # This is the detail of the payment to the producer, i.e. received products
        wb = None
        for producer in producer_qs:
            wb = export_invoice(year=year, producer=producer, wb=wb, sheet_name=slugify(producer))
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                "%s %s" % (_('Payment'), year),
                repanier.apps.REPANIER_SETTINGS_GROUP_NAME
            )
            wb.save(response)
            return response
        return

    name = "export_producer_%d" % (year,)
    return (name, (action, name, _("Export purchases of %s") % (year,)))


class ProducerDataForm(forms.ModelForm):
    permanences = forms.ModelMultipleChoiceField(
        Permanence.objects.filter(status=PERMANENCE_PLANNED),
        widget=admin.widgets.FilteredSelectMultiple(repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME, False),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(ProducerDataForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['permanences'].initial = self.instance.permanence_set.all()

    def clean_price_list_multiplier(self):
        # Let the user delete the price list multiplier if he/she select is_resale_price_fixed
        price_list_multiplier = self.cleaned_data['price_list_multiplier']
        if price_list_multiplier is None:
            price_list_multiplier = DECIMAL_ONE
        elif price_list_multiplier < DECIMAL_ZERO:
            self.add_error(
                'price_list_multiplier',
                _('The price must be greater than or equal to zero.'))
        return price_list_multiplier

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if settings.DJANGO_SETTINGS_ENV != "dev":
            reference_site = self.cleaned_data["reference_site"]
            for allowed_host in settings.ALLOWED_HOSTS:
                if reference_site.endswith(allowed_host):
                    self.add_error(
                        'reference_site',
                        _("The reference site may not be your site."))
                    break
        producer_pre_opening = self.cleaned_data["producer_pre_opening"]
        manage_replenishment = self.cleaned_data["manage_replenishment"]
        manage_production = self.cleaned_data["manage_production"]
        invoice_by_basket = self.cleaned_data["invoice_by_basket"]
        is_resale_price_fixed = self.cleaned_data["is_resale_price_fixed"]
        price_list_multiplier = self.cleaned_data["price_list_multiplier"]
        if manage_replenishment and producer_pre_opening:
            # The producer set his offer -> no possibility to manage stock
            self.add_error('producer_pre_opening',
                           _("Either 'manage replenishment' or 'producer pre opening' may be set. Not both."))
            self.add_error('manage_replenishment',
                           _("Either 'manage replenishment' or 'producer pre opening' may be set. Not both."))
        if manage_replenishment and invoice_by_basket:
            # The group manage the replenishment -> no possibility for the producer to prepare basket
            self.add_error('invoice_by_basket',
                           _("Either 'manage replenishment' or 'invoice by basket' may be set. Not both."))
            self.add_error('manage_replenishment',
                           _("Either 'manage replenishment' or 'invoice by basket' may be set. Not both."))
        if invoice_by_basket and self.instance.id is not None:
            if BoxContent.objects.filter(product__producer_id=self.instance.id).exists():
                self.add_error('invoice_by_basket',
                               _("Some products of this producer are in a box. This implies that this producer cannot invoice by basket."))
        if is_resale_price_fixed and producer_pre_opening:
            # The producer set his price -> no possibility to fix the resale price
            self.add_error('producer_pre_opening',
                           _("Either 'is resale price fixed' or 'producer pre opening' may be set. Not both."))
            self.add_error('is_resale_price_fixed',
                           _("Either 'is resale price fixed' or 'producer pre opening' may be set. Not both."))
        if manage_replenishment and manage_production:
            self.add_error('manage_production',
                           _("Either 'manage replenishment' or 'manage production' may be set. Not both."))
            self.add_error('manage_replenishment',
                           _("Either 'manage replenishment' or 'manage production' may be set. Not both."))
        if is_resale_price_fixed and manage_production:
            self.add_error('manage_production',
                           _("Either 'is resale price fixed' or 'manage production' may be set. Not both."))
            self.add_error('is_resale_price_fixed',
                           _("Either 'is resale price fixed' or 'manage production' may be set. Not both."))
        if manage_production and price_list_multiplier != DECIMAL_ONE:
            self.add_error('manage_production',
                           _("The 'price list multiplier' must be set to 1 when 'manage production'."))
            self.add_error('price_list_multiplier',
                           _("The 'price list multiplier' must be set to 1 when 'manage production'."))
        if is_resale_price_fixed and price_list_multiplier != DECIMAL_ONE:
            # Important : For invoicing correctly
            self.add_error('price_list_multiplier',
                           _("The 'price list multiplier' must be set to 1 when 'fixed reseale price'."))
            self.add_error('is_resale_price_fixed',
                           _("The 'price list multiplier' must be set to 1 when 'fixed reseale price'."))
        bank_account = self.cleaned_data["bank_account"]
        if bank_account:
            other_bank_account = Producer.objects.filter(
                bank_account=bank_account
            ).order_by("?")
            if self.instance.id is not None:
                other_bank_account = other_bank_account.exclude(id=self.instance.id)
            if other_bank_account.exists():
                self.add_error('bank_account', _('This bank account already belongs to another producer.'))

    def save(self, *args, **kwargs):
        instance = super(ProducerDataForm, self).save(*args, **kwargs)
        if instance.id is not None:
            instance.permanence_set = Permanence.objects.filter(producers=instance.pk).exclude(
                status=PERMANENCE_PLANNED).order_by('?')
            instance.permanence_set.add(*self.cleaned_data['permanences'])
            # The previous save is called with "commit=False"
            # But we need to update the producer
            # to recalculate the products prices. So a call to self.instance.save() is required
            # self.instance.save()
            # for product in Product.objects.filter(producer_id=instance.id).order_by('?'):
            #     product.save()
            # update_offer_item(producer_id=instance.id)

        return instance


class ProducerAdmin(ImportExportMixin, admin.ModelAdmin):
    form = ProducerDataForm
    resource_class = ProducerResource
    search_fields = ('short_profile_name', 'email')
    list_per_page = 16
    list_max_show_all = 16
    list_filter = ('is_active', 'invoice_by_basket')
    actions = [
        'export_xlsx_customer_prices',
    ]
    # change_list_template = 'admin/producer_change_list.html'

    def has_delete_permission(self, request, producer=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            if producer is not None:
                if producer.represent_this_buyinggroup:
                    # I can't delete the producer representing the buying group
                    return False
            return True
        return False

    def has_add_permission(self, request):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP,
                          CONTRIBUTOR_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request)

    def get_urls(self):
        urls = super(ProducerAdmin, self).get_urls()
        my_urls = [
            url(r'^export_stock/$', self.export_xlsx_stock),
            url(r'^import_stock/$', self.import_xlsx_stock),
        ]
        return my_urls + urls

    def export_xlsx_customer_prices(self, request, producer_qs):
        wb = export_customer_prices(producer_qs=producer_qs, wb=None, producer_prices=False)
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}.xlsx".format(
                slugify(_("Products"))
            )
            wb.save(response)
            return response
        else:
            return

    export_xlsx_customer_prices.short_description = _(
        "Export products of selected producer(s) as XSLX file at customer's prices")

    def export_xlsx_stock(self, request):
        # return xlsx_stock.admin_export(self, Producer.objects.all())
        wb = export_producer_stock(producers=Producer.objects.filter(
            Q(manage_replenishment=True) | Q(manage_production=True)
        ).order_by("short_profile_name"), wb=None)
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}.xlsx".format(
                slugify(_("Current stock"))
            )
            wb.save(response)
            return response
        else:
            return

    export_xlsx_stock.short_description = _("Export stock to a xlsx file")

    def import_xlsx_stock(self, request):
        return import_xslx_view(
            self, admin, request, Producer.objects.all(), _("Import stock"), handle_uploaded_stock,
            action='import_xlsx_stock', form_klass=ImportXlsxForm)

    import_xlsx_stock.short_description = _("Import stock from a xlsx file")

    def get_actions(self, request):
        actions = super(ProducerAdmin, self).get_actions(request)
        this_year = timezone.now().year
        actions.update(OrderedDict(create__producer_action(y) for y in [this_year, this_year - 1, this_year - 2]))
        return actions

    def get_list_display(self, request):
        if repanier.apps.REPANIER_SETTINGS_INVOICE:
            return ('__str__', 'get_products', 'get_balance', 'phone1', 'email')
        else:
            return ('__str__', 'get_products', 'phone1', 'email')

    def get_fieldsets(self, request, producer=None):
        fields_basic = [
            ('short_profile_name', 'long_profile_name', 'language'),
            ('email', 'email2', 'email3'),
            ('phone1', 'phone2', 'fax'),
        ]
        if producer is not None:
            fields_basic += [
                'permanences',
                ('get_admin_balance', 'get_admin_date_balance'),
            ]
        if producer is None or not producer.represent_this_buyinggroup:
            fields_basic += [
                ('producer_price_are_wo_vat', 'is_active'),
            ]
        fields_advanced = [
            'bank_account',
            'vat_id',
            'is_resale_price_fixed',
            'price_list_multiplier',
            'minimum_order_value',
            'invoice_by_basket',
            'manage_replenishment',
            'manage_production',
            'sort_products_by_reference',
            'producer_pre_opening',
            'address',
            'memo',
            'reference_site',
            'web_services_activated',
        ]
        if producer is not None and producer.represent_this_buyinggroup:
            fields_advanced += [
                'represent_this_buyinggroup'
            ]
        fieldsets = (
            (None, {'fields': fields_basic}),
            (_('Advanced options'), {'classes': ('collapse',), 'fields': fields_advanced})
        )
        return fieldsets

    def get_readonly_fields(self, request, producer=None):
        if producer is not None:
            if producer.represent_this_buyinggroup:
                return ['web_services_activated', 'represent_this_buyinggroup', 'get_admin_date_balance',
                        'get_admin_balance']
            else:
                return ['web_services_activated', 'get_admin_date_balance',
                        'get_admin_balance']
        else:
            return ['web_services_activated']

    def save_model(self, request, producer, form, change):
        producer.web_services_activated, drop1, drop2 = producer_web_services_activated(producer.reference_site)
        super(ProducerAdmin, self).save_model(
            request, producer, form, change)

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLS, XLSX_OPENPYXL_1_8_6) if f().can_import()]

    class Media:
        js = ('js/export_import_stock.js',)
