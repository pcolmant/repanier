import django
from django.conf import settings
from django.http import Http404
from django.utils import translation
from django.views.generic import DetailView

from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.models.purchase import Purchase
from repanier.tools import get_repanier_template_name


class CustomerInvoiceView(DetailView):
    template_name = get_repanier_template_name("customer_invoice_form.html")
    model = CustomerInvoice

    def get_object(self, queryset=None):
        # Important to handle customer without any invoice
        try:
            obj = super().get_object(queryset)
        except Http404:
            obj = None
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context["object"] is None:
            # This customer has never been invoiced
            context["bank_account_set"] = BankAccount.objects.none()
            purchase_set = Purchase.objects.none()
            context["purchase_set"] = purchase_set
            purchase_by_other_set = Purchase.objects.none()
            context["purchase_by_other_set"] = purchase_by_other_set
            # if self.request.user.is_staff:
            #     raise Http404
            # else:
            customer = self.request.user.customer
            context["customer"] = customer
            context["download_invoice"] = False
        else:
            customer_invoice = self.get_object()
            bank_account_set = BankAccount.objects.filter(
                customer_invoice=customer_invoice
            ).order_by("operation_date")
            context["bank_account_set"] = bank_account_set
            if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
                purchase_set = Purchase.objects.filter(
                    customer_invoice=customer_invoice,
                    offer_item__translations__language_code=translation.get_language(),
                    is_box_content=False,
                ).order_by("producer", "offer_item__translations__order_sort_order")
            else:
                purchase_set = Purchase.objects.filter(
                    customer_invoice=customer_invoice,
                    offer_item__translations__language_code=translation.get_language(),
                ).order_by("offer_item__translations__order_sort_order")
            context["purchase_set"] = purchase_set
            purchase_by_other_set = (
                Purchase.objects.filter(
                    customer_invoice__customer_charged_id=customer_invoice.customer_id,
                    # customer_charged_id=customer_invoice.customer_id,
                    permanence_id=customer_invoice.permanence_id,
                    offer_item__translations__language_code=translation.get_language(),
                )
                .exclude(customer_id=customer_invoice.customer_id)
                .order_by(
                    "customer", "producer", "offer_item__translations__order_sort_order"
                )
            )
            context["purchase_by_other_set"] = purchase_by_other_set
            if customer_invoice.invoice_sort_order is not None:
                previous_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=customer_invoice.customer_id,
                        invoice_sort_order__isnull=False,
                        invoice_sort_order__lt=customer_invoice.invoice_sort_order,
                    )
                    .order_by("-invoice_sort_order")
                    .only("id")
                    .first()
                )
                next_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=customer_invoice.customer_id,
                        invoice_sort_order__isnull=False,
                        invoice_sort_order__gt=customer_invoice.invoice_sort_order,
                    )
                    .order_by("invoice_sort_order")
                    .only("id")
                    .first()
                )
            else:
                previous_customer_invoice = None
                next_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=customer_invoice.customer_id,
                        invoice_sort_order__isnull=False,
                    )
                    .order_by("invoice_sort_order")
                    .only("id")
                    .first()
                )
            if previous_customer_invoice is not None:
                context["previous_customer_invoice_id"] = previous_customer_invoice.id
            if next_customer_invoice is not None:
                context["next_customer_invoice_id"] = next_customer_invoice.id
            context["customer"] = customer_invoice.customer
            context["download_invoice"] = (
                Purchase.objects.filter(
                    customer_invoice__customer_charged_id=customer_invoice.customer_id,
                    # customer_charged_id=customer_invoice.customer_id,
                    permanence_id=customer_invoice.permanence_id,
                )
                .order_by("?")
                .exists()
            )
        return context

    def get_queryset(self):
        if django.VERSION[0] < 2:
            pk = int(self.kwargs.get("pk", 0))
        else:
            pk = self.kwargs.get("pk", 0)
        if self.request.user.is_staff:
            if pk == 0:
                customer_id = self.request.GET.get("customer", None)
                last_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=customer_id, invoice_sort_order__isnull=False
                    )
                    .only("id")
                    .order_by("-invoice_sort_order")
                    .first()
                )
                if last_customer_invoice is not None:
                    self.kwargs["pk"] = last_customer_invoice.id
            return CustomerInvoice.objects.filter(
                invoice_sort_order__isnull=False
            ).order_by("-invoice_sort_order")
        else:
            if pk == 0:
                last_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer__user_id=self.request.user.id,
                        invoice_sort_order__isnull=False,
                    )
                    .only("id")
                    .order_by("-invoice_sort_order")
                    .first()
                )
                if last_customer_invoice is not None:
                    self.kwargs["pk"] = last_customer_invoice.id
            return CustomerInvoice.objects.filter(
                customer__user_id=self.request.user.id, invoice_sort_order__isnull=False
            ).order_by("-invoice_sort_order")
