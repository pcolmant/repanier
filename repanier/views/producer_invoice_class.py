# -*- coding: utf-8
from __future__ import unicode_literals

from django.http import Http404
from django.utils import translation
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView

from repanier.models import Purchase
from repanier.const import DECIMAL_ZERO
from repanier.models import ProducerInvoice, BankAccount, OfferItem, Producer


class ProducerInvoiceView(DetailView):
    template_name = 'repanier/producer_invoice_form.html'
    model = ProducerInvoice
    uuid = None

    def get_object(self, queryset=None):
        # Important to handle producer without any invoice
        try:
            obj = super(ProducerInvoiceView, self).get_object(queryset)
        except Http404:
            obj = None  # ProducerInvoice.objects.none()
        return obj

    # @method_decorator(never_cache)
    # def get(self, request, *args, **kwargs):
    #     return super(ProducerInvoiceView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProducerInvoiceView, self).get_context_data(**kwargs)
        if context['object'] is None:
            # This producer has never been invoiced
            raise Http404
        else:
            producer_invoice = self.get_object()
            bank_account_set = BankAccount.objects.filter(producer_invoice=producer_invoice)
            context['bank_account_set'] = bank_account_set
            offer_item_set = OfferItem.objects.filter(
                permanence_id=producer_invoice.permanence_id,
                producer_id=producer_invoice.producer_id,
                translations__language_code=translation.get_language()
            ).exclude(
                quantity_invoiced=DECIMAL_ZERO
            ).order_by(
                "translations__producer_sort_order"
            ).distinct()
            context['offer_item_set'] = offer_item_set
            if producer_invoice.invoice_sort_order is not None:
                previous_producer_invoice = ProducerInvoice.objects.filter(
                    producer_id=producer_invoice.producer_id,
                    invoice_sort_order__isnull=False,
                    invoice_sort_order__lt=producer_invoice.invoice_sort_order
                ).order_by('-invoice_sort_order').only("id").first()
                next_producer_invoice = ProducerInvoice.objects.filter(
                    producer_id=producer_invoice.producer_id,
                    invoice_sort_order__isnull=False,
                    invoice_sort_order__gt=producer_invoice.invoice_sort_order
                ).order_by('invoice_sort_order').only("id").first()
            else:
                previous_producer_invoice = None
                next_producer_invoice = ProducerInvoice.objects.filter(
                    producer_id=producer_invoice.producer_id,
                    invoice_sort_order__isnull=False
                ).order_by('invoice_sort_order').only("id").first()
            if previous_producer_invoice is not None:
                context['previous_producer_invoice_id'] = previous_producer_invoice.id
            if next_producer_invoice is not None:
                context['next_producer_invoice_id'] = next_producer_invoice.id
            context['uuid'] = self.uuid
            context['producer'] = producer_invoice.producer
        return context

    def get_queryset(self):
        self.uuid = None
        if self.request.user.is_staff:
            producer_id = self.request.GET.get('producer', None)
        else:
            self.uuid = self.kwargs.get('uuid', None)
            if self.uuid:
                try:
                    producer = Producer.objects.filter(uuid=self.uuid).order_by('?').first()
                    producer_id = producer.id
                except:
                    raise Http404
            else:
                return ProducerInvoice.objects.none()
        pk = self.kwargs.get('pk', None)
        if (pk is None) or (pk == '0'):
            last_producer_invoice = ProducerInvoice.objects.filter(
                producer_id=producer_id, invoice_sort_order__isnull=False
            ).only("id").order_by("-invoice_sort_order").first()
            if last_producer_invoice is not None:
                self.kwargs['pk'] = last_producer_invoice.id
        return ProducerInvoice.objects.filter(producer_id=producer_id)
