from django.http import Http404
from django.views.generic import DetailView
from repanier.const import SaleStatus
from repanier.models import Customer

from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.tools import get_repanier_template_name


class CustomerHistoryView(DetailView):
    template_name = get_repanier_template_name("customer_history_form.html")
    model = Customer
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
        if context["object"] is not None:
            # This customer exists
            customer = self.get_object()
            context["customer"] = customer
            not_invoiced_customer_invoice_set = CustomerInvoice.objects.filter(
                customer_id=customer.id,
                invoice_sort_order__isnull=True,
                status__lte=SaleStatus.INVOICED,
            )
            context["not_invoiced_customer_invoice_set"] = not_invoiced_customer_invoice_set
            not_invoiced_bank_account_set = BankAccount.objects.filter(
                customer=customer.id,
                customer_invoice__isnull=True,
            ).order_by("operation_date")
            context["not_invoiced_bank_account_set"] = not_invoiced_bank_account_set
            customer_invoice_set = CustomerInvoice.objects.filter(
                customer_id=customer.id,
                invoice_sort_order__isnull=False,
                status=SaleStatus.INVOICED,
            ).order_by("-invoice_sort_order")
            invoiced_array = []
            for customer_invoice in customer_invoice_set:
                bank_account_set = BankAccount.objects.filter(
                    customer_invoice=customer_invoice
                ).order_by("operation_date")
                invoiced_array += [
                    {
                        "customer_invoice": customer_invoice,
                        "bank_account_set": bank_account_set,
                    }
                ]
            context["invoiced_array"] = invoiced_array
        else:
            context["customer"] = None
        return context

    def get_queryset(self):
        user = self.request.user
        if user.is_repanier_staff:
            customer_id = self.kwargs.get("customer_id", user.customer_id)
        else:
            customer_id = user.customer_id
        self.my_invoices = customer_id == user.customer_id
        self.kwargs["pk"] = customer_id
        return Customer.objects.all()
