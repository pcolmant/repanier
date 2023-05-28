from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from repanier.const import OrderUnit
from repanier.models.product import Product
from rest_framework import serializers
from rest_framework.fields import DecimalField


class ProductSerializer(serializers.ModelSerializer):
    producer_name = serializers.ReadOnlyField(source="producer.short_profile_name")
    department_for_customer = serializers.ReadOnlyField(
        source="department_for_customer.short_name_v2"
    )
    label = serializers.StringRelatedField(
        source="production_mode", read_only=True, many=True
    )
    customer_unit_price_amount = DecimalField(
        max_digits=8,
        decimal_places=2,
        source="customer_unit_price.amount",
        read_only=True,
    )
    unit_deposit_amount = DecimalField(
        max_digits=8, decimal_places=2, source="unit_deposit.amount", read_only=True
    )

    class Meta:
        model = Product
        fields = (
            "reference",
            "is_active",
            "is_into_offer",
            "producer_name",
            "long_name",
            "department_for_customer",
            "order_unit",
            "get_order_unit_display",
            "order_average_weight",
            "customer_unit_price_amount",
            "unit_deposit_amount",
            "vat_level",
            "get_vat_level_display",
            "customer_minimum_order_quantity",
            "customer_increment_order_quantity",
            "wrapped",
            "stock",
            "label",
            "picture2",
            "offer_description_v2",
        )


@csrf_exempt
def products_rest(request, producer_short_profile_name):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == "GET":
        products = Product.objects.filter(
            producer__short_profile_name=producer_short_profile_name.decode(
                "unicode-escape"
            ),
            order_unit__lte=OrderUnit.DEPOSIT,
        )
        serializer = ProductSerializer(products, many=True)
        return JsonResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def product_rest(request, producer_short_profile_name, reference):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == "GET":
        product = Product.objects.filter(
            reference=reference,
            producer__short_profile_name=producer_short_profile_name.decode(
                "unicode-escape"
            ),
            order_unit__lte=OrderUnit.DEPOSIT,
        ).first()
        if product is not None:
            serializer = ProductSerializer(product)
            return JsonResponse(serializer.data)
    return HttpResponse(status=404)
