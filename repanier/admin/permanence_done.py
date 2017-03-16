# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.contrib import admin
from django.core.checks import messages
from django.db.models import Q, F, Sum
from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.template import Context as TemplateContext, Template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.models import TranslationDoesNotExist

import repanier.apps
from repanier.admin.fkey_choice_cache_mixin import ForeignKeyCacheMixin
from repanier.admin.forms import InvoiceOrderForm, ProducerInvoicedFormSet, PermanenceInvoicedForm
from repanier.const import *
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.models import Customer, Purchase, Permanence, Producer, PermanenceBoard, LUT_PermanenceRole, BankAccount, ProducerInvoice, Configuration
from repanier.task import task_invoice
from repanier.tools import send_email_to_who, get_signature
from repanier.xlsx import xlsx_invoice, xlsx_purchase


class PermanenceBoardInline(ForeignKeyCacheMixin, admin.TabularInline):

    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ['permanence_role', 'customer']
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True, rght=F('lft') + 1).order_by("tree_id", "lft")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class PermanenceDoneAdmin(TranslatableAdmin):
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
    list_display = ('__str__', 'get_producers', 'get_customers', 'get_board', 'get_full_status_display')
    ordering = ('-permanence_date',)
    actions = [
        'export_xlsx',
        'import_xlsx',
        'generate_invoices',
        'cancel_invoices',
        'preview_invoices',
        'send_invoices',
        'archive',
        'cancel_archive',
    ]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def export_xlsx(self, request, queryset):
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_SEND:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        return xlsx_purchase.admin_export_permanence_by_producer(request, permanence)

    export_xlsx.short_description = _("Export orders prepared as XSLX file")

    def import_xlsx(self, request, queryset):
        permanence = queryset.first()
        if permanence is None or permanence.status != PERMANENCE_SEND:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        return xlsx_purchase.admin_import(self, admin, request, queryset, action ='import_xlsx')

    import_xlsx.short_description = _("Import orders prepared from a XLSX file")

    def preview_invoices(self, request, queryset):
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [PERMANENCE_DONE, PERMANENCE_ARCHIVED]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        return xlsx_invoice.admin_export(request, queryset)

    preview_invoices.short_description = _("Preview invoices before sending them by email")

    def generate_invoices(self, request, queryset):
        if 'done' in request.POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        elif 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_SEND:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        previous_permanence_not_invoiced = Permanence.objects.filter(
            status=PERMANENCE_SEND,
            permanence_date__lt=permanence.permanence_date).order_by("permanence_date").first()
        if previous_permanence_not_invoiced is not None:
            user_message = _("You must first invoice the %(permanence)s.") % {'permanence': previous_permanence_not_invoiced}
            user_message_level = messages.WARNING
            self.message_user(request, user_message, user_message_level)
            return None

        max_payment_date = timezone.now().date()
        bank_account = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL) \
            .only("operation_date").order_by("-id").first()
        if bank_account is not None:
            if bank_account.operation_date > max_payment_date:
                max_payment_date = bank_account.operation_date
            min_payment_date = bank_account.operation_date
        else:
            # This cas should never occur because of the first bank aoocunt record created at startup if none exists
            # via config.save() in apps.
            min_payment_date = timezone.now().date()

        if max_payment_date < min_payment_date:
            max_payment_date = min_payment_date
        if 'apply' in request.POST and admin.ACTION_CHECKBOX_NAME in request.POST:
            permanence_form = PermanenceInvoicedForm(request.POST)
            producer_invoiced_formset = ProducerInvoicedFormSet(request.POST)
            if permanence_form.is_valid() and producer_invoiced_formset.is_valid():
                payment_date = permanence_form.cleaned_data.get('payment_date')
                if payment_date < min_payment_date or payment_date > max_payment_date:
                    permanence_form.add_error(
                        'payment_date',
                        _('The payment date must be between %(min_payment_date)s and %(max_payment_date)s.') % {
                            'min_payment_date': min_payment_date.strftime(settings.DJANGO_SETTINGS_DATE),
                            'max_payment_date': max_payment_date.strftime(settings.DJANGO_SETTINGS_DATE)
                        }
                    )
                else:
                    Producer.objects.all().order_by('?').order_by('?').update(to_be_paid=False)
                    for producer_invoiced_form in producer_invoiced_formset:
                        if producer_invoiced_form.is_valid() and producer_invoiced_form.has_changed():
                            selected = producer_invoiced_form.cleaned_data.get('selected')
                            short_profile_name = producer_invoiced_form.cleaned_data.get('short_profile_name')
                            producer = Producer.objects.filter(short_profile_name=short_profile_name).order_by('?').first()
                            if selected:
                                producer.to_be_paid = True
                                producer.save(update_fields=['to_be_paid'])
                            producer_invoice = ProducerInvoice.objects.filter(
                                producer=producer.id,
                                permanence_id=permanence.id
                            ).order_by(
                                '?'
                            ).first()
                            producer_invoice.to_be_invoiced_balance = producer_invoiced_form.cleaned_data.get(
                                'to_be_invoiced_balance')
                            producer_invoice.invoice_reference = producer_invoiced_form.cleaned_data.get(
                                'invoice_reference')
                            if not producer_invoice.invoice_reference:
                                producer_invoice.invoice_reference = None
                            producer_invoice.save(update_fields=['to_be_invoiced_balance', 'invoice_reference'])

                    user_message, user_message_level = task_invoice.admin_generate(
                        request,
                        payment_date=payment_date,
                        permanence=permanence)
                    if user_message_level == messages.INFO:
                        previous_latest_total = BankAccount.objects.filter(
                            operation_status=BANK_NOT_LATEST_TOTAL,
                            producer__isnull=True,
                            customer__isnull=True
                        ).order_by('-id').first()
                        previous_latest_total_id = previous_latest_total.id if previous_latest_total is not None else 0
                        return render(request, 'repanier/confirm_admin_bank_movement.html', {
                            'sub_title': _("Please make the following payments, whose bank movements have been generated"),
                            'action': 'generate_invoices',
                            'permanence': permanence,
                            'bankaccounts': BankAccount.objects.filter(
                                id__gt=previous_latest_total_id,
                                producer__isnull=False,
                                producer__represent_this_buyinggroup=False,
                                customer__isnull=True,
                                operation_status=BANK_CALCULATED_INVOICE
                            ).order_by(
                                'producer',
                                '-operation_date',
                                '-id'
                            ),
                            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                        })
        else:
            Producer.objects.all().order_by('?').update(
                to_be_paid=False,
            )
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id,
            ).order_by('?').update(
                delta_vat=DECIMAL_ZERO,
                delta_deposit=DECIMAL_ZERO,
                delta_price_with_tax=DECIMAL_ZERO
            )
            for producer in Producer.objects.filter(
                Q(producerinvoice__permanence=permanence.id) |
                Q(is_active=True, balance__gt=0) |
                Q(is_active=True, balance__lt=0) |
                Q(is_active=True, represent_this_buyinggroup=True)
            ).order_by().distinct():
                producer_invoice = ProducerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    producer_id=producer.id
                ).order_by('?').first()
                if producer_invoice is None:
                    producer_invoice = ProducerInvoice.objects.create(
                        producer_id=producer.id,
                        permanence_id=permanence.id,
                        status=permanence.status
                    )
                if not producer.manage_production:
                    producer.to_be_paid = True
                    producer.save(update_fields=['to_be_paid'])
                    # We have already pay to much (look at the bank movements).
                    # So we do not need to pay anything
                    producer_invoice.calculated_invoiced_balance.amount = \
                        producer.get_calculated_invoiced_balance(permanence.id)
                else:
                    producer_invoice.calculated_invoiced_balance.amount = producer_invoice.total_price_with_tax.amount
                if permanence.highest_status == PERMANENCE_SEND:
                    # First time invoiced ? Yes : propose the calculated invoiced balance as to be invoiced balance
                    producer_invoice.to_be_invoiced_balance = producer_invoice.calculated_invoiced_balance
                    producer_invoice.save(update_fields=[
                        'calculated_invoiced_balance',
                        'to_be_invoiced_balance'
                    ])
                else:
                    producer_invoice.save(update_fields=[
                        'calculated_invoiced_balance'
                    ])

            permanence_form = PermanenceInvoicedForm(payment_date=max_payment_date)

            qs = ProducerInvoice.objects.filter(
                producer__to_be_paid=True,
                permanence_id=permanence.id
            ).order_by("producer")
            producer_invoiced = [{
                'selected': True,
                'short_profile_name': pi.producer.short_profile_name,
                'calculated_invoiced_balance': pi.calculated_invoiced_balance,
                'to_be_invoiced_balance': pi.to_be_invoiced_balance,
                'invoice_reference': pi.invoice_reference
            } for pi in qs]
            producer_invoiced_formset = ProducerInvoicedFormSet(initial=producer_invoiced)

        return render(request, 'repanier/confirm_admin_invoice.html', {
            'sub_title'                : _("Please, confirm the action : generate the invoices"),
            'action'                   : 'generate_invoices',
            'permanence'               : permanence,
            'permanence_form'          : permanence_form,
            'producer_invoiced_formset': producer_invoiced_formset,
            'action_checkbox_name'     : admin.ACTION_CHECKBOX_NAME,
        })

    generate_invoices.short_description = _('generate invoices')

    def archive(self, request, queryset):
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [
            PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if permanence.status == PERMANENCE_CLOSED:
            permanence.set_status(PERMANENCE_SEND)
        Producer.objects.all().order_by('?').update(to_be_paid=True)
        user_message, user_message_level = task_invoice.admin_generate(
            request,
            permanence=permanence,
            payment_date=timezone.now().date()
        )
        self.message_user(request, user_message, user_message_level)
        return None

    archive.short_description = _('archive')

    def send_invoices(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_DONE:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_customer_mail)
        try:
            invoice_description = permanence.invoice_description
        except TranslationDoesNotExist:
             invoice_description = EMPTY_STRING
        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_invoice_email=True)
        # TODO : Align on tools.payment_message
        customer_order_amount = \
                _('The amount of your order is %(amount)s.') % {
                    'amount': RepanierMoney(123.45)
                }
        customer_last_balance = \
            _('The balance of your account as of %(date)s is %(balance)s.') % {
                'date'   : timezone.now().strftime(settings.DJANGO_SETTINGS_DATE),
                'balance': RepanierMoney(123.45)
            }
        customer_payment_needed = "%s %s %s (%s) %s \"%s\"." % (
            _('Please pay'),
            RepanierMoney(123.45),
            _('to the bank account number'),
            repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT,
            _('with communication'),
            _('short_basket_name'))
        context = TemplateContext({
            'name'               : _('long_basket_name'),
            'long_basket_name'   : _('long_basket_name'),
            'basket_name'        : _('short_basket_name'),
            'short_basket_name'  : _('short_basket_name'),
            'permanence_link'    : mark_safe('<a href=#">%s</a>' % permanence),
            'last_balance_link'  : mark_safe('<a href="#">%s</a>' % customer_last_balance),
            'last_balance'       : customer_last_balance,
            'order_amount'       : mark_safe(customer_order_amount),
            'payment_needed'     : mark_safe(customer_payment_needed),
            'invoice_description': mark_safe(invoice_description),
            'signature'          : mark_safe(
                '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
        })
        template_invoice_customer_mail = template.render(context)

        invoice_customer_email_will_be_sent, invoice_customer_email_will_be_sent_to = send_email_to_who(
            repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER
        )

        template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_producer_mail)


        context = TemplateContext({
            'name'             : _('long_profile_name'),
            'long_profile_name': _('long_profile_name'),
            'permanence_link'  : mark_safe('<a href=#">%s</a>' % permanence),
            'signature'        : mark_safe(
                '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
        })
        template_invoice_producer_mail = template.render(context)

        invoice_producer_email_will_be_sent, invoice_producer_email_will_be_sent_to = send_email_to_who(
            repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER
        )
        if 'apply' in request.POST:
            form = InvoiceOrderForm(request.POST)
            if form.is_valid():
                user_message, user_message_level = task_invoice.admin_send(
                    permanence.id
                )
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = InvoiceOrderForm(
                initial={
                    'template_invoice_customer_mail': mark_safe(template_invoice_customer_mail),
                    'template_invoice_producer_mail': mark_safe(template_invoice_producer_mail),
                }
            )
        return render(
            request,
            'repanier/confirm_admin_send_invoice.html', {
                'sub_title'                             : _("Please, confirm the action : send invoices"),
                'action_checkbox_name'                  : admin.ACTION_CHECKBOX_NAME,
                'action'                                : 'send_invoices',
                'permanence'                            : permanence,
                'form'                                  : form,
                'invoice_customer_email_will_be_sent'   : invoice_customer_email_will_be_sent,
                'invoice_customer_email_will_be_sent_to': invoice_customer_email_will_be_sent_to,
                'invoice_producer_email_will_be_sent'   : invoice_producer_email_will_be_sent,
                'invoice_producer_email_will_be_sent_to': invoice_producer_email_will_be_sent_to
        })

    send_invoices.short_description = _('send invoices')

    def cancel_invoices(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_DONE:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None

        if 'apply' in request.POST:
            user_message, user_message_level = task_invoice.admin_cancel(queryset)
            self.message_user(request, user_message, user_message_level)
            return None
        return render(request, 'repanier/confirm_admin_action.html', {
            'sub_title'           : _("Please, confirm the action : cancel the invoices"),
            'action'              : 'cancel_invoices',
            'permanence'          : permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    cancel_invoices.short_description = _('cancel latest invoices')

    def cancel_archive(self, request, queryset):
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_ARCHIVED:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        user_message, user_message_level = task_invoice.admin_cancel(queryset)
        self.message_user(request, user_message, user_message_level)
        return None

    cancel_archive.short_description = _('cancel archiving')

    def get_actions(self, request):
        actions = super(PermanenceDoneAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        if repanier.apps.REPANIER_SETTINGS_INVOICE:
            del actions['archive']
            del actions['cancel_archive']
        else:
            del actions['export_xlsx']
            del actions['import_xlsx']
            del actions['generate_invoices']
            del actions['preview_invoices']
            del actions['send_invoices']
            del actions['cancel_invoices']

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
        if repanier.apps.REPANIER_SETTINGS_INVOICE:
            return qs.filter(status__gte=PERMANENCE_SEND)
        else:
            return qs.filter(status__gte=PERMANENCE_CLOSED)

    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
            Purchase.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceDoneAdmin, self).save_model(
            request, permanence, form, change)
