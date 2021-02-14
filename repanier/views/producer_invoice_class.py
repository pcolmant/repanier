from django.http import Http404
from django.utils import translation
from django.views.generic import DetailView

from repanier.const import DECIMAL_ZERO
from repanier.models.bankaccount import BankAccount
from repanier.models.invoice import ProducerInvoice
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.tools import get_repanier_template_name


class ProducerInvoiceView(DetailView):
    template_name = get_repanier_template_name("producer_invoice_form.html")
    model = ProducerInvoice

    def get_object(self, queryset=None):
        # Important to handle producer without any invoice
        try:
            object = self.get_queryset().first()
        except Http404:
            object = None
        return object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        producer_invoice = context["producerinvoice"]
        if producer_invoice is None:
            # This producer has never been invoiced
            raise Http404
        else:
            bank_account_set = BankAccount.objects.filter(
                producer_invoice_id=producer_invoice.id
            ).order_by("operation_date")
            context["bank_account_set"] = bank_account_set
            offer_item_set = (
                OfferItemWoReceiver.objects.filter(
                    permanence_id=producer_invoice.permanence_id,
                    producer_id=producer_invoice.producer_id,
                    translations__language_code=translation.get_language(),
                )
                .exclude(qty=DECIMAL_ZERO)
                .order_by("translations__producer_sort_order")
                .distinct()
            )
            context["offer_item_set"] = offer_item_set
            previous_producer_invoice = (
                ProducerInvoice.objects.previous_producer_invoice(producer_invoice)
                .only("id")
                .first()
            )
            if previous_producer_invoice is not None:
                context["previous_producer_invoice_id"] = previous_producer_invoice.id
            next_producer_invoice = (
                ProducerInvoice.objects.next_producer_invoice(producer_invoice)
                .only("id")
                .first()
            )
            if next_producer_invoice is not None:
                context["next_producer_invoice_id"] = next_producer_invoice.id
            context["producer"] = producer_invoice.producer
        return context

    def get_queryset(self):
        pk = self.kwargs.get("pk", 0)
        producer_login_uuid = self.kwargs.get("login_uuid", 0)
        return ProducerInvoice.objects.last_producer_invoice(
            pk=pk, producer_login_uuid=producer_login_uuid
        )
