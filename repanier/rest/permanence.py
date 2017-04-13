from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from repanier.const import PERMANENCE_OPENED
from repanier.models import Permanence, OfferItem
from repanier.rest.view import JSONResponse


class PermanenceSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    status_code = serializers.ReadOnlyField()
    status = serializers.ReadOnlyField()
    producers = serializers.RelatedField(read_only=True)

    def to_representation(self, obj):
        return {
            'id'         : obj.id,
            'name'       : str(obj),
            'status_code': obj.status,
            'status'     : obj.get_status_display(),
            'producers'  : list(obj.producers.values_list('short_profile_name', flat=True))
        }


@csrf_exempt
@require_GET
def permanences_rest(request):
    permanences = Permanence.objects.filter(status=PERMANENCE_OPENED)
    serializer = PermanenceSerializer(permanences, many=True)
    return JSONResponse(serializer.data)


class OfferItemSerializer(serializers.Serializer):

    class Meta:
        model = OfferItem
        fields = (
            'reference',
            'get_long_name',
            'quantity_invoiced',
            'manage_replenishment',
            'stock',
            'add_2_stock'
        )


@csrf_exempt
@require_GET
def permanence_producer_rest(request, permanence_id, producer_name):
    offer_item = OfferItem.objects.filter(
        permanence_id=permanence_id,
        producer__short_profile_name=producer_name.decode('unicode-escape'),
        status=PERMANENCE_OPENED
    ).order_by('?')
    if offer_item.exists():
        serializer = OfferItemSerializer(offer_item, many=True)
        return JSONResponse(serializer.data)


@csrf_exempt
def permanence_producer_product_rest(request, permanence_id, producer_name, reference):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == 'GET':
        offer_item = OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer__short_profile_name=producer_name.decode('unicode-escape'),
            reference=reference.decode('unicode-escape'),
            status=PERMANENCE_OPENED
        ).order_by('?')
        if offer_item.exists():
            serializer = OfferItemSerializer(offer_item)
            return JSONResponse(serializer.data)
    return HttpResponse(status=404)
