# -*- coding: utf-8
from django import forms
from django.conf import settings
from django.conf.urls import url
from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.const import EMPTY_STRING
from repanier.models.configuration import Configuration
from repanier.tools import send_test_email
from repanier.widget.button_test_mail_config import ButtonTestMailConfigWidget


class ConfigurationDataForm(TranslatableModelForm):
    home_site = forms.URLField(
        label=_("Home site"),
        required=False,
        widget=forms.URLInput(attrs={'style': "width:100% !important"}))
    send_test_mail_button = forms.CharField(label=EMPTY_STRING, widget=ButtonTestMailConfigWidget)
    group_label = forms.CharField(
        label=_("Label to mention on the invoices of the group"),
        required=False,
        widget=forms.TextInput(attrs={'style': "width:100% !important"}))
    email_host_user = forms.CharField(
        label=_("Email host user"),
        help_text=_("For @gmail.com : username@gmail.com"),
        required=False,
        widget=forms.EmailInput(attrs={'style': "width:100% !important"})
    )
    new_email_host_password = forms.CharField(
        label=_("Email host password"),
        help_text=_(
            "For @gmail.com, you must generate an application password, see: https://security.google.com/settings/security/apppasswords"),
        required=False,
        widget=forms.PasswordInput(attrs={'style': "width:100% !important"}))
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
            email_is_custom = self.cleaned_data["email_is_custom"]
            if email_is_custom:
                if new_email_host_password:
                    # Send test email

                    email_host = self.cleaned_data["email_host"]
                    email_port = self.cleaned_data["email_port"]
                    email_use_tls = self.cleaned_data["email_use_tls"]
                    email_host_user = self.cleaned_data["email_host_user"]
                    email_send = send_test_email(
                        host=email_host,
                        port=email_port,
                        host_user=email_host_user,
                        host_password=new_email_host_password,
                        use_tls=email_use_tls,
                        cc=(self.request.user.email,)
                    )
                    if not email_send:
                        self.add_error(
                            'email_is_custom',
                            _('Repanier tried to send a test email without success.'))
                        self.instance.email_is_custom = False
                        self.instance.email_host_password = new_email_host_password

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
        # nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one configuration record created at application start
        return False

    def has_change_permission(self, request, obj=None):
        # Only a coordinator has this permission
        user = request.user
        if user.is_coordinator:
            return True
        return False

    # def get_urls(self):
    #     urls = super(ConfigurationAdmin, self).get_urls()
    #     my_urls = [
    #         url(r'^test_mail_config/$', self.admin_site.admin_view(self.test_mail_config), name="test_mail_config"),
    #     ]
    #     return my_urls + urls
    #
    # def test_mail_config(self, request):
    #     redirect_to = reverse('admin:repanier_configuration_change', args=(1,))
    #     return HttpResponseRedirect(redirect_to)

    def get_fieldsets(self, *args, **kwargs):
        fields = [
            ('group_name', 'name'),
            ('bank_account', 'max_week_wo_participation'),
            ('membership_fee', 'membership_fee_duration'),
            'display_anonymous_order_form',
            'display_who_is_who',
            'how_to_register',
        ]
        if settings.REPANIER_SETTINGS_TEST_MODE:
            fields += [
                'test_mode',
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
            'email_is_custom',
            'send_test_mail_button',
            ('email_host', 'email_port', 'email_use_tls'),
            ('email_host_user', 'new_email_host_password')
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
