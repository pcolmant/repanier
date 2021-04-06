from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from rest_framework.fields import DecimalField
from rest_framework.renderers import JSONRenderer

from repanier.models.producer import Producer


class ProducerSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField('get_short_profile_name')
    name = serializers.SerializerMethodField('get_long_profile_name')
    # minimum_order_value_amount = DecimalField(max_digits=8, decimal_places=2, source='minimum_order_value.amount',
    #                                           read_only=True)

    @staticmethod
    def get_short_profile_name(obj):
        return obj.short_profile_name

    @staticmethod
    def get_long_profile_name(obj):
        return obj.long_profile_name

    class Meta:
        model = Producer
        fields = (
            'id',
            'name',
            # 'minimum_order_value_amount'
        )


@csrf_exempt
def producers_list(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == 'GET':
        producers = Producer.objects.filter(is_active=True)
        serializer = ProducerSerializer(producers, many=True)
        return JsonResponse(serializer.data, safe=False)
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
