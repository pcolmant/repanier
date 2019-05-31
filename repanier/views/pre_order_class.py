# -*- coding: utf-8
from django.http import Http404
from django.utils import translation
from django.views.generic import DetailView

from repanier.const import PERMANENCE_PRE_OPEN
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.tools import get_repanier_template_name


class PreOrderView(DetailView):
    template_name = get_repanier_template_name("pre_order_form.html")
    model = Permanence
    producer = None
    offer_uuid = None

    def get(self, request, *args, **kwargs):
        self.producer = None
        if request.user.is_staff:
            producer_id = request.GET.get('producer', None)
            if producer_id is not None:
                producer = Producer.objects.filter(
                    id=producer_id
                ).order_by('?').only("id").first()
                if producer is None:
                    raise Http404
                else:
                    self.producer = producer
            else:
                raise Http404
        else:
            self.offer_uuid = kwargs.get('offer_uuid', None)
            if self.offer_uuid is not None:
                producer = Producer.objects.filter(
                    offer_uuid=self.offer_uuid
                ).order_by('?').only("id").first()
                if producer is None:
                    raise Http404
                else:
                    self.producer = producer
                    producer.offer_filled = True
                    producer.save(update_fields=['offer_filled'])
            else:
                raise Http404

        return super(PreOrderView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PreOrderView, self).get_context_data(**kwargs)
        permanence_pre_opened = self.get_object()
        if permanence_pre_opened is not None:
            offer_item_set = OfferItemWoReceiver.objects.filter(
                producer_id=self.producer,
                permanence_id=permanence_pre_opened.id,
                translations__language_code=translation.get_language(),
                is_active=True
            ).order_by(
                "translations__long_name"
            ).distinct()
            context['offer_item_set'] = offer_item_set
            context['producer'] = self.producer
            context['offer_uuid'] = self.offer_uuid
        return context

    def get_queryset(self):
        pk = self.kwargs.get('pk', 0)
        if pk == 0:
            permanence_pre_opened = Permanence.objects.filter(
                status=PERMANENCE_PRE_OPEN
            ).order_by("-is_updated_on").only("id").first()
            if permanence_pre_opened is not None:
                self.kwargs['pk'] = permanence_pre_opened.id
        return Permanence.objects.all()
