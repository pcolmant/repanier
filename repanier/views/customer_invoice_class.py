from django.conf import settings
from django.http import Http404
from django.views.generic import DetailView
from repanier.const import SaleStatus
from repanier.models import Customer

from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.models.purchase import Purchase
from repanier.tools import get_repanier_template_name


class CustomerInvoiceView(DetailView):
    template_name = get_repanier_template_name("customer_invoice_form.html")
    model = CustomerInvoice
    my_invoices = False

    def get_object(self, queryset=None):
        # Important to handle customer without any invoice
        try:
            obj = super().get_object(queryset)
        except Http404:
            obj = None
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_invoices"] = self.my_invoices
        if context["object"] is None:
            # This customer has never been invoiced
            context["bank_account_set"] = BankAccount.objects.none()
            purchase_set = Purchase.objects.none()
            context["purchase_set"] = purchase_set
            purchase_by_other_set = Purchase.objects.none()
            context["purchase_by_other_set"] = purchase_by_other_set
            customer = Customer.objects.filter(id=self.request.user.customer_id)
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
                ).order_by("producer", "offer_item__order_sort_order_v2")
            else:
                purchase_set = Purchase.objects.filter(
                    customer_invoice=customer_invoice,
                ).order_by("offer_item__order_sort_order_v2")
            context["purchase_set"] = purchase_set
            purchase_by_other_set = (
                Purchase.objects.filter(
                    customer_invoice__customer_charged_id=customer_invoice.customer_id,
                    permanence_id=customer_invoice.permanence_id,
                )
                .exclude(customer_id=customer_invoice.customer_id)
                .order_by("customer", "producer", "offer_item__order_sort_order_v2")
            )
            context["purchase_by_other_set"] = purchase_by_other_set
            if customer_invoice.invoice_sort_order is not None:
                previous_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=customer_invoice.customer_id,
                        invoice_sort_order__isnull=False,
                        invoice_sort_order__lt=customer_invoice.invoice_sort_order,
                        status__lte=SaleStatus.INVOICED,
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
                        status__lte=SaleStatus.INVOICED,
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
                        status__lte=SaleStatus.INVOICED,
                    )
                    .order_by("invoice_sort_order")
                    .only("id")
                    .first()
                )
            if previous_customer_invoice is not None:
                context["previous_customer_invoice_id"] = previous_customer_invoice.id
            if next_customer_invoice is not None:
                context["next_customer_invoice_id"] = next_customer_invoice.id
            else:
                customer_invoice_not_invoiced_set = CustomerInvoice.objects.filter(
                    customer_id=customer_invoice.customer_id,
                    invoice_sort_order__isnull=True,
                    status__lte=SaleStatus.INVOICED,
                )
                not_invoiced_array = []
                for customer_invoice in customer_invoice_not_invoiced_set:
                    purchase_set = Purchase.objects.filter(
                        customer_invoice_id=customer_invoice.id
                    ).order_by(
                        "customer", "producer", "offer_item__order_sort_order_v2"
                    )
                    not_invoiced_array += [
                        {
                            "customer_invoice": customer_invoice,
                            "purchase_set": purchase_set,
                        }
                    ]
                context["not_invoiced_array"] = not_invoiced_array
                not_invoiced_bank_account_set = BankAccount.objects.filter(
                    customer=customer_invoice.customer_id,
                    customer_invoice__isnull=True,
                ).order_by("operation_date")
                context["not_invoiced_bank_account_set"] = not_invoiced_bank_account_set
            context["customer"] = customer_invoice.customer
            context["download_invoice"] = Purchase.objects.filter(
                customer_invoice__customer_charged_id=customer_invoice.customer_id,
                permanence_id=customer_invoice.permanence_id,
            ).exists()
        return context

    def get_queryset(self):
        invoice_id = self.kwargs.get("invoice_id", 0)
        user = self.request.user
        if user.is_repanier_staff:
            if invoice_id == 0:
                customer_id = self.kwargs.get("customer_id", user.customer_id)
            else:
                customer_id = (
                    CustomerInvoice.objects.filter(id=invoice_id)
                    .only("customer_id")
                    .first()
                    .customer_id
                )
        else:
            customer_id = user.customer_id
        self.my_invoices = customer_id == user.customer_id
        if invoice_id == 0:
            last_customer_invoice = (
                CustomerInvoice.objects.filter(
                    customer_id=customer_id,
                    invoice_sort_order__isnull=False,
                    status__lte=SaleStatus.INVOICED,
                )
                .only("id")
                .order_by("-invoice_sort_order")
                .first()
            )
            if last_customer_invoice is not None:
                invoice_id = last_customer_invoice.id
        self.kwargs["pk"] = invoice_id
        return CustomerInvoice.objects.filter(
            customer_id=customer_id,
            invoice_sort_order__isnull=False,
            status=SaleStatus.INVOICED,
        ).order_by("-invoice_sort_order")
