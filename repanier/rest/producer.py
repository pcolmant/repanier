from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from rest_framework.fields import DecimalField

from repanier.models.producer import Producer


class ProducerSerializer(serializers.ModelSerializer):
    minimum_order_value_amount = DecimalField(max_digits=8, decimal_places=2, source='minimum_order_value.amount',
                                              read_only=True)

    class Meta:
        model = Producer
        fields = (
            'short_profile_name',
            'long_profile_name',
            'email',
            'language',
            'phone1',
            'vat_id',
            'address',
            'invoice_by_basket',
            'minimum_order_value_amount'
        )


@csrf_exempt
def producers_list(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == 'GET':
        producers = Producer.objects.filter(is_active=True)
        serializer = ProducerSerializer(producers, many=True)
        return JsonResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def producer_detail(request, short_profile_name):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == 'GET':
        producer = Producer.objects.filter(
            short_profile_name=short_profile_name.decode('unicode-escape'),
            is_active=True,
            represent_this_buyinggroup=False
        ).order_by('?').first()
        if producer is not None:
            serializer = ProducerSerializer(producer)
            return JsonResponse(serializer.data)
    return HttpResponse(status=404)
