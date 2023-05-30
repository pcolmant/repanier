import logging

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.checks import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy, path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from repanier.admin.admin_filter import AdminFilterPermanenceDoneStatus
from repanier.admin.forms import (
    ProducerInvoicedFormSet,
    PermanenceInvoicedForm,
    ImportPurchasesForm,
    ImportInvoiceForm,
)
from repanier.admin.sale import SaleAdmin
from repanier.admin.tools import (
    check_permanence,
    check_cancel_in_post,
    check_done_in_post,
)
from repanier.const import *
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.middleware import add_filter
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import ProducerInvoice
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


class PermanenceDoneAdmin(SaleAdmin):
    list_display = (
        "get_permanence_admin_display",
        "get_row_actions",
        "get_producers_without_download",
        "get_customers_without_download",
        "get_board",
        "get_html_status_display",
    )
    change_list_url = reverse_lazy("admin:repanier_permanencedone_changelist")
    description = "invoice_description_v2"
    list_filter = (AdminFilterPermanenceDoneStatus,)
    ordering = (
        "-invoice_sort_order",
        "-canceled_invoice_sort_order",
        "-permanence_date",
        "-id",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, permanence=None):
        return request.user.is_invoice_manager

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-new-invoice/",
                self.admin_site.admin_view(self.import_new_invoice),
                name="permanence-import-new-invoice",
            ),
            path(
                "<int:permanence_id>/export-invoice/",
                self.admin_site.admin_view(self.export_purchases),
                name="permanence-export-invoice",
            ),
            path(
                "<int:permanence_id>/import-invoice/",
                self.admin_site.admin_view(self.import_updated_purchases),
                name="permanence-import-invoice",
            ),
            path(
                "<int:permanence_id>/invoice/",
                self.admin_site.admin_view(self.invoice),
                name="permanence-invoice",
            ),
            path(
                "<int:permanence_id>/accounting-report/",
                self.admin_site.admin_view(self.accounting_report),
                name="permanence-accounting-report",
            ),
            path(
                "<int:permanence_id>/archive/",
                self.admin_site.admin_view(self.archive),
                name="permanence-archive",
            ),
            path(
                "<int:permanence_id>/cancel-delivery/",
                self.admin_site.admin_view(self.cancel_delivery),
                name="permanence-cancel-delivery",
            ),
            path(
                "<int:permanence_id>/cancel-invoicing/",
                self.admin_site.admin_view(self.cancel_invoicing),
                name="permanence-cancel-invoicing",
            ),
            path(
                "<int:permanence_id>/cancel-archiving/",
                self.admin_site.admin_view(self.cancel_archiving),
                name="permanence-cancel-archiving",
            ),
            path(
                "<int:permanence_id>/restore-delivery/",
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

    @check_permanence(SaleStatus.SEND)
    def export_purchases(self, request, permanence_id, permanence=None):
        wb = export_purchase(permanence=permanence, wb=None)
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(_("Accounting entries"), permanence)
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    @check_cancel_in_post
    @check_permanence(SaleStatus.SEND)
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
    @check_permanence(SaleStatus.SEND)
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
                "model_verbose_name_plural": _("Offers in payment"),
                "sub_title": _("Please, confirm the action : cancel delivery."),
                "action": "cancel_delivery",
                "permanence": permanence,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    @check_permanence(SaleStatus.INVOICED)
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
        user_message = _("No accounting entry for {permanence}").format(
            permanence=permanence
        )
        user_message_level = messages.WARNING
        self.message_user(request, user_message, user_message_level)
        return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    @check_done_in_post
    @check_cancel_in_post
    @check_permanence(SaleStatus.SEND)
    def invoice(self, request, permanence_id, permanence=None):
        max_payment_date = timezone.now().date()
        bank_account = (
            BankAccount.objects.filter(operation_status=BankMovement.LATEST_TOTAL)
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
        if "apply" in request.POST and ACTION_CHECKBOX_NAME in request.POST:
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
                            producer_invoice = ProducerInvoice.objects.filter(
                                permanence_id=permanence_id,
                                invoice_sort_order__isnull=True,
                                producer_id=producer_id,
                            ).first()
                            if selected:
                                at_least_one_selected = True
                                producer_invoice.to_be_invoiced_balance = (
                                    producer_invoiced_form.cleaned_data.get(
                                        "to_be_invoiced_balance"
                                    )
                                )
                                producer_invoice.invoice_reference = (
                                    producer_invoiced_form.cleaned_data.get(
                                        "invoice_reference", EMPTY_STRING
                                    )
                                )
                                producer_invoice.to_be_paid = True
                            else:
                                producer_invoice.to_be_invoiced_balance = DECIMAL_ZERO
                                producer_invoice.invoice_reference = EMPTY_STRING
                                producer_invoice.to_be_paid = False
                            producer_invoice.delta_vat = DECIMAL_ZERO
                            producer_invoice.delta_price_with_tax = DECIMAL_ZERO
                            producer_invoice.save(
                                update_fields=[
                                    "to_be_invoiced_balance",
                                    "invoice_reference",
                                    "delta_vat",
                                    "delta_price_with_tax",
                                    "to_be_paid",
                                ]
                            )
                    if at_least_one_selected:
                        permanence.invoice(payment_date=payment_date)
                        previous_latest_total = (
                            BankAccount.objects.filter(
                                operation_status=BankMovement.LATEST_TOTAL,
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
                                    operation_status=BankMovement.CALCULATED_INVOICE,
                                ).order_by("producer", "-operation_date", "-id"),
                                "action_checkbox_name": ACTION_CHECKBOX_NAME,
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
            if permanence.payment_date is not None:
                # In this case we the permanence has already been invoiced in the past
                # and the invoice has been cancelled
                payment_date = permanence.payment_date
                if payment_date < min_payment_date or payment_date > max_payment_date:
                    payment_date = min_payment_date
            else:
                payment_date = max_payment_date
            permanence_form = PermanenceInvoicedForm(payment_date=payment_date)

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
                producer_invoice.calculated_invoiced_balance.amount = (
                    producer.get_calculated_purchases(permanence_id)
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
                    "represent_this_buyinggroup": producer.represent_this_buyinggroup,
                }
            )

        producer_invoiced_formset = ProducerInvoicedFormSet(initial=producers_invoiced)

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
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "min_payment_date": min_payment_date,
                "max_payment_date": max_payment_date,
            },
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.SEND)
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
                "model_verbose_name_plural": _("Offers in payment"),
                "sub_title": _("Please, confirm the action : generate archive."),
                "action": "archive",
                "permanence": permanence,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    def cancel_invoice_or_archive_or_cancelled(
        self, request, permanence, action, sub_title
    ):
        if "apply" in request.POST:
            if permanence.status == SaleStatus.INVOICED:
                last_bank_account_total = (
                    BankAccount.objects.filter(
                        operation_status=BankMovement.LATEST_TOTAL
                    )
                    .only("permanence")
                    .first()
                )
                if last_bank_account_total is not None:
                    last_permanence_invoiced_id = last_bank_account_total.permanence_id
                    if last_permanence_invoiced_id is not None:
                        if last_permanence_invoiced_id == permanence.id:
                            # This is well the latest closed permanence. The invoices can be cancelled without damages.
                            permanence.cancel_invoice(last_bank_account_total)
                            user_message = _("The selected accounting entry has been cancelled")
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
                            "You have not selected the last accounting entry"
                        )
                        user_message_level = messages.ERROR
                else:
                    user_message = _("The selected accounting entry has been cancelled")
                    user_message_level = messages.INFO
                    permanence.set_status(
                        old_status=SaleStatus.INVOICED, new_status=SaleStatus.SEND
                    )
            else:
                if permanence.status == SaleStatus.ARCHIVED:
                    permanence.set_status(
                        old_status=SaleStatus.ARCHIVED, new_status=SaleStatus.SEND
                    )
                if permanence.status == SaleStatus.CANCELLED:
                    permanence.set_status(
                        old_status=SaleStatus.CANCELLED, new_status=SaleStatus.SEND
                    )
                user_message = _("Archiving has been cancelled")
                user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Offers in payment"),
                "sub_title": sub_title,
                "action": action,
                "permanence": permanence,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.INVOICED)
    def cancel_invoicing(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "cancel_invoicing",
            _("Please, confirm the action : cancel the invoices."),
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.ARCHIVED)
    def cancel_archiving(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "cancel_archiving",
            _("Please, confirm the action : cancel the archiving."),
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.CANCELLED)
    def restore_delivery(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "restore_delivery",
            _("Please, confirm the action : restore the delivery."),
        )

    def get_row_actions(self, permanence):

        if permanence.status == SaleStatus.SEND:
            if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
                return format_html(
                    '<div class="repanier-button-row">'
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a> '
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-upload"></i></a> '
                    '<a class="repanier-a-tooltip repanier-a-cancel" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-truck fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a>'
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-cash-register" style="color: #32CD32;"></i></a>'
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
                    _("Book"),
                )

            else:
                return format_html(
                    '<div class="repanier-button-row">'
                    '<a class="repanier-a-tooltip repanier-a-cancel" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-truck fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a> '
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-archive" style="color: #32CD32;"></i></a>'
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

        elif permanence.status == SaleStatus.INVOICED:
            if BankAccount.objects.filter(
                operation_status=BankMovement.LATEST_TOTAL, permanence_id=permanence.id
            ).exists():
                # This is the latest invoiced permanence
                # Invoicing can be cancelled
                cancel_invoice = format_html(
                    '<a class="repanier-a-tooltip repanier-a-cancel" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-cash-register fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a> ',
                    add_filter(
                        reverse(
                            "admin:permanence-cancel-invoicing", args=[permanence.pk]
                        )
                    ),
                    _("Cancel accounting registration"),
                )
            else:
                cancel_invoice = EMPTY_STRING

            return format_html(
                '<div class="repanier-button-row">'
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-file-invoice-dollar"></i></a> '
                "{}"
                "</div>",
                add_filter(
                    reverse("admin:permanence-accounting-report", args=[permanence.pk])
                ),
                _("Accounting report"),
                cancel_invoice,
            )

        elif permanence.status == SaleStatus.ARCHIVED:
            return format_html(
                '<div class="repanier-button-row">'
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-trash-restore"></i></a>'
                "</div>",
                add_filter(
                    reverse("admin:permanence-cancel-archiving", args=[permanence.pk])
                ),
                _("Restore"),
            )

        elif permanence.status == SaleStatus.CANCELLED:
            return format_html(
                '<div class="repanier-button-row">'
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-trash-restore"></i></a>'
                "</div>",
                add_filter(
                    reverse("admin:permanence-restore-delivery", args=[permanence.pk])
                ),
                _("Restore"),
            )

        return EMPTY_STRING

    get_row_actions.short_description = EMPTY_STRING

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(status__gte=SaleStatus.SEND)
