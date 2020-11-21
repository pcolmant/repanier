from django.conf import settings
from django.http import Http404
from django.utils import translation
from django.views.generic import DetailView

from repanier.models import Customer
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import CustomerInvoice
from repanier.models.purchase import Purchase
from repanier.tools import get_repanier_template_name


class CustomerInvoiceView(DetailView):
    template_name = get_repanier_template_name("customer_invoice_form.html")
    model = CustomerInvoice
    extra_context = None

    def get_object(self, queryset=None):
        # Important to handle customer without any invoice
        try:
            object = self.get_queryset().first()
        except Http404:
            object = None
        return object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer_invoice = context["customerinvoice"]
        if customer_invoice is None:
            # Wrong URL parameter or This customer has never been invoiced
            context["bank_account_set"] = BankAccount.objects.none()
            purchase_set = Purchase.objects.none()
            context["purchase_set"] = purchase_set
            purchase_by_other_set = Purchase.objects.none()
            context["purchase_by_other_set"] = purchase_by_other_set
            try:
                context["customer"] = Customer.objects.get(id=context["customer_id"])
            except Customer.DoesNotExist:
                raise Http404
            context["download_invoice"] = False
        else:
            bank_account_set = BankAccount.objects.filter(
                customer_invoice_id=customer_invoice.id
            ).order_by("operation_date")
            context["bank_account_set"] = bank_account_set
            if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
                purchase_set = Purchase.objects.filter(
                    customer_invoice_id=customer_invoice.id,
                    offer_item__translations__language_code=translation.get_language(),
                ).order_by("producer", "offer_item__translations__order_sort_order")
            else:
                purchase_set = Purchase.objects.filter(
                    customer_invoice_id=customer_invoice.id,
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
            previous_customer_invoice = (
                CustomerInvoice.objects.previous_customer_invoice(customer_invoice)
                .only("id")
                .first()
            )
            if previous_customer_invoice is not None:
                context["previous_customer_invoice_id"] = previous_customer_invoice.id
            next_customer_invoice = (
                CustomerInvoice.objects.next_customer_invoice(customer_invoice)
                .only("id")
                .first()
            )
            if next_customer_invoice is not None:
                context["next_customer_invoice_id"] = next_customer_invoice.id
            context["customer"] = customer_invoice.customer
            context["download_invoice"] = Purchase.objects.filter(
                customer_invoice__customer_charged_id=customer_invoice.customer_id,
                # customer_charged_id=customer_invoice.customer_id,
                permanence_id=customer_invoice.permanence_id,
            ).exists()
        return context

    def get_queryset(self):
        pk = self.kwargs.get("pk", 0)
        if self.request.user.is_staff:
            customer_id = self.kwargs.get("customer_id", 0)
        else:
            customer_id = self.request.user.customer_id
        self.extra_context = {"customer_id": customer_id}
        return CustomerInvoice.objects.last_customer_invoice(
            pk=pk, customer_id=customer_id
        )
