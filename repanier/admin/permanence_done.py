import logging

from django.contrib import admin
from django.db import transaction
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.checks import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy, path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from repanier.models import PermanenceDone
from repanier.models.permanence import Permanence
from repanier.admin.admin_filter import AdminFilterPermanenceDoneStatus
from repanier.admin.forms import (
    ProducerInvoicedFormSet,
    PermanenceInvoicedForm,
    ImportPurchasesForm,
    ImportInvoiceForm,
)
from repanier.admin.sale import SaleAdmin
from repanier.accounting_policy import AccountingPolicy
from repanier.accounting_closing import ClosingBalance
from repanier.admin.tools import (
    check_permanence,
    check_cancel_in_post,
    check_done_in_post,
    get_back_to_change_list_url,
)
from django.conf import settings
from repanier.const import BankMovement, DECIMAL_ZERO, EMPTY_STRING, OrderUnit, SaleStatus
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

@admin.register(PermanenceDone)
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
        if not request.user.is_invoice_manager:
            return False
        if permanence is None:
            return True
        return permanence.status == SaleStatus.SEND.value

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
                "<int:permanence_id>/closing-balance/",
                self.admin_site.admin_view(self.closing_balance),
                name="permanence-closing-balance",
            ),
            path(
                "<int:permanence_id>/closing-balance-adjustment/",
                self.admin_site.admin_view(self.closing_balance_adjustment),
                name="permanence-closing-balance-adjustment",
            ),
            path(
                "<int:permanence_id>/closing-products/",
                self.admin_site.admin_view(self.closing_products),
                name="permanence-closing-products",
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
            path(
                "<int:permanence_id>/preparation-link/",
                self.admin_site.admin_view(self.preparation_link),
                name="permanence-preparation-link",
            ),
        ]
        return custom_urls + urls

    @check_permanence(SaleStatus.SEND)
    def preparation_link(self, request, permanence_id, permanence=None):
        from repanier.accounting_policy import AccountingPolicy
        from repanier.preparation_sync import (
            make_preparation_token,
            revoke_preparation_access,
        )
        if not AccountingPolicy.use_mobile_preparation():
            raise PermissionDenied

        action = request.POST.get("action")
        if action == "generate":
            token = make_preparation_token(permanence.id)
        else:
            token = None
        if action == "revoke":
            revoke_preparation_access(permanence.id)

        access = getattr(permanence, "preparation_access", None)
        link = ""
        if token:
            from django.urls import reverse
            link = request.build_absolute_uri(
                reverse("repanier:preparation_page", args=[token])
            )
        elif access is not None and access.is_valid():
            link = ""
        return render(
            request,
            get_repanier_template_name("admin/preparation_link.html"),
            {
                "permanence": permanence,
                "link": link,
                "access": access,
                "can_generate": not permanence.is_demo,
            },
        )

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
            return HttpResponseRedirect(
                get_back_to_change_list_url(request, self)
            )
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Offers in payment"),
                "breadcrumb_url": self.change_list_url,
                "sub_title": _("Please confirm the action: cancel delivery."),
                "action": "cancel_delivery",
                "permanence": permanence,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    @check_permanence(SaleStatus.SEND)
    def closing_balance_adjustment(self, request, permanence_id, permanence=None):
        if request.method != "POST":
            raise PermissionDenied
        if (
            not self.has_change_permission(request, permanence)
            or permanence.is_demo
            or not AccountingPolicy.manage_permanence_accounting()
        ):
            raise PermissionDenied
        import decimal
        from django.core.exceptions import ValidationError
        from repanier.accounting_closing import (
            create_accounting_adjustment,
            create_catalogue_adjustment,
        )
        from repanier.models.customer import Customer
        from repanier.models.offeritem import OfferItem
        from repanier.models.product import Product

        try:
            customer = Customer.objects.filter(pk=request.POST.get("customer_id")).first()
            offer_id = request.POST.get("offer_item_id")
            product_id = request.POST.get("product_id")
            if customer is None or bool(offer_id) == bool(product_id):
                raise ValidationError("Select a member and exactly one delivery or catalogue product.")
            if offer_id:
                offer_item = OfferItem.objects.filter(pk=offer_id, permanence=permanence).first()
                if offer_item is None:
                    raise ValidationError("The product is not in this delivery.")
                create_accounting_adjustment(
                    permanence=permanence, customer=customer, offer_item=offer_item,
                    quantity=request.POST.get("quantity", "0"),
                )
            else:
                product = Product.objects.filter(pk=product_id).first()
                if product is None:
                    raise ValidationError("The catalogue product does not exist.")
                create_catalogue_adjustment(
                    permanence=permanence, customer=customer, product=product,
                    quantity=request.POST.get("quantity", "0"),
                )
            self.message_user(
                request,
                _("Accounting adjustment added and totals recalculated."),
                messages.INFO,
            )
        except (ValidationError, decimal.InvalidOperation, ValueError) as error:
            self.message_user(request, str(error), messages.ERROR)
        return HttpResponseRedirect(
            reverse(
                "admin:permanence-closing-balance",
                args=[permanence_id],
            )
        )

    @check_permanence(SaleStatus.SEND)
    def closing_products(self, request, permanence_id, permanence=None):
        if (
            request.method != "GET"
            or not self.has_change_permission(request, permanence)
            or permanence.is_demo
            or not AccountingPolicy.manage_permanence_accounting()
        ):
            raise PermissionDenied
        from repanier.models.offeritem import OfferItem

        context = {
            **self.admin_site.each_context(request),
            "permanence": permanence,
            "offers": OfferItem.objects.filter(
                permanence=permanence,
            ).select_related("product", "producer").order_by("producer__short_profile_name", "long_name_v2"),
        }
        template = (
            "repanier/admin/closing_products_partial.html"
            if request.headers.get("HX-Request") == "true"
            else "repanier/admin/closing_products.html"
        )
        return render(request, template, context)

    @check_permanence(SaleStatus.SEND)
    def closing_balance(self, request, permanence_id, permanence=None):
        if (
            not self.has_change_permission(request, permanence)
            or permanence.is_demo
            or not AccountingPolicy.manage_permanence_accounting()
        ):
            raise PermissionDenied
        balance = ClosingBalance(permanence).check()
        from repanier.models.customer import Customer
        from repanier.models.offeritem import OfferItem
        from repanier.models.product import Product
        return render(
            request,
            get_repanier_template_name("admin/confirm_invoice.html"),
            {
                **self.admin_site.each_context(request),
                "action": "closing-balance",
                "permanence": permanence,
                "permanence_form": PermanenceInvoicedForm(),
                "producer_invoiced_formset": ProducerInvoicedFormSet(),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "min_payment_date": timezone.now().date(),
                "max_payment_date": timezone.now().date(),
                "closing_blocking": balance.blocking,
                "closing_warnings": balance.warnings,
                "adjustment_customers": Customer.objects.filter(
                    may_order=True,
                    is_active=True,
                    is_anonymized=False,
                ).order_by("short_basket_name"),
                "adjustment_offers": OfferItem.objects.filter(
                    permanence=permanence,
                ).select_related("product").order_by("long_name_v2"),
                "adjustment_products": Product.objects.filter(
                    producer__in=permanence.producers.all(),
                    is_active=True,
                    is_box=False,
                    order_unit__lt=OrderUnit.DEPOSIT,
                ).exclude(
                    offeritem__permanence=permanence,
                ).select_related("producer").order_by("producer__short_profile_name", "long_name_v2"),
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

    def _apply_invoice(
        self, request, permanence, payment_date, producer_invoiced_formset
    ):
        """Run the whole closing sequence in one transaction: producer
        invoices, promotion of the preparation and the invoicing itself.
        Any refusal rolls everything back and returns ("rejected", errors)."""
        from repanier.preparation_closure import promote_preparation_to_accounting

        with transaction.atomic():
            at_least_one_selected = False
            for producer_invoiced_form in producer_invoiced_formset:
                if not producer_invoiced_form.is_valid():
                    continue
                producer_id = producer_invoiced_form.cleaned_data.get("id")
                selected = producer_invoiced_form.cleaned_data.get("selected")
                producer_invoice = ProducerInvoice.objects.filter(
                    permanence_id=permanence.id,
                    invoice_sort_order__isnull=True,
                    producer_id=producer_id,
                ).first()
                if producer_invoice is None:
                    continue
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
            if not at_least_one_selected:
                transaction.set_rollback(True)
                return "none_selected", []

            promotion = promote_preparation_to_accounting(
                permanence,
                user=request.user,
                parcel_dispositions=request.POST.get("parcel_dispositions"),
            )
            if promotion["status"] != "applied":
                transaction.set_rollback(True)
                return "rejected", [
                    "{}: {}".format(key, value)
                    for key, value in promotion.items()
                    if key != "status"
                ]

            promotion_closing = ClosingBalance(permanence).check()
            if not promotion_closing.is_valid:
                transaction.set_rollback(True)
                return "rejected", [
                    "{}: {}".format(finding["code"], finding["message"])
                    for finding in promotion_closing.blocking
                ]

            permanence.invoice(payment_date=payment_date)
            invoiced = Permanence.objects.filter(
                id=permanence.id, status=SaleStatus.WAIT_FOR_INVOICED
            ).exists()
            if not invoiced:
                # Permanence.invoice() returns silently when it cannot invoice
                transaction.set_rollback(True)
                return "rejected", [
                    "INVOICE: the permanence could not be invoiced, nothing was changed."
                ]
        return "applied", []

    @check_done_in_post
    @check_cancel_in_post
    @check_permanence(SaleStatus.SEND)
    def invoice(self, request, permanence_id, permanence=None):
        if (
            permanence.is_demo
            or not AccountingPolicy.manage_permanence_accounting()
            or not self.has_change_permission(request, permanence)
        ):
            raise PermissionDenied
        closing_balance = ClosingBalance(permanence).check()
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
            if not closing_balance.is_valid:
                for finding in closing_balance.blocking:
                    permanence_form_errors = finding["message"]
                    messages.error(
                        request,
                        "{}: {}".format(finding["code"], permanence_form_errors),
                    )
                return HttpResponseRedirect(
                    self.get_redirect_to_change_list_url()
                )
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
                    outcome, errors = self._apply_invoice(
                        request,
                        permanence,
                        payment_date,
                        producer_invoiced_formset,
                    )
                    if outcome == "applied":
                        template_name = get_repanier_template_name(
                            "admin/confirm_bank_movement.html"
                        )
                        calculated_invoices = BankAccount.objects.filter(permanence_id=permanence.id, producer__isnull=False,
                                                        producer__represent_this_buyinggroup=False,
                                                        customer__isnull=True,
                                                        operation_status=BankMovement.CALCULATED_INVOICE, ).order_by(
                            "producer", "-operation_date", "-id")
                        return render(
                            request,
                            template_name,
                            {
                                **self.admin_site.each_context(request),
                                "action": "invoice",
                                "permanence": permanence,
                                "bankaccounts": calculated_invoices,
                                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                            },
                        )
                    else:
                        if outcome == "none_selected":
                            self.message_user(
                                request,
                                _("You must select at least one producer."),
                                messages.WARNING,
                            )
                        for error in errors:
                            messages.error(request, error)
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
                "closing_blocking": closing_balance.blocking,
                "closing_warnings": closing_balance.warnings,
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
            # The archive button also lives on the preparation screen:
            # a ?back= there keeps the user on the list he started
            # from, exactly like the cancel delivery button.
            return HttpResponseRedirect(
                get_back_to_change_list_url(request, self)
            )
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Offers in payment"),
                "breadcrumb_url": self.change_list_url,
                "sub_title": _("Please confirm the action: generate archive."),
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
                                "You must first cancel the invoices of {} whose date is {}."
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
                    # Also re-applies the membership fee extensions
                    # of the members charged at close time
                    permanence.restore_delivery()
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
                "breadcrumb_url": self.change_list_url,
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
            _("Please confirm the action: cancel the invoices."),
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.ARCHIVED)
    def cancel_archiving(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "cancel_archiving",
            _("Please confirm the action: cancel the archiving."),
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.CANCELLED)
    def restore_delivery(self, request, permanence_id, permanence=None):
        return self.cancel_invoice_or_archive_or_cancelled(
            request,
            permanence,
            "restore_delivery",
            _("Please confirm the action: restore the delivery."),
        )

    def get_row_actions(self, permanence):

        if permanence.status == SaleStatus.SEND:
            if AccountingPolicy.manage_permanence_accounting():
                preparation_action = ""
                closing_action = format_html(
                    '<a class="btn btn-outline-primary btn-sm" style="min-height:44px" '
                    'href="{}">{}</a> ',
                    add_filter(
                        reverse(
                            "admin:permanence-closing-balance",
                            args=[permanence.pk],
                        )
                    ),
                    _("Closing checklist"),
                )
                if permanence.is_demo:
                    closing_action = ""
                if AccountingPolicy.use_mobile_preparation() and not permanence.is_demo:
                    preparation_action = format_html(
                        '<a class="btn btn-outline-success btn-sm" style="min-height:44px" '
                        'href="{}">{}</a> ',
                        add_filter(
                            reverse(
                                "admin:permanence-preparation-link",
                                args=[permanence.pk],
                            )
                        ),
                        _("GSM preparation"),
                    )
                return format_html(
                    '<div class="repanier-button-row">'
                    "{}"
                    "{}"
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-download"></i></a> '
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-upload"></i></a> '
                    '<a class="repanier-a-tooltip repanier-a-cancel" href="{}" data-repanier-tooltip="{}"><span class="fa-stack fa-1x"><i class="fas fa-truck fa-stack-1x" style="color:black;"></i><i style="color:Tomato" class="fas fa-ban fa-stack-2x"></i></span></a>'
                    '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-cash-register" style="color: #32CD32;"></i></a>'
                    "</div>",
                    preparation_action,
                    closing_action,
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
