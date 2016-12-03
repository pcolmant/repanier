from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers

from repanier.const import PERMANENCE_PRE_OPEN, PERMANENCE_SEND
from repanier.models import Permanence, OfferItem
from repanier.rest.view import JSONResponse


class PermanenceSerializer(serializers.ModelSerializer):
    producers_name = serializers.StringRelatedField(source='producers', read_only=True, many=True)

    class Meta:
        model = Permanence
        fields = (
            'id',
            '__str__',
            'status',
            'get_status_display',
            'producers_name'
        )


class OfferItemSerializer(serializers.ModelSerializer):
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
def permanences_rest(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == 'GET':
        permanences = Permanence.objects.filter(status__gte=PERMANENCE_PRE_OPEN, status__lte=PERMANENCE_SEND)
        serializer = PermanenceSerializer(permanences, many=True)
        return JSONResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def permanence_producer_rest(request, permanence_id, short_profile_name):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == 'GET':
        offer_item = OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer__short_profile_name=short_profile_name.decode('unicode-escape'),
            permanence__status__gte=PERMANENCE_PRE_OPEN,
            permanence__status__lte=PERMANENCE_SEND
        ).order_by('?')
        if offer_item.exists():
            serializer = OfferItemSerializer(offer_item, many=True)
            return JSONResponse(serializer.data)
    return HttpResponse(status=404)


@csrf_exempt
def permanence_producer_product_rest(request, permanence_id, short_profile_name, reference):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == 'GET':
        offer_item = OfferItem.objects.filter(
            permanence_id=permanence_id,
            producer__short_profile_name=short_profile_name.decode('unicode-escape'),
            reference=reference.decode('unicode-escape'),
            permanence__status__gte=PERMANENCE_PRE_OPEN,
            permanence__status__lte=PERMANENCE_SEND
        ).order_by('?')
        if offer_item.exists():
            serializer = OfferItemSerializer(offer_item)
            return JSONResponse(serializer.data)
    return HttpResponse(status=404)
