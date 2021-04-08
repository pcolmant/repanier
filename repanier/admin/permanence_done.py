import logging
import threading

from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.core.checks import messages
from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template import Context as TemplateContext, Template
from django.urls import reverse, reverse_lazy
from django.utils import timezone, translation
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm
from parler.utils.context import switch_language

import repanier.apps
from repanier.admin.forms import (
    InvoiceOrderForm,
    ProducerInvoicedFormSet,
    PermanenceInvoicedForm,
    ImportPurchasesForm,
    ImportInvoiceForm,
)
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.admin.tools import (
    check_permanence,
    check_cancel_in_post,
    check_done_in_post,
    get_query_filters,
    add_filter,
)
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
from repanier.tools import get_repanier_template_name
from repanier.xlsx.views import import_xslx_view
from repanier.xlsx.xlsx_invoice import (
    export_bank,
    export_invoice,
    handle_uploaded_invoice,
)
from repanier.xlsx.xlsx_purchase import handle_uploaded_purchase, export_purchase
from repanier.xlsx.xlsx_stock import export_permanence_stock

logger = logging.getLogger(__name__)


class PermanenceBoardInline(InlineForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ["permanence_role", "customer"]
    extra = 1

    def has_delete_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(
                is_active=True, rght=F("lft") + 1
            ).order_by("tree_id", "lft")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class PermanenceDoneForm(TranslatableModelForm):
    short_name = forms.CharField(
        label=_("Offer name"),
        widget=forms.TextInput(attrs={"style": "width:100% !important"}),
    )

    class Meta:
        model = PermanenceDone
        fields = "__all__"


class PermanenceDoneAdmin(TranslatableAdmin):
    form = PermanenceDoneForm
    change_list_url = reverse_lazy("admin:repanier_permanencedone_changelist")

    fields = ("permanence_date", "short_name", "invoice_description")
    readonly_fields = ("status", "automatically_closed")
    list_per_page = 10
    list_max_show_all = 10
    inlines = [PermanenceBoardInline]
    date_hierarchy = "permanence_date"
    list_display = ("get_permanence_admin_display",)
    list_display_links = ("get_permanence_admin_display",)
    search_fields = [
        "customerproducerinvoice__producer__short_profile_name",
        "customerproducerinvoice__customer__short_basket_name",
    ]
    ordering = (
        "-invoice_sort_order",
        "-canceled_invoice_sort_order",
        "-permanence_date",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_invoice_manager:
            return True
        return False

    def get_redirect_to_change_list_url(self):
        return "{}{}".format(self.change_list_url, get_query_filters())

    def get_list_display(self, request):
        list_display = ["get_permanence_admin_display", "get_row_actions"]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += ["language_column"]
        list_display += [
            "get_producers_without_download",
            "get_customers_without_download",
            "get_board",
            "get_html_status_display",
        ]
        return list_display

    def get_urls(self):
        urls = super(PermanenceDoneAdmin, self).get_urls()
        custom_urls = [
            url(
                r"^import-new-invoice/$",
                self.admin_site.admin_view(self.import_new_invoice),
                name="permanence-import-new-invoice",
            ),
            url(
                r"^(?P<permanence_id>.+)/export-invoice/$",
                self.admin_site.admin_view(self.export_purchases),
                name="permanence-export-invoice",
            ),
            url(
                r"^(?P<permanence_id>.+)/import-invoice/$",
                self.admin_site.admin_view(self.import_updated_purchases),
                name="permanence-import-invoice",
            ),
            url(
                r"^(?P<permanence_id>.+)/invoice/$",
                self.admin_site.admin_view(self.invoice),
                name="permanence-invoice",
            ),
            url(
                r"^(?P<permanence_id>.+)/send-invoices/$",
                self.admin_site.admin_view(self.send_invoices),
                name="permanence-send-invoices",
            ),
            url(
                r"^(?P<permanence_id>.+)/accounting-report/$",
                self.admin_site.admin_view(self.accounting_report),
                name="permanence-accounting-report",
            ),
            url(
                r"^(?P<permanence_id>.+)/archive/$",
                self.admin_site.admin_view(self.archive),
                name="permanence-archive",
            ),
            url(
                r"^(?P<permanence_id>.+)/cancel-delivery/$",
                self.admin_site.admin_view(self.cancel_delivery),
                name="permanence-cancel-delivery",
            ),
            url(
                r"^(?P<permanence_id>.+)/cancel-invoicing/$",
                self.admin_site.admin_view(self.cancel_invoicing),
                name="permanence-cancel-invoicing",
            ),
            url(
                r"^(?P<permanence_id>.+)/cancel-archiving/$",
                self.admin_site.admin_view(self.cancel_archiving),
                name="permanence-cancel-archiving",
            ),
            url(
                r"^(?P<permanence_id>.+)/restore-delivery/$",
                self.admin_site.admin_view(self.restore_delivery),
                name="permanence-restore-delivery",
            ),
        ]
        return custom_urls + urls

    @check_cancel_in_post
    def import_new_invoice(self, request):
        return import_xslx_view(
            self,
            admin,
            request,
            None,
            _("Import an invoice"),
            handle_uploaded_invoice,
            action="import_new_invoice",
            form_klass=ImportInvoiceForm,
        )

    @check_permanence(PERMANENCE_SEND, PERMANENCE_SEND_STR)
    def export_purchases(self, request, permanence_id, permanence=None):
        wb = export_purchase(permanence=permanence, wb=None)
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(_("Invoices"), permanence)
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    @check_cancel_in_post
    @check_permanence(PERMANENCE_SEND, PERMANENCE_SEND_STR)
    def import_updated_purchases(self, request, permanence_id, permanence=None):
        return import_xslx_view(
            self,
            admin,
            request,
            permanence,
            _("Import purchases"),
            handle_uploaded_purchase,
            action="import_updated_purchases",
            form_klass=ImportPurchasesForm,
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_SEND, PERMANENCE_SEND_STR)
    def cancel_delivery(self, request, permanence_id, permanence=None):
        if "apply" in request.POST:
            permanence.cancel_delivery()
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Billing offers"),
                "sub_title": _("Please, confirm the action : cancel delivery."),
                "action": "cancel_delivery",
                "permanence": permanence,
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            },
        )

    @check_permanence(PERMANENCE_INVOICED, PERMANENCE_INVOICED_STR)
    def accounting_report(self, request, permanence_id, permanence=None):
        wb = export_bank(permanence=permanence, wb=None, sheet_name=permanence)
        wb = export_invoice(permanence=permanence, wb=wb, sheet_name=permanence)
        wb = export_permanence_stock(
            permanence=permanence, wb=wb, ws_customer_title=None
        )
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
        user_message = _("No invoice available for {permanence}.'.").format(
            permanence=permanence
        )
        user_message_level = messages.WARNING
        self.message_user(request, user_message, user_message_level)
        return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    @check_done_in_post
    @check_cancel_in_post
    @check_permanence(PERMANENCE_SEND, PERMANENCE_SEND_STR)
    def invoice(self, request, permanence_id, permanence=None):
        max_payment_date = timezone.now().date()
        bank_account = (
            BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL)
            .only("operation_date")
            .order_by("-id")
            .first()
        )
        if bank_account is not None:
            if bank_account.operation_date > max_payment_date:
                max_payment_date = bank_account.operation_date
            min_payment_date = bank_account.operation_date
        else:
            # This cas should never occur because of the first bank account record created at startup if none exists
            # via config.save() in apps.
            min_payment_date = timezone.now().date()

        if max_payment_date < min_payment_date:
            max_payment_date = min_payment_date
        if "apply" in request.POST and admin.ACTION_CHECKBOX_NAME in request.POST:
            permanence_form = PermanenceInvoicedForm(request.POST)
            producer_invoiced_formset = ProducerInvoicedFormSet(request.POST)
            if permanence_form.is_valid() and producer_invoiced_formset.is_valid():
                payment_date = permanence_form.cleaned_data.get("payment_date")
                if payment_date < min_payment_date or payment_date > max_payment_date:
                    permanence_form.add_error(
                        "payment_date",
                        _(
                            "The payment date must be between %(min_payment_date)s and %(max_payment_date)s."
                        )
                        % {
                            "min_payment_date": min_payment_date.strftime(
                                settings.DJANGO_SETTINGS_DATE
                            ),
                            "max_payment_date": max_payment_date.strftime(
                                settings.DJANGO_SETTINGS_DATE
                            ),
                        },
                    )
                else:
                    at_least_one_selected = False
                    for producer_invoiced_form in producer_invoiced_formset:
                        if producer_invoiced_form.is_valid():
                            producer_id = producer_invoiced_form.cleaned_data.get("id")
                            selected = producer_invoiced_form.cleaned_data.get(
                                "selected"
                            )
                            producer_invoice = (
                                ProducerInvoice.objects.filter(
                                    permanence_id=permanence_id,
                                    invoice_sort_order__isnull=True,
                                    producer_id=producer_id,
                                )
                                .order_by("?")
                                .first()
                            )
                            if selected:
                                at_least_one_selected = True
                                producer_invoice.to_be_invoiced_balance = producer_invoiced_form.cleaned_data.get(
                                    "to_be_invoiced_balance"
                                )
                                producer_invoice.invoice_reference = producer_invoiced_form.cleaned_data.get(
                                    "invoice_reference", EMPTY_STRING
                                )
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
                            "admin/confirm_bank_movement.html"
                        )
                        return render(
                            request,
                            template_name,
                            {
                                **self.admin_site.each_context(request),
                                "action": "invoice",
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
                        return HttpResponseRedirect(
                            self.get_redirect_to_change_list_url()
                        )
        else:
            producers_invoiced = []
            for producer_invoice in (
                ProducerInvoice.objects.filter(
                    permanence_id=permanence_id, invoice_sort_order__isnull=True
                )
                .order_by("producer")
                .select_related("producer")
            ):
                producer = producer_invoice.producer
                if not producer.represent_this_buyinggroup:
                    # We have already pay to much (look at the bank movements).
                    # So we do not need to pay anything
                    producer_invoice.calculated_invoiced_balance.amount = producer.get_calculated_invoiced_balance(
                        permanence_id
                    )
                else:
                    producer_invoice.calculated_invoiced_balance.amount = RepanierMoney(
                        producer_invoice.get_total_price_with_tax().amount
                    )
                # First time invoiced ? Yes : propose the calculated invoiced balance as to be invoiced balance
                producer_invoice.to_be_invoiced_balance = (
                    producer_invoice.calculated_invoiced_balance
                )
                producer_invoice.save(
                    update_fields=[
                        "calculated_invoiced_balance",
                        "to_be_invoiced_balance",
                    ]
                )
                producers_invoiced.append(
                    {
                        "id": producer_invoice.producer_id,
                        "selected": True,
                        "short_profile_name": producer_invoice.producer.short_profile_name,
                        "calculated_invoiced_balance": producer_invoice.calculated_invoiced_balance,
                        "to_be_invoiced_balance": producer_invoice.to_be_invoiced_balance,
                        "invoice_reference": producer_invoice.invoice_reference,
                        "producer_price_are_wo_vat": producer_invoice.producer.producer_price_are_wo_vat,
                    }
                )
            if permanence.payment_date is not None:
                # In this case we the permanence has already been invoiced in the past
                # and the invoice has been cancelled
                payment_date = permanence.payment_date
            else:
                payment_date = max_payment_date
            permanence_form = PermanenceInvoicedForm(payment_date=payment_date)

            producer_invoiced_formset = ProducerInvoicedFormSet(
                initial=producers_invoiced
            )

        template_name = get_repanier_template_name("admin/confirm_invoice.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action": "invoice",
                "permanence": permanence,
                "permanence_form": permanence_form,
                "producer_invoiced_formset": producer_invoiced_formset,
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            },
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_SEND, PERMANENCE_SEND_STR)
    def archive(self, request, permanence_id, permanence=None):
        if "apply" in request.POST:
            permanence.archive()
            user_message = _("Action performed.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Billing offers"),
                "sub_title": _("Please, confirm the action : generate archive."),
                "action": "archive",
                "permanence": permanence,
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            },
        )

    def cancel_invoice_or_archive_or_cancelled(
        self, request, permanence, action, sub_title
    ):
        if "apply" in request.POST:
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
                        old_status=PERMANENCE_INVOICED, new_status=PERMANENCE_SEND
                    )
            else:
                if permanence.status == PERMANENCE_ARCHIVED:
                    permanence.set_status(
                        old_status=PERMANENCE_ARCHIVED, new_status=PERMANENCE_SEND
                    )
                if permanence.status == PERMANENCE_CANCELLED:
                    permanence.set_status(
                        old_status=PERMANENCE_CANCELLED, new_status=PERMANENCE_SEND
                    )
                user_message = _("The selected invoice has been restored.")
                user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Billing offers"),
                "sub_title": sub_title,
                "action": action,
                "permanence": permanence,
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            },
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_INVOICED, PERMANENCE_INVOICED_STR)
    def cancel_invoicing(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "cancel_invoicing",
            _("Please, confirm the action : cancel the invoices."),
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_ARCHIVED, PERMANENCE_ARCHIVED_STR)
    def cancel_archiving(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "cancel_archiving",
            _("Please, confirm the action : cancel the archiving."),
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_CANCELLED, PERMANENCE_CANCELLED_STR)
    def restore_delivery(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "restore_delivery",
            _("Please, confirm the action : restore the delivery."),
        )

    @check_cancel_in_post
    @check_permanence(PERMANENCE_INVOICED, PERMANENCE_INVOICED_STR)
    def send_invoices(self, request, permanence_id, permanence=None):
        if "apply" in request.POST:
            t = threading.Thread(
                target=email_invoice.send_invoice, args=(permanence_id,)
            )
            t.start()
            user_message = _("The invoices are being send.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

        template_invoice_customer_mail = []
        template_invoice_producer_mail = []
        invoice_customer_email_will_be_sent, invoice_customer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_CUSTOMER
        )
        invoice_producer_email_will_be_sent, invoice_producer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_INVOICE_MAIL_TO_PRODUCER
        )

        if invoice_customer_email_will_be_sent or invoice_producer_email_will_be_sent:
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)
                invoice_responsible = Staff.get_or_create_invoice_responsible()

                if invoice_customer_email_will_be_sent:
                    with switch_language(
                        repanier.apps.REPANIER_SETTINGS_CONFIG, language_code
                    ):
                        template = Template(
                            repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_customer_mail
                        )
                    with switch_language(permanence, language_code):
                        invoice_description = permanence.safe_translation_getter(
                            "invoice_description",
                            any_language=True,
                            default=EMPTY_STRING,
                        )
                    # TODO : Align on tools.payment_message
                    customer_order_amount = _(
                        "The amount of your order is %(amount)s."
                    ) % {"amount": RepanierMoney(123.45)}
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
                            communication = "{} ({})".format(
                                _("Short name"), permanence.short_name
                            )
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
                            "permanence_link": mark_safe(
                                '<a href="#">{}</a>'.format(permanence)
                            ),
                            "last_balance_link": mark_safe(
                                '<a href="#">{}</a>'.format(customer_last_balance)
                            ),
                            "last_balance": customer_last_balance,
                            "order_amount": mark_safe(customer_order_amount),
                            "payment_needed": mark_safe(customer_payment_needed),
                            "invoice_description": mark_safe(invoice_description),
                            "signature": invoice_responsible["html_signature"],
                        }
                    )
                    template_invoice_customer_mail.append(language_code)
                    template_invoice_customer_mail.append(template.render(context))

                if invoice_producer_email_will_be_sent:
                    with switch_language(
                        repanier.apps.REPANIER_SETTINGS_CONFIG, language_code
                    ):
                        template = Template(
                            repanier.apps.REPANIER_SETTINGS_CONFIG.invoice_producer_mail
                        )
                    context = TemplateContext(
                        {
                            "name": _("Long name"),
                            "long_profile_name": _("Long name"),
                            "permanence_link": mark_safe(
                                '<a href="#">{}</a>'.format(permanence)
                            ),
                            "signature": invoice_responsible["html_signature"],
                        }
                    )
                    template_invoice_producer_mail.append(language_code)
                    template_invoice_producer_mail.append(template.render(context))

            translation.activate(cur_language)
        form = InvoiceOrderForm(
            initial={
                "template_invoice_customer_mail": mark_safe(
                    "<br>==============<br>".join(template_invoice_customer_mail)
                ),
                "template_invoice_producer_mail": mark_safe(
                    "<br>==============<br>".join(template_invoice_producer_mail)
                ),
            }
        )
        template_name = get_repanier_template_name("admin/confirm_send_invoice.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
                "action": "send_invoices",
                "permanence": permanence,
                "form": form,
                "invoice_customer_email_will_be_sent_to": invoice_customer_email_will_be_sent_to,
                "invoice_producer_email_will_be_sent_to": invoice_producer_email_will_be_sent_to,
            },
        )

    def get_row_actions(self, permanence):

        if permanence.status == PERMANENCE_SEND:
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                return format_html(
                    '<div class="repanier-button-row">'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a></span>'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-upload"></i></a></span>'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-truck fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a></span>'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-cash-register" style="color: #32CD32;"></i></a></span>'
                    "</div>",
                    add_filter(
                        reverse("admin:permanence-export-invoice", args=[permanence.pk])
                    ),
                    _("Export"),
                    add_filter(
                        reverse("admin:permanence-import-invoice", args=[permanence.pk])
                    ),
                    _("Import"),
                    add_filter(
                        reverse(
                            "admin:permanence-cancel-delivery", args=[permanence.pk]
                        )
                    ),
                    _("Cancel the delivery"),
                    add_filter(
                        reverse("admin:permanence-invoice", args=[permanence.pk])
                    ),
                    _("To invoice"),
                )

            else:
                return format_html(
                    '<div class="repanier-button-row">'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-truck fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a></span>'
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-archive" style="color: #32CD32;"></i></a></span>'
                    "</div>",
                    add_filter(
                        reverse(
                            "admin:permanence-cancel-delivery", args=[permanence.pk]
                        )
                    ),
                    _("Cancel the delivery"),
                    add_filter(
                        reverse("admin:permanence-archive", args=[permanence.pk])
                    ),
                    _("To archive"),
                )

        elif permanence.status == PERMANENCE_INVOICED:
            if (
                BankAccount.objects.filter(
                    operation_status=BANK_LATEST_TOTAL, permanence_id=permanence.id
                )
                .order_by("?")
                .exists()
            ):
                # This is the latest invoiced permanence
                # Invoicing can be cancelled
                cancel_invoice = format_html(
                    '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-cash-register fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a></span> ',
                    add_filter(
                        reverse(
                            "admin:permanence-cancel-invoicing", args=[permanence.pk]
                        )
                    ),
                    _("Cancel the invoicing"),
                )
            else:
                cancel_invoice = EMPTY_STRING

            return format_html(
                '<div class="repanier-button-row">'
                '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-file-invoice-dollar"></i></a></span>'
                '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-envelope-open-text"></i></a></span>'
                "{}"
                "</div>",
                add_filter(
                    reverse("admin:permanence-accounting-report", args=[permanence.pk])
                ),
                _("Accounting report"),
                add_filter(
                    reverse("admin:permanence-send-invoices", args=[permanence.pk])
                ),
                _("Send the invoices"),
                cancel_invoice,
            )

        elif permanence.status == PERMANENCE_ARCHIVED:
            return format_html(
                '<div class="repanier-button-row">'
                '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-trash-restore"></i></a></span>'
                "</div>",
                add_filter(
                    reverse("admin:permanence-cancel-archiving", args=[permanence.pk])
                ),
                _("Restore"),
            )

        elif permanence.status == PERMANENCE_CANCELLED:
            return format_html(
                '<div class="repanier-button-row">'
                '<span class="repanier-a-container"><a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-trash-restore"></i></a></span>'
                "</div>",
                add_filter(
                    reverse("admin:permanence-restore-delivery", args=[permanence.pk])
                ),
                _("Restore"),
            )

        return EMPTY_STRING

    get_row_actions.short_description = EMPTY_STRING

    def get_actions(self, request):
        actions = super(PermanenceDoneAdmin, self).get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]

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
        extra_context["module_name"] = EMPTY_STRING
        return super(PermanenceDoneAdmin, self).changelist_view(
            request, extra_context=extra_context
        )

    def get_queryset(self, request):
        qs = super(PermanenceDoneAdmin, self).get_queryset(request)
        return qs.filter(status__gte=PERMANENCE_SEND)

    def save_model(self, request, permanence, form, change):
        if change and ("permanence_date" in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date
            )
        super(PermanenceDoneAdmin, self).save_model(request, permanence, form, change)

    # class Media:
    #     if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
    #         js = (
    #             "admin/js/jquery.init.js",
    #             get_repanier_static_name("js/import_invoice.js"),
    #         )
