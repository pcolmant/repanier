# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.const import COORDINATION_GROUP, EMPTY_STRING
from repanier.models.configuration import Configuration
from repanier.models.producer import Producer
from repanier.tools import send_test_email


class ConfigurationDataForm(TranslatableModelForm):
    home_site = forms.URLField(
        label=_("home site"),
        required=False,
        widget=forms.URLInput(attrs={'style': "width:100% !important"}))
    group_label = forms.CharField(
        label=_("group label"),
        required=False,
        widget=forms.TextInput(attrs={'style': "width:100% !important"}))
    email_host_user = forms.CharField(
        label=_("email host user"),
        help_text=_("For @gmail.com : username@gmail.com"),
        required=False,
        widget=forms.EmailInput(attrs={'style': "width:100% !important"})
    )
    email_host_password = forms.CharField(
        label=_("email host password"),
        help_text=_(
            "For @gmail.com, you must generate an application password, see: https://security.google.com/settings/security/apppasswords"),
        required=False,
        widget=forms.PasswordInput(attrs={'style': "width:100% !important"}))
    sms_gateway_mail = forms.CharField(
        label=_("sms gateway email"),
        help_text=_(
            "To actually send sms, use for e.g. on a GSM : https://play.google.com/store/apps/details?id=eu.apksoft.android.smsgateway"),
        required=False,
        widget=forms.EmailInput(attrs={'style': "width:50% !important"}))

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        send_order_mail_to_customer = self.cleaned_data["send_order_mail_to_customer"]
        send_abstract_order_mail_to_customer = self.cleaned_data["send_abstract_order_mail_to_customer"]
        if send_abstract_order_mail_to_customer and not send_order_mail_to_customer:
            self.add_error(
                'send_abstract_order_mail_to_customer',
                _('The abstract can only be send if the order is also send to customer'))
        send_order_mail_to_producer = self.cleaned_data["send_order_mail_to_producer"]
        send_abstract_order_mail_to_producer = self.cleaned_data.get("send_abstract_order_mail_to_producer", EMPTY_STRING)
        if send_abstract_order_mail_to_producer and not send_order_mail_to_producer:
            self.add_error(
                'send_abstract_order_mail_to_customer',
                _('The abstract can only be send if the order is also send to producer'))
        if not settings.DJANGO_SETTINGS_DEMO:
            email_is_custom = self.cleaned_data["email_is_custom"]
            if email_is_custom:
                email_host_password = self.cleaned_data["email_host_password"]
                # Send test email
                if not email_host_password:
                    email_host_password = self.instance.previous_email_host_password
                email_host = self.cleaned_data["email_host"]
                email_port = self.cleaned_data["email_port"]
                email_use_tls = self.cleaned_data["email_use_tls"]
                email_host_user = self.cleaned_data["email_host_user"]
                email_send = send_test_email(
                    host=email_host,
                    port=email_port,
                    host_user=email_host_user,
                    host_password=email_host_password,
                    use_tls=email_use_tls
                )
                if not email_send:
                    self.add_error(
                        'email_is_custom',
                        _('Repanier tried to send a test email without success.'))
                    self.instance.email_is_custom = False

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
        if request.user.is_superuser or request.user.groups.filter(name=COORDINATION_GROUP).exists():
            return True
        return False

    def get_fieldsets(self, *args, **kwargs):
        fields = [
            ('group_name', 'name'),
            ('bank_account', 'max_week_wo_participation'),
            ('membership_fee', 'membership_fee_duration'),
            'display_anonymous_order_form',
        ]
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields += [
                'display_producer_on_order_form',
                'customers_must_confirm_orders',
                'test_mode',
            ]
        fieldsets = [
            (None, {
                'fields': fields,
            }),
        ]
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
            if Producer.objects.filter(producer_pre_opening=True).order_by('?').only('id').exists():
                fieldsets += [
                    (_('Pre-opening mails'), {
                        'classes': ('collapse',),
                        'fields' :
                            (
                                'offer_producer_mail',
                            ),
                    }),
                ]
        fieldsets += [
            (_('Opening mails'), {
                'classes': ('collapse',),
                'fields' :
                    (
                        'send_opening_mail_to_customer', 'offer_customer_mail',
                    ),
            }),
            ]
        if settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fieldsets += [
                (_('Ordering mails'), {
                    'classes': ('collapse',),
                    'fields' :
                        (
                            'send_order_mail_to_customer', 'send_abstract_order_mail_to_customer',
                            'order_customer_mail',
                            'send_order_mail_to_producer', 'order_producer_mail',
                            'send_order_mail_to_board', 'order_staff_mail',
                        ),
                }),
            ]
        else:
            fieldsets += [
                (_('Ordering mails'), {
                    'classes': ('collapse',),
                    'fields' :
                        (
                            'send_order_mail_to_customer', 'send_abstract_order_mail_to_customer',
                            'order_customer_mail',
                            'send_cancel_order_mail_to_customer', 'cancel_order_customer_mail',
                            'send_order_mail_to_producer', 'send_abstract_order_mail_to_producer',
                            'order_producer_mail',
                            'send_order_mail_to_board', 'order_staff_mail',
                        ),
                }),
                (_('Invoicing mails'), {
                    'classes': ('collapse',),
                    'fields' :
                        (
                            'send_invoice_mail_to_customer', 'invoice_customer_mail',
                            'send_invoice_mail_to_producer', 'invoice_producer_mail',
                        ),
                }),
            ]
        if settings.DJANGO_SETTINGS_IS_MINIMALIST:
            fields = [
                'invoice',
                'how_to_register',
            ]
        else:
            fields = [
                'home_site',
                ('transport', 'min_transport'),
                'group_label',
                # 'page_break_on_customer_check',
                'close_wo_sending',
                'display_who_is_who',
                'invoice',
                ('currency', 'vat_id'),
                'sms_gateway_mail',
            ]

        fields += [
            'email_is_custom',
            ('email_host', 'email_port', 'email_use_tls'),
            ('email_host_user', 'email_host_password')
        ]
        fieldsets += [
            (_('Advanced options'), {
                'classes': ('collapse',),
                'fields' : fields,
            }),
        ]
        return fieldsets
