# -*- coding: utf-8
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.const import EMPTY_STRING
from repanier.models.configuration import Configuration
from repanier.widget.button_test_mail_config import ButtonTestMailConfigWidget


class ConfigurationDataForm(TranslatableModelForm):
    home_site = forms.URLField(
        label=_("Home site"),
        required=False,
        widget=forms.URLInput(attrs={'style': "width:100% !important"}))
    send_test_mail_button = forms.CharField(
        label=EMPTY_STRING, widget=ButtonTestMailConfigWidget,
        required=False
    )
    group_label = forms.CharField(
        label=_("Label to mention on the invoices of the group"),
        required=False,
        widget=forms.TextInput(attrs={'style': "width:100% !important"}))
    email_host_user = forms.CharField(
        label=_("Email host user"),
        initial=settings.DEFAULT_FROM_EMAIL,
        empty_value=settings.DEFAULT_FROM_EMAIL,
        help_text=settings.DEFAULT_FROM_EMAIL,
        required=False,
        # widget=forms.EmailInput(attrs={'style': "width:100% !important"})
    )
    new_email_host_password = forms.CharField(
        label=_("Email host password"),
        help_text=_(
            "For @gmail.com, you must generate an application password, see: https://security.google.com/settings/security/apppasswords"),
        required=False,
        # widget=forms.PasswordInput(attrs={'style': "width:100% !important"})
    )
    sms_gateway_mail = forms.CharField(
        label=_("Sms gateway email"),
        help_text=_(
            "To actually send sms, use for e.g. on a GSM : https://play.google.com/store/apps/details?id=eu.apksoft.android.smsgateway"),
        required=False,
        widget=forms.EmailInput(attrs={'style': "width:50% !important"}))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        # Voilà, now you can access request anywhere in your form methods by using self.request!
        super(ConfigurationDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if not settings.REPANIER_SETTINGS_DEMO:
            new_email_host_password = self.cleaned_data["new_email_host_password"]
            if not new_email_host_password:
                self.instance.email_host_password = self.instance.previous_email_host_password
            else:
                self.instance.email_host_password = new_email_host_password

    class Meta:
        model = Configuration
        fields = "__all__"


class ConfigurationAdmin(TranslatableAdmin):
    form = ConfigurationDataForm

    def has_delete_permission(self, request, obj=None):
        # Nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one configuration record created at application start
        return False

    def has_change_permission(self, request, obj=None):
        # Only a repanier_admin has this permission
        return request.user.is_repanier_admin

    def get_fieldsets(self, *args, **kwargs):
        fields = [
            ('group_name', 'name'),
            ('bank_account', 'max_week_wo_participation'),
            ('membership_fee', 'membership_fee_duration'),
            'display_anonymous_order_form',
            'display_who_is_who',
            'how_to_register',
        ]
        fieldsets = [
            (None, {
                'fields': fields,
            }),
        ]
        if settings.REPANIER_SETTINGS_PRE_OPENING:
            fieldsets += [
                (_('Pre-opening mails'), {
                    'classes': ('collapse',),
                    'fields':
                        (
                            'offer_producer_mail',
                        ),
                }),
            ]
        fieldsets += [
            (_('Opening mails'), {
                'classes': ('collapse',),
                'fields':
                    (
                        'offer_customer_mail',
                    ),
            }),
        ]
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            fieldsets += [
                (_('Ordering mails'), {
                    'classes': ('collapse',),
                    'fields':
                        (
                            'send_abstract_order_mail_to_customer',
                            'order_customer_mail',
                            'cancel_order_customer_mail',
                            'order_producer_mail',
                            'send_order_mail_to_board', 'order_staff_mail',
                        ),
                }),
            ]
        else:
            fieldsets += [
                (_('Ordering mails'), {
                    'classes': ('collapse',),
                    'fields':
                        (
                            'send_abstract_order_mail_to_customer',
                            'order_customer_mail',
                            'order_producer_mail',
                            'send_order_mail_to_board', 'order_staff_mail',
                        ),
                })
            ]
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            fieldsets += [
                (_('Invoicing mails'), {
                    'classes': ('collapse',),
                    'fields':
                        (
                            'send_invoice_mail_to_customer', 'invoice_customer_mail',
                            'send_invoice_mail_to_producer', 'invoice_producer_mail',
                        ),
                }),
            ]

        if not settings.REPANIER_SETTINGS_IS_MINIMALIST:
            fields = [
                'home_site',
                ('transport', 'min_transport'),
                'group_label',
                # 'page_break_on_customer_check',
                'xlsx_portrait',
                ('currency', 'vat_id'),
                'sms_gateway_mail',
            ]
            fieldsets += [
                (_('Advanced options'), {
                    'classes': ('collapse',),
                    'fields': fields,
                }),
            ]

        fields = [
            'email_host_user',
            'email_is_custom',
            'send_test_mail_button',
            'new_email_host_password',
            'email_host',
            'email_port',
            'email_use_tls'
        ]
        fieldsets += [
            (_('Advanced mail server configuration'), {
                'classes': ('collapse',),
                'fields': fields,
            }),
        ]

        return fieldsets

    def get_form(self, request, obj=None, **kwargs):

        AdminForm = super(ConfigurationAdmin, self).get_form(request, obj, **kwargs)

        class AdminFormWithRequest(AdminForm):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return AdminForm(*args, **kwargs)

        return AdminFormWithRequest
