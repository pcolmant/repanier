# -*- coding: utf-8
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.const import ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP
from repanier.models import Permanence, Producer


class ConfigurationDataForm(TranslatableModelForm):
    def __init__(self, *args, **kwargs):
        super(ConfigurationDataForm, self).__init__(*args, **kwargs)

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
        send_abstract_order_mail_to_producer = self.cleaned_data["send_abstract_order_mail_to_producer"]
        if send_abstract_order_mail_to_producer and not send_order_mail_to_producer:
            self.add_error(
                'send_abstract_order_mail_to_customer',
                _('The abstract can only be send if the order is also send to producer'))


class ConfigurationAdmin(TranslatableAdmin):
    form = ConfigurationDataForm

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def get_fieldsets(self, *args, **kwargs):
        fieldsets = [
            (None, {
                'fields':
                    (('test_mode', 'group_name', 'name'),
                     'display_anonymous_order_form',
                     ('display_producer_on_order_form', 'max_week_wo_participation'),
                     'customers_must_confirm_orders',
                     ('bank_account', 'vat_id'),
                     ('membership_fee', 'membership_fee_duration')),
            }),
        ]
        if Producer.objects.filter(producer_pre_opening=True).order_by('?').only('id').exists():
            fieldsets += [
                (_('Pre-opening mails'), {
                    'classes': ('collapse',),
                    'fields' :
                        (
                            'offer_producer_mail_subject', 'offer_producer_mail',
                        ),
                }),
            ]
        fieldsets += [
            (_('Opening mails'), {
                'classes': ('collapse',),
                'fields' :
                    (
                        'send_opening_mail_to_customer', 'offer_customer_mail_subject', 'offer_customer_mail',
                    ),
            }),
            (_('Ordering mails'), {
                'classes': ('collapse',),
                'fields' :
                    (
                        'send_order_mail_to_customer', 'send_abstract_order_mail_to_customer', 'order_customer_mail_subject', 'order_customer_mail',
                        'send_cancel_order_mail_to_customer', 'cancel_order_customer_mail_subject', 'cancel_order_customer_mail',
                        'send_order_mail_to_producer', 'send_abstract_order_mail_to_producer', 'order_producer_mail_subject', 'order_producer_mail',
                        'send_order_mail_to_board', 'order_staff_mail_subject', 'order_staff_mail',
                    ),
            }),
            (_('Invoicing mails'), {
                'classes': ('collapse',),
                'fields' :
                    (
                        'send_invoice_mail_to_customer', 'invoice_customer_mail_subject', 'invoice_customer_mail',
                        'send_invoice_mail_to_producer', 'invoice_producer_mail_subject', 'invoice_producer_mail',
                    ),
            }),
            (_('Advanced options'), {
                'classes': ('collapse',),
                'fields' :
                    (
                        'home_site',
                        'transport',
                        'min_transport',
                        'group_label',
                        'page_break_on_customer_check',
                        'close_wo_sending',
                        'sms_gateway_mail',
                        ('currency', 'invoice',),
                    ),
            }),
        ]
        return fieldsets

    def get_readonly_fields(self, request, configuration=None):
        permanence = Permanence.objects.all().order_by('?')
        is_coordinator = request.user.is_superuser or request.user.is_staff

        if is_coordinator or permanence.first() is None:
            return []
        else:
            return ['bank_account']
