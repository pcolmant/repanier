# -*- coding: utf-8
import threading

from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.core.checks import messages
from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template import Context as TemplateContext, Template
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

import repanier.apps
from repanier.admin.forms import (
    InvoiceOrderForm,
    ProducerInvoicedFormSet,
    PermanenceInvoicedForm,
    ImportXlsxForm,
    ImportInvoiceForm,
)
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import *
from repanier.email import email_invoice
from repanier.email.email import RepanierEmail
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice
from repanier.models.lut import LUT_PermanenceRole
from repanier.models.permanence import PermanenceDone
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.staff import Staff
from repanier.tools import get_repanier_template_name, get_repanier_static_name
from repanier.xlsx.views import import_xslx_view
from repanier.xlsx.xlsx_invoice import (
    export_bank,
    export_invoice,
    handle_uploaded_invoice,
)
from repanier.xlsx.xlsx_purchase import handle_uploaded_purchase, export_purchase
from repanier.xlsx.xlsx_stock import export_permanence_stock


class PermanenceBoardInline(InlineForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ['permanence_role', 'customer']
    extra = 1

    def has_delete_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True, rght=F('lft') + 1).order_by(
                "tree_id", "lft")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class PermanenceDoneForm(TranslatableModelForm):
    short_name = forms.CharField(label=_("Offer name"),
                                 widget=forms.TextInput(attrs={'style': "width:100% !important"}))

    class Meta:
        model = PermanenceDone
        fields = "__all__"


class PermanenceDoneAdmin(TranslatableAdmin):
    form = PermanenceDoneForm

    fields = ("permanence_date", "short_name", "invoice_description")  # 'status'
    readonly_fields = ("status", "automatically_closed")
    # exclude = ['offer_description', ]
    list_per_page = 10
    list_max_show_all = 10
    inlines = [PermanenceBoardInline]
    date_hierarchy = "permanence_date"
    list_display = ["get_permanence_admin_display"]
    ordering = ("-invoice_sort_order", "-permanence_date")
    # ordering = ('status', '-permanence_date', 'id')
    actions = [
        "export_xlsx",
        "import_xlsx",
        "generate_invoices",
        "preview_invoices",
        "send_invoices",
        "cancel_delivery",
        "cancel_invoices",
        "generate_archive",
        "cancel_archive",
    ]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_invoice_manager:
            return True
        return False

    def get_list_display(self, request):
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            return ('get_permanence_admin_display', 'language_column', 'get_producers',
                    'get_customers', 'get_board', 'get_html_status_display')
        else:
            return ('get_permanence_admin_display', 'get_producers',
                    'get_customers', 'get_board', 'get_html_status_display')

    def get_urls(self):
        urls = super(PermanenceDoneAdmin, self).get_urls()
        my_urls = [
            url(r'^import_invoice/$', self.admin_site.admin_view(self.add_delivery)),
        ]
        return my_urls + urls

    def add_delivery(self, request):
        return import_xslx_view(
            self, admin, request, None, _("Import an invoice"),
            handle_uploaded_invoice, action='add_delivery', form_klass=ImportInvoiceForm
        )

    def cancel_delivery(self, request, permanence_qs):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = permanence_qs.first()
        if permanence is None or permanence.status not in [
            PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            permanence.cancel_delivery()
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        template_name = get_repanier_template_name("confirm_admin_action.html")
        return render(request, template_name, {
            'sub_title': _("Please, confirm the action : cancel delivery."),
            'action': 'cancel_delivery',
            'permanence': permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    cancel_delivery.short_description = _("Cancel delivery")

    def export_xlsx(self, request, permanence_qs):
        permanence = permanence_qs.first()
        if permanence.status != PERMANENCE_SEND:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        wb = export_purchase(permanence=permanence, wb=None)
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                _("Invoices"),
                permanence
            )
            wb.save(response)
            return response
        else:
            return

    export_xlsx.short_description = _("1 --- Export billing preparation list")

    def import_xlsx(self, request, permanence_qs):
        permanence = permanence_qs.first()
        if permanence.status != PERMANENCE_SEND:
            user_message = _(
                "The status of %(permanence)s prohibit you to perform this action."
            ) % {"permanence": permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        return import_xslx_view(
            self,
            admin,
            request,
            permanence_qs[:1],
            _("Import orders prepared"),
            handle_uploaded_purchase,
            action="import_xlsx",
            form_klass=ImportXlsxForm,
        )

    import_xlsx.short_description = _("2 --- Import, update billing preparation list")

    def preview_invoices(self, request, permanence_qs):
        valid_permanence_qs = permanence_qs.filter(
            status__in=[PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]
        )
        wb = None
        first = True
        for permanence in valid_permanence_qs:
            if first:
                wb = export_bank(permanence=permanence, wb=wb, sheet_name=permanence)
            wb = export_invoice(permanence=permanence, wb=wb, sheet_name=permanence)
            if first:
                wb = export_permanence_stock(
                    permanence=permanence, wb=wb, ws_customer_title=None
                )
                first = False
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(
                _("Accounting report"), settings.REPANIER_SETTINGS_GROUP_NAME
            )
            wb.save(response)
            return response
        user_message = _("No invoice available for %(permanence)s.") % {
            "permanence": ", ".join("{}".format(p) for p in permanence_qs.all())
        }
        user_message_level = messages.WARNING
        self.message_user(request, user_message, user_message_level)
        return

    preview_invoices.short_description = _("4 --- Export accounting report")

    def generate_invoices(self, request, permanence_qs):
        if 'done' in request.POST:
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        elif 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = permanence_qs.first()
        if permanence.status != PERMANENCE_SEND:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return

        max_payment_date = timezone.now().date()
        bank_account = BankAccount.objects.filter(
            operation_status=BANK_LATEST_TOTAL
        ).only("operation_date").order_by("-id").first()
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
                    at_least_one_selected = False
                    for producer_invoiced_form in producer_invoiced_formset:
                        if producer_invoiced_form.is_valid():
                            selected = producer_invoiced_form.cleaned_data.get('selected')
                            short_profile_name = producer_invoiced_form.cleaned_data.get('short_profile_name')
                            producer_invoice = ProducerInvoice.objects.filter(
                                permanence_id=permanence.id,
                                invoice_sort_order__isnull=True,
                                producer__short_profile_name=short_profile_name,
                            ).order_by(
                                '?'
                            ).first()
                            if selected:
                                at_least_one_selected = True
                                producer_invoice.to_be_invoiced_balance = producer_invoiced_form.cleaned_data.get(
                                    'to_be_invoiced_balance')
                                producer_invoice.invoice_reference = producer_invoiced_form.cleaned_data.get(
                                    'invoice_reference', EMPTY_STRING)
                                producer_invoice.to_be_paid = True
                            else:
                                producer_invoice.to_be_invoiced_balance = DECIMAL_ZERO
                                producer_invoice.invoice_reference = EMPTY_STRING
                                producer_invoice.to_be_paid = False
                            producer_invoice.delta_vat = DECIMAL_ZERO
                            producer_invoice.delta_deposit = DECIMAL_ZERO
                            producer_invoice.delta_price_with_tax = DECIMAL_ZERO
                            producer_invoice.save(
                                update_fields=[
                                    "to_be_invoiced_balance",
                                    "invoice_reference",
                                    "delta_vat",
                                    "delta_deposit",
                                    "delta_price_with_tax",
                                    "to_be_paid",
                                ]
                            )
                    if at_least_one_selected:
                        permanence.invoice(payment_date=payment_date)
                        previous_latest_total = (
                            BankAccount.objects.filter(
                                operation_status=BANK_NOT_LATEST_TOTAL,
                                producer__isnull=True,
                                customer__isnull=True,
                            )
                            .order_by("-id")
                            .first()
                        )
                        previous_latest_total_id = (
                            previous_latest_total.id
                            if previous_latest_total is not None
                            else 0
                        )
                        template_name = get_repanier_template_name(
                            "confirm_admin_bank_movement.html"
                        )
                        return render(
                            request,
                            template_name,
                            {
                                "sub_title": _(
                                    "Please make the following payments, whose bank movements have been generated."
                                ),
                                "action": "generate_invoices",
                                "permanence": permanence,
                                "bankaccounts": BankAccount.objects.filter(
                                    id__gt=previous_latest_total_id,
                                    producer__isnull=False,
                                    producer__represent_this_buyinggroup=False,
                                    customer__isnull=True,
                                    operation_status=BANK_CALCULATED_INVOICE,
                                ).order_by("producer", "-operation_date", "-id"),
                                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
                            },
                        )
                    else:
                        user_message = _("You must select at least one producer.")
                        user_message_level = messages.WARNING
                        self.message_user(request, user_message, user_message_level)
                        return
        else:
            producer_invoiced = []
            for producer_invoice in ProducerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    invoice_sort_order__isnull=True,
            ).order_by("producer").select_related("producer"):
                producer = producer_invoice.producer
                if not producer.represent_this_buyinggroup:
                    # We have already pay to much (look at the bank movements).
                    # So we do not need to pay anything
                    producer_invoice.calculated_invoiced_balance.amount = \
                        producer.get_calculated_invoiced_balance(permanence.id)
                else:
                    producer_invoice.calculated_invoiced_balance.amount = producer_invoice.get_total_price_with_tax().amount
                # First time invoiced ? Yes : propose the calculated invoiced balance as to be invoiced balance
                producer_invoice.to_be_invoiced_balance = producer_invoice.calculated_invoiced_balance
                producer_invoice.save(update_fields=[
                    'calculated_invoiced_balance',
                    'to_be_invoiced_balance'
                ])
                producer_invoiced.append({
                    'selected': True,
                    'short_profile_name': producer_invoice.producer.short_profile_name,
                    'calculated_invoiced_balance': producer_invoice.calculated_invoiced_balance,
                    'to_be_invoiced_balance': producer_invoice.to_be_invoiced_balance,
                    'invoice_reference': producer_invoice.invoice_reference
                })
            if permanence.payment_date is not None:
                # In this case we have also, permanence.status > PERMANENCE_SEND
                permanence_form = PermanenceInvoicedForm(payment_date=permanence.payment_date)
            else:
                permanence_form = PermanenceInvoicedForm(payment_date=max_payment_date)

            producer_invoiced_formset = ProducerInvoicedFormSet(initial=producer_invoiced)

        template_name = get_repanier_template_name("confirm_admin_invoice.html")
        return render(request, template_name, {
            'sub_title': _("Please, confirm the action : generate the invoices."),
            'action': 'generate_invoices',
            'permanence': permanence,
            'permanence_form': permanence_form,
            'producer_invoiced_formset': producer_invoiced_formset,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    generate_invoices.short_description = _('3 --- Generate invoices')

    def generate_archive(self, request, permanence_qs):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = permanence_qs.first()

        if permanence is None or permanence.status not in [
            PERMANENCE_CLOSED,
            PERMANENCE_SEND,
        ]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return

        if 'apply' in request.POST:
            permanence.archive()
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        template_name = get_repanier_template_name("confirm_admin_action.html")
        return render(request, template_name, {
            'sub_title': _("Please, confirm the action : generate archive."),
            'action': 'generate_archive',
            'permanence': permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    generate_archive.short_description = _('Archive')

    def cancel_invoice_or_archive_or_cancelled(self, request, permanence_qs, action):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = permanence_qs.first()
        if permanence.status not in [
            PERMANENCE_INVOICED,
            PERMANENCE_ARCHIVED,
            PERMANENCE_CANCELLED,
        ]:
            user_message = _(
                "The status of %(permanence)s prohibit you to perform this action."
            ) % {"permanence": permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return

        if 'apply' in request.POST:
            if permanence.status == PERMANENCE_INVOICED:
                last_bank_account_total = (
                    BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL)
                    .only("permanence")
                    .first()
                )
                if last_bank_account_total is not None:
                    last_permanence_invoiced_id = last_bank_account_total.permanence_id
                    if last_permanence_invoiced_id is not None:
                        if last_permanence_invoiced_id == permanence.id:
                            # This is well the latest closed permanence. The invoices can be cancelled without damages.
                            permanence.cancel_invoice(last_bank_account_total)
                            user_message = _("The selected invoice has been canceled.")
                            user_message_level = messages.INFO
                        else:
                            user_message = _(
                                "You mus first cancel the invoices of {} whose date is {}."
                            ).format(
                                last_bank_account_total.permanence,
                                last_bank_account_total.permanence.permanence_date.strftime(
                                    settings.DJANGO_SETTINGS_DATE
                                ),
                            )
                            user_message_level = messages.ERROR
                    else:
                        user_message = _(
                            "The selected invoice is not the latest invoice."
                        )
                        user_message_level = messages.ERROR
                else:
                    user_message = _("The selected invoice has been canceled.")
                    user_message_level = messages.INFO
                    permanence.set_status(
                        old_status=(PERMANENCE_INVOICED,), new_status=PERMANENCE_SEND
                    )
            else:
                permanence.set_status(
                    old_status=(PERMANENCE_ARCHIVED, PERMANENCE_CANCELLED),
                    new_status=PERMANENCE_SEND,
                )
                user_message = _("The selected invoice has been restored.")
                user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        template_name = get_repanier_template_name("confirm_admin_action.html")
        return render(
            request,
            template_name,
            {
                "sub_title": _("Please, confirm the action : cancel the invoices.")
                if permanence.status == PERMANENCE_INVOICED
                else _("Please, confirm the action : cancel the archiving.")
                if permanence.status == PERMANENCE_ARCHIVED
                else _("Please, confirm the action : restore the delivery."),
                "action": action,
                "permanence": permanence,
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            },
        )

    def cancel_invoices(self, request, permanence_qs):
        return self.cancel_invoice_or_archive_or_cancelled(
            request, permanence_qs, "cancel_invoices"
        )

    cancel_invoices.short_description = _(
        "Cancel the last invoice or the last cancellation of delivery"
    )

    def cancel_archive(self, request, permanence_qs):
        return self.cancel_invoice_or_archive_or_cancelled(
            request, permanence_qs, "cancel_archive"
        )

    cancel_archive.short_description = _("Cancel archiving")

    def send_invoices(self, request, permanence_qs):
        if "cancel" in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = permanence_qs.first()
        if permanence.status != PERMANENCE_INVOICED:
            user_message = _(
                "The status of %(permanence)s prohibit you to perform this action."
            ) % {"permanence": permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        template = Template(
            repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_customer_mail
        )
        invoice_description = permanence.safe_translation_getter(
            "invoice_description", any_language=True, default=EMPTY_STRING
        )
        staff = Staff.get_or_create_invoice_responsible()

        # TODO : Align on tools.payment_message
        customer_order_amount = _("The amount of your order is %(amount)s.") % {
            "amount": RepanierMoney(123.45)
        }
        customer_last_balance = _(
            "The balance of your account as of %(date)s is %(balance)s."
        ) % {
            "date": timezone.now().strftime(settings.DJANGO_SETTINGS_DATE),
            "balance": RepanierMoney(123.45),
        }
        bank_account_number = repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT
        if bank_account_number is not None:
            group_name = settings.REPANIER_SETTINGS_GROUP_NAME
            if permanence.short_name:
                communication = "{} ({})".format(_("Short name"), permanence.short_name)
            else:
                communication = _("Short name")
            customer_payment_needed = '<font color="#bd0926">{}</font>'.format(
                _(
                    "Please pay a provision of %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s."
                )
                % {
                    "payment": RepanierMoney(123.45),
                    "name": group_name,
                    "number": bank_account_number,
                    "communication": communication,
                }
            )
        else:
            customer_payment_needed = EMPTY_STRING
        context = TemplateContext(
            {
                "name": _("Long name"),
                "long_basket_name": _("Long name"),
                "basket_name": _("Short name"),
                "short_basket_name": _("Short name"),
                "permanence_link": mark_safe('<a href="#">{}</a>'.format(permanence)),
                "last_balance_link": mark_safe(
                    '<a href="#">{}</a>'.format(customer_last_balance)
                ),
                "last_balance": customer_last_balance,
                "order_amount": mark_safe(customer_order_amount),
                "payment_needed": mark_safe(customer_payment_needed),
                "invoice_description": mark_safe(invoice_description),
                "signature": staff.get_html_signature,
            }
        )
        template_invoice_customer_mail = template.render(context)

        invoice_customer_email_will_be_sent, invoice_customer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER
        )

        template = Template(
            repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_producer_mail
        )

        context = TemplateContext(
            {
                "name": _("Long name"),
                "long_profile_name": _("Long name"),
                "permanence_link": mark_safe('<a href="#">{}</a>'.format(permanence)),
                "signature": staff.get_html_signature,
            }
        )
        template_invoice_producer_mail = template.render(context)

        invoice_producer_email_will_be_sent, invoice_producer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER
        )
        if "apply" in request.POST:
            form = InvoiceOrderForm(request.POST)
            if form.is_valid():
                t = threading.Thread(
                    target=email_invoice.send_invoice, args=(permanence.id,)
                )
                t.start()
                user_message = _(
                    "Emails containing the invoices will be send to the customers and the producers."
                )
                user_message_level = messages.INFO
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = InvoiceOrderForm(
                initial={
                    "template_invoice_customer_mail": mark_safe(
                        template_invoice_customer_mail
                    ),
                    "template_invoice_producer_mail": mark_safe(
                        template_invoice_producer_mail
                    ),
                }
            )
        template_name = get_repanier_template_name("confirm_admin_send_invoice.html")
        return render(
            request,
            template_name,
            {
                "sub_title": _("Please, confirm the action : send invoices."),
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
                "action": "send_invoices",
                "permanence": permanence,
                "form": form,
                "invoice_customer_email_will_be_sent": invoice_customer_email_will_be_sent,
                "invoice_customer_email_will_be_sent_to": invoice_customer_email_will_be_sent_to,
                "invoice_producer_email_will_be_sent": invoice_producer_email_will_be_sent,
                "invoice_producer_email_will_be_sent_to": invoice_producer_email_will_be_sent_to,
            },
        )

    send_invoices.short_description = _("5 --- Send invoices")

    def get_actions(self, request):
        actions = super(PermanenceDoneAdmin, self).get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            del actions["generate_archive"]
            del actions["cancel_archive"]
        else:
            del actions["export_xlsx"]
            del actions["import_xlsx"]
            del actions["generate_invoices"]
            del actions["preview_invoices"]
            del actions["send_invoices"]
            del actions["cancel_invoices"]

        if not actions:
            try:
                self.list_display.remove("action_checkbox")
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def changelist_view(self, request, extra_context=None):
        # Important : Linked to the use of lambda in model verbose_name
        extra_context = extra_context or {}
        # extra_context['module_name'] = "{}".format(self.model._meta.verbose_name_plural())
        # Finally I found the use of EMPTY_STRING nicer on the UI
        extra_context['module_name'] = EMPTY_STRING
        return super(PermanenceDoneAdmin, self).changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super(PermanenceDoneAdmin, self).get_queryset(request)
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            return qs.filter(
                status__gte=PERMANENCE_SEND
            )
        else:
            return qs.filter(
                status__gte=PERMANENCE_CLOSED
            )

    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceDoneAdmin, self).save_model(
            request, permanence, form, change)

    class Media:
        js = ('admin/js/jquery.init.js', get_repanier_static_name("js/import_invoice.js"),)
