from django.http import Http404
from django.utils.translation import gettext_lazy as _
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
    customer_id = 0

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
        customer_invoice = context["object"]
        # Use get() instead of filter().first() for single object lookup
        # and select_related for user if needed
        customer = Customer.objects.select_related('user').filter(id=self.customer_id).first()
        context["customer"] = customer
        context["previous_customer_invoice_id"] = None
        context["next_customer_invoice_id"] = None
        context["not_invoiced_array"] = None
        context["not_invoiced_bank_account_set"] = None
        context["display_admin_balance"] = False
        context["fast_forward"] = True
        if customer_invoice is None:
            # This customer has never been invoiced
            context["bank_account_set"] = BankAccount.objects.none()
            purchase_set = Purchase.objects.none()
            context["purchase_set"] = purchase_set
            purchase_by_other_set = Purchase.objects.none()
            context["purchase_by_other_set"] = purchase_by_other_set
            context["download_invoice"] = False

        else:
            bank_account_set = BankAccount.objects.filter(
                customer_invoice=customer_invoice
            ).order_by("operation_date").select_related(
                'customer_invoice'
            )
            context["bank_account_set"] = bank_account_set
            purchase_set = Purchase.objects.filter(
                customer_invoice=customer_invoice,
            ).order_by("producer", "offer_item").select_related(
                'producer', 'offer_item', 'customer'
            )
            context["purchase_set"] = purchase_set
            purchase_by_other_set = (
                Purchase.objects.filter(
                    customer_invoice__customer_charged_id=self.customer_id,
                    permanence_id=customer_invoice.permanence_id,
                )
                .exclude(customer_id=self.customer_id)
                .order_by("customer", "producer", "offer_item")
                .select_related('producer', 'offer_item', 'customer')
            )
            context["purchase_by_other_set"] = purchase_by_other_set
            context["download_invoice"] = Purchase.objects.filter(
                customer_invoice__customer_charged_id=self.customer_id,
                permanence_id=customer_invoice.permanence_id,
            ).exists()
            previous_customer_invoice = None
            next_customer_invoice = None
            if customer_invoice.status == SaleStatus.INVOICED:
                previous_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=self.customer_id,
                        invoice_sort_order__isnull=False,
                        invoice_sort_order__lt=customer_invoice.invoice_sort_order,
                        status__gte=SaleStatus.INVOICED,
                    )
                    .order_by("-invoice_sort_order")
                    .only("id")
                    .first()
                )
                next_customer_invoice = (
                    CustomerInvoice.objects.filter(
                        customer_id=self.customer_id,
                        invoice_sort_order__isnull=False,
                        invoice_sort_order__gt=customer_invoice.invoice_sort_order,
                        status__gte=SaleStatus.INVOICED,
                    )
                    .order_by("invoice_sort_order")
                    .only("id")
                    .first()
                )
                if next_customer_invoice is None:
                    context["fast_forward"] = False
                    if customer is not None:
                        next_customer_invoice = CustomerInvoice.objects.filter(
                            customer_id=customer.id,
                            status__lt=SaleStatus.INVOICED,
                        ).only("id").first()
                    else:
                        next_customer_invoice = None
            elif customer_invoice.status != SaleStatus.ARCHIVED:
                previous_customer_invoice = CustomerInvoice.objects.filter(
                    customer_id=customer.id,
                    status=SaleStatus.INVOICED,
                ).order_by("-invoice_sort_order").first()
                next_customer_invoice = None

            if previous_customer_invoice is not None:
                context["previous_customer_invoice_id"] = previous_customer_invoice.id
            if next_customer_invoice is not None:
                context["next_customer_invoice_id"] = next_customer_invoice.id
        return context

    def get_queryset(self):
        invoice_id = self.kwargs.get("invoice_id", 0)
        user = self.request.user
        if user.is_repanier_staff:
            if invoice_id == 0:
                customer_id = self.kwargs.get("customer_id", user.customer_id)
            else:
                invoice_obj = CustomerInvoice.objects.filter(id=invoice_id).only("customer_id").first()
                customer_id = invoice_obj.customer_id if invoice_obj else user.customer_id
        else:
            customer_id = user.customer_id

        # Protection indispensable si customer_id est None ou introuvable :
        if not customer_id:
            raise Http404("{}".format(_("No customer associated with this invoice.")))

        self.my_invoices = customer_id == user.customer_id
        if invoice_id == 0:
            # Use a single query with fallback using coalesce
            last_customer_invoice = (
                CustomerInvoice.objects.filter(
                    customer_id=customer_id,
                )
                .only("id")
                .order_by(
                    '-invoice_sort_order',  # INVOICED invoices have sort_order
                    '-id'  # Fallback for ARCHIVED invoices
                )
                .first()
            )
            if last_customer_invoice is not None:
                invoice_id = last_customer_invoice.id
        self.kwargs["pk"] = invoice_id
        self.customer_id = customer_id
        return CustomerInvoice.objects.filter(
            customer_id=customer_id,
        )
        # ).order_by("-invoice_sort_order", "-id")
