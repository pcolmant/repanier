from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework import serializers

from repanier.const import SALE_OPENED
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanence import Permanence


class PermanenceSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    status_code = serializers.ReadOnlyField()
    status = serializers.ReadOnlyField()
    producers = serializers.RelatedField(read_only=True)

    def to_representation(self, obj):
        return {
            "id": obj.id,
            "name": str(obj),
            "status_code": obj.status,
            "status": obj.get_status_display(),
            "producers": list(obj.producers.values_list("short_name", flat=True)),
        }


@csrf_exempt
@require_GET
def permanences_rest(request):
    permanences = Permanence.objects.filter(status=SALE_OPENED)
    serializer = PermanenceSerializer(permanences, many=True)
    return JsonResponse(serializer.data)


class OfferItemSerializer(serializers.Serializer):
    class Meta:
        model = OfferItemWoReceiver
        fields = (
            "reference",
            "get_long_name",
            "qty",
            "stock",
        )


@csrf_exempt
@require_GET
def permanence_producer_rest(request, permanence_id, producer_name):
    offer_item = OfferItemWoReceiver.objects.filter(
        permanence_id=permanence_id,
        producer__short_name=producer_name.decode("unicode-escape"),
        status=SALE_OPENED,
    ).order_by("?")
    if offer_item.exists():
        serializer = OfferItemSerializer(offer_item, many=True)
        return JsonResponse(serializer.data)


@csrf_exempt
def permanence_producer_product_rest(request, permanence_id, producer_name, reference):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == "GET":
        offer_item = OfferItemWoReceiver.objects.filter(
            permanence_id=permanence_id,
            producer__short_name=producer_name.decode("unicode-escape"),
            reference=reference.decode("unicode-escape"),
            status=SALE_OPENED,
        ).order_by("?")
        if offer_item.exists():
            serializer = OfferItemSerializer(offer_item)
            return JsonResponse(serializer.data)
    return HttpResponse(status=404)
